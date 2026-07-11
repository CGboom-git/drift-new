import json, glob, os

BASE = "/home/cg/Code/DRIFT/runs/sourceflow_4case_c_smoke"
for d in sorted(glob.glob(BASE + "/*")):
    name = os.path.basename(d)
    sf_path = os.path.join(d, "source_flow.json")
    result_path = os.path.join(d, "result.json")
    
    result = {}
    if os.path.exists(result_path):
        with open(result_path) as f:
            result = json.load(f)
    
    print(f"\n{'='*60}")
    print(f"CASE: {name}")
    print(f"  utility={result.get('utility')}, security={result.get('security')}")
    
    if not os.path.exists(sf_path):
        print("  no source_flow.json")
        continue
    
    with open(sf_path) as f:
        sf = json.load(f)
    
    trace = sf.get("validation_trace", [])
    validations = [e for e in trace if e["event"] == "source_flow_action_validation"]
    cae_events = [e for e in trace if "controlled_action_extension" in e.get("event","")]
    side_effects = [e for e in trace if "side_effect" in e.get("event","")]
    
    print(f"  total events: {len(trace)}")
    print(f"  action_validations: {len(validations)}")
    print(f"  CAE events: {len(cae_events)}")
    
    for v in validations:
        d = v["details"]
        if d.get("decision") != "allow" or v.get("would_reject"):
            print(f"    [!] {d.get('tool_name')}: {d.get('decision')} reason={d.get('reason')}")
    
    for c in cae_events:
        d = c.get("details", {})
        print(f"    [CAE] {c['event']}: {d.get('tool_name','?')} reason={d.get('reason','?')} decision={c.get('decision','?')}")
    
    for s in side_effects:
        print(f"    [SE] {s['event']}: decision={s.get('decision')}")
    
    # Check for rejected tool examples
    for v in validations:
        d = v["details"]
        if d.get("decision") == "reject" or v.get("would_reject"):
            bfs = d.get("blocked_flows", [])
            for bf in bfs:
                print(f"    BLOCKED: {bf.get('sink')} reason={bf.get('reason')} labels={bf.get('source_labels','')[:80]}")
