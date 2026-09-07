# Delegation Contract、Task Tree 与消息协议

作者：杨正武
来源：https://imcoders.cn/playbook/agent/28-delegation-contract/
更新：2026-08-12T00:00:00.000Z

让每次委派携带目标、最小上下文、约束、权限、验收标准和可追踪的父子 Run 关系。

---


委派不是把父 Agent 的一句想法转发出去。子 Agent 如果不知道交付物、约束、可用证据和验收标准，只能重新猜测父任务；父 Agent 如果没有记录 Child Run 和委派版本，也无法可靠地等待、取消、重试或判断结果是否仍然有效。

> Delegation Contract 是 Parent 与 Child 之间的工作契约。消息可以承载契约，但一段聊天记录不能替代契约。

## 术语来源与适用范围

Delegation、Handoff、Task 和 Message 在不同框架中含义不同。[A2A Protocol 规范](https://github.com/a2aproject/A2A/blob/main/docs/specification.md)定义了跨 Agent 系统的 Task、Message、Artifact、Part 与 `contextId`，其中 Task 是具有生命周期的有状态工作单元。[OpenAI Agents SDK Handoffs](https://openai.github.io/openai-agents-python/handoffs/)把 Handoff 暴露为模型可选择的 Tool，并允许过滤接收方看到的输入历史。

A2A 面向独立 Agent 系统之间的互操作，不负责规定一个应用内部的 Parent / Child Run 树；OpenAI Handoff 默认可以发生在同一 Run 内，也不等于本章所说的独立 Child Run。本章的 `Delegation Contract`、`root_run_id`、`parent_run_id` 与传播规则是 Playbook 参考设计，不是 A2A 或某个 SDK 的标准字段。

实施跨系统通信时，应直接采用并锁定对应协议版本，再把本章的内部字段映射到协议的 Task、Message、Artifact 与 metadata，不能声称自定义 Schema 就是 A2A。

## 三种协作语义不要混用

| 语义 | 控制权 | 生命周期 | 适用场景 |
| --- | --- | --- | --- |
| 一次性 Subagent 调用 | Parent 保留 | Child 完成一次有界任务后返回 | 分类、翻译、局部分析 |
| Handoff | 从当前 Owner 转给接收方 | 可以留在同一 Run，也可以映射为新 Run | 对话路由、领域接力 |
| 持续消息协作 | 各方保留独立 Run | 多轮、异步、可等待与恢复 | 长任务、跨系统协作 |

一次性调用需要稳定的输入输出 Schema；Handoff 必须更新 Owner；持续协作则需要 Message ID、顺序、去重、关联关系和终止协议。不要只用一个 `send_message(agent, text)` 覆盖三种语义。

## Delegation Contract 最小结构

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“Delegation Contract 最小结构”落成可检查的结构化记录，主要字段包括 `delegation_id`、`contract_version`、`root_run_id`、`parent_run_id`、`child_run_id`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
delegation_id: del_204
contract_version: 3
root_run_id: run_root_88
parent_run_id: run_root_88
child_run_id: run_child_91

goal: 验证数据库迁移是否向后兼容
scope:
  include:
    - db/migrations/20260812_add_status.sql
    - tests/migrations/status_test.py
  exclude:
    - 生产环境执行

context_refs:
  - artifact://requirements/api-status-v4
  - git://repo/pull/128#diff
confirmed_facts:
  - 旧版本应用仍可能运行 30 分钟
assumptions:
  - 当前数据库为 PostgreSQL 16

constraints:
  deadline: 2026-08-12T10:30:00Z
  token_budget: 18000
  allowed_tools: [read_file, run_test, query_schema]
  side_effect_policy: read_only

acceptance:
  output_schema: migration_review_v2
  required_evidence:
    - forward_test_result
    - rollback_test_result
  completion_rule: 所有 required_evidence 均存在且无 destructive_change

return_policy:
  mode: artifact_and_summary
  on_blocked: message_parent
  on_failure: preserve_checkpoint
```

Contract 应把事实与假设分开。Parent 的推测如果作为 confirmed fact 下发，会在整个 Task Tree 中被放大。Context 也应优先传引用和摘要，Child 按权限读取原始 Artifact，而不是复制父 Agent 的全部 Conversation。

## Parent / Child Run 生命周期

![Delegation Contract 与 Parent / Child Run 生命周期](/playbook-images/agent/delegation-task-tree.svg)

**代码块说明｜层级示意：** 这段文本图按缩进和树枝符号阅读，用来展开“Parent / Child Run 生命周期”中的父子关系与归属边界。它描述的是逻辑结构，不要求数据库或服务按同样层级拆分。

```text
Parent RUNNING
  ↓ create contract
Child CREATED → READY → RUNNING
                  ├── COMPLETED → Parent validates artifact
                  ├── BLOCKED   → Parent supplies input or replans
                  ├── FAILED    → Retry policy creates new Attempt
                  └── CANCELED  → Parent records partial effects
```

Parent 不应该因为创建 Child 就自动进入 WAITING。它可能继续创建其他并行 Child，或处理本地任务。只有当前可执行工作全部依赖 Child 结果时，Parent 才进入等待状态。

Child 返回 COMPLETED 也不意味着 Parent 接受结果。Parent 需要验证 Artifact 是否满足当前 Contract，检查 Contract 是否已经被新版本取代，再把结果写入 Root State。

## Task Tree 不是 Conversation Tree

Task Tree 表达工作依赖与责任：

**代码块说明｜层级示意：** 这段文本图按缩进和树枝符号阅读，用来展开“Task Tree 不是 Conversation Tree”中的父子关系与归属边界。它描述的是逻辑结构，不要求数据库或服务按同样层级拆分。

```text
root_run_id = run_100

run_100  Root: 审查发布
├── run_101  API 兼容性
│   └── run_104  OpenAPI 差异检查
├── run_102  数据迁移
└── run_103  UI 回归
```

每个节点拥有自己的 Run State、Attempt、预算与 Trace。Conversation 可以与多个 Run 相关，一个 Run 也可以消费多个 Message。不要用“消息回复关系”推断任务依赖。

建议保留：

- `root_run_id`：整棵树的关联与总预算归因。
- `parent_run_id`：直接委派关系。
- `delegation_id`：这一次工作契约。
- `contract_version`：防止旧结果覆盖新要求。
- `attempt_id`：区分同一 Child Run 的执行重试。

## 消息信封必须支持去重和关联

**代码块说明｜Playbook 参考 Schema：** 这段 JSON 把“消息信封必须支持去重和关联”落成可检查的结构化记录，主要字段包括 `message_id`、`sender_run_id`、`recipient_run_id`、`delegation_id`、`in_reply_to`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```json
{
  "message_id": "msg_782",
  "sender_run_id": "run_102",
  "recipient_run_id": "run_100",
  "delegation_id": "del_204",
  "in_reply_to": "msg_771",
  "type": "artifact_ready",
  "sequence": 8,
  "created_at": "2026-08-12T10:14:03Z",
  "payload": {
    "artifact_ref": "artifact://migration-review/44",
    "contract_version": 3
  }
}
```

`message_id` 用于幂等去重，`in_reply_to` 用于因果关联，`sequence` 只在明确的发送方或 Channel 范围内有意义。分布式系统中不要假设所有 Agent 共享一个完美全局顺序。

消息类型至少区分：

- `progress`：非终态进展，不触发完成。
- `artifact_ready`：产物可验证。
- `input_required`：Child 需要额外事实或选择。
- `blocked`：当前条件无法继续。
- `cancel_requested` / `cancel_acknowledged`：取消请求与确认。
- `contract_revised`：Parent 发布新版本契约。

## Interrupt、Cancel 与权限怎样传播

传播策略不能只写“递归取消所有 Child”。

| Parent 事件 | Child 默认处理 | 必须保留的事实 |
| --- | --- | --- |
| Interrupt | 到安全点保存 Checkpoint，转为暂停 | 当前 Step、局部 Artifact、外部 Effect |
| Cancel | 请求停止未开始和可中断工作 | Cancel 是否确认、已发生副作用 |
| Deadline exceeded | 停止新动作，允许提交部分结果 | 已完成范围、缺口与证据 |
| Permission revoked | 立即禁止后续受限 Tool | 已授权动作与撤销时刻 |
| Contract revised | 比较版本，继续、重启或拒绝旧任务 | 使用的 Contract Version |

取消是协作协议，不是时间倒流。Child 已发送邮件或创建资源时，Parent 取消不能自动撤销这些副作用；仍需沿用副作用章节的确认与补偿机制。

权限也不应由 Parent 直接复制给 Child。Child 的有效权限应由自身身份、委派范围、Tool Policy 和环境策略取交集，并在每次动作执行时重新检查。

## 防止委派失控

- 设置最大深度、最大 Child 数和总预算。
- Child 再委派时必须继承 Root 约束，不能扩大 Scope 或权限。
- Contract 缺少验收条件时拒绝启动，而不是让 Child 自行补全高风险要求。
- Parent 对超时 Child 使用状态查询和取消协议，不盲目重复创建相同任务。
- 所有结果携带 Contract Version，过期结果只进入候选区，不能直接覆盖正式 Artifact。

## 本章检查

- 是否明确区分一次性调用、Handoff 与持续消息协作。
- Delegation Contract 是否包含 Goal、Scope、Context、约束、权限和 Acceptance。
- 事实、假设与引用是否分开传递。
- Root、Parent、Child、Delegation、Contract Version 和 Attempt 是否可关联。
- Message 是否支持去重、回复关联和局部顺序。
- Interrupt、Cancel、权限撤销与 Contract 更新是否有传播规则。
- Child 完成后是否仍由 Parent 验收，而不是自动视为 Root Goal 完成。
