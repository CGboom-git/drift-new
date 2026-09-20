"""Freeze and validate the RCVR ablation matrix without issuing model requests.

This is deliberately a preflight utility.  It writes a fresh execution manifest
and per-arm configuration files, while leaving the historical ``targeted_*``
inventory and all legacy Full files untouched.  A future online worker must
consume this manifest verbatim and record the named configuration fields.
"""
import argparse
import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
ROOT = Path(__file__).resolve().parent
PROTOCOL = ROOT / "rcvr_ablation_protocol.json"
INPUT_MANIFEST = ROOT / "targeted_manifest.json"
OUTPUT_ROOT = REPO / "reports" / "rcvr_ablation_preflight"
EXPECTED = {
    "B0_APDE": ("off", "full", False, True),
    "B1_RCVR": ("full", "full", True, True),
    "B2_WO_BINDING": ("full", "full", False, True),
    "B3_UNKNOWN_STOP": ("strict", "full", True, True),
    "B4_UNKNOWN_ALLOW": ("allow", "full", True, True),
    "B5_WO_EVIDENCE_ISOLATION": ("full", "full", True, False),
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_inputs():
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    inventory = json.loads(INPUT_MANIFEST.read_text(encoding="utf-8"))
    if protocol.get("method_name") != "RCVR":
        raise ValueError("protocol_method_name_must_be_RCVR")
    observed = {}
    for arm in protocol.get("configurations", []):
        arm_id = arm.get("id")
        observed[arm_id] = (arm.get("mode"), arm.get("relation_mode"),
                            arm.get("enable_binding_verification"), arm.get("enable_evidence_isolation"))
    if observed != EXPECTED:
        raise ValueError({"invalid_ablation_matrix": observed, "expected": EXPECTED})
    if inventory.get("case_count") != len(inventory.get("cases", [])):
        raise ValueError("frozen_case_count_mismatch")
    missing = [case["case_id"] for case in inventory["cases"]
               if not (REPO / case["payload_file"]).is_file()]
    if missing:
        raise ValueError({"missing_frozen_payloads": missing})
    return protocol, inventory


def prepare():
    protocol, inventory = load_inputs()
    configs = []
    for arm in protocol["configurations"]:
        arm_id = arm["id"]
        mode, relation, binding_enabled, isolation_enabled = EXPECTED[arm_id]
        config = {
            "method_name": "RCVR",
            "config_id": arm_id,
            "display_label": arm["label"],
            "rcvr_mode": mode,
            "compat_rcdc_mode": mode,
            "relation_mode": relation,
            "enable_binding_verification": binding_enabled,
            "enable_evidence_isolation": isolation_enabled,
            "recovery_model_calls_cap": protocol["common_controls"]["recovery_model_calls_cap"],
            "recovery_read_calls_cap": protocol["common_controls"]["recovery_read_calls_cap"],
            "recovery_tools": protocol["common_controls"]["recovery_tools"],
            "frozen_input_manifest": str(INPUT_MANIFEST.relative_to(REPO)),
            "frozen_input_manifest_sha256": sha256(INPUT_MANIFEST),
            "online_started": False,
        }
        dump(OUTPUT_ROOT / "configs" / f"{arm_id}.json", config)
        configs.append(config)
    result = {
        "method_name": "RCVR",
        "preflight_only": True,
        "online_started": False,
        "protocol_sha256": sha256(PROTOCOL),
        "frozen_input_manifest_sha256": sha256(INPUT_MANIFEST),
        "case_count": inventory["case_count"],
        "smoke_case_count": len(inventory["smoke_case_ids"]),
        "configurations": configs,
        "execution_order": ["B0_APDE", "B1_RCVR", "B2_WO_BINDING", "B3_UNKNOWN_STOP", "B4_UNKNOWN_ALLOW", "B5_WO_EVIDENCE_ISOLATION"],
        "required_before_online": [
            "certify scenario categories without outcome selection",
            "implement an online worker that consumes these exact configurations",
            "instrument APDE, base-model, recovery-model, and tool calls separately",
            "obtain explicit approval for the exact online command",
        ],
    }
    dump(OUTPUT_ROOT / "preflight.json", result)
    print(json.dumps({"method_name": "RCVR", "case_count": result["case_count"],
                      "arms": result["execution_order"], "online_started": False}))


def check():
    protocol, inventory = load_inputs()
    config_paths = [OUTPUT_ROOT / "configs" / f"{arm}.json" for arm in EXPECTED]
    if not all(path.is_file() for path in config_paths):
        raise ValueError("run_prepare_first")
    records = [json.loads(path.read_text(encoding="utf-8")) for path in config_paths]
    for record in records:
        expected_mode, expected_relation, expected_binding, expected_isolation = EXPECTED[record["config_id"]]
        if (record["rcvr_mode"], record["relation_mode"], record.get("enable_binding_verification"),
                record.get("enable_evidence_isolation")) != (expected_mode, expected_relation, expected_binding, expected_isolation):
            raise ValueError({"config_not_effective": record["config_id"]})
        if record["frozen_input_manifest_sha256"] != sha256(INPUT_MANIFEST):
            raise ValueError({"frozen_input_changed": record["config_id"]})
    print(json.dumps({"method_name": protocol["method_name"], "configurations_checked": len(records),
                      "case_count": inventory["case_count"], "online_started": False}))


def launch():
    raise SystemExit("Online launch intentionally unavailable: this preflight utility never issues API requests.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "check", "launch"))
    args = parser.parse_args()
    {"prepare": prepare, "check": check, "launch": launch}[args.command]()
