import json, glob, os

BASE = "/home/cg/Code/DRIFT/runs/gpt-4o-mini-2024-07-18"
count = 0
total_avs = 0
found = 0

for suite in ["banking", "workspace", "travel"]:
    for sf_path in glob.glob(f"{BASE}/{suite}/user_task_*/important_instructions/source_flow/injection_task_*.json"):
        sf = json.load(open(sf_path))
        count += 1
        for e in sf.get("validation_trace", []):
            if e.get("event") == "source_flow_action_validation":
                for av in e["details"].get("arg_validations", []):
                    total_avs += 1
                    dt = av.get("derivation_type")
                    if dt:
                        found += 1
                        print(f"  {av['sink']:45s} dt={dt:30s} rs={av.get('resolution_status',''):30s}")

print(f"\nFiles checked: {count}")
print(f"Total arg_validations: {total_avs}")
print(f"With derivation_type: {found}")
