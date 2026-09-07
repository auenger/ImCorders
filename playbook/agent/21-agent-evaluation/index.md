# 结果、过程与轨迹评估

作者：杨正武
来源：https://imcoders.cn/playbook/agent/21-agent-evaluation/
更新：2026-08-12T00:00:00.000Z

同时评估目标完成、产物质量、计划、工具选择、执行轨迹、安全和恢复行为。

---


最终答案正确，不代表执行合理：Agent 可能泄露敏感数据、调用了错误 Tool，或在十次无效重试后偶然得到结果。轨迹看起来专业也不代表目标完成：一份结构完整的报告，可能引用了错误数据。

> Outcome 判断“做成没有”，Trajectory 判断“怎样做成”，Safety 判断“这条路径是否允许”。三者不能被一个总分掩盖。

## 术语来源与适用范围

Evaluation、Ground Truth、Precision / Recall、Inter-rater Agreement 来自软件测试、统计学习和质量评估。模型厂商与 Agent 平台也普遍使用 Grader、LLM-as-a-Judge、Trace Grading 等术语，但各家的对象和分数不可直接互换。[OpenAI Evaluation Best Practices](https://platform.openai.com/docs/guides/evaluation-best-practices)强调任务特定的评估、自动评分与人工判断组合；[NIST AI RMF](https://www.nist.gov/itl/ai-risk-management-framework)提供的是风险管理框架，而不是 Agent 轨迹评分协议。

本章的七层 `Agent Evaluation Matrix`、硬门禁和校准流程是 Playbook 的分析框架，不是行业标准。它适用于具有 Goal、Run、Tool 与 Artifact 的执行系统；纯聊天应用可以采用其中的答案质量部分，不必虚构不存在的 Plan 或 Tool 指标。

## 七层评估矩阵

![Agent Evaluation Matrix：结果、轨迹与运行约束](/playbook-images/agent/agent-evaluation-matrix.svg)

| 层次 | 关键问题 | 优先评估器 | 是否可作硬门禁 |
| --- | --- | --- | --- |
| Goal Completion | 用户目标是否真正完成 | 业务状态 + 验收断言 | 是 |
| Artifact Quality | 产物是否正确、完整、可用 | Schema、测试、静态分析、人工 | 是 |
| Trajectory Quality | 路径是否有效、收敛、可解释 | 规则 + Trace Grader | 视任务而定 |
| Tool Selection & Arguments | Tool 与参数是否正确 | 契约验证 + 对照标签 | 是 |
| Permission & Safety | 是否越权、泄密或绕过审批 | Policy Replay + 安全规则 | 是 |
| Cost & Latency | 是否落在预算与 SLO 内 | Metric 计算 | 是 |
| Recovery Behavior | 中断、超时和未知副作用后是否安全继续 | 故障注入 + Event 断言 | 是 |

不要把“7.8 分”作为唯一结论。质量 9 分但发生越权，Run 仍然不合格；答案正确但重复扣款，仍然是严重失败。

## 先写验收证据，再选择评估器

好的评估从 Acceptance Contract 开始：

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“先写验收证据，再选择评估器”落成可检查的结构化记录，主要字段包括 `acceptance`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
acceptance:
  goal: 将服务升级到 v3.4，并保持向后兼容
  evidence:
    - deployment.version == "3.4"
    - smoke_tests.pass == true
    - api_contract.breaking_changes == 0
  forbidden:
    - production_secret_in_trace
    - unapproved_database_migration
  budgets:
    wall_time: PT20M
    cost_usd: 2.50
```

如果没有可观察证据，“完成”就只能依赖模型自述。模型提交 `completion_requested` 只是申请，Evaluator 必须验证环境状态或 Artifact。

## 四类评估器怎样组合

### 确定性验证器

单元测试、Schema、编译器、SQL 断言、业务状态查询和 Policy Engine 可重复、便宜、可解释。能确定性验证的内容，不应先交给 LLM 判断。

### LLM-as-a-Judge

适合评估表达质量、语义覆盖、风格遵循和需要上下文理解的软标准。Judge 应看到明确 Rubric、候选结果和必要证据，不应看到会泄露实验分组的无关信息。优先做成对比较或分项判定，少用没有锚点的 1–10 总分。

### Agent-as-a-Judge

当验证需要主动查询环境、运行测试或检查多个 Artifact 时，Judge 本身也可以是受限 Agent。它必须拥有独立权限、只读优先的 Tool 集和明确停止条件。Agent Judge 是更强的执行型评估器，不代表天然更客观。

### 人工评估

用于高风险、安全边界、新任务定义、Judge 分歧与抽样校准。人工不是“永远正确的标签机器”，也需要 Rubric、证据界面和分歧处理流程。

## 轨迹评估关注关键决策，不评分隐藏思维

Trajectory Evaluation 应评价可观察动作：选了哪个 Tool、参数来自哪里、是否重复、是否验证、是否遵守审批。不要要求保存或评分模型隐藏推理。可用指标包括：

- 必要 Step 覆盖率与禁止 Step 命中率。
- 错误 Tool 选择率与参数修复次数。
- 无进展 Step、重复 Tool Call 和 Replan 次数。
- 首次失败后的恢复策略是否改变。
- 完成前是否获得要求的验证证据。

允许多条正确路径时，不要把 Golden Trajectory 当成唯一顺序。可以规定关键不变量与允许的部分顺序，而不是逐 Token 或逐 Step 比对。

## Evaluator Calibration

**代码块说明｜流程示意：** 这段文本图按箭头方向阅读，用来说明“Evaluator Calibration”中的执行顺序、状态变化或责任流转。它表达逻辑关系，不代表组件必须按图中的数量和位置部署。

```text
定义 Rubric
    ↓
双人标注一组代表性样本
    ↓
解决分歧，形成 Adjudicated Ground Truth
    ↓
运行自动 Evaluator
    ↓
按任务切片计算一致率、误报和漏报
    ↓
调整 Rubric / 阈值 / Judge Prompt
    ↓
冻结 Evaluator Version
```

Judge 与被评模型使用相同模型家族时可能共享偏差；缓解方式包括：混合确定性证据、使用独立 Judge、隐藏版本身份、保留人工盲测样本，并在难例和安全例上单独看误差。不要因为总体一致率高，就忽略高风险切片的漏报。

## Evaluation Result 参考结构

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“Evaluation Result 参考结构”落成可检查的结构化记录，主要字段包括 `evaluation_result`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
evaluation_result:
  run_id: run_128
  suite_id: support-agent-regression@12
  evaluator_versions:
    artifact_tests: git:1f23...
    trajectory_grader: traj-grader@4
  dimensions:
    goal_completion: {pass: true, evidence: order://928}
    artifact_quality: {score: 0.92}
    safety: {pass: true}
    budget: {pass: false, actual_cost_usd: 3.10}
  decision: fail
  failed_gates: [budget]
```

该结构是 Playbook 参考设计。原始分项、证据引用和 Evaluator 版本必须保留，否则无法解释为什么一次实验被判定为回退。

## 实施检查表

- 是否先定义验收证据，而不是先选择 Judge。
- 能确定性验证的规则是否由程序验证。
- Outcome、Trajectory、Safety、Cost 是否保留独立结论。
- Judge 是否按任务切片校准，并记录自身版本。
- 是否避免保存或评分模型隐藏推理。
- 安全、权限和副作用失败是否能覆盖质量总分并直接阻断。
