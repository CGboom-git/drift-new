"""Freeze RCVR task anchors from DRIFT's existing secure-planning state.

This module never calls a model. It normalizes the initial DRIFT trajectory,
parameter checklist, TAER backbone, and SourceFlow contract semantics into an
immutable task anchor before any runtime tool observation exists.
"""
from dataclasses import dataclass
import json

from .schema import canonical, digest


PLANNER_VERSION = "secure_planner_sourceflow_v1"


@dataclass(frozen=True)
class TaskAnchor:
    task_id: str
    user_task: str
    planner_version: str
    actions: str
    planner_metadata: str

    @property
    def anchor_id(self):
        return digest({"task_id": self.task_id, "user_task": self.user_task,
                       "planner_version": self.planner_version,
                       "actions": json.loads(self.actions)})

    @classmethod
    def create(cls, task_id, user_task, actions, planner_metadata=None):
        return cls(task_id, user_task, PLANNER_VERSION, canonical(actions),
                   canonical(planner_metadata or {}))


def _checklist(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            value = []
    return value if isinstance(value, list) else []


def _source_tools(condition):
    """Extract declared source tools from DRIFT's checklist condition field."""
    if isinstance(condition, str):
        return [condition] if condition else []
    if isinstance(condition, (list, tuple)):
        return [item for item in condition if isinstance(item, str) and item]
    if isinstance(condition, dict):
        return [str(value) for value in condition.values() if isinstance(value, str) and value]
    return []


def freeze_from_secure_plan(task_id, user_task, initial_trajectory, initial_checklist,
                            backbone, contracts):
    """Create ``C_t`` without re-planning or using runtime observations."""
    checklist = _checklist(initial_checklist)
    trajectory = list(initial_trajectory or [])
    steps = getattr(backbone, "backbone_steps", {}) or {}
    ordered_ids = list(getattr(backbone, "backbone_order", []) or [])
    actions = []

    for index, tool in enumerate(trajectory):
        node = checklist[index] if index < len(checklist) and isinstance(checklist[index], dict) else {}
        step = steps.get(ordered_ids[index]) if index < len(ordered_ids) else None
        required = getattr(step, "required_parameters", None) if step else node.get("required parameters", {})
        conditions = getattr(step, "conditions", None) if step else node.get("conditions", {})
        required = required if isinstance(required, dict) else {}
        conditions = conditions if isinstance(conditions, dict) else {}
        contract_args = contracts.get("tools", {}).get(tool, {}).get("args", {})
        fixed_constraints, origin_rules = [], []
        for parameter, value in required.items():
            if parameter not in contract_args or value is None:
                continue
            fixed_constraints.append({"parameter": parameter, "kind": "equals", "value": value,
                                      "comparison": "exact",
                                      "authority_basis": "secure_planner_user_requirement"})
        for parameter, condition in conditions.items():
            if parameter not in contract_args:
                continue
            sources = [name for name in _source_tools(condition)
                       if str(contracts.get("tools", {}).get(name, {}).get("tool_type", "")).startswith("READ")]
            if sources:
                origin_rules.append({"parameter": parameter, "source_tools": sources,
                                     "sink_role": contract_args[parameter].get("sink_role", "unknown"),
                                     "authority_basis": "secure_planner_condition_plus_sourceflow_contract"})
        actions.append({"tool": tool, "consumer_step_id": getattr(step, "step_id", None),
                        "fixed_constraints": fixed_constraints, "binding_rules": [],
                        "origin_rules": origin_rules})

    return TaskAnchor.create(task_id, user_task, actions, {
        "source": "drift_secure_planner_and_sourceflow_contract",
        "runtime_observations_in_anchor": False,
        "initial_trajectory": trajectory,
        "checklist_node_count": len(checklist),
        "backbone_initialized": bool(getattr(backbone, "initialized", False)),
        "action_count": len(actions),
    })
