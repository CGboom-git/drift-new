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
        declared = condition.get("source_tool", condition.get("source_tools"))
        if isinstance(declared, str) and declared:
            return [declared]
        if isinstance(declared, (list, tuple)):
            return [item for item in declared if isinstance(item, str) and item]
        return [str(value) for value in condition.values() if isinstance(value, str) and value]
    return []


def _binding_rule(parameter, condition, fixed_values, contracts):
    """Compile a planner-declared record relation without consulting runtime data.

    A plain ``"parameter": "read_tool"`` condition remains SourceFlow
    provenance metadata.  A structured condition can additionally specify the
    record selection and field relation that the stock RCDC witness validator
    already understands.  This is a schema, rather than a task-family rule.
    """
    if not isinstance(condition, dict):
        return None
    source_tool = condition.get("source_tool")
    if not isinstance(source_tool, str) or not source_tool:
        return None
    if not str(contracts.get("tools", {}).get(source_tool, {}).get("tool_type", "")).startswith("READ"):
        return None
    request = condition.get("request", {})
    predicates = condition.get("predicates", [])
    value_field = condition.get("value_field")
    identity_field = condition.get("identity_field", "")
    if (not isinstance(request, dict) or not isinstance(predicates, list) or not predicates
            or not isinstance(value_field, str) or not value_field
            or not isinstance(identity_field, str)):
        return None
    normalized_predicates = []
    for predicate in predicates:
        if not isinstance(predicate, dict):
            return None
        field = predicate.get("field")
        operator = predicate.get("operator", "equals")
        if not isinstance(field, str) or operator not in {"equals", "prefix", "date"}:
            return None
        if "value_from_parameter" in predicate:
            reference = predicate["value_from_parameter"]
            if not isinstance(reference, str) or reference not in fixed_values:
                return None
            value = fixed_values[reference]
        elif "value" in predicate:
            value = predicate["value"]
        else:
            return None
        normalized_predicates.append({"field": field, "value": value, "operator": operator})
    comparison = condition.get("comparison", "exact")
    if comparison not in {"exact", "number", "set_of_strings"}:
        return None
    rule = {
        "parameter": parameter, "source_tool": source_tool, "request": request,
        "predicates": normalized_predicates, "value_field": value_field,
        "identity_field": identity_field, "rule_id": condition.get("rule_id", "R3"),
        "comparison": comparison, "relation_type": "unique_object_field",
        "authority_basis": "secure_planner_relation_plus_sourceflow_contract",
    }
    if condition.get("selection") == "max":
        selection_field = condition.get("selection_field")
        if not isinstance(selection_field, str) or not selection_field:
            return None
        rule.update(selection="max", selection_field=selection_field)
    return rule


def _semantic_role(role):
    """Collapse contract field labels to the capability vocabulary."""
    if not isinstance(role, str):
        return ""
    if role.startswith("principal"):
        return "principal"
    return role


def _compile_relation_choices_atomic(checklist, trajectory, contracts, choices, user_query):
    """Materialize model *choices* into auditable binding conditions.

    The model may select only declared tools, fields and relation kinds.  This
    compiler owns every literal and final checklist mutation, so a model cannot
    smuggle a new source, field, target or runtime observation into an anchor.
    ``choices`` deliberately has a smaller surface than the legacy checklist:
    each item describes one action parameter and record relation.
    """
    if not isinstance(checklist, list) or not isinstance(choices, list):
        return None
    tools = contracts.get("tools", {}) if isinstance(contracts, dict) else {}
    caps = contracts.get("binding_capabilities", {}) if isinstance(contracts, dict) else {}
    allowed_relations = set(caps.get("relation_types", []))
    compatibility = caps.get("parameter_role_compatibility", {})
    nodes = [dict(node, **{"required parameters": dict(node.get("required parameters", {})),
                            "conditions": dict(node.get("conditions", {}))})
             for node in checklist]
    by_tool = {node.get("name"): node for node in nodes if isinstance(node, dict)}
    query = str(user_query).lower()

    for choice in choices:
        if not isinstance(choice, dict):
            return None
        action = choice.get("action_tool")
        parameter = choice.get("parameter")
        node = by_tool.get(action)
        action_args = tools.get(action, {}).get("args", {})
        if action not in trajectory or not isinstance(parameter, str) or parameter not in action_args or node is None:
            return None
        if choice.get("kind") == "operational_default":
            sink_role = action_args[parameter].get("sink_role", "")
            policy = choice.get("policy")
            if not ((sink_role == "content" and policy is None)
                    or (sink_role == "control" and parameter == "date" and policy == "host_execution_time")):
                return None
            node["required parameters"][parameter] = None
            node["conditions"][parameter] = {"kind": "operational_default", **(
                {"policy": policy} if policy else {})}
            continue
        source = choice.get("source_tool")
        relation = choice.get("relation")
        value_field = choice.get("value_field")
        identity_field = choice.get("identity_field", "")
        source_node = tools.get(source, {})
        fields = source_node.get("output_semantics", {}).get("fields", {})
        if (not isinstance(source, str) or not str(source_node.get("tool_type", "")).startswith("READ")
                or relation not in allowed_relations or not isinstance(value_field, str)
                or value_field not in fields or (identity_field and identity_field not in fields)):
            return None
        sink_role = action_args[parameter].get("sink_role", "")
        value_role = _semantic_role(fields[value_field].get("role")) if isinstance(fields[value_field], dict) else ""
        if value_role not in set(compatibility.get(sink_role, [])):
            return None
        predicates = []
        for item in choice.get("selection", []):
            if not isinstance(item, dict) or item.get("operator", "equals") not in {"equals", "prefix", "date"}:
                return None
            field, value = item.get("field"), item.get("value")
            if not isinstance(field, str) or field not in fields or not isinstance(value, dict):
                return None
            kind = value.get("kind")
            if kind == "user_literal":
                literal = value.get("value")
                if not isinstance(literal, (str, int, float)) or str(literal).lower() not in query:
                    return None
                predicate = {"field": field, "value": literal, "operator": item.get("operator", "equals")}
            elif kind == "fixed_action_parameter":
                reference = value.get("parameter")
                fixed = node.get("required parameters", {}).get(reference)
                if not isinstance(reference, str) or fixed is None:
                    return None
                predicate = {"field": field, "value_from_parameter": reference,
                             "operator": item.get("operator", "equals")}
            elif kind == "runtime_self":
                predicate = {"field": field, "value": "__RCVR_RUNTIME_SELF__",
                             "operator": item.get("operator", "equals")}
            else:
                return None
            predicates.append(predicate)
        if not predicates:
            return None
        node["required parameters"][parameter] = None
        node["conditions"][parameter] = {
            "source_tool": source, "request": choice.get("request", {}), "predicates": predicates,
            "value_field": value_field, "identity_field": identity_field,
            "comparison": choice.get("comparison", "exact"), "rule_id": "R3",
            "selection_relation": relation,
        }
    return nodes


def compile_relation_choices(checklist, trajectory, contracts, choices, user_query, allow_partial=False):
    """Compile choices atomically, or retain independently valid choices for repair.

    Partial mode is used only after the secure planner failed format retries.
    An invalid proposed relation is discarded; it cannot erase a separately
    valid binding.  The compiler then supplies the explicitly approved
    operational defaults for content and execution date.
    """
    if not allow_partial:
        return _compile_relation_choices_atomic(checklist, trajectory, contracts, choices, user_query)
    if not isinstance(choices, list):
        return None
    result, accepted = checklist, 0
    for choice in choices:
        candidate = _compile_relation_choices_atomic(result, trajectory, contracts, [choice], user_query)
        if candidate is not None:
            result, accepted = candidate, accepted + 1
    if not accepted:
        return None
    tools = contracts.get("tools", {}) if isinstance(contracts, dict) else {}
    for node in result:
        tool = node.get("name")
        if tool not in trajectory:
            continue
        args = tools.get(tool, {}).get("args", {})
        for parameter, value in node.get("required parameters", {}).items():
            if value is not None or parameter not in args:
                continue
            role = args[parameter].get("sink_role")
            if role == "content":
                node["conditions"].setdefault(parameter, {"kind": "operational_default"})
            elif role == "control" and parameter == "date":
                node["conditions"].setdefault(parameter, {
                    "kind": "operational_default", "policy": "host_execution_time"})
    return result


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
        # The normalized initial checklist is the immutable planner artifact.
        # TAER's backbone supplies only the stable consumer-step identity and
        # is a fallback for older snapshots that did not retain a node.
        required = node.get("required parameters", getattr(step, "required_parameters", {}))
        conditions = node.get("conditions", getattr(step, "conditions", {}))
        required = required if isinstance(required, dict) else {}
        conditions = conditions if isinstance(conditions, dict) else {}
        contract_args = contracts.get("tools", {}).get(tool, {}).get("args", {})
        fixed_constraints, origin_rules, binding_rules = [], [], []
        for parameter, value in required.items():
            if parameter not in contract_args or value is None:
                continue
            fixed_constraints.append({"parameter": parameter, "kind": "equals", "value": value,
                                      "comparison": "exact",
                                      "authority_basis": "secure_planner_user_requirement"})
        fixed_values = {rule["parameter"]: rule["value"] for rule in fixed_constraints}
        for parameter, condition in conditions.items():
            if parameter not in contract_args:
                continue
            sources = [name for name in _source_tools(condition)
                       if str(contracts.get("tools", {}).get(name, {}).get("tool_type", "")).startswith("READ")]
            if sources:
                origin_rules.append({"parameter": parameter, "source_tools": sources,
                                     "sink_role": contract_args[parameter].get("sink_role", "unknown"),
                                     "authority_basis": "secure_planner_condition_plus_sourceflow_contract"})
                rule = _binding_rule(parameter, condition, fixed_values, contracts)
                if rule is not None:
                    binding_rules.append(rule)
        actions.append({"tool": tool, "consumer_step_id": getattr(step, "step_id", None),
                        "fixed_constraints": fixed_constraints, "binding_rules": binding_rules,
                        "origin_rules": origin_rules})

    return TaskAnchor.create(task_id, user_task, actions, {
        "source": "drift_secure_planner_and_sourceflow_contract",
        "runtime_observations_in_anchor": False,
        "initial_trajectory": trajectory,
        "checklist_node_count": len(checklist),
        "backbone_initialized": bool(getattr(backbone, "initialized", False)),
        "action_count": len(actions),
    })
