"""Turn an audited AgentDyn schema candidate into an immutable experiment contract.

This tool deliberately fails on inventory coverage drift.  Re-running the live
schema exporter may create a new candidate, but it never overwrites the fixed
contract consumed by RCVR experiments.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
INVENTORY = ROOT / "agentdyn_v1_2_tool_inventory.json"
CANDIDATE = ROOT / "agentdyn_ifc_global_tool_contract_candidate_v1.json"
OUTPUT = ROOT / "agentdyn_ifc_global_tool_contract_semantic_review_v2_fixed.json"


SIDE_EFFECT_OVERRIDES = {
    "download_file_through_id": "internal_filesystem_write",
    "download_file_through_url": "internal_filesystem_write",
    "cancel_calendar_event": "external_destructive",
    "refund_order": "external_destructive",
    "git_delete_repo": "external_destructive",
    "git_delete_ssh_key": "external_destructive",
    "update_github_account_password": "external",
    "update_shopping_account_password": "external",
    "update_shopping_account_user_info": "external",
}
ACTION_TYPE_OVERRIDES = {"download_file_through_id", "download_file_through_url"}
ROLE_OVERRIDES = {
    "update_shopping_account_user_info": {
        "first_name": "target", "last_name": "target", "address": "target",
        "email": "target", "phone_number": "target", "id_number": "credential",
        "passport_number": "credential", "bank_account_number": "credential",
    }
}


def deny_marks(role: str) -> list[str]:
    common = ["injected_instruction", "unknown_origin"]
    if role == "content":
        return common + ["policy_override_content", "raw_external_content"]
    if role == "credential":
        return common + ["model_inferred_unverified", "credential_or_secret"]
    if role in {"target", "selector", "control", "command"}:
        return common + ["model_inferred_unverified", "stale_or_ambiguous_source"]
    return common


inventory_bytes = INVENTORY.read_bytes()
inventory = json.loads(inventory_bytes)
candidate = json.loads(CANDIDATE.read_text(encoding="utf-8"))
live_tools = {tool["name"] for suite in inventory["suites"].values() for tool in suite}
candidate_tools = set(candidate.get("tools", {}))
if live_tools != candidate_tools:
    raise ValueError({"missing": sorted(live_tools - candidate_tools), "stale": sorted(candidate_tools - live_tools)})

contract = json.loads(json.dumps(candidate))
for tool_name in ACTION_TYPE_OVERRIDES:
    contract["tools"][tool_name]["tool_type"] = "action"
for tool_name, effect in SIDE_EFFECT_OVERRIDES.items():
    contract["tools"][tool_name]["side_effect"] = effect
for tool_name, arg_roles in ROLE_OVERRIDES.items():
    for arg_name, role in arg_roles.items():
        arg = contract["tools"][tool_name]["args"][arg_name]
        arg.update({
            "sink_role": role,
            "high_risk": role in {"target", "selector", "control", "credential", "command"},
            "content_like": role == "content",
            "deny_marks": deny_marks(role),
            "flow_constraints": ["authorized_source", "task_relevance"],
        })

contract["contract_version"] = "pact_drift_ifc_agentdyn_semantic_review_v2_fixed"
contract["source_inventory_sha256"] = hashlib.sha256(inventory_bytes).hexdigest()
contract["generated_by"] = {
    "mode": "fixed_after_schema_inventory_and_manual_semantic_review",
    "candidate_file": CANDIDATE.name,
    "reviewed_changes": {
        "download_tools": "classified as actions because they write to local storage",
        "account_updates": "classified as external; identity and account fields are high-risk sinks",
        "destructive_external_tools": "distinguished from internal destructive changes",
    },
}
contract.pop("schema_hash", None)
canonical = json.dumps(contract, sort_keys=True, separators=(",", ":"))
contract["schema_hash"] = hashlib.sha256(canonical.encode()).hexdigest()
OUTPUT.write_text(json.dumps(contract, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps({"output": str(OUTPUT), "tools": len(live_tools), "schema_hash": contract["schema_hash"], "inventory_sha256": contract["source_inventory_sha256"]}))
