import json, os, glob

BASE = "/home/cg/Code/DRIFT/runs/gpt-4o-mini-2024-07-18"
for sf_path in sorted(glob.glob(BASE + "/**/*.source_flow.json", recursive=True)):
    name = sf_path.replace(BASE + "/", "").replace("/important_instructions/source_flow/", "/")
    print(f"\n{'='*60}")
    print(f"CASE: {name}")
    with open(sf_path) as f:
        sf = json.load(f)
    trace = sf.get("validation_trace", [])
    
    # Also get result for utility/security
    result_path = sf_path.replace("/source_flow/", "/").replace(".source_flow.json", ".json")
    if os.path.exists(result_path):
        with open(result_path) as f:
            result = json.load(f)
        print(f"  utility={result.get('utility')} security={result.get('security')}")
    
    for e in trace:
        ev = e.get("event", "")
        if any(kw in ev for kw in ["controlled_action", "side_effect", "post_action", "source_flow_action_validation"]):
            d = e.get("details", {})
            print(f"  [{ev}] tool={d.get('tool_name','?')} decision={e['decision']} reason={d.get('reason','?')}")
            if ev == "post_action_side_effect_mismatch":
                print(f"    unexpected={json.dumps(d.get('unexpected_output_fields',''), indent=2)}")
