# Trace、Span 与 Event：看见完整执行轨迹

作者：杨正武
来源：https://imcoders.cn/playbook/agent/20-trace-span-event/
更新：2026-08-12T00:00:00.000Z

以 Run 为核心关联模型、Tool、子 Agent、审批、成本和外部副作用的完整因果链。

---


一次模型调用返回成功，只能说明模型 API 正常响应。它不能说明 Agent 为什么选择这个 Tool、审批等待了多久、重试是否重复产生副作用，也不能说明最终目标是否完成。Agent Observability 必须从一次 LLM Call 扩展到完整 Run。

> Trace 解释一次执行的因果路径，Event 保存发生过的事实，Metric 聚合系统趋势；三者互相引用，但不能互相替代。

## 术语来源与适用范围

Trace、Span、Event、Log 和 Metric 来自分布式系统可观测性。[OpenTelemetry Trace 规范](https://opentelemetry.io/docs/specs/otel/trace/)把 Trace 表示为由 Span 构成的因果图；[W3C Trace Context](https://www.w3.org/TR/trace-context/)定义了跨服务传播 `traceparent` 与 `tracestate` 的标准方式。OpenTelemetry 也提供 GenAI 语义约定，但相关字段仍可能处于 Development 状态，实施时必须锁定所采用的语义约定版本。

2026 年 OpenTelemetry 已宣布逐步弃用旧的 Span Events API，新代码倾向把 Event 作为与当前 Span 关联的 Log-based Event 记录。因此本章使用的 `Event` 是领域事实的上位概念，不等同于某个 SDK 的 `span.addEvent()` 方法。

本章的 `Agent Trace`、Run / Attempt / Step 关联字段与 Event 分类是 Playbook 参考模型，不是 OpenTelemetry 或 W3C 新增的标准对象。实际系统可以用 OpenTelemetry 承载底层相关性，再通过业务属性表达 Agent 语义。

## LLM Trace 只是 Agent Trace 的一部分

![Agent Trace、Span 与 Event 的最小语义模型](/playbook-images/agent/agent-observability-model.svg)

**代码块说明｜层级示意：** 这段文本图按缩进和树枝符号阅读，用来展开“LLM Trace 只是 Agent Trace 的一部分”中的父子关系与归属边界。它描述的是逻辑结构，不要求数据库或服务按同样层级拆分。

```text
Run run_128
├── Attempt 1
│   ├── Step 1: assemble_context
│   ├── Step 2: model_decision
│   └── Step 3: execute_tool → timeout → effect_unknown
└── Attempt 2
    ├── Step 4: confirm_external_effect
    └── Step 5: verify_goal → completed
```

这里的对象回答不同问题：

| 对象 | 回答的问题 | 生命周期 |
| --- | --- | --- |
| Run | 用户目标的这次执行是什么 | 从接受目标到终态 |
| Attempt | 哪次执行尝试正在承载 Run | Worker 重启或策略重试可新建 |
| Step | Agent 语义上推进了哪一步 | 计划、决策、动作或验证 |
| Span | 哪段操作耗时并调用了什么下游 | 一段有开始和结束的操作 |
| Event | 某个时刻发生了什么事实 | 不可变记录 |

Step 不必等于 Span。一个 `deploy_application` Step 可能包含模型决策、审批等待、构建和部署多个 Span；一个批处理 Span 也可能执行多个细粒度内部动作。把两者强制一一对应，会让业务语义迁就观测实现。

## Trace 与 Event Stream 的边界

Trace 适合回答“这次请求经过了什么因果路径、时间花在哪里”；Event Stream 适合回答“系统按顺序发生了哪些领域事实，并据此重建状态”。

**代码块说明｜层级示意：** 这段文本图按缩进和树枝符号阅读，用来展开“Trace 与 Event Stream 的边界”中的父子关系与归属边界。它描述的是逻辑结构，不要求数据库或服务按同样层级拆分。

```text
Trace:       span A ─────┬─ span B ──┐
                         └─ span C ───┴─ duration / causality

Event Stream: e1 → e2 → e3 → e4 → e5
              accepted  tool_requested  approved  effect_committed  completed
```

Trace 可以采样、聚合或按保留期删除；承担恢复和审计职责的 Event 不应因为 Trace 采样而消失。反过来，Event Store 也不适合替代高基数延迟分析和跨服务调用图。

## Agent Trace 最小关联字段

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“Agent Trace 最小关联字段”落成可检查的结构化记录，主要字段包括 `agent_observation`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
agent_observation:
  trace_id: 4bf92f3577b34da6a3ce929d0e0e4736
  span_id: 00f067aa0ba902b7
  parent_span_id: 7a8f...

  run_id: run_128
  root_run_id: run_128
  attempt_id: attempt_2
  step_id: step_5
  tool_call_id: null

  agent_version_manifest_id: avm_42
  context_manifest_id: ctxm_91
  checkpoint_id: cp_8
  workspace_version: git:8c19...

  operation: verify_goal
  outcome: success
  started_at: 2026-08-12T09:32:10Z
  duration_ms: 841
```

这是 Playbook 的关联示例。`trace_id` 与 `span_id` 应遵循底层 Trace 实现；其他字段可以作为 Attribute、Resource、Link 或业务索引保存。异步队列和子 Run 不应伪造父子 Span，可使用 Span Link 或显式 `parent_run_id` 表达因果关系。

## 成本、延迟和副作用怎样归因

成本应先记录在最接近发生点的位置，再向上聚合：模型 Span 记录 Token 与供应商费用；Tool Span 记录 API 费用；Step 聚合本步骤；Run 汇总整个目标。

延迟至少拆成：

- **Active Compute**：模型、Tool 和确定性计算实际运行时间。
- **Queue Time**：等待 Worker 或并发配额。
- **Approval Time**：等待人工决定。
- **External Wait**：等待异步任务或第三方系统。
- **Recovery Time**：故障发生到恢复继续。

外部副作用必须通过 `logical_operation_id`、`idempotency_key_digest` 和 `external_effect_id` 关联到 Tool Call。不要把完整 Idempotency Key 或支付凭证写入普通 Trace。

## Trace 默认不记录完整 Context

Prompt、Tool 参数、Tool Result 和模型输出可能包含用户数据、Secret、源代码与业务机密。可观测平台通常比生产数据库拥有更广的查询面，因此“方便调试”不是复制全部正文的理由。

推荐分三层记录：

| 层级 | 默认内容 | 访问方式 |
| --- | --- | --- |
| Metadata | ID、版本、Token、时延、状态、摘要哈希 | 常规 Trace 查询 |
| Redacted Preview | 脱敏后的短摘要与错误分类 | 受控调试权限 |
| Secure Payload | 必要时加密保存的原始输入输出 | 单独存储、短保留期、审计访问 |

禁止进入 Trace 的内容至少包括原始 Secret、访问 Token、完整 Cookie、私钥、未脱敏身份证件和模型隐藏推理。需要复现输入时，优先记录受版本控制的来源引用与 Context Assembly Manifest，而不是复制所有正文。

## 采样不能只按成功率

低成本成功 Run 可以概率采样；以下 Run 应优先保留完整 Trace：失败、超预算、触发审批、发生副作用、不确定结果、安全拦截、用户投诉和新版本 Canary。采样决策还应保留原因，避免数据集误以为线上只有失败案例。

## 实施检查表

- Run、Attempt、Step、Span 和 Event 是否有明确边界。
- 异步调用和子 Run 是否保留可查询的因果链接。
- Trace 采样是否不会破坏恢复、审计和副作用账本。
- 成本与等待时间是否能归因到具体 Step、Skill、Tool 和版本。
- 敏感正文是否默认不进入 Trace，访问是否有单独审计。
- 语义约定版本是否固定，Development 字段升级是否经过迁移验证。
