import re
from .base_llm import BaseLLM
import time

# could be dynamically imported similar to other models
from openai import OpenAI

import openai

from pyopenagi.utils.chat_template import Response
import json


def _format_openai_error(e):
    parts = [f"{type(e).__name__}"]
    status = getattr(e, "status_code", None)
    if status is not None:
        parts.append(f"status={status}")
    body = getattr(e, "body", None)
    if body:
        parts.append(f"body={body}")
    response = getattr(e, "response", None)
    if response is not None:
        text = getattr(response, "text", None)
        if text:
            parts.append(f"response_text={text}")
    cause = getattr(e, "__cause__", None)
    if cause is not None:
        parts.append(f"cause={cause}")
    return " | ".join(parts)

class GPTLLM(BaseLLM):

    def __init__(self, llm_name: str,
                 max_gpu_memory: dict = None,
                 eval_device: str = None,
                 max_new_tokens: int = 1024,
                 log_mode: str = "console"):
        super().__init__(llm_name,
                         max_gpu_memory,
                         eval_device,
                         max_new_tokens,
                         log_mode)

    def load_llm_and_tokenizer(self) -> None:
        self.model = OpenAI()
        self.tokenizer = None

    def parse_tool_calls(self, tool_calls):
        if tool_calls:
            parsed_tool_calls = []
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                parsed_tool_calls.append(
                    {
                        "name": function_name,
                        "parameters": function_args
                    }
                )
            return parsed_tool_calls
        return None

    def process(self,
            agent_process,
            temperature=0.0
        ):
        # ensures the model is the current one
        assert re.search(r'gpt', self.model_name, re.IGNORECASE)

        """ wrapper around openai api """
        agent_process.set_status("executing")
        agent_process.set_start_time(time.time())
        messages = agent_process.query.messages
        # print(messages)
        self.logger.log(
            f"{agent_process.agent_name} is switched to executing.\n",
            level = "executing"
        )
        time.sleep(2)
        try:
            response = self.model.chat.completions.create(
                model=self.model_name,
                messages = messages,
                tools = agent_process.query.tools,
                # tool_choice = "required" if agent_process.query.tools else None,
                max_tokens = self.max_new_tokens,
                seed = 0,
                temperature = temperature,
            )
            response_message = response.choices[0].message.content
            tool_calls = self.parse_tool_calls(
                response.choices[0].message.tool_calls
            )
            # print(tool_calls)
            # print(response.choices[0].message)
            agent_process.set_response(
                Response(
                    response_message = response_message,
                    tool_calls = tool_calls
                )
            )
        except openai.APIConnectionError as e:
            detail = _format_openai_error(e)
            self.logger.log(f"OpenAI API connection error detail: {detail}", level="error")
            agent_process.set_response(
                Response(
                    response_message = f"Server connection error: {detail}"
                )
            )
        except openai.RateLimitError as e:
            detail = _format_openai_error(e)
            self.logger.log(f"OpenAI rate limit error detail: {detail}", level="error")
            agent_process.set_response(
                Response(
                    response_message = f"OpenAI RATE LIMIT error: {detail}"
                )
            )
        except openai.APIStatusError as e:
            detail = _format_openai_error(e)
            self.logger.log(f"OpenAI status error detail: {detail}", level="error")
            agent_process.set_response(
                Response(
                    response_message = f"OpenAI STATUS error: {detail}"
                )
            )
        except openai.BadRequestError as e:
            detail = _format_openai_error(e)
            self.logger.log(f"OpenAI bad request error detail: {detail}", level="error")
            agent_process.set_response(
                Response(
                    response_message = f"OpenAI BAD REQUEST error: {detail}"
                )
            )
        except Exception as e:
            detail = _format_openai_error(e)
            self.logger.log(f"Unexpected OpenAI wrapper error detail: {detail}", level="error")
            agent_process.set_response(
                Response(
                    response_message = f"An unexpected error occurred: {detail}"
                )
            )

        agent_process.set_status("done")
        agent_process.set_end_time(time.time())
