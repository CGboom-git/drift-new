import json
from collections import Counter, defaultdict
from pathlib import Path

RUN = Path("runs/gpt-4o-mini-2024-07-18-full_attack_gpt4omini_runtime_trace_retry1_20260823")
SUITES = ["banking", "slack", "travel", "workspace"]


def norm_relation(event):
    anchor = event.get("task_anchor_result") or {}
    relation = anchor.get("relation")
    if relation:
        return relation
    source = anchor.get("source")
    if source == "deterministic_backbone":
        return "DIRECT_EFFECT_DETERMINISTIC"
    status = anchor.get("status")
    if status == "disabled":
        return "ANCHOR_DISABLED"
    return "UNSPECIFIED"


cases = []
for suite in SUITES:
    for result_path in sorted((RUN / suite).glob("user_task_*/important_instructions/injection_task_*.json")):
        result = json.loads(result_path.read_text(encoding="utf-8"))
        trace_path = Path(result["runtime_drift_trace_path"])
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        out_events = [
            e for e in trace.get("taer_runtime_decisions", [])
            if isinstance(e, dict) and e.get("plan_match_status") != "IN_PLAN"
        ]
        relations = Counter(norm_relation(e) for e in out_events)
        decisions = Counter(e.get("final_decision", "UNKNOWN") for e in out_events)
        scope_failed = any((e.get("bounded_scope") or {}).get("passed") is False for e in out_events)
        scope_evaluated = any(
            (e.get("bounded_scope") or {}).get("status") == "evaluated"
            or (e.get("bounded_scope") or {}).get("passed") is not None
            for e in out_events
        )
        one_time_tools = {
            (e.get("runtime_action") or {}).get("tool_name")
            for e in out_events
            if (e.get("ephemeral_authorization") or {}).get("granted") is True
            and (e.get("ephemeral_authorization") or {}).get("lifetime") == "one_time"
        }
        tool_counts = Counter(a.get("tool_name") for a in trace.get("runtime_actions", []))
        repeated_authorized_tool = any(tool and tool_counts[tool] > 1 for tool in one_time_tools)
        cases.append({
            "case_id": f"{suite}/{result['user_task_id']}/{result['injection_task_id']}",
            "suite": suite,
            "utility": bool(result.get("utility")),
            "attack_success": bool(result.get("security")),
            "drift_type": trace.get("summary", {}).get("candidate_drift_type"),
            "taer_trigger": bool(out_events),
            "event_count": len(out_events),
            "relations": dict(relations),
            "decisions": dict(decisions),
            "scope_evaluated": scope_evaluated,
            "scope_failed": scope_failed,
            "one_time_grant": bool(one_time_tools),
            "repeated_authorized_tool": repeated_authorized_tool,
        })


def count_cases(predicate):
    return sum(1 for c in cases if predicate(c))


triggered = [c for c in cases if c["taer_trigger"]]
summary = {
    "total_cases": len(cases),
    "taer_trigger_cases": len(triggered),
    "negative_no_taer_cases": len(cases) - len(triggered),
    "taer_by_suite": Counter(c["suite"] for c in triggered),
    "taer_by_drift_type": Counter(c["drift_type"] for c in triggered),
    "case_relations": {
        relation: count_cases(lambda c, r=relation: c["relations"].get(r, 0) > 0)
        for relation in sorted({r for c in triggered for r in c["relations"]})
    },
    "event_relations": Counter(r for c in triggered for r, n in c["relations"].items() for _ in range(n)),
    "case_decisions": {
        decision: count_cases(lambda c, d=decision: c["decisions"].get(d, 0) > 0)
        for decision in sorted({d for c in triggered for d in c["decisions"]})
    },
    "scope_evaluated_cases": count_cases(lambda c: c["scope_evaluated"]),
    "scope_failed_cases": count_cases(lambda c: c["scope_failed"]),
    "one_time_grant_cases": count_cases(lambda c: c["one_time_grant"]),
    "repeated_authorized_tool_cases": count_cases(lambda c: c["repeated_authorized_tool"]),
    "multi_taer_event_cases": count_cases(lambda c: c["event_count"] > 1),
    "taer_attack_success_cases": count_cases(lambda c: c["taer_trigger"] and c["attack_success"]),
    "all_attack_success_cases": count_cases(lambda c: c["attack_success"]),
    "taer_utility_success_cases": count_cases(lambda c: c["taer_trigger"] and c["utility"]),
}

cross = defaultdict(Counter)
for c in triggered:
    cross[c["suite"]]["triggered"] += 1
    cross[c["suite"]]["allow_case"] += c["decisions"].get("ALLOW", 0) > 0
    cross[c["suite"]]["reject_case"] += c["decisions"].get("REJECT", 0) > 0
    cross[c["suite"]]["scope_failed"] += c["scope_failed"]
    cross[c["suite"]]["one_time_grant"] += c["one_time_grant"]
    cross[c["suite"]]["repeated_auth_tool"] += c["repeated_authorized_tool"]
    cross[c["suite"]]["attack_success"] += c["attack_success"]
summary["suite_cross"] = cross

print(json.dumps({"summary": summary, "triggered_cases": triggered}, indent=2, default=dict))
