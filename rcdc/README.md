# RCDC Experimental Branch

状态：Step 1 本地实现和预检。在线入口尚未启用，不能将此目录描述为已完成在线验证。

核心代码不导入模型 API。`integration.py` 组合原 Full 组件，原 Full、TAER、SourceFlow、工具执行器文件均未修改。`components(..., mode='off')` 返回原组件；独立命令行默认 `--rcdc_mode off`，原 pipeline_main.py 的参数表不变。

约束冻结为不可变 JSON 快照，区分用户语义、模型计划/checklist/backbone、工具合同。运行时不读取 benchmark 标准答案。当前明确支持：退款、指定事件加参与者、沿用会议参与者、新增 Slack 频道成员、频道消息和最大文件选择。语义同义词匹配不由 LLM 猜测。

模式：off 完全旁路；shadow 只算 verdict；strict 未知/非法停止；retry 在共同读工具上普通补证提议；full 只允许满足当前缺失条件的确切读请求。INVALID 不进入恢复；只读恢复后重算 witness，原候选参数不自动改写。VALID 仍须通过 APDE，且仅表示已实现约束，不代表完整操作授权。

证据只能由宿主工具响应入口写入账本。跨任务、跨尝试、同 ID 歧义、未来记录不能形成有效 witness。当前对结构化字段真实性存在前提，不能抵御任意可信字段篡改；没有 exactly-once 或持久授权保证。

预检命令（项目根目录）：

```bash
/data/home/qyc/.conda/envs/drift/bin/python -B -m experiments.rcdc.run_targeted test
/data/home/qyc/.conda/envs/drift/bin/python -B -m experiments.rcdc.summarize_targeted
```

详细状态与未完成协议见 reports/rcdc_targeted/REPORT_CN.md。自然样本清单已冻结；它不是已完成 A-F 场景认证的正式在线 manifest。旧单元测试四项失败需确认基线政策，未启动新模型实验。
