# 从线上轨迹到优化闭环

作者：杨正武
来源：https://imcoders.cn/playbook/agent/25-optimization-loop/
更新：2026-08-12T00:00:00.000Z

把观测、评估、数据集、实验和发布门禁连接成可审计的持续优化流程。

---


可观测性让团队看见失败，但看见不等于改进。没有根因分类，团队最容易反复“调 Prompt”；没有固定数据集和版本清单，离线提升无法归因；没有发布门禁，线上轨迹又会制造新一轮不可解释的 Bad Case。

> 优化闭环不是让 Agent 自动修改自己，而是让每个问题都能变成证据、假设、实验、发布决定和可回滚版本。

## 术语来源与适用范围

Continuous Improvement、Root Cause Analysis、Offline Evaluation、A/B Test、Canary Release 和 Quality Gate 来自质量工程、实验平台、SRE 与 ML 系统。Google 的[生产 ML 部署测试](https://developers.google.com/machine-learning/crash-course/production-ml-systems/deployment-testing)强调版本控制、发布前质量验证与渐进上线，但不定义 Agent 自动优化协议。

本章的 `Agent Optimization Flywheel`、根因到变更位置的决策表和门禁顺序是 Playbook 的参考流程。它适合持续运行、能保留 Trace 与版本资产的 Agent；低流量高风险系统应更依赖模拟、专家审查和阶段性发布，而不是追求快速在线实验。

## Agent Optimization Flywheel

![Agent Optimization Flywheel：证据驱动的持续优化闭环](/playbook-images/agent/agent-optimization-flywheel.svg)

**代码块说明｜层级示意：** 这段文本图按缩进和树枝符号阅读，用来展开“Agent Optimization Flywheel”中的父子关系与归属边界。它描述的是逻辑结构，不要求数据库或服务按同样层级拆分。

```text
Production Trace
    ↓
Bad Case Detection
    ↓
Root Cause Classification
    ↓
Dataset / Regression Case
    ↓
Prompt / Skill / Tool / Model / Runtime Change
    ↓
Offline Experiment
    ↓
Quality Gate
    ↓
Canary Release ─────失败────→ Rollback + New Evidence
    └────成功────→ Production
```

闭环中的每条箭头都要留下关联 ID：Bad Case 指向源 Run，Regression Case 指向脱敏证据，Change 指向假设，Experiment 指向 Manifest 差异，Release 指向门禁结果。

## 先分类根因，再选择改动位置

| 观察到的问题 | 优先检查 | 常见修复位置 | 不应先做什么 |
| --- | --- | --- | --- |
| 关键约束未进入模型 | Context Manifest、裁剪记录 | Context Assembly / Retrieval | 盲目换大模型 |
| 不知道任务方法 | Skill 命中与步骤覆盖 | Skill | 把完整手册塞进 System Prompt |
| 选错相邻能力 | Router 候选与 Tool 描述 | Registry / Router / Tool Schema | 只加“请仔细选择” |
| 参数错误或结果含糊 | Tool Contract 与错误语义 | Tool / Adapter | 让模型解析非结构化错误 |
| 重复副作用 | Idempotency 与 Effect Ledger | Runtime / Tool | 增加模型重试次数 |
| 无进展循环 | State Diff、错误签名、预算 | Loop / Replanner / Stop Policy | 只提高最大 Step 数 |
| 输出表达不符合要求 | Acceptance 与 Artifact Rubric | Prompt / Skill / Template | 改动 Runtime 调度 |
| 多任务切片都能力不足 | 相同输入上的模型比较 | Model | 同时改 Prompt 和模型后归因 |

这张表是诊断起点，不是自动结论。一个 Bad Case 可能有多重原因，例如 Tool Result 含糊导致 Run State 写入错误，再触发无效 Replan。

## 从 Bad Case 到可检验假设

不要写“优化退款 Agent”。应写：

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“从 Bad Case 到可检验假设”落成可检查的结构化记录，主要字段包括 `change_hypothesis`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
change_hypothesis:
  evidence: badcase://refund-timeout-0042
  root_cause: timeout 被映射为失败，而不是 effect_unknown
  change: Tool Adapter 返回结构化 outcome=unknown，并触发确认流程
  expected:
    duplicate_effect_rate: 0
    recovery_success_rate: ">= 0.95"
  guardrails:
    goal_completion_rate: "no regression > 1pp"
    p95_latency: "increase <= 10%"
```

假设必须同时写目标指标和护栏指标，避免为了减少延迟而降低验证质量，或为了提高完成率而绕过审批。

## Offline Experiment 的顺序

1. 在最小相关 Unit / Contract Test 中验证修复。
2. 在 Bad Case 与相邻反例上验证，不只测原始 Case。
3. 运行完整 Regression Suite，按任务、风险和语言切片。
4. 使用固定 Evaluator Version 比较 Baseline 与 Candidate。
5. 对高风险和 Judge 分歧样本进行人工复核。

如果 Candidate 改动了 Evaluator 本身，不能直接与旧分数比较；应先用冻结的校准集验证新 Evaluator，再进行双轨评分。

## Quality Gate 应分硬门禁和优化目标

**代码块说明｜流程示意：** 这段文本图按箭头方向阅读，用来说明“Quality Gate 应分硬门禁和优化目标”中的执行顺序、状态变化或责任流转。它表达逻辑关系，不代表组件必须按图中的数量和位置部署。

```text
Hard Gates
  safety = pass
  permission = pass
  duplicate_effect = 0
  artifact_contract = pass
        ↓
Quality Floors
  completion >= baseline - tolerance
  key slices >= fixed threshold
        ↓
Optimization Objectives
  cost ↓ / latency ↓ / preference score ↑
```

加权总分不能覆盖硬门禁。总体提升也不能覆盖关键切片回退，例如中文任务提升但财务写操作显著退化。

## Canary 不是把生产用户当测试集

上线前仍需完成离线验证。Canary 的作用是验证离线无法完整模拟的真实分布、集成与性能。应限制流量、风险动作和爆炸半径，使用稳定分组，定义自动停止条件，并准备可操作的回滚。

安全事件、重复副作用和跨租户访问应立即停止；成本或延迟回退可以使用短观察窗；需要延迟标签的质量指标则要保留足够观察期。不能在标签尚未回来时仅凭点击率宣布成功。

## 自动优化的边界

可以自动化：发现异常、聚类 Bad Case、生成候选 Regression Case、提出变更草案、运行离线实验和汇总差异。

默认需要人工或独立门禁：修改权限策略、扩大 Tool 作用域、降低安全阈值、把生产数据加入训练集、自动发布高风险能力，以及修改评估器后又由同一评估器证明自己更好。

任何自动生成的 Prompt 或 Skill 变更都必须成为版本化 Artifact，经过相同 Regression 与 Canary 流程。线上反馈不能直接写入活动 System Prompt。

## 实施检查表

- 每个优化是否从可定位的 Bad Case 和根因开始。
- 变更假设是否声明目标指标、护栏和预期适用切片。
- 实验是否绑定 Dataset、Evaluator 与 Agent Version Manifest。
- 硬门禁是否独立于加权质量总分。
- Canary 是否限制爆炸半径并定义停止、回滚与标签等待策略。
- 自动优化是否只能提出和验证候选，不能绕过权限与发布治理。
