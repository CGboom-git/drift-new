import json, os, glob

BASE = "/home/cg/Code/DRIFT/runs/gpt-4o-mini-2024-07-18"

sf_files = []
for root, dirs, files in os.walk(BASE):
    for f in files:
        if f.endswith(".source_flow.json"):
            sf_files.append(os.path.join(root, f))

slack = [s for s in sf_files if "slack" in s and "user_task_18" in s]
travel = [s for s in sf_files if "travel" in s and "user_task_4" in s]

TARGET_SINKS = [
    "send_direct_message.recipient", "send_direct_message.body",
    "send_channel_message.channel", "send_channel_message.body",
    "create_calendar_event.participants", "create_calendar_event.title",
    "create_calendar_event.location",
]

for name, paths in [("slack/18/1", slack), ("travel/4/0", travel)]:
    path = paths[0] if paths else None
    if not path:
        print(f"\n{name}: NO FILE")
        continue
    print(f"\n{'='*70}")
    print(f"CASE: {name}")
    print(f"{'='*70}\n")

    with open(path) as f:
        sf = json.load(f)

    records = sf.get("records", [])
    trace = sf.get("validation_trace", [])

    for e in trace:
        if e.get("event") == "source_flow_action_validation":
            d = e.get("details", {})
            tool_name = d.get("tool_name", "?")
            avs = d.get("arg_validations", [])
            if not avs:
                print(f"  [{tool_name}] decision={d.get('decision')} (no arg_validations)")
                continue
            
            relevant = [av for av in avs if any(t in str(av.get("sink","")) for t in TARGET_SINKS)]
            all_avs = avs if not relevant else relevant

            for av in all_avs:
                sink = av.get("sink", "?")
                print(f"\n  --- {sink} ---")
                print(f"  value: (see below)")
                print(f"  sink_role: {av.get('sink_role','?')}")
                print(f"  resolution_status: {av.get('resolution_status','?')}")
                print(f"  source_labels: {av.get('source_labels','?')}")
                print(f"  actual_origin_tools: {av.get('actual_origin_tools','?')}")
                print(f"  actual_origin_paths: {av.get('actual_origin_paths','?')}")
                print(f"  expected_root_tools: {av.get('expected_root_tools','?')}")
                print(f"  decision: {av.get('decision','?')}")
                print(f"  reason: {av.get('reason','?')}")
                
                labels = set(av.get("source_labels", []))
                for c in ["injected_instruction", "sanitized_observation", "user_explicit",
                           "delegated_task_source", "structured_field", "unknown_origin",
                           "model_generated", "clean_support_preferred", "selection_from_read_result"]:
                    if c in labels:
                        print(f"    HAS {c}")

                matched_ids = av.get("matched_sources", [])
                if matched_ids:
                    print(f"\n    Matched SourceRecords ({len(matched_ids)}):")
                    for rec in records:
                        if rec.get("source_id") in matched_ids:
                            val = str(rec.get("value", ""))[:200]
                            print(f"      [{rec.get('source_kind')}] tool={rec.get('tool')} labels={rec.get('source_labels',[])}")
                            print(f"        value: {val.replace(chr(10),' ')}")

    # Blocked flows / warnings
    print(f"\n  === BLOCKED/WARN ===")
    for e in trace:
        if e.get("event") == "source_flow_action_validation":
            d = e.get("details", {})
            for bf in d.get("blocked_flows", []):
                print(f"  BLOCK: {bf.get('sink')} reason={bf.get('reason')} labels={bf.get('source_labels','')[:100]}")
            for w in d.get("warnings", []):
                print(f"  WARN: {w.get('sink')} reason={w.get('reason')} labels={w.get('source_labels','')[:100]}")

    # All records with injected_instruction
    print(f"\n  === INJECTED RECORDS ===")
    for rec in records:
        if "injected_instruction" in rec.get("source_labels", []):
            print(f"  [{rec.get('source_kind')}] tool={rec.get('tool')} value={str(rec.get('value',''))[:150]}")
