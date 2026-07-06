import json, os, glob

BASE = "/home/cg/Code/DRIFT/runs/gpt-4o-mini-2024-07-18"

for suite in ["banking", "slack", "travel", "workspace"]:
    if not os.path.exists(f"{BASE}/{suite}"):
        print(f"{suite}: (not run)")
        continue
    total = ut = sec = 0
    for rp in glob.glob(f"{BASE}/{suite}/**/important_instructions/injection_task_*.json", recursive=True):
        if "source_flow" in rp:
            continue
        try:
            d = json.load(open(rp))
            total += 1
            if d.get("utility"): ut += 1
            if d.get("security"): sec += 1
        except:
            pass
    ut_pct = ut/total*100 if total else 0
    sec_pct = sec/total*100 if total else 0
    print(f"{suite:<12} {total:>5} cases  ut={ut:>4} ({ut_pct:.0f}%)  sec={sec:>3} ({sec_pct:.0f}%)")
