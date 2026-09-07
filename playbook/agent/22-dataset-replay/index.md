# Dataset、Bad Case、Replay 与 Regression

作者：杨正武
来源：https://imcoders.cn/playbook/agent/22-dataset-replay/
更新：2026-08-12T00:00:00.000Z

把线上轨迹转化为经过脱敏、去重和验证的回归数据，并支持从状态或轨迹重放。

---


Trace 是运行记录，不是天然可靠的数据集。它可能包含重复请求、过期环境、敏感内容、错误标签和被中途人工修正的结果。把线上 Trace 原样塞进训练或回归系统，会把生产噪声固化成新的偏差。

> Dataset 是经过选择、去重、脱敏、标注和版本化的评估资产；Bad Case 是待解释的失败证据，不是自动成立的训练样本。

## 术语来源与适用范围

Training / Validation / Test Split、Golden Dataset、Data Leakage 和 Regression Test 来自机器学习与软件测试；Replay 在事件溯源、工作流引擎和可观测平台中又有不同含义。[Google Production ML Monitoring](https://developers.google.com/machine-learning/crash-course/production-ml-systems/monitoring)强调固定数据切分、版本追踪与线上质量监控，但并未定义 Agent Dataset Schema。

本章把 Replay 分为 Input Replay、Decision Replay、State Replay 和 Effect Simulation，并给出 `Trace-to-Dataset Pipeline`。这些是 Playbook 参考分类，不是某个框架协议。只有在 Runtime 保存了足够版本、Context 来源和外部依赖时，才可能实现接近确定性的重放。

## 四类数据集不要混用

| 数据集 | 来源 | 主要用途 | 关键约束 |
| --- | --- | --- | --- |
| Golden | 人工确认或确定性生成 | 稳定质量门禁 | 规模小、证据强、变更受审 |
| Bad Case | 线上失败与投诉 | 根因分析、回归补洞 | 不能直接当标准答案 |
| Online Sample | 按策略抽样的真实流量 | 分布监控、发现新切片 | 记录采样权重和同意边界 |
| Experiment | 特定假设构造或扩增 | 比较 Prompt / Skill / Model | 不污染最终保留测试集 |

Golden 不是“永远不变”。外部 API、政策和产品需求变化时，旧答案可能失效；更新必须留下原因、Reviewer 和适用版本。

## Trace-to-Dataset Pipeline

![从生产 Trace 到可复现回归数据集](/playbook-images/agent/trace-dataset-pipeline.svg)

**代码块说明｜流程示意：** 这段文本图按箭头方向阅读，用来说明“Trace-to-Dataset Pipeline”中的执行顺序、状态变化或责任流转。它表达逻辑关系，不代表组件必须按图中的数量和位置部署。

```text
Production Trace
    ↓  Candidate Selection
    ↓  Consent / Retention / Redaction
    ↓  Deduplication & Leakage Check
    ↓  Slice & Difficulty Annotation
    ↓  Ground Truth / Acceptance Evidence
    ↓  Reviewer Adjudication
    ↓  Dataset Version + Immutable Case IDs
```

### 1. 选择候选

来源包括失败、用户纠正、安全拦截、超预算、新版本 Canary 和低置信度 Judge 分歧。采样成功 Run 作为对照，否则数据集会严重偏向失败分布。

### 2. 脱敏与最小化

删除与任务无关的个人信息和 Secret；必要字段使用一致的占位映射，保持跨 Step 关系，例如把同一客户稳定替换为 `customer_A`。仅仅把姓名打码但保留邮箱、地址和 Tool Result，仍可能重新识别。

### 3. 去重与泄漏检查

同一用户重试、模板化请求和派生样本可能高度相似。应同时使用业务键、规范化文本哈希与语义近邻去重。测试样本及其近似改写不得进入用于调 Prompt 或训练 Judge 的数据。

### 4. 标注切片与证据

至少记录领域、语言、风险、Tool 依赖、任务长度、是否需要恢复和失败类型。标签应指向可验证证据，而不是只写 `expected_answer`。

## Replay 有四种保真度

| 类型 | 固定什么 | 重新执行什么 | 用途 |
| --- | --- | --- | --- |
| Input Replay | 用户输入与资产版本 | 整个 Run | 端到端回归，受外部漂移影响最大 |
| Decision Replay | Context 与候选动作 | 模型决策 | 比较模型或 Prompt |
| State Replay | Checkpoint、Workspace 引用 | 后续 Step | 恢复与 Replan 测试 |
| Effect Simulation | Tool 契约与录制响应 | 在模拟环境执行副作用 | 安全测试，不触碰真实系统 |

Replay 不等于重新发送所有真实 Tool Call。邮件、退款和生产发布默认必须使用 Stub、Sandbox、Dry Run 或录制响应。对读操作也要标明 `live`、`snapshot` 或 `recorded`，因为当前数据库状态可能已经变化。

## Regression Case 参考结构

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“Regression Case 参考结构”落成可检查的结构化记录，主要字段包括 `case`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
case:
  case_id: refund-timeout-0042
  source: production_bad_case
  source_run_ref: secure://run_128
  redaction_policy: pii-v3
  consent_scope: evaluation_only

  fixture:
    input_ref: artifact://case/input.json
    checkpoint_ref: artifact://case/checkpoint.json
    workspace_snapshot: ws://support-sandbox@18
    agent_version_manifest: avm_42
    tool_mode: simulated

  acceptance:
    required: [refund_confirmed_once, user_notified]
    forbidden: [duplicate_refund, secret_in_output]
  slices: [financial_write, timeout, recovery]
```

这些字段是 Playbook 参考设计。真实系统还应保存 Fixture 和 Evaluator 的内容哈希，使 Case ID 指向不可变版本。

## 防止错误轨迹被重新学习

Bad Case 经过人工修正后，也不能把整条修正轨迹当作唯一最佳路径。只提取：导致失败的条件、必须满足的不变量、正确证据和禁止行为。模型生成的合成 Case 必须与真实 Case 分开标记，并经过独立验证。

建立隔离边界：生产 Trace 进入 Candidate Store；只有通过隐私、质量和证据门禁的 Case 才进入 Regression Suite；只有进一步满足用途授权的数据才可能进入训练集。

## 实施检查表

- Trace 是否经过选择、脱敏、去重、标注和审核后才成为 Dataset。
- Golden、Bad Case、Online Sample 与 Experiment 是否独立版本化。
- 回放是否明确使用 live、snapshot、recorded 还是 simulated Tool。
- 测试集及其近似样本是否与优化数据隔离。
- Case 是否绑定 Agent、Tool、Environment 与 Evaluator 版本。
- 副作用 Replay 是否默认禁止连接生产环境。
