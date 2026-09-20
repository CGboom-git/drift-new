"""Opt-in, process-restorable snapshots at the first RCVR UNKNOWN decision.

Snapshots contain benchmark observations and must stay in a private run directory.
Only load snapshots produced by this process: pickle is not a safe interchange
format for untrusted input.
"""
from __future__ import annotations

import copy
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import pickle
import re
import tempfile

from .schema import canonical, digest


VERSION = 1
CLIENT_COUNTERS = ("completion_tokens", "prompt_tokens", "total_tokens", "tokens_dict")


def _safe_component(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", str(value))[:90]


def _llm_state(llm):
    # The OpenAI transport and logger own sockets, locks, and credentials. A
    # resumed worker constructs fresh instances and restores only policy state.
    return copy.deepcopy({key: value for key, value in vars(llm).items()
                          if key not in {"client", "logger"}})


def capture(root, context, llm, executor, spec, call, decision, env, messages, extra_args):
    """Persist the exact pre-recovery state and return its private file path."""
    if decision.verdict != "UNKNOWN":
        raise ValueError("checkpoint_requires_unknown")
    if not spec or spec.tool != call.tool:
        raise ValueError("checkpoint_candidate_spec_mismatch")
    if call.position != executor.clock:
        raise ValueError("checkpoint_clock_mismatch")
    if "pre_environment" not in context:
        raise ValueError("checkpoint_pre_environment_missing")
    calls = messages[-1].get("tool_calls") or []
    if len(calls) != 1 or getattr(calls[0], "id", None) != call.call_id:
        raise ValueError("checkpoint_batch_requires_single_candidate")
    case_dir = (Path(root) / _safe_component(context["run_tag"])
                / _safe_component(context["suite"]) / _safe_component(call.task_id)
                / _safe_component(context["injection_task_id"]))
    case_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    name = f"{call.position:04d}_{_safe_component(call.call_id)}.pkl"
    path = case_dir / name
    state = {
        "version": VERSION,
        "context": copy.deepcopy(context),
        "spec": spec,
        "call": call,
        "decision": decision,
        "ledger": copy.deepcopy(executor.ledger),
        "clock": executor.clock,
        "llm_state": _llm_state(llm),
        "client_counters": {key: copy.deepcopy(getattr(llm.client, key, None))
                            for key in CLIENT_COUNTERS},
        "environment": env.model_copy(deep=True),
        "messages": copy.deepcopy(messages),
        "extra_args": copy.deepcopy(extra_args),
        "hashes": {
            "spec": spec.constraint_id,
            "candidate": digest({"task_id": call.task_id, "tool": call.tool,
                                 "arguments": call.arguments, "call_id": call.call_id}),
            "evidence": digest([asdict(e) for e in executor.ledger.evidence()]),
            "environment": digest(env.model_dump(mode="json")),
        },
    }
    raw = pickle.dumps(state, protocol=pickle.HIGHEST_PROTOCOL)
    sha = hashlib.sha256(raw).hexdigest()
    if path.exists():
        raise FileExistsError(f"checkpoint_already_exists:{path}")
    with tempfile.NamedTemporaryFile(prefix=".checkpoint-", suffix=".tmp",
                                     dir=case_dir, delete=False) as stream:
        temp = Path(stream.name)
        os.chmod(temp, 0o600)
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)
    sidecar = path.with_suffix(".json")
    sidecar.write_text(canonical({"version": VERSION, "sha256": sha,
                                  "checkpoint": str(path), "hashes": state["hashes"],
                                  "initial_verdict": decision.verdict}) + "\n",
                       encoding="utf-8")
    os.chmod(sidecar, 0o600)
    return path


def load(path):
    """Read a trusted local snapshot and verify its sidecar before unpickling."""
    path = Path(path)
    raw = path.read_bytes()
    sidecar = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    if hashlib.sha256(raw).hexdigest() != sidecar["sha256"]:
        raise ValueError("checkpoint_checksum_mismatch")
    state = pickle.loads(raw)
    if state.get("version") != VERSION or state["decision"].verdict != "UNKNOWN":
        raise ValueError("invalid_checkpoint_version_or_verdict")
    if state["spec"].constraint_id != state["hashes"]["spec"]:
        raise ValueError("checkpoint_spec_changed")
    if digest(state["environment"].model_dump(mode="json")) != state["hashes"]["environment"]:
        raise ValueError("checkpoint_environment_changed")
    return state
