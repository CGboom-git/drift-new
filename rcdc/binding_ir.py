"""Single frozen binding representation shared by RCVR and SourceFlow."""
import json


def from_anchor(anchor):
    """Compile immutable anchor actions to SourceFlow's checklist input shape.

    This is an adapter, not another planner: it preserves only frozen action
    constraints and binding rules, so legacy checklist formatting cannot alter
    the evidence policy after execution begins.
    """
    if anchor is None:
        return None
    nodes = []
    for action in json.loads(anchor.actions):
        required = {item['parameter']: item['value'] for item in action.get('fixed_constraints', [])}
        conditions = {}
        for rule in action.get('binding_rules', []):
            conditions[rule['parameter']] = {
                'source_tool': rule['source_tool'], 'request': rule['request'],
                'predicates': rule['predicates'], 'value_field': rule['value_field'],
                'identity_field': rule.get('identity_field', ''),
                'comparison': rule.get('comparison', 'exact'), 'rule_id': rule.get('rule_id', 'R3'),
            }
        nodes.append({'name': action['tool'], 'required parameters': required, 'conditions': conditions})
    return json.dumps(nodes, ensure_ascii=False, sort_keys=True)
