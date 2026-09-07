# Event、Artifact、Checkpoint 与 Trace

作者：杨正武
来源：https://imcoders.cn/playbook/agent/07-event-artifact-checkpoint/
更新：2026-08-12T00:00:00.000Z

区分执行事件、正式产物、恢复快照和观测轨迹，明确每类对象的事实边界。

---


Agent Runtime 会产生大量数据：消息、模型输出、工具结果、日志、文件、状态快照和链路追踪。如果统称为“Memory”或“日志”，系统就无法回答两个关键问题：任务恢复时应该相信谁，用户最终又能引用什么。

本章用五类对象建立边界：State、Event、Checkpoint、Artifact 与 Trace。

## 五类对象不是五份重复数据

| 对象 | 核心问题 | 是否可变 | 主要消费者 |
| --- | --- | --- | --- |
| State | 当前有效状态是什么？ | 会更新 | Scheduler、Agent Loop |
| Event | 发生了什么变化？ | 只追加 | Runtime、订阅者、审计 |
| Checkpoint | 从哪里可以准确恢复？ | 创建后不可变 | Resume、Retry |
| Artifact | 执行产生了什么正式结果？ | 版本化 | 用户、下游系统 |
| Trace | 时间花在哪里，因果链怎样展开？ | 观测投影 | 运维、评估、调试 |

![State、Event、Checkpoint、Artifact 与 Trace 的数据流](/playbook-images/agent/runtime-facts.svg)

它们可以引用同一份底层 Blob，但语义不能互换。一次测试输出既可以产生 `step.completed` Event，也可以被 Trace Span 记录耗时；若它是交付证据，还应注册为 Artifact。三者指向同一内容，不代表是同一个对象。

## State 保存当前有效事实

State 是 Runtime 推进任务时读取的当前视图：Run 状态、当前 Attempt、未完成任务、已确认事实、等待条件、预算和最新 Checkpoint。

State 通常需要原子更新，并带版本号：

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“State 保存当前有效事实”落成可检查的结构化记录，主要字段包括 `run_state`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
run_state:
  run_id: run_128
  revision: 37
  status: input_required
  current_attempt_id: attempt_002
  pending_request_id: req_09
  latest_checkpoint_id: cp_019
  remaining_steps: 18
```

更新时使用比较并交换，避免两个 Worker 同时推进：

**代码块说明｜存储约束示例：** 这段 SQL 展示“State 保存当前有效事实”落到持久化层时必须守住的约束。它强调数据一致性意图；表名、字段名和数据库语法需要按实际实现调整。

```sql
UPDATE run_state
SET status = 'running', revision = 38
WHERE run_id = 'run_128' AND revision = 37;
```

若影响行数为零，说明当前状态已经变化，Worker 必须重新读取，不能覆盖新结果。

## Event 记录已经发生的变化

Event 是不可变的执行事实。它不只服务于日志，也驱动前端更新、异步 Tool、审计和外部自动化。

**代码块说明｜Playbook 参考 Schema：** 这段 JSON 把“Event 记录已经发生的变化”落成可检查的结构化记录，主要字段包括 `event_id`、`run_id`、`attempt_id`、`sequence`、`type`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```json
{
  "event_id": "evt_01J5Y7",
  "run_id": "run_128",
  "attempt_id": "attempt_002",
  "sequence": 38,
  "type": "run.input_required",
  "occurred_at": "2026-08-11T15:36:10+08:00",
  "producer": "runtime-scheduler",
  "data": {
    "request_id": "req_09",
    "input_type": "approval",
    "prompt": "允许修改 auth/config.ts 吗？"
  },
  "schema_version": 1
}
```

一个可用的 Event Stream 至少要定义：

- `event_id` 用于去重。
- Run 内单调递增的 `sequence` 用于排序和补收。
- `type` 与 `schema_version` 用于兼容演进。
- `occurred_at` 表示事实发生时间，而不是消费者收到时间。
- `producer` 和关联对象 ID 用于追溯来源。
- `data` 只承载这个事件需要的最小内容，大对象使用引用。

客户端断线重连时，应能提交最后确认的序号：

**代码块说明｜接口示例：** 以 `GET /runs/run_128/events?after_sequence=34` 为例，这段报文说明“Event 记录已经发生的变化”如何通过系统边界表达。它用于解释操作语义；真正实现应采用并锁定所选 Protocol 的版本、认证与错误约定。

```http
GET /runs/run_128/events?after_sequence=34
```

Runtime 可以把 Event 持久化到数据库、日志流或两者结合。是否永久保存取决于合规和成本，但只要 Protocol 承诺断线补收，就必须明确保留期限和截断行为。

## Event 与 State 的一致性

如果先更新 State 再发 Event，进程可能在两者之间崩溃，订阅者永远收不到变化；反过来也可能让订阅者看到尚未成立的状态。

常见解决方式是把 State 更新与 Outbox Event 写入同一事务：

**代码块说明｜流程示意：** 这段文本图按箭头方向阅读，用来说明“Event 与 State 的一致性”中的执行顺序、状态变化或责任流转。它表达逻辑关系，不代表组件必须按图中的数量和位置部署。

```text
事务内：校验 state_revision → 更新 State → 写入 Event Outbox
事务后：Publisher 读取 Outbox → 投递 Event → 标记已投递
```

投递可能重复，所以消费者仍需按 `event_id` 幂等处理。这比追求不现实的“网络中绝不重复”更可靠。

## Checkpoint 是恢复契约

Checkpoint 是某一时刻足以恢复执行的完整快照或可解析快照引用。它不是简单的聊天历史截屏。

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“Checkpoint 是恢复契约”落成可检查的结构化记录，主要字段包括 `checkpoint`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
checkpoint:
  checkpoint_id: cp_019
  run_id: run_128
  attempt_id: attempt_001
  state_revision: 31
  resume_cursor: after_step_018
  state_ref: blob://checkpoints/cp_019.json
  pending_operations: []
  side_effect_ledger_ref: blob://effects/run_128.json
  agent_version: agent_v7
  runtime_schema_version: 3
  created_at: 2026-08-11T15:23:58+08:00
```

可恢复意味着它至少包含：目标与约束、任务进度、已确认事实、等待条件、预算、版本信息和副作用账本。恢复后还要重新观察可能变化的外部环境，不能假设快照中的文件或网页仍然最新。

Checkpoint 适合建立在安全边界上，例如 Tool 调用完成并写回结果之后。若在外部支付请求已发出、结果尚未记录时保存，恢复后直接重发可能产生双重扣款。此时必须依赖幂等键和副作用对账，而不是只靠快照。

## Artifact 是可以被引用的正式结果

Agent 的结果不应该只埋在最终 Response 中。代码补丁、报告、测试记录、图片和数据集都需要独立身份、类型、版本与完整性信息。

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“Artifact 是可以被引用的正式结果”落成可检查的结构化记录，主要字段包括 `artifact`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
artifact:
  artifact_id: artifact_204
  run_id: run_128
  step_id: step_044
  kind: code_patch
  name: login-compatibility.patch
  media_type: text/x-diff
  uri: artifact://run_128/login-compatibility.patch
  size_bytes: 4812
  digest: sha256:9c73...
  version: 2
  created_at: 2026-08-11T15:48:21+08:00
  provenance:
    agent_version: agent_v7
    source_artifacts: []
  validation:
    status: passed
    evidence_artifacts:
      - artifact_205
```

Response 是对结果的解释，Artifact 才是可交付对象。这样下游系统可以下载补丁、校验摘要、关联测试证据，而不必从自然语言中抽取代码。

临时 Tool 输出不必全部注册为 Artifact。判断标准是它是否需要被用户或下游系统稳定引用、版本化、验证或保留。

## Trace 是观测投影，不是恢复事实源

Trace 通常把 Run、模型调用、Tool 调用和数据库操作组织成 Span 因果链。它适合回答：哪一步最慢、失败从哪里传播、Token 花在哪里、多个服务怎样协作。

但 Trace 系统通常允许采样、丢弃、脱敏和异步上报。Span 名称也会随实现重构。因此 Trace 不能自动承担唯一恢复事实源。

**代码块说明｜结构示意：** 这段文本把“Trace 是观测投影，不是恢复事实源”中的关键对象并列出来，帮助读者识别各自责任与边界。它用于概念建模，不代表唯一的产品命名或实现结构。

```text
执行事实：Run State + Event + Checkpoint + 副作用账本
观测投影：Trace / Metrics / Logs
```

两者应该通过 `run_id`、`attempt_id` 和 `step_id` 关联。调试者可以从失败 Run 跳到 Trace，Runtime 恢复时仍然读取受事务和版本控制的执行数据。

## 保留策略必须按对象设计

五类对象的保存时间不应该相同：

- State 保留到业务不再需要查询该 Run。
- Event 根据补收窗口、审计与合规要求保留。
- Checkpoint 在 Run 终止后可以降级归档，但高风险副作用账本应更久。
- Artifact 按交付物策略版本化和清理。
- Trace 可以采样，并使用更短的热存储周期。

删除也要保持引用一致。Artifact 被清理后，元数据可以标记 `expired`；不能让 Event 仍宣称存在一个可下载对象，却返回无解释的 404。

## 本章检查

- 当前 State 是否有版本控制，能否阻止并发覆盖。
- Event 是否不可变、可排序、可去重，并明确断线补收窗口。
- State 更新与 Event 发布是否避免双写不一致。
- Checkpoint 是否包含恢复所需状态、版本和副作用账本。
- Artifact 是否拥有稳定引用、摘要、来源和验证状态。
- Trace 是否只作为观测投影，而不是唯一恢复依据。
- 大对象是否通过引用保存，并按对象类型设计保留策略。
