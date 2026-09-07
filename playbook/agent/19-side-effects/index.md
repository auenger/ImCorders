# 副作用、幂等、事务与补偿

作者：杨正武
来源：https://imcoders.cn/playbook/agent/19-side-effects/
更新：2026-08-12T00:00:00.000Z

控制重试、取消和故障恢复对真实外部系统产生的重复或不可逆影响。

---


Checkpoint 可以恢复 Agent 的内部执行，却不能让外部世界倒转。邮件一旦发出、退款一旦受理、代码一旦推送，即使 Worker 随后崩溃，这些效果也可能已经真实存在。

分布式执行最危险的窗口是：

**代码块说明｜流程示意：** 这段文本图按箭头方向阅读，用来说明“副作用、幂等、事务与补偿”中的执行顺序、状态变化或责任流转。它表达逻辑关系，不代表组件必须按图中的数量和位置部署。

```text
Runtime 发出请求 → 外部系统已提交 → 响应在网络中丢失 → Runtime 不知道结果
```

此时盲目重试可能重复创建资源，直接宣布失败又可能掩盖已经发生的动作。副作用治理的目标不是“永不失败”，而是在不确定状态下仍能安全确认、重试或补偿。

## 术语来源与适用范围

Side Effect、Idempotency、Transaction、Rollback、Saga 与 Compensation 都来自编程语言、数据库和分布式系统，不是 Agent 专属概念。HTTP 方法的幂等语义由 [RFC 9110](https://www.rfc-editor.org/rfc/rfc9110.html#name-idempotent-methods) 定义；业务 API 也常提供 Idempotency Key，但键格式、保留期和冲突行为由各 API 自行约定。Saga / Compensation 描述跨多个本地事务处理失败的一类模式，并不等于数据库 ACID Rollback。

Durable Workflow 系统通常也把恢复定位到具体状态或 Task，而不是无条件从头执行。例如 [AWS Step Functions Redrive](https://docs.aws.amazon.com/step-functions/latest/dg/redrive-executions.html) 会保留成功步骤的结果与执行历史，并从未成功步骤继续；其 [Error Handling](https://docs.aws.amazon.com/step-functions/latest/dg/concepts-error-handling.html) 则允许每个 Task 分别声明 Retry 与 Catch。具体行为因 Runtime 而异，但共同说明“流程失败”不等于“所有已完成步骤都要重做或撤销”。

本章提出的 `Side-effect Contract`、`Step Effect Record`、`External Effect Record` 与决策表是本 Playbook 的参考设计，用于把这些既有分布式系统原则接入 Agent Runtime。它们不是 RFC 或通用 Agent Protocol 的标准对象。

## 流程恢复与单次 Tool Retry 是两个层级

一个包含多个关键动作的 Agent 流程，不能只声明“整个 Run 最多重试三次”。每个节点的副作用、完成条件和恢复策略可能完全不同：

**代码块说明｜流程示意：** 这段文本图按箭头方向阅读，用来说明“流程恢复与单次 Tool Retry 是两个层级”中的执行顺序、状态变化或责任流转。它表达逻辑关系，不代表组件必须按图中的数量和位置部署。

```text
生成邮件草稿 → 发送邮件 → 创建 CRM 跟进记录 → 通知负责人
     pure          external write       idempotent write       external write
```

假设邮件已经发送成功，创建 CRM 记录时 Runtime 崩溃。正确恢复通常是：

**代码块说明｜流程示意：** 这段文本图按箭头方向阅读，用来说明“流程恢复与单次 Tool Retry 是两个层级”中的执行顺序、状态变化或责任流转。它表达逻辑关系，不代表组件必须按图中的数量和位置部署。

```text
确认“发送邮件”节点已经完成
           ↓
保留它的 Provider Message ID 与结果
           ↓
跳过邮件节点
           ↓
从“创建 CRM 跟进记录”继续
```

不是重新运行整条流程，也不是因为后续节点失败就撤销已经发送的邮件。流程级恢复首先回答“哪些节点已经形成可信事实”，然后才对第一个未完成或结果未知的节点选择确认、重试、替代或补偿。

![Agent 流程半程失败后的节点级恢复](/playbook-images/agent/workflow-effect-recovery.svg)

## 每个关键操作点都需要恢复契约

不必给纯推理中的每一个微小 Step 建立复杂事务，但所有可能改变外部状态、消耗稀缺资源或影响后续分支的关键操作点，都应该声明：

| 字段 | 回答的问题 |
| --- | --- |
| `completion_semantics` | 什么证据才算该节点完成 |
| `effect_class` | 是否产生外部副作用，是否可逆 |
| `idempotency` | 同一逻辑操作能否安全重复 |
| `confirmation` | 响应丢失后怎样查询真实状态 |
| `retry_policy` | 哪些错误允许重试，预算是多少 |
| `resume_policy` | 恢复时跳过、确认、重试还是人工处理 |
| `compensation` | 哪种业务条件下需要补偿，由谁授权 |
| `checkpoint_policy` | 节点前后保存哪些输入、结果和外部 ID |

参考节点契约：

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“每个关键操作点都需要恢复契约”落成可检查的结构化记录，主要字段包括 `workflow_step`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
workflow_step:
  step_id: send_case_email
  tool: send_email@4
  logical_operation_id: op_case_92_email

  completion_semantics:
    required_state: provider_accepted
    evidence: provider_message_id

  effect:
    class: external_write
    reversible: false
    idempotency: supported

  confirmation:
    tool: get_email_status
    lookup_by: [provider_message_id, idempotency_key]

  recovery:
    when_confirmed: skip_and_continue
    when_not_committed: retry_with_original_key
    when_unknown: reconcile_then_pause

  compensation:
    automatic: false
    strategy: send_correction_if_business_required
```

这些字段和枚举属于 Playbook 参考设计。重点不是统一字段名，而是恢复前能够回答上述问题。

## 节点状态必须表达“未知”与“已确认”

只记录 `success / failed` 不足以恢复外部副作用。本章建议至少区分：

| 节点状态 | 含义 | 恢复动作 |
| --- | --- | --- |
| `not_started` | 尚未发出外部请求 | 可以正常执行 |
| `in_flight` | 请求已发出，尚未得到确定结论 | 先确认外部状态 |
| `confirmed` | 达到节点定义的完成条件且已有证据 | 保留结果并跳过 |
| `not_committed` | 已确认外部系统没有提交 | 可按原 Key 重试 |
| `failed` | 确定失败，且没有产生目标效果 | 按节点 Retry / Catch 策略处理 |
| `unknown` | 无法判断是否提交 | 不盲目重试，进入 Reconcile 或人工处理 |
| `compensated` | 原效果仍存在历史，但已执行补偿动作 | 从补偿后的业务状态继续 |

这组名称不是通用 Workflow 状态标准。特别是 `compensated` 不等于原动作从未发生；审计中必须同时保留原 Effect 与 Compensation Effect。

## 恢复点应该落在关键效果边界

对外部写操作，一个可靠的恢复序列通常是：

**代码块说明｜结构示意：** 这段文本把“恢复点应该落在关键效果边界”中的关键对象并列出来，帮助读者识别各自责任与边界。它用于概念建模，不代表唯一的产品命名或实现结构。

```text
1. 持久化 Tool Call Intent、规范化参数摘要和 Idempotency Key
2. 调用外部系统
3. 持久化 Result、External Effect ID 与确认状态
4. 提交该节点 Checkpoint
5. 调度后继节点
```

如果在第 2 步之后、第 3 步之前崩溃，节点是 `unknown`：外部效果可能已经发生，但本地尚未记录。恢复时通过原 Idempotency Key、Provider Message ID 或业务查询接口确认。无法把外部提交与本地状态写入放在同一个 ACID 事务时，这个不确定窗口不能被完全消除，只能通过稳定操作 ID、可查询接口和 Reconciliation 缩小风险。

Checkpoint 不需要复制外部对象，只需保存可以重新确认它的稳定引用和证据。恢复完成节点时也不应重新让模型猜测“邮件大概发过了”，而应读取 Effect Record 与外部权威状态。

## 邮件场景：发送完成后从后继节点继续

假设客户投诉流程包含四个节点：

**代码块说明｜结构示意：** 这段文本把“邮件场景：发送完成后从后继节点继续”中的关键对象并列出来，帮助读者识别各自责任与边界。它用于概念建模，不代表唯一的产品命名或实现结构。

```text
S1 生成并审核邮件
S2 发送客户邮件
S3 创建 CRM 跟进任务
S4 通知客户负责人
```

S2 调用邮件服务后返回：

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“邮件场景：发送完成后从后继节点继续”落成可检查的结构化记录，主要字段包括 `provider_message_id`、`status`、`accepted_at`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
provider_message_id: msg_73
status: accepted
accepted_at: 2026-08-12T15:20:04+08:00
```

Runtime 将 `msg_73` 写入 Step Effect Record，并把 S2 标记为 `confirmed`。随后 S3 因 CRM 服务超时而中断。恢复时应按以下顺序处理：

1. 读取流程 Checkpoint，发现 S1、S2 已确认，S3 未完成。
2. 必要时调用 `get_email_status(msg_73)`，确认邮件服务仍记录该消息。
3. 保留 S2 的输出，不再次调用 `send_email`。
4. 检查 S3 的请求是否曾提交；未提交则用 S3 自己的 Idempotency Key 重试。
5. S3 成功后继续 S4。

这里还要定义“发送完成”的业务含义：

- `accepted`：邮件服务已接受任务。
- `sent`：邮件服务已尝试交给下游服务器。
- `delivered`：存在送达回执，但也不必然代表用户已阅读。
- `opened`：依赖追踪机制，可能缺失或受隐私设置影响。

如果流程目标只是“提交客户通知”，S2 可以在 `accepted` 时完成；如果合规要求确认送达，则 S2 可能需要等待 `delivered` 或进入人工处理。完成语义必须预先写在节点契约里，不能在故障发生后临时改变。

## 流程失败不自动触发全局补偿

是否补偿应根据业务不变量，而不是只看顶层 Run 状态：

| 场景 | 已完成效果 | 后续失败后的建议 |
| --- | --- | --- |
| 邮件已正确发送，CRM 记录失败 | 客户通知仍然有效 | 保留邮件，从 CRM 节点恢复 |
| 库存已预留，支付最终失败 | 无支付时不应长期占用库存 | 释放库存 |
| 会议已创建，邀请发送失败 | 会议本身仍可能有效 | 重试邀请或人工确认，不必先删会议 |
| 错误内容邮件已发送 | 错误信息已经外部可见 | 不能撤销；按审批发送更正或说明 |
| 生产发布完成，验证失败 | 新版本已真实运行 | 根据发布 Policy 回滚版本或停止流量 |

因此 Compensation Policy 至少需要 `trigger_condition`，例如“业务目标终止且前置资源不应继续占用”，而不能简单配置成 `on_workflow_failure: undo_all`。

## Step Effect Record：让恢复依据事实而不是对话

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“Step Effect Record：让恢复依据事实而不是对话”落成可检查的结构化记录，主要字段包括 `step_effect`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
step_effect:
  workflow_id: customer-case-92
  run_id: run_128
  step_id: send_case_email
  step_revision: 1
  logical_operation_id: op_case_92_email
  idempotency_key_ref: idem_email_92

  status: confirmed
  completion_state: provider_accepted
  external_system: mail-provider
  external_effect_id: msg_73
  request_digest: sha256:mail...
  confirmed_at: 2026-08-12T15:20:04+08:00

  next_step: create_crm_followup
  compensation_status: not_required
```

`Step Effect Record` 是本 Playbook 在既有 Effect Record 基础上增加的流程关联视角，不是 Workflow 行业标准。它把副作用证据绑定到流程节点，使 Runtime 能跳过已确认节点，并定位第一个需要处理的节点。

## 先区分四种动作

| 类型 | 示例 | 失败后处理 |
| --- | --- | --- |
| Pure / Read-only | 计算哈希、读取公开配置 | 通常可直接重试，但注意数据新鲜度和成本 |
| Idempotent Write | 设置标签为固定值 | 同一意图重复执行结果不继续累积 |
| Reversible Write | 修改 Workspace 文件 | 可用明确逆操作恢复，但仍需处理并发 |
| Irreversible / Compensatable | 发邮件、支付、生产发布 | 不能真正回滚，只能补偿、对冲或人工处理 |

“HTTP PUT 是幂等的”不代表具体业务永远安全；如果服务端每次调用都会发送通知或更新时间戳，观察到的副作用仍可能不同。契约必须描述真实实现。

## Side-effect Contract 参考 Schema

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“Side-effect Contract 参考 Schema”落成可检查的结构化记录，主要字段包括 `side_effect_contract`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
side_effect_contract:
  tool: create_refund@3.1
  effect_class: financial_write
  commit_semantics: remote_atomic

  idempotency:
    supported: true
    key_scope: operation
    retention: PT24H
    same_key_different_payload: reject

  confirmation:
    external_effect_id_field: refund_id
    lookup_tool: get_refund_by_idempotency_key

  recovery:
    rollback: unsupported
    compensation_tool: cancel_refund
    compensation_deadline: PT10M

  audit:
    record_request_digest: true
    record_response_digest: true
```

`remote_atomic`、`operation` 等枚举是说明性字段，不是外部标准。它们表达 Runtime 在调用前必须知道的事实：提交点在哪里、怎样确认、能否重试、怎样补偿。

## Idempotency Key 应绑定逻辑动作

同一次逻辑副作用在技术重试中必须复用同一个 Key；用户明确要求再执行一次，则必须使用新 Key：

**代码块说明｜层级示意：** 这段文本图按缩进和树枝符号阅读，用来展开“Idempotency Key 应绑定逻辑动作”中的父子关系与归属边界。它描述的是逻辑结构，不要求数据库或服务按同样层级拆分。

```text
Run run_128
└── Logical Operation op_refund_payment_9
    ├── Attempt 1 → key idem_7 → timeout
    ├── Confirm lookup → unknown
    └── Attempt 2 → key idem_7 → returns original refund rf_902

New user request
└── Logical Operation op_refund_payment_9_again
    └── Attempt 1 → key idem_8
```

因此 Key 通常不应简单绑定整个 Run：一个 Run 可能合法地产生多个不同副作用；也不应绑定 Attempt：每次重试换 Key 会失去去重能力。更稳妥的范围是“Tool Call 所代表的逻辑业务操作”，并包含目标资源和规范化参数摘要。

**代码块说明｜关系式：** 这段表达式把“Idempotency Key 应绑定逻辑动作”压缩成便于比较的组成关系。它是分析模型，不是可执行代码，也不是要求实现者采用的行业标准公式。

```text
idempotency_key = stable_hash(
  tenant + operation_type + target + normalized_payload + logical_operation_id
)
```

该公式是参考构造，不是标准算法。Key 不应泄露敏感参数，也不能只依赖模型自由生成的描述。

## Exactly-once 通常是端到端属性

Runtime 可以做到 Event 去重和 At-least-once 投递，但只有外部系统也支持同一幂等语义，才能避免重复业务效果。不要因为队列“只消费一次”就宣称邮件只会发送一次；Worker 可能在发送后、提交 Checkpoint 前崩溃。

更实际的目标是：

- 每个逻辑动作有稳定 ID。
- 每次请求携带同一幂等键。
- 外部效果返回稳定 `external_effect_id`。
- 响应丢失时先确认，再决定是否重试。
- 所有决定能够审计和恢复。

## External Effect Record

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“External Effect Record”落成可检查的结构化记录，主要字段包括 `external_effect`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
external_effect:
  effect_id: effect_55
  run_id: run_128
  tool_call_id: call_81
  logical_operation_id: op_refund_payment_9
  idempotency_key_ref: idem_7
  request_digest: sha256:51a...

  status: confirmed
  external_system: payments-prod
  external_effect_id: rf_902
  committed_at: 2026-08-12T13:20:04+08:00

  approval_id: apr_39
  compensation_status: not_required
```

这是 Playbook 参考记录。真实系统可放在 Outbox、Workflow State 或审计库中，但不要把它只写进模型可编辑的自然语言 Summary。

## 响应未知时：先确认，再重试

**代码块说明｜层级示意：** 这段文本图按缩进和树枝符号阅读，用来展开“响应未知时：先确认，再重试”中的父子关系与归属边界。它描述的是逻辑结构，不要求数据库或服务按同样层级拆分。

```text
Tool Call timeout
       ↓
副作用是否可能已提交？
  ├─ 否 → 按退避策略重试
  └─ 是
      ↓
用 Idempotency Key / External ID 查询
  ├─ 已提交 → 记录并继续
  ├─ 未提交 → 使用原 Key 重试
  └─ 仍未知 → 暂停、告警或人工确认
```

“timeout”描述的是调用方没有按时收到结果，不等于外部系统没有执行。Tool Result 应使用 `outcome: unknown`，而不是武断返回 `failed`。

## Rollback 与 Compensation

Rollback 回到同一事务提交前的状态；Compensation 是一个新的业务动作，用来抵消或解释先前动作。两者不能混称：

- 数据库事务尚未 Commit，可以 Rollback。
- Workspace 修改已 Commit 到临时分支，可以产生逆向 Commit。
- 邮件已经送达，无法 Rollback；只能发更正邮件。
- 退款已经入账，可能需要新建反向交易，且需要新的授权。

补偿自身也是副作用，也可能失败、重复或需要审批，因此必须拥有新的 Tool Call、幂等键、状态和审计记录。

## Retry、Rollback 与 Compensation 决策表

| 当前事实 | 自动 Retry | Rollback | Compensation |
| --- | --- | --- | --- |
| 请求确定未发出 | 可以 | 不需要 | 不需要 |
| 只读请求超时 | 通常可以 | 不需要 | 不需要 |
| 写请求支持幂等且复用原 Key | 可以，受预算限制 | 视事务而定 | 失败后可能需要 |
| 写请求是否提交未知且可查询 | 先查询，不直接重试 | 视结果而定 | 视结果而定 |
| 写请求不支持幂等且结果未知 | 不应自动重试 | 通常不可用 | 暂停并人工处理 |
| 外部效果已确认且目标改变 | 不能把重试当撤销 | 仅未提交事务可用 | 发起新的补偿动作 |

## Cancel 只阻止未来步骤

当 Run 收到 Cancel：

1. 停止尚未开始的 Tool Call。
2. 尝试取消仍在进行且外部接口支持取消的调用。
3. 不把已经确认的效果标记为“已撤销”。
4. 将 `unknown` 效果加入确认队列。
5. 根据 Policy 决定是否自动补偿、请求审批或交给人工。

Run 最终状态可以是 `cancelled_with_effects` 或 `cancelled_pending_reconciliation`。这些是本 Playbook 建议的表达，不是统一状态枚举；无论命名如何，都必须让调用者知道 Cancel 后外部世界是否仍有残留影响。

## 并发与前置条件

幂等只处理“同一动作重复”，不能防止两个不同动作并发覆盖。更新共享资源时还要使用版本号、ETag、余额校验或 Compare-and-Swap：

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“并发与前置条件”落成可检查的结构化记录，主要字段包括 `update`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
update:
  target: deployment/prod
  expected_revision: 42
  desired_image: app:2.8.0
```

如果 revision 已变，应返回冲突并重新 Observation，而不是让 Agent用旧 Context 强行覆盖。

## 本章检查

- 流程是否按关键操作点声明完成语义、幂等、确认、重试和补偿策略。
- 恢复时是否读取节点级事实，并跳过已有可信证据的 `confirmed` 节点。
- 邮件、支付或发布等节点是否区分 accepted、committed、delivered 等业务状态。
- 顶层 Run 失败是否避免自动推导为“撤销全部已完成节点”。
- Compensation 是否由明确业务不变量触发，而不是由技术异常直接触发。
- Checkpoint 是否保存定位外部效果所需的稳定 ID，而不是复制或猜测外部状态。
- 每个写 Tool 是否声明真实副作用、提交语义和确认方式。
- Idempotency Key 是否绑定逻辑业务操作，并在技术重试中复用。
- 同 Key 不同 Payload 是否被明确拒绝。
- 超时是否可能表示 `unknown`，而非自动等同失败。
- 是否记录 External Effect ID、请求摘要和审批依据。
- Retry 前是否先判断幂等、提交状态和重试预算。
- 是否区分 Rollback 与新的 Compensation 动作。
- Cancel 后是否盘点 confirmed、in-flight 和 unknown 效果。
- 并发写是否使用版本或前置条件保护。
