"""Freeze an AgentDyn RCVR B1 pilot scope before any online call.

The script validates the requested IDs against AgentDyn's live v1.2 suite
objects, records the matching contract schema hash, and writes an isolated
preflight root.  It makes no model/API requests.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from agentdojo.task_suite.load_suites import get_suites


REPO = Path(__file__).resolve().parents[2]
AGENTDYN_SUITES = {"shopping", "github", "dailylife"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ids_for(suite, attribute: str) -> set[str]:
    return set(getattr(suite, attribute, {}).keys())


def parse_ids(value: str) -> list[str]:
    values = [item.strip() for item in value.split(",") if item.strip()]
    if not values:
        raise ValueError("at_least_one_id_required")
    return values


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", required=True, choices=sorted(AGENTDYN_SUITES))
    parser.add_argument("--user-task", help="One or more comma-separated user task IDs.")
    parser.add_argument("--injection-task", help="One or more comma-separated injection task IDs.")
    parser.add_argument("--all", action="store_true", help="Freeze every user/injection task in the selected suite.")
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)

    suites = get_suites("v1.2")
    suite = suites[args.suite]
    if args.all:
        if args.user_task or args.injection_task:
            raise ValueError("all_scope_cannot_mix_explicit_ids")
        users = sorted(ids_for(suite, "_user_tasks"))
        injections = sorted(ids_for(suite, "_injection_tasks"))
    else:
        if not args.user_task or not args.injection_task:
            raise ValueError("explicit_scope_requires_user_and_injection_ids")
        users, injections = parse_ids(args.user_task), parse_ids(args.injection_task)
    missing_users = sorted(set(users) - ids_for(suite, "_user_tasks"))
    missing_injections = sorted(set(injections) - ids_for(suite, "_injection_tasks"))
    if missing_users or missing_injections:
        raise ValueError({"missing_user_tasks": missing_users, "missing_injection_tasks": missing_injections})

    contract_path = REPO / "contracts" / "agentdyn_ifc_global_tool_contract_semantic_review_v2_fixed.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if contract.get("benchmark") != "agentdyn" or not contract.get("schema_hash"):
        raise ValueError("agentdyn_contract_invalid")

    output_root = args.output_root.resolve()
    config_dir = output_root / "configs"
    config_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": "rcvr-agentdyn-pilot-1",
        "benchmark": "agentdyn",
        "benchmark_version": "v1.2",
        "selection": {"suite": args.suite, "mode": "all" if args.all else "explicit", "user_task_ids": users, "injection_task_ids": injections},
        "case_count": len(users) * (1 + len(injections)),
        "contract_file": str(contract_path.relative_to(REPO).as_posix()),
        "contract_schema_hash": contract["schema_hash"],
        "online_started": False,
    }
    manifest_path = output_root / "agentdyn_targeted_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    config = {
        "method_name": "RCVR", "config_id": "B1_RCVR", "display_label": "Full RCVR",
        "rcvr_mode": "full", "compat_rcdc_mode": "full", "relation_mode": "full",
        "enable_binding_verification": True, "enable_evidence_isolation": True,
        "recovery_model_calls_cap": 2, "recovery_read_calls_cap": 2,
        "recovery_tools": "READ-only runtime tools", "contract_profile": "agentdyn",
        "contract_schema_hash": contract["schema_hash"],
        "frozen_input_manifest": str(manifest_path.relative_to(REPO).as_posix()),
        "frozen_input_manifest_sha256": sha256(manifest_path), "online_started": False,
    }
    config_path = config_dir / "B1_RCVR.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path), "config": str(config_path), "selection": manifest["selection"]}))


if __name__ == "__main__":
    main()
