"""Generate repeated initial plans for AgentDojo benign tasks.

This script reuses the existing DRIFT Secure Planner prompt, model wiring,
and tool schema extraction, but stops immediately after plan generation.
It does not execute tools or run any validation / SourceFlow / TAER logic.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from client import OpenAIModel, OpenRouterModel, GoogleModel
from import_lib import get_suite
from prompts import CONSTRAINTS_BUILD_PROMPT
from DRIFTLLM import DRIFTLLM
from utils import get_logger, set_seed


DEFAULT_BENCHMARK_VERSION = "v1.2"
DEFAULT_MODEL = "gpt-4o-mini-2024-07-18"
DEFAULT_RUNS_PER_TASK = 5


@dataclass
class PlannerRunResult:
    suite: str
    task_id: str
    run_id: int
    user_query: str
    raw_planner_output: Any
    parsed_function_trajectory: list[str]
    parameter_checklist: Any
    model_config: dict[str, Any]
    token_usage: dict[str, Any]
    latency_seconds: float | None
    error_status: str


def build_client(model_name: str, logger):
    if model_name.startswith("gpt-"):
        return OpenAIModel(model=model_name, logger=logger)
    if model_name.startswith("gemini-"):
        return GoogleModel(model=model_name, logger=logger)
    return OpenRouterModel(model=model_name, logger=logger)


def to_tool_schema(tools):
    llm = object.__new__(DRIFTLLM)
    return DRIFTLLM.achieve_tools(llm, tools)


def extract_user_query(task) -> str:
    prompt = getattr(task, "PROMPT", None)
    if prompt:
        return prompt
    goal = getattr(task, "GOAL", None)
    if goal:
        return goal
    return str(task)


def flatten_completion(completion: Any) -> str:
    if completion is None:
        return ""
    if isinstance(completion, list):
        if not completion:
            return ""
        return str(completion[0])
    return str(completion)


def normalize_json_field(value: Any) -> Any:
    if isinstance(value, (dict, list, str, int, float, bool)) or value is None:
        return value
    return str(value)


def parse_run_output(llm: DRIFTLLM, completion: list[str], query: str):
    llm.initial_constraints_build(completion, query)
    return llm.initial_function_trajectory, llm.initial_node_checklist


def run_single_plan(client, suite_name: str, task_id: str, task, tools, logger, model_name: str, run_id: int):
    user_query = extract_user_query(task)
    start_tokens = {
        "total_completion_tokens": client.completion_tokens,
        "total_prompt_tokens": client.prompt_tokens,
        "total_total_tokens": client.total_tokens,
    }
    llm = object.__new__(DRIFTLLM)
    llm.client = client
    llm.args = argparse.Namespace(taer_mode="off")
    llm.model = model_name
    llm.temperature = 0.0
    llm.logger = logger
    llm.function_trajectory = []
    llm.initial_function_trajectory = []
    llm.achieved_function_trajectory = []
    llm.node_checklist = "None"
    llm.initial_node_checklist = "None"
    llm.taer_state = None
    llm._user_explicit_entities = set()
    llm._runtime_read_extensions = {}

    try:
        tools_docs = to_tool_schema(tools)
        messages = [
            {"role": "system", "content": CONSTRAINTS_BUILD_PROMPT},
            {"role": "user", "content": user_query},
        ]

        start = time.perf_counter()
        completion = client.agent_run(messages, tools_docs, query=user_query)
        latency = time.perf_counter() - start

        raw_output = flatten_completion(completion)
        parsed_traj, checklist = parse_run_output(llm, completion, user_query)

        return PlannerRunResult(
            suite=suite_name,
            task_id=task_id,
            run_id=run_id,
            user_query=user_query,
            raw_planner_output=raw_output,
            parsed_function_trajectory=list(parsed_traj or []),
            parameter_checklist=normalize_json_field(checklist),
            model_config={
                "model": model_name,
                "benchmark_version": DEFAULT_BENCHMARK_VERSION,
            },
            token_usage={
                "completion_tokens": client.completion_tokens - start_tokens["total_completion_tokens"],
                "prompt_tokens": client.prompt_tokens - start_tokens["total_prompt_tokens"],
                "total_tokens": client.total_tokens - start_tokens["total_total_tokens"],
                "cumulative": {
                    "completion_tokens": client.completion_tokens,
                    "prompt_tokens": client.prompt_tokens,
                    "total_tokens": client.total_tokens,
                },
            },
            latency_seconds=latency,
            error_status="",
        )
    except Exception as exc:
        return PlannerRunResult(
            suite=suite_name,
            task_id=task_id,
            run_id=run_id,
            user_query=user_query,
            raw_planner_output="",
            parsed_function_trajectory=[],
            parameter_checklist=None,
            model_config={
                "model": model_name,
                "benchmark_version": DEFAULT_BENCHMARK_VERSION,
            },
            token_usage={
                "completion_tokens": client.completion_tokens - start_tokens["total_completion_tokens"],
                "prompt_tokens": client.prompt_tokens - start_tokens["total_prompt_tokens"],
                "total_tokens": client.total_tokens - start_tokens["total_total_tokens"],
                "cumulative": {
                    "completion_tokens": client.completion_tokens,
                    "prompt_tokens": client.prompt_tokens,
                    "total_tokens": client.total_tokens,
                },
            },
            latency_seconds=None,
            error_status=f"{type(exc).__name__}: {exc}",
        )


def main():
    parser = argparse.ArgumentParser(description="Generate repeated initial plans for AgentDojo benign tasks.")
    parser.add_argument("--benchmark_version", default=DEFAULT_BENCHMARK_VERSION)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--suite", default="all", choices=["all", "banking", "slack", "travel", "workspace"])
    parser.add_argument("--runs_per_task", type=int, default=DEFAULT_RUNS_PER_TASK)
    parser.add_argument("--max_tasks", type=int, default=None)
    parser.add_argument("--output_jsonl", default="runs/planner_stability/planner_runs.jsonl")
    parser.add_argument("--output_json", default="runs/planner_stability/planner_runs.json")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    if args.seed is not None:
        set_seed(args.seed)

    output_jsonl = Path(args.output_jsonl)
    output_json = Path(args.output_json)
    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_jsonl.write_text("", encoding="utf-8")

    logger = get_logger(str(output_jsonl.parent / "planner_stability.log"))
    logger.info("Loading AgentDojo suites for planner stability analysis")

    suites = get_suite(args.benchmark_version, args.suite) if args.suite != "all" else None
    if suites is None:
        from import_lib import get_suites

        suites = get_suites(args.benchmark_version)
    else:
        suites = {args.suite: suites}

    client = build_client(args.model, logger)

    records: list[dict[str, Any]] = []
    total_tasks = 0

    for suite_name, suite in suites.items():
        if args.suite != "all" and suite_name != args.suite:
            continue

        for task_id, task in suite.user_tasks.items():
            if args.max_tasks is not None and total_tasks >= args.max_tasks:
                break
            total_tasks += 1
            for run_id in range(1, args.runs_per_task + 1):
                run_result = run_single_plan(
                    client=client,
                    suite_name=suite_name,
                    task_id=task_id,
                    task=task,
                    tools=suite.tools,
                    logger=logger,
                    model_name=args.model,
                    run_id=run_id,
                )
                records.append(asdict(run_result))
                with output_jsonl.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(asdict(run_result), ensure_ascii=False, default=str) + "\n")
            if args.max_tasks is not None and total_tasks >= args.max_tasks:
                break

    with output_json.open("w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2, default=str)

    logger.info(f"Saved {len(records)} planner runs to {output_jsonl} and {output_json}")


if __name__ == "__main__":
    main()
