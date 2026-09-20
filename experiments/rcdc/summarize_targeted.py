"""Report actual preflight state. Unrun online cells are null, never zero scores."""
import csv
import json
from pathlib import Path
from .run_targeted import ROOT, REPORT, dump, sha, REPO


def main():
    manifest = json.loads((ROOT/'targeted_manifest.json').read_text())
    checks = json.loads((REPORT/'preflight_tests.json').read_text())
    tests = {}
    for name in ('rcdc_unit_tests','rcdc_integration_tests','legacy_tests'):
        tests[name] = (REPORT/(name+'.txt')).read_text()
    groups = []
    for arm in ('C0','C1','C2','C3','C4'):
        groups.append({'config':arm,'status':'NOT_RUN','completed_cases':0,'benign_utility':None,
            'utility_under_attack':None,'asr':None,'invalid_effectful_call_rate':None,
            'legitimate_recovery_success':None,'unknown_resolution_rate':None,
            'recovery_exhaustion_rate':None,'witness_coverage':None,'average_recovery_steps':None,
            'tool_call_overhead':None,'llm_call_overhead':None,'tokens':None})
    summary = {'stage':'STEP_1_PREFLIGHT_BLOCKED','online_experiments_started':False,
        'natural_cases':manifest['case_count'],'distinct_user_tasks':manifest['distinct_user_tasks'],
        'families':manifest['families'],'smoke_cases':len(manifest['smoke_case_ids']),
        'scenario_manifest_complete':False,'online_results':groups,'preflight':checks,
        'rq1':'local deterministic object/field discrimination demonstrated; online APDE incremental effect not measured',
        'rq2':'NOT_MEASURED','rq3':'NOT_MEASURED',
        'blocking_requirement':'existing legacy tests must all pass, but untouched baseline has four reproducible failures',
        'pending_work':['complete recovery and APDE protocol integration tests','freeze A-F scenario fixtures',
                        'instrument complete model/tool budgets and counters','implement online worker and metrics from actual events'],
        'manifest_sha256':sha(ROOT/'targeted_manifest.json')}
    dump(REPORT/'summary.json',summary)
    for name in ('summary.csv','ablation_table.csv'):
        with (REPORT/name).open('w') as f:
            writer=csv.DictWriter(f,fieldnames=list(groups[0]));writer.writeheader();writer.writerows(groups)
    dump(REPORT/'review_cases.json',{'selection':'first clean and first attack per frozen task, no outcome filtering',
        'status':'PREPARED_NOT_RUN','cases':[c for c in manifest['cases'] if c['case_id'] in manifest['smoke_case_ids']]})
    lines = ['# RCDC 第一阶段：实现与预检报告','',
        '当前停在 Step 1 的基线测试门槛，尚未进入在线实验。所有在线指标均为 null/NOT_RUN，不将未运行记成 0% 或成功。', '',
        '## 已实现和已验证','',
        '- 独立 rcdc/ 模块：不可变 ConstraintSpec、三值 Witness、按任务/尝试/调用关联的证据账本、证据版本失效检查、有界恢复和读去重、宿主反馈消息身份登记。',
        '- 默认 off；独立集成工厂直接返回原 ToolsExecutor 与 DRIFTToolsExecutionLoop。未给原 pipeline_main.py 添加参数，统一开关目前仅在独立入口有效。',
        '- off/shadow 使用真实 AgentDojo 虚拟环境的响应和状态对比测试；strict UNKNOWN 在下一次模型调用前停止。未声称仅凭单元测试证明所有 Full 路径等价。',
        '- 21 项机制测试、6 项真实环境集成测试通过。六个任务的标准动作均通过各自规则；ground_truth 只在测试断言中使用，未输入运行时编译器。',
        '- 历史扫描形成 67 个完整日志自然 task/case，来自 6 个用户任务、5 个任务族；12 个 smoke 候选。67 条不是 67 个独立用户任务，后续推断需按用户任务分层。',
        '- 显式对象、闭集、数值范围支持三值判定。数值规则不隐式解析任意字符串；participant 集合比较是显式声明的规则语义。',
        '- 记录初始计划/checklist/backbone 为模型来源，contract 为工具来源；不将模型固定值提升为用户授权。宿主反馈不通过文本标签认证。', '',
        '## 已确认的基线问题','',
        '原 tests/ 在独立进程中没有导入 RCDC，结果仍为 161 passed、4 failed：', '',
        '- test_append_to_file_delegated_file_chain_downgrades_new_goal：期待 boundary 调用一次，实际零次。',
        '- test_mixed_authorized_and_unauthorized_targets_still_rejects_new_goal：期待不进入 fallback，实际发生 advisory_only fallback。',
        '- test_taer_new_goal_rejected_without_boundary：同样发生测试不期望的 advisory_only fallback。',
        '- test_validator_none_output_restored_before_checklist：期待 checklist 调用一次，实际零次。', '',
        '完整证据见 legacy_tests.txt。单独运行 taer 测试还暴露其模块 mock 依赖测试导入顺序；没有修改旧测试或掩盖失败。原 Full/TAER/SourceFlow/contracts 文件与引用历史输入哈希保持一致，见 preflight_tests.json。', '',
        '## 当前不能声称完成的部分','',
        'run_targeted.py 目前提供 prepare/test 与拒绝启动的 launch 门槛，不是已经完成的在线 worker。恢复读经过原 APDE 验证，但完整恢复对话、外部检测、重启生命周期、批量候选与额外 APDE 模型预算还需完成协议测试。',
        'A-F 分类没有按旧结果标签硬贴。C/D/E/F 需要独立冻结的恢复诱导、刷新、伪造、未解决测试条件；现有单元测试覆盖这些机制不等于 67 条线上自然样本覆盖它们。',
        'retry/full 当前是同模型、同 K、同最大提议与读工具调用的设计；APDE 验证本身产生的模型调用还需完整计数，尚不能声称总成本完全可比。',
        '未完成 audit_binding_witness/ 存在接口不一致，明确排除。使用此前 authorization_audit_20260908/output_v1_1、stage2/output_v2 和 host_feedback_pilot_20260909 作为先导依据，不将其数字当成本轮结果。', '',
        '## 七项研究问题','',
        '1. Binding Witness 独立增量：本地测试确认 provenance=True 仍可因对象错绑得到 INVALID；本轮在线相对 APDE 增量尚未测量。',
        '2. Strict 合法任务损失：未运行，无法估计。',
        '3. Bounded Recovery 恢复合法 UNKNOWN 数：只有测试夹具的 UNKNOWN→VALID，尚无在线分母。',
        '4. 普通 retry 是否同样有效：未运行，不能宣称 full 更好。',
        '5. 是否约束扩张：测试中 full 拒绝范围外读取；尚无在线攻击验证。',
        '6. 仍 UNKNOWN：缺证、未来证据、重复身份、对象不唯一、未知转换、恢复预算耗尽；具体在线 case 尚未产生。',
        '7. 是否扩大规模：当前不扩大。先处理基线测试门槛与 Step 1 协议，再执行12个固定 smoke，通过后才进入60–120范围。', '',
        '## 需要确认的基线政策','',
        '用户要求“off 旧单元测试全部通过”与现有未修改基线存在冲突。建议保留四项失败并明确冻结为已知基线，要求 RCDC 无新增失败和独立 off 等价检查通过，再继续 Step 1；这需要用户接受对全绿要求的例外。另一选择是单独修复原基线或旧测试，但将改变所比较的基线，需要单独审查，不能顺带修改。',
        '未发起 API 请求；指定实验 env 未用于付费调用。未修改原主实验或历史 runs。']
    (REPORT/'REPORT_CN.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'stage':summary['stage'],'natural_cases':manifest['case_count'],'online_started':False}))


if __name__ == '__main__':
    main()
