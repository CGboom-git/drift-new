from import_lib import *

class DRIFTToolsExecutionLoop(ToolsExecutionLoop):
    """Executes in loop a sequence of pipeline elements related to tool execution until the
    LLM does not return any tool calls.

    Args:
        elements: a sequence of pipeline elements to be executed in loop. One of them should be
            an LLM, and one of them should be a [ToolsExecutor][agentdojo.agent_pipeline.ToolsExecutor] (or
            something that behaves similarly by executing function calls). You can find an example usage
            of this class [here](../../concepts/agent_pipeline.md#combining-pipeline-components).
        max_iters: maximum number of iterations to execute the pipeline elements in loop.
    """

    def __init__(self, elements: Sequence[BasePipelineElement], max_iters: int = 15) -> None:
        self.elements = elements
        self.max_iters = max_iters

    def query(
        self,
        query: str,
        runtime: FunctionsRuntime,
        env: Env = EmptyEnv(),
        messages: Sequence[ChatMessage] = [],
        extra_args: dict = {},
    ) -> tuple[str, FunctionsRuntime, Env, Sequence[ChatMessage], dict]:
        if len(messages) == 0:
            raise ValueError("Messages should not be empty when calling ToolsExecutionLoop")

        logger = Logger().get()
        for _ in range(self.max_iters):
            last_message = messages[-1]
            if not last_message.get("role") == "assistant":
                break
            if last_message.get("tool_calls") is None:
                break
            if len(last_message.get("tool_calls") or []) == 0:
                break
            for element in self.elements:
                if isinstance(element, ToolsExecutor):
                    handled = self._execute_with_rejected_tool_responses(
                        element, query, runtime, env, messages, extra_args
                    )
                    if handled is not None:
                        query, runtime, env, messages, extra_args = handled
                        logger.log(messages)
                        continue
                query, runtime, env, messages, extra_args = element.query(query, runtime, env, messages, extra_args)
                logger.log(messages)
        return query, runtime, env, messages, extra_args

    def _execute_with_rejected_tool_responses(self, executor, query, runtime, env, messages, extra_args):
        rejected_entries = list((extra_args or {}).get("rejected_tool_calls") or [])
        if not rejected_entries or not messages or messages[-1].get("role") != "assistant":
            return None

        assistant_message = messages[-1]
        tool_calls = list(assistant_message.get("tool_calls") or [])
        if not tool_calls:
            return None

        rejected_by_id = {
            entry.get("tool_call_id"): entry
            for entry in rejected_entries
            if entry.get("tool_call_id")
        }
        if not rejected_by_id:
            return None

        def call_id(tool_call):
            value = getattr(tool_call, "id", None)
            if value is None and isinstance(tool_call, dict):
                value = tool_call.get("id")
            return value

        executable_calls = [
            tool_call for tool_call in tool_calls
            if call_id(tool_call) not in rejected_by_id
        ]
        if len(executable_calls) == len(tool_calls):
            return None

        temp_assistant = dict(assistant_message)
        temp_assistant["tool_calls"] = executable_calls
        exec_messages = [*messages[:-1], temp_assistant]
        query, runtime, env, exec_messages, extra_args = executor.query(
            query, runtime, env, exec_messages, extra_args
        )

        executed_results = {
            msg.get("tool_call_id"): msg
            for msg in exec_messages[len(messages):]
            if msg.get("role") == "tool"
        }

        ordered_results = []
        for tool_call in tool_calls:
            tool_call_id = call_id(tool_call)
            if tool_call_id in rejected_by_id:
                content = rejected_by_id[tool_call_id].get(
                    "content", "[CALL ERROR] Tool call rejected and not executed."
                )
                ordered_results.append({
                    "role": "tool",
                    "content": f"</function_error>\n{content}\n</function_error>",
                    "error": content,
                    "tool_call_id": tool_call_id,
                    "tool_call": tool_call,
                })
            elif tool_call_id in executed_results:
                ordered_results.append(executed_results[tool_call_id])

        remaining = [
            entry for entry in rejected_entries
            if entry.get("tool_call_id") not in rejected_by_id
        ]
        if remaining:
            extra_args["rejected_tool_calls"] = remaining
        else:
            extra_args.pop("rejected_tool_calls", None)

        return query, runtime, env, [*messages, *ordered_results], extra_args
