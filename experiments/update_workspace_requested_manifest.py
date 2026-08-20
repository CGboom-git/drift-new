"""Regenerate the manifest for the requested workspace regression cases."""
import json
from pathlib import Path


CASES = [
    (13, 0), (13, 2), (13, 4),
    (20, 0), (20, 3),
    (34, 0), (34, 2),
    (39, 0), (39, 3),
    (30, 0), (30, 3),
    (2, 0),
    (19, 0), (19, 3),
]

ROOT = Path("/home/cg/Code/drift-new-bestbackup/runs/gpt-4o-workspace_requested_cases/workspace")
ATTACK_TYPE = "important_instructions"


def main():
    manifest = []
    for user_task, injection_task in CASES:
        result_path = ROOT / f"user_task_{user_task}" / ATTACK_TYPE / f"injection_task_{injection_task}.json"
        record = {
            "user_task": user_task,
            "injection_task": injection_task,
            "result_path": str(result_path),
        }
        if result_path.exists():
            payload = json.loads(result_path.read_text(encoding="utf-8"))
            record["utility"] = payload.get("utility")
            record["security"] = payload.get("security")
            record["duration"] = payload.get("duration")
        else:
            record["missing"] = True
        manifest.append(record)

    manifest_path = ROOT / "requested_cases_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(manifest_path)
    print(f"utility={sum(1 for item in manifest if item.get('utility'))}/{len(manifest)}")
    print(f"security={sum(1 for item in manifest if item.get('security'))}/{len(manifest)}")


if __name__ == "__main__":
    main()
