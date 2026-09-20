"""Read the frozen RCVR task-spec coverage registry.

The registry is an audit and authoring control. It never supplies benchmark
ground truth or dynamic values to the online executor. A task is "verified"
only after its deterministic specification and tests have been added to the
compiler.
"""
from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO / "experiments" / "rcdc" / "task_spec_registry_v1.json"


@lru_cache(maxsize=1)
def entries():
    payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    if payload.get("benchmark_version") != "v1.2" or payload.get("task_count") != 97:
        raise ValueError("invalid_task_spec_registry")
    result = {(entry["suite"], entry["user_task_id"]): entry for entry in payload["entries"]}
    if len(result) != 97:
        raise ValueError("task_spec_registry_identity_mismatch")
    return result


def coverage(suite: str | None, task_id: str):
    """Return a JSON-safe scope record; unknown identity is never covered."""
    entry = entries().get((suite, task_id)) if suite else None
    if entry is None:
        return {"suite": suite, "task_id": task_id, "runtime_status": "unknown_task_identity",
                "spec_family": None, "action_tools": []}
    return {key: entry.get(key) for key in
            ("suite", "user_task_id", "runtime_status", "spec_family", "action_tools")}
