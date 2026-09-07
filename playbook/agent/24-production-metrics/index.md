# 质量、成本、安全与效率指标

作者：杨正武
来源：https://imcoders.cn/playbook/agent/24-production-metrics/
更新：2026-08-12T00:00:00.000Z

用分层指标识别任务失败、Token 浪费、延迟热点、无进展循环和危险行为。

---


模型调用成功率 99.9%，不代表 Agent 可靠。一个 Run 可以每次 API 都成功，却没有完成目标；也可以最终完成，却花费不可接受、绕过审批或在恢复时重复产生副作用。Agent 生产指标必须从基础设施一直连到目标结果。

> Metric 用于发现趋势和触发调查，Trace 用于解释单次因果，Evaluation 用于判断具体质量；Dashboard 不能替代其中任何一个。

## 术语来源与适用范围

Latency、Error Rate、SLO、Error Budget、RED / USE 等来自 SRE 与可观测性实践；Token、Tool Call 和 Goal Completion 是生成式 AI 与 Agent 系统增加的维度。[Google SRE Workbook](https://sre.google/workbook/implementing-slos/)提供 SLI / SLO 的设计原则，[OpenTelemetry Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/)提供跨信号命名规范，但不会替团队定义业务质量。

本章的 `Production Metrics Catalog`、Progress Fingerprint 和 Dashboard 草图是 Playbook 参考设计。指标名称应映射到团队现有 Metric 规范，避免与 OpenTelemetry 的 Stable / Development 字段混淆。

## 五层生产指标

![Agent 生产 Dashboard：从目标质量到运行健康](/playbook-images/agent/agent-production-dashboard.svg)

| 层级 | 核心指标 | 主要回答 |
| --- | --- | --- |
| Outcome | Goal Completion、Artifact Pass、用户修正率 | 是否做成 |
| Trajectory | 无进展率、重复调用、Replan、恢复成功率 | 路径是否收敛 |
| Action & Safety | Tool 错误、审批、越权、未知副作用 | 行动是否安全 |
| Cost & Latency | Token、费用、端到端时延、等待占比 | 资源是否合理 |
| Runtime Health | Queue、Worker、Checkpoint、Trace 缺失 | 系统是否健康 |

一个 Dashboard 应允许从总览下钻到任务类型、Agent Version、Skill、Tool、租户、风险等级和错误类别，但不要把 `user_id`、`run_id` 等高基数标识直接做成 Metric Label；这些留给 Trace 或 Log 查询。

## Outcome 指标必须依赖完成证据

**代码块说明｜关系式：** 这段表达式把“Outcome 指标必须依赖完成证据”压缩成便于比较的组成关系。它是分析模型，不是可执行代码，也不是要求实现者采用的行业标准公式。

```text
goal_completion_rate
= 有验收证据的 completed Run / 所有进入终态且可评估的 Run
```

`completion_requested`、模型说“已完成”或 HTTP 200 都不能充当分子。还要单独记录 `not_evaluable`，避免把缺失证据偷偷算成成功或从分母排除。

建议按任务类型报告：一次信息查询、一次代码变更和一次退款的完成定义不同，混合成总体平均值没有可操作性。

## 识别“循环但没有进展”

只统计 Step 数不能判断循环。Agent 可能连续读取不同文件取得进展，也可能反复调用同一个 Tool 却没有改变状态。本 Playbook 建议生成 `Progress Fingerprint`：

**代码块说明｜关系式：** 这段表达式把“识别“循环但没有进展””压缩成便于比较的组成关系。它是分析模型，不是可执行代码，也不是要求实现者采用的行业标准公式。

```text
fingerprint = hash(
  normalized_active_tasks,
  confirmed_fact_versions,
  workspace_version,
  external_effect_ledger,
  unresolved_blockers
)
```

在连续多个决策 Step 中 Fingerprint 不变，同时动作模式重复，可记为 `no_progress_window`。这是参考检测方法，不是行业标准；实际阈值必须按任务长度校准。

可配合观察：相同 Tool + 参数摘要重复次数、相同错误签名、Context 摘要变化率、Replan 后路径是否变化，以及预算消耗速度。

## 成本归因到逻辑层，不只看账单

**代码块说明｜层级示意：** 这段文本图按缩进和树枝符号阅读，用来展开“成本归因到逻辑层，不只看账单”中的父子关系与归属边界。它描述的是逻辑结构，不要求数据库或服务按同样层级拆分。

```text
Run Cost
├── Model: input / cached / output / reasoning tokens
├── Retrieval: embedding / index / rerank
├── Tool: API fee / compute / egress
├── Workspace: sandbox compute / storage
└── Human: approval and review time
```

成本应同时保留货币值与原始用量；供应商价格变化后，历史 Token 不应被误解为同一费用。按 `run_id → step_id → skill_id / tool_id → agent_version` 聚合，才能定位是模型选择、Context 过载还是 Tool 重试造成浪费。

## 延迟看关键路径和等待结构

端到端 P95 很重要，但还要拆分 Model、Tool、Queue、Approval、External Wait 和 Recovery。并行执行时，各 Span 时长不能简单相加为用户等待时间；端到端延迟由关键路径决定。

交互式 Agent 可以设置首个有用反馈时间与最终完成时间两个 SLO。长任务还应监控无心跳时间、Checkpoint 间隔和等待状态是否向用户可见。

## 安全指标不能只做平均值

至少监控：Policy Deny、需要审批的动作占比、审批绕过尝试、敏感数据拦截、跨租户访问、未知副作用、补偿执行和高风险动作人工确认率。

安全事件通常低频但高损，不能因为“每万次只有一次”就接受。用绝对事件数、严重度、受影响范围和检测时间报告，并设置零容忍硬门禁。

## 预算与告警

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“预算与告警”落成可检查的结构化记录，主要字段包括 `run_budgets`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
run_budgets:
  max_cost_usd: 3.00
  max_wall_time: PT20M
  max_model_calls: 18
  max_no_progress_steps: 3
  max_high_risk_actions: 1
```

预算耗尽前应分级处理：70% 提醒并压缩低价值 Context；90% 要求 Replan；100% 停止、等待人工或按策略降级。降级不能绕过安全和验收要求。

告警应面向可采取的动作。例如“退款 Tool 未知副作用率超过阈值”比“Agent 错误率升高”更容易定位。每个告警应链接到受影响版本、代表 Trace、Runbook 和回滚入口。

## 实施检查表

- Goal Completion 是否依赖外部证据而不是模型自述。
- 指标是否能按任务、版本、Skill、Tool 和风险切片。
- Metric Label 是否避免用户和 Run 级高基数数据。
- 是否能识别状态不变的重复动作与无进展窗口。
- 成本是否包含模型之外的 Tool、Sandbox 和人工成本。
- 安全指标是否使用严重度与硬门禁，而不是被平均值稀释。
