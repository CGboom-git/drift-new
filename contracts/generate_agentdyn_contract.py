"""Generate the reviewed AgentDyn v1.2 semantic tool contract from live schemas."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent
INVENTORY = ROOT / "agentdyn_v1_2_tool_inventory.json"
# This is a schema-derived *candidate*, never the contract used by experiments.
OUTPUT = ROOT / "agentdyn_ifc_global_tool_contract_candidate_v1.json"

READ_TOOLS = {
    "get_balance", "get_shopping_account_user_information", "get_shopping_linked_unread_emails",
    "get_shopping_linked_received_emails", "search_product", "view_order_history", "get_invoice",
    "view_cart", "cart_total", "view_available_discounts", "get_received_emails", "get_sent_emails",
    "get_unread_emails", "search_emails", "list_directory", "read_file", "browse_webpage",
    "download_file_through_url", "download_file_through_id", "get_current_day", "get_day_calendar_events",
    "search_calendar_events", "get_github_linked_unread_emails", "get_logged_in_github_user_information",
    "get_github_account_user_information", "get_github_repository_information", "git_get_linked_ssh_keys",
}
CREDENTIAL_ARGS = {"password", "otp", "ssh_key"}
TARGET_ARGS = {"recipient", "recipients", "cc", "bcc", "participants", "collaborator_email", "new_owner_username", "new_owner_email", "location", "url"}
CONTROL_ARGS = {"amount", "quantity", "date", "day", "start_time", "end_time", "new_start_time", "new_end_time", "force", "overwrite_local", "discount_code"}
CONTENT_ARGS = {"subject", "body", "content", "title", "description", "comment_body", "first_name", "last_name", "address", "input_values", "inputs"}
EXTERNAL_ACTION_PREFIXES = ("send_", "input_", "git_", "checkout_", "refund_")
DESTRUCTIVE_PREFIXES = ("delete_", "clear_", "cancel_", "refund_", "git_delete_")
REPAIR_FOR = {
    "create_dir": ["download_file_through_url", "download_file_through_id", "git_clone", "git_pull"],
    "verify_shopping_account": ["checkout_selected_cart", "refund_order", "update_shopping_account_password", "update_shopping_account_user_info"],
    "verify_transaction": ["send_money"],
    "verify_github_account": ["git_create_repo", "git_delete_repo", "git_transfer_repo_ownership", "git_invite_collaborators", "git_push", "git_pull", "git_issue", "git_add_ssh_key", "git_delete_ssh_key", "update_github_account_password"],
}


def role_for(arg_name: str) -> str:
    if arg_name in CREDENTIAL_ARGS or "password" in arg_name:
        return "credential"
    if arg_name in TARGET_ARGS:
        return "target"
    if arg_name in CONTROL_ARGS:
        return "control"
    if arg_name in CONTENT_ARGS:
        return "content"
    if arg_name == "input_ids" or arg_name.endswith(("_id", "_ids")):
        return "selector"
    if arg_name in {"repo_name", "product_name", "brand", "category", "rating_min", "rating_max", "price", "price_min", "price_max", "path", "source_path", "destination_path", "save_dir", "local_path", "local_dir_path", "query", "sender", "username", "email", "phone_number", "id_number", "passport_number", "bank_account_number", "attachments"}:
        return "selector"
    return "argument"


def deny_marks(role: str) -> list[str]:
    common = ["injected_instruction", "unknown_origin"]
    if role == "content":
        return common + ["policy_override_content", "raw_external_content"]
    if role == "credential":
        return common + ["model_inferred_unverified", "credential_or_secret"]
    if role in {"target", "selector", "control", "command"}:
        return common + ["model_inferred_unverified", "stale_or_ambiguous_source"]
    return common


def side_effect(tool_name: str, tool_type: str) -> str:
    if tool_type == "read":
        if tool_name.startswith("download_"):
            return "internal_filesystem_write"
        if "unread_emails" in tool_name or "received_emails" in tool_name:
            return "internal_read_state_update"
        if tool_name == "browse_webpage":
            return "conditional_external_navigation"
        return "none"
    if tool_name.startswith(DESTRUCTIVE_PREFIXES) or tool_name in {"delete_node", "cart_remove_product"}:
        return "destructive"
    if tool_name.startswith(EXTERNAL_ACTION_PREFIXES) or tool_name in {"add_calendar_event_participants", "create_calendar_event", "reschedule_calendar_event", "login_shopping_account", "login_github_account"}:
        return "external"
    return "internal"


inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
variants: dict[str, list[dict]] = defaultdict(list)
for suite_name, tools in inventory["suites"].items():
    for tool in tools:
        variants[tool["name"]].append({"suite": suite_name, **tool})

tools_out, schema_hashes = {}, {}
for tool_name, tool_variants in sorted(variants.items()):
    properties, required_by_suite = {}, {}
    for variant in tool_variants:
        schema = variant["parameters"]
        required_by_suite[variant["suite"]] = schema.get("required", [])
        for arg_name, arg_schema in schema.get("properties", {}).items():
            properties.setdefault(arg_name, arg_schema)
    args = {}
    for arg_name in sorted(properties):
        role = role_for(arg_name)
        args[arg_name] = {"name": arg_name, "sink_role": role, "high_risk": role in {"target", "selector", "control", "credential", "command"}, "content_like": role == "content", "deny_marks": deny_marks(role), "flow_constraints": ["task_relevance", "non_instructional_content"] if role == "content" else ["authorized_source", "task_relevance"]}
    hashes = sorted({v["schema_hash"] for v in tool_variants})
    schema_hashes[tool_name] = hashes[0] if len(hashes) == 1 else hashes
    tool_type = "read" if tool_name in READ_TOOLS else "action"
    tools_out[tool_name] = {"name": tool_name, "tool_type": tool_type, "side_effect": side_effect(tool_name, tool_type), "suites": sorted(v["suite"] for v in tool_variants), "description": tool_variants[0]["description"], "args": args, "repair_for": REPAIR_FOR.get(tool_name, []), "schema_variants": {"hashes": hashes, "required_by_suite": required_by_suite}}

contract = {"benchmark": "agentdyn", "benchmark_version": "v1.2", "contract_version": "pact_drift_ifc_agentdyn_semantic_review_v1", "adapter": {"name": "agentdyn", "suites": ["shopping", "github", "dailylife"], "notes": "Dataset-scoped contract generated from live AgentDyn schemas; semantic roles are rule-reviewed and must be audited when schemas change."}, "generated_by": {"mode": "deterministic_schema_inventory_plus_manual_semantic_review", "source": "AgentDyn v1.2 live Function objects"}, "sink_roles": ["target", "command", "credential", "content", "selector", "control", "argument"], "tool_schema_hashes": schema_hashes, "tools": tools_out}
canonical = json.dumps(contract, sort_keys=True, separators=(",", ":"))
contract["schema_hash"] = hashlib.sha256(canonical.encode()).hexdigest()
OUTPUT.write_text(json.dumps(contract, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"wrote {OUTPUT} with {len(tools_out)} unique tools")
