"""Export AgentDyn v1.2 tool schemas from its live Function objects.

Run with the AgentDyn source directory placed before site-packages in
``PYTHONPATH``.  The output is deliberately schema-only; semantic roles are
added by the separately reviewed generator.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from agentdojo.task_suite.load_suites import get_suites


def schema_for(tool):
    model = tool.parameters
    if hasattr(model, "model_json_schema"):
        return model.model_json_schema()
    if hasattr(model, "schema"):
        return model.schema()
    return {}


inventory = {"benchmark": "agentdyn", "benchmark_version": "v1.2", "suites": {}}
for suite_name in ("shopping", "github", "dailylife"):
    items = []
    for tool in get_suites("v1.2")[suite_name].tools:
        schema = schema_for(tool)
        canonical = json.dumps(schema, sort_keys=True, separators=(",", ":"))
        items.append(
            {
                "name": tool.name,
                "description": tool.description,
                "full_docstring": tool.full_docstring,
                "parameters": schema,
                "return_type": str(tool.return_type),
                "schema_hash": hashlib.sha256(canonical.encode()).hexdigest(),
            }
        )
    inventory["suites"][suite_name] = items

path = Path(__file__).with_name("agentdyn_v1_2_tool_inventory.json")
path.write_text(json.dumps(inventory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(path)
for suite_name, items in inventory["suites"].items():
    print(suite_name, len(items))
