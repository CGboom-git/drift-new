"""Resume every supported UNKNOWN checkpoint in three fresh processes."""
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone


repo = Path(__file__).resolve().parents[2]
out = repo / "reports/rcvr_mechanism_subset15_20260920"
checkpoints = out / "checkpoints/rcvr_mechanism_subset15_20260920"
branches = out / "branches"
worker = repo / "experiments/rcdc/resume_checkpoint.py"
records = []
for checkpoint in sorted(checkpoints.rglob("*.pkl")):
    relative = checkpoint.relative_to(checkpoints)
    target = branches / relative.parent
    target.mkdir(parents=True, exist_ok=True)
    for arm in ("reject", "allow", "recovery"):
        result = target / f"{checkpoint.stem}_{arm}.json"
        if result.exists():
            records.append({"checkpoint": str(relative), "arm": arm, "status": "already_complete"})
            continue
        command = [sys.executable, "-B", str(worker), "--checkpoint", str(checkpoint),
                   "--branch", arm, "--output-dir", str(target)]
        completed = subprocess.run(command, cwd=repo, capture_output=True, text=True)
        record = {"checkpoint": str(relative), "arm": arm,
                  "status": "complete" if completed.returncode == 0 and result.exists() else "failed",
                  "returncode": completed.returncode,
                  "recorded_at": datetime.now(timezone.utc).isoformat()}
        if record["status"] == "failed":
            record["stderr_tail"] = completed.stderr[-2000:]
        records.append(record)
        (out / "branch_progress.json").write_text(json.dumps(records, indent=2) + "\n")
print(json.dumps({"checkpoint_count": len(list(checkpoints.rglob("*.pkl"))),
                  "branch_count": len(records),
                  "failed": sum(row["status"] == "failed" for row in records)}, indent=2))
