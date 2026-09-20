import csv
import json
from collections import defaultdict
from pathlib import Path

RUN_NAME = "gpt-4o-mini-2024-07-18-full_attack_gpt4omini_runtime_trace_retry1_20260823"
ROOT = Path("runs") / RUN_NAME
OUT = ROOT / "analysis" / "runtime_authorization_drift"
SUITES = ["banking", "slack", "travel", "workspace"]
TYPES = ["NO_DRIFT", "IN_PLAN_PROVENANCE_DRIFT", "OUT_OF_PLAN_DRIFT", "MIXED_DRIFT"]
LABELS = {
    "NO_DRIFT": "No Drift",
    "IN_PLAN_PROVENANCE_DRIFT": "In-plan Provenance Drift",
    "OUT_OF_PLAN_DRIFT": "Out-of-plan Drift",
    "MIXED_DRIFT": "Mixed Drift",
}


def classify(action_drift, provenance_drift):
    if action_drift and provenance_drift:
        return "MIXED_DRIFT"
    if action_drift:
        return "OUT_OF_PLAN_DRIFT"
    if provenance_drift:
        return "IN_PLAN_PROVENANCE_DRIFT"
    return "NO_DRIFT"


def pct(n, d):
    return 100.0 * n / d if d else 0.0


def latex_escape(value):
    return str(value).replace("_", r"\_").replace("%", r"\%")


OUT.mkdir(parents=True, exist_ok=True)
rows = []
mismatches = []
missing = []
for suite in SUITES:
    pattern = ROOT / suite
    for result_path in sorted(pattern.glob("user_task_*/important_instructions/injection_task_*.json")):
        result = json.loads(result_path.read_text(encoding="utf-8"))
        trace_value = result.get("runtime_drift_trace_path")
        trace_path = Path(trace_value) if trace_value else (
            result_path.parent / "runtime_drift_trace" / f"{result_path.stem}.runtime_drift.json"
        )
        if not trace_path.is_absolute() and not trace_path.exists():
            trace_path = Path.cwd() / trace_path
        if not trace_path.exists():
            missing.append(str(result_path))
            continue
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        summary = trace.get("summary", {})
        action_count = int(summary.get("out_of_plan_action_count", 0) or 0)
        provenance_count = int(summary.get("provenance_drift_count", 0) or 0)
        taer_count = int(summary.get("taer_decision_count", 0) or 0)
        taer_out_of_plan_count = sum(
            event.get("plan_match_status") != "IN_PLAN"
            for event in trace.get("taer_runtime_decisions", [])
            if isinstance(event, dict)
        )
        action_drift = action_count > 0
        provenance_drift = provenance_count > 0
        drift_type = classify(action_drift, provenance_drift)
        recorded = summary.get("candidate_drift_type")
        if recorded and recorded != drift_type:
            mismatches.append((str(result_path), recorded, drift_type))
        user_id = result.get("user_task_id")
        injection_id = result.get("injection_task_id")
        rows.append({
            "case_id": f"{suite}/{user_id}/{injection_id}",
            "suite": suite,
            "user_task_id": user_id,
            "injection_task_id": injection_id,
            "drift_type": drift_type,
            "utility_success": bool(result.get("utility")),
            "attack_success": bool(result.get("security")),
            "PGPV_trigger": provenance_drift,
            "TAER_trigger": taer_out_of_plan_count > 0,
            "action_drift": action_drift,
            "provenance_drift": provenance_drift,
            "out_of_plan_action_count": action_count,
            "provenance_drift_count": provenance_count,
            "taer_decision_count": taer_count,
            "taer_out_of_plan_decision_count": taer_out_of_plan_count,
            "runtime_action_count": int(summary.get("runtime_action_count", 0) or 0),
            "total_tokens": int(result.get("total_tokens", 0) or 0),
            "duration_seconds": float(result.get("duration", 0) or 0),
            "result_path": str(result_path),
            "trace_path": str(trace_path),
        })

if missing:
    raise SystemExit(f"Missing {len(missing)} trace files")
if mismatches:
    raise SystemExit(f"Classification mismatches: {mismatches[:5]}")

case_fields = list(rows[0])
with (OUT / "drift_case_statistics.csv").open("w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=case_fields)
    writer.writeheader()
    writer.writerows(rows)


def grouped(scope_rows):
    result = []
    for drift_type in TYPES:
        subset = [r for r in scope_rows if r["drift_type"] == drift_type]
        n = len(subset)
        result.append({
            "drift_type": drift_type,
            "drift_label": LABELS[drift_type],
            "cases": n,
            "ratio_percent": pct(n, len(scope_rows)),
            "utility_successes": sum(r["utility_success"] for r in subset),
            "utility_percent": pct(sum(r["utility_success"] for r in subset), n),
            "attack_successes": sum(r["attack_success"] for r in subset),
            "asr_percent": pct(sum(r["attack_success"] for r in subset), n),
            "pgpv_triggers": sum(r["PGPV_trigger"] for r in subset),
            "pgpv_trigger_percent": pct(sum(r["PGPV_trigger"] for r in subset), n),
            "taer_triggers": sum(r["TAER_trigger"] for r in subset),
            "taer_trigger_percent": pct(sum(r["TAER_trigger"] for r in subset), n),
            "avg_tokens": sum(r["total_tokens"] for r in subset) / n if n else 0,
            "avg_duration_seconds": sum(r["duration_seconds"] for r in subset) / n if n else 0,
        })
    return result


scopes = [("all", rows)] + [(suite, [r for r in rows if r["suite"] == suite]) for suite in SUITES]
all_summaries = []
for scope, scope_rows in scopes:
    for item in grouped(scope_rows):
        all_summaries.append({"scope": scope, **item})

with (OUT / "drift_distribution.csv").open("w", newline="", encoding="utf-8-sig") as f:
    fields = ["scope", "drift_type", "drift_label", "cases", "ratio_percent"]
    writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(all_summaries)

with (OUT / "drift_performance_summary.csv").open("w", newline="", encoding="utf-8-sig") as f:
    fields = ["scope", "drift_type", "drift_label", "cases", "utility_successes",
              "utility_percent", "attack_successes", "asr_percent", "avg_tokens", "avg_duration_seconds"]
    writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(all_summaries)

with (OUT / "component_activation_summary.csv").open("w", newline="", encoding="utf-8-sig") as f:
    fields = ["scope", "drift_type", "drift_label", "cases", "pgpv_triggers",
              "pgpv_trigger_percent", "taer_triggers", "taer_trigger_percent"]
    writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(all_summaries)

overall = [r for r in all_summaries if r["scope"] == "all"]
suite_summary = {suite: grouped(subset) for suite, subset in scopes if suite != "all"}

latex = []
latex.append(r"\begin{table}[t]")
latex.append(r"\centering")
latex.append(r"\caption{Runtime authorization drift distribution.}")
latex.append(r"\begin{tabular}{lrr}")
latex.append(r"\toprule Drift Type & Cases & Ratio (\%) \\ \midrule")
for r in overall:
    latex.append(f"{latex_escape(r['drift_label'])} & {r['cases']} & {r['ratio_percent']:.2f} \\")
latex.append(r"\midrule Total & 949 & 100.00 \\ \bottomrule")
latex.append(r"\end{tabular}")
latex.append(r"\end{table}")
latex.append("")
latex.append(r"\begin{table}[t]")
latex.append(r"\centering")
latex.append(r"\caption{Performance and component activation by drift type.}")
latex.append(r"\begin{tabular}{lrrrrr}")
latex.append(r"\toprule Drift Type & Cases & Utility (\%) & ASR (\%) & PGPV (\%) & TAER (\%) \\ \midrule")
for r in overall:
    latex.append(
        f"{latex_escape(r['drift_label'])} & {r['cases']} & {r['utility_percent']:.2f} & "
        f"{r['asr_percent']:.2f} & {r['pgpv_trigger_percent']:.2f} & {r['taer_trigger_percent']:.2f} \\")
latex.append(r"\bottomrule \end{tabular}")
latex.append(r"\end{table}")
(OUT / "drift_tables.tex").write_text("\n".join(latex) + "\n", encoding="utf-8")

def count_pct(value, total):
    return f"{value}/{total} ({pct(value, total):.2f}%)"

report = [
    "# GPT-4o-mini Runtime Authorization Drift 分层消融分析",
    "",
    f"- 实验目录：`{ROOT}`",
    f"- 有效攻击 case：{len(rows)}",
    "- 配置：Full TAER、Source Flow Validation、Runtime Drift Trace、important_instructions 攻击。",
    "- 本报告是完成实验记录上的离线分层/组件激活分析，不修改算法、不重跑实验。",
    "",
    "## 分类与触发口径",
    "",
    "- Action drift：`out_of_plan_action_count > 0`。",
    "- Provenance drift：`provenance_drift_count > 0`。",
    "- PGPV Trigger：本 case 出现 provenance drift。",
    "- TAER Trigger：至少存在一次 `plan_match_status != IN_PLAN` 的结构化 TAER 决策；计划内直接放行记账不算触发。",
    "- Utility 与 ASR 均按 case 微平均。",
    "",
    "## Drift 分布与性能",
    "",
    "| Drift Type | Cases | Ratio | Utility | ASR | Avg Token | Avg Time |",
    "|---|---:|---:|---:|---:|---:|---:|",
]
for r in overall:
    report.append(
        f"| {r['drift_label']} | {r['cases']} | {r['ratio_percent']:.2f}% | "
        f"{count_pct(r['utility_successes'], r['cases'])} | "
        f"{count_pct(r['attack_successes'], r['cases'])} | "
        f"{r['avg_tokens']:.0f} | {r['avg_duration_seconds']:.1f}s |"
    )

report += [
    "",
    "## 组件激活",
    "",
    "| Drift Type | PGPV Trigger | TAER Trigger |",
    "|---|---:|---:|",
]
for r in overall:
    report.append(
        f"| {r['drift_label']} | {count_pct(r['pgpv_triggers'], r['cases'])} | "
        f"{count_pct(r['taer_triggers'], r['cases'])} |"
    )

report += ["", "## Suite 分布", ""]
for suite in SUITES:
    report += [f"### {suite.title()}", "", "| Drift Type | Cases | Ratio | Utility | ASR |", "|---|---:|---:|---:|---:|"]
    for r in suite_summary[suite]:
        report.append(
            f"| {r['drift_label']} | {r['cases']} | {r['ratio_percent']:.2f}% | "
            f"{count_pct(r['utility_successes'], r['cases'])} | {count_pct(r['attack_successes'], r['cases'])} |"
        )
    report.append("")

report += [
    "## 主要发现",
    "",
    "1. **Runtime drift 是主导现象。** 879/949（92.62%）case 出现至少一种 drift；其中 Mixed Drift 451/949（47.52%）最多，In-plan Provenance Drift 399/949（42.04%）次之。",
    "2. **攻击成功集中在 action drift。** 10 个攻击成功 case 全部位于 Out-of-plan/Mixed 两类：Out-of-plan 1/29、Mixed 9/451；No Drift 与 In-plan Provenance Drift 均为 0。合并后，含 action drift 的条件 ASR 为 10/480（2.08%），不含 action drift 为 0/469（0%）。",
    "3. **Mixed Drift 的运行代价最高。** Mixed Drift 平均 38,362 token、46.2 秒；相较 In-plan Provenance Drift 的 24,731 token、30.9 秒，分别增加约 55.1% 和 49.3%。",
    "4. **组件对应关系总体成立但并非一一映射。** PGPV Trigger 按 provenance drift 定义，因此 provenance 两类为 100%。在线 TAER 的计划外结构化决策覆盖 Out-of-plan 9/29（31.03%）和 Mixed 191/451（42.35%）；另外 In-plan Provenance Drift 中有 31 个 TAER Trigger，说明离线顺序分类与在线 backbone/repair 判定口径存在差异。",
    "5. **风险主要来自 Banking。** 10 个攻击成功中 Banking Mixed Drift 占 7 个；Slack 为 0，Travel 为 1，Workspace 为 2。",
    "6. **Utility 不能直接解释为组件因果收益。** In-plan Provenance Drift Utility 最高（276/399，69.17%），No Drift 最低（28/70，40%），这也可能反映 case 难度与轨迹结构差异，不能据此认定 drift 提升 Utility。",
    "",
    "## 解释边界",
    "",
    "这组结果能够回答不同 runtime drift 类型下 Full 系统的性能，以及 PGPV/TAER 的实际激活对应关系。"
    "它不能单独证明移除某个 TAER 子组件后的因果性能变化；后者仍需在同一冻结 case 集上运行 "
    "`no_anchor`、`no_scope`、`no_ephemeral` 并与 `full` 配对比较。",
    "",
    "## 输出文件",
    "",
    "- `drift_case_statistics.csv`：逐 case 统计。",
    "- `drift_distribution.csv`：总体及分 suite 漂移分布。",
    "- `drift_performance_summary.csv`：Utility、ASR、token、耗时。",
    "- `component_activation_summary.csv`：PGPV/TAER 激活率。",
    "- `drift_tables.tex`：论文 LaTeX 表格。",
]
(OUT / "drift_ablation_analysis.md").write_text("\n".join(report) + "\n", encoding="utf-8")

manifest = {
    "run_name": RUN_NAME,
    "case_count": len(rows),
    "missing_trace_count": len(missing),
    "classification_mismatch_count": len(mismatches),
    "outputs": sorted(p.name for p in OUT.iterdir()),
}
(OUT / "analysis_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(json.dumps({"manifest": manifest, "overall": overall}, indent=2))
