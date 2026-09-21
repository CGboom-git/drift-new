"""Offline extension of the frozen AgentDojo IFC contract with output semantics.

This script reads tool declarations only.  It never loads user tasks, task
environments, trajectories, or runtime observations.
"""
import copy
import hashlib
import json
from pathlib import Path

from pydantic import TypeAdapter
from agentdojo.task_suite.load_suites import get_suite


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "agentdojo_ifc_global_tool_contract_semantic_review_gpt55.json"
TARGET = ROOT / "agentdojo_ifc_global_tool_contract_semantic_review_gpt55_output_v2.json"
FIELD_ROLES = {
    "id": "identity", "uuid": "identity", "event_id": "identity", "file_id": "identity",
    "sender": "principal_source", "author": "principal_source", "owner": "principal_owner",
    "recipient": "principal_destination", "participants": "principal_set", "email": "principal",
    "amount": "financial_value", "price": "financial_value", "cost": "financial_value",
    "date": "time", "start_time": "time", "end_time": "time",
    "subject": "content", "body": "content", "title": "content", "message": "content",
    "url": "resource_locator", "path": "resource_locator", "name": "display_name",
}


def fields(schema):
    defs = schema.get("$defs", {})
    while "$ref" in schema:
        schema = defs.get(schema["$ref"].rsplit("/", 1)[-1], {})
    while schema.get("type") == "array":
        schema = schema.get("items", {})
        while "$ref" in schema:
            schema = defs.get(schema["$ref"].rsplit("/", 1)[-1], {})
    return schema.get("properties", {}) if isinstance(schema.get("properties"), dict) else {}


def main():
    contract = json.loads(SOURCE.read_text(encoding="utf-8"))
    tools = {}
    for suite in ("banking", "slack", "travel", "workspace"):
        for tool in get_suite("v1.2", suite).tools:
            tools.setdefault(tool.name, tool)
    for name, node in contract["tools"].items():
        tool = tools.get(name)
        if tool is None or getattr(tool, "return_type", None) is None:
            continue
        schema = TypeAdapter(tool.return_type).json_schema()
        node["output_semantics"] = {
            "schema": schema,
            "fields": {field: {"role": FIELD_ROLES.get(field.lower(), "attribute")}
                       for field in fields(schema)},
            "source": "offline_declared_return_type",
        }
    contract["binding_capabilities"] = {
        "relation_types": ["unique_selected_record_field", "same_principal", "opposite_principal"],
        "parameter_role_compatibility": {
            "target": ["principal", "principal_destination", "resource_locator"],
            "selector": ["identity", "display_name", "resource_locator"],
            "control": ["financial_value", "time", "attribute"],
            "content": ["content", "display_name", "attribute"],
        },
    }
    contract["contract_version"] = "pact_drift_ifc_global_semantic_review_output_v2"
    contract["generation_mode"] = "offline_declared_return_type_plus_fixed_field_role_review"
    contract.pop("schema_hash", None)
    canonical = json.dumps(contract, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    contract["schema_hash"] = hashlib.sha256(canonical).hexdigest()
    TARGET.write_text(json.dumps(contract, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(TARGET)
    print(contract["schema_hash"])


if __name__ == "__main__":
    main()
