# Run State：Agent 现在做到哪里

作者：杨正武
来源：https://imcoders.cn/playbook/agent/11-run-state/
更新：2026-08-12T00:00:00.000Z

建立可以持久化、版本化和恢复的执行状态，而不是依赖不断膨胀的对话历史。

---


当一个 Agent 运行几十个 Step 后，最常见的实现方式是继续把消息追加到 Conversation：用户说过什么、模型想过什么、调用过什么 Tool、Tool 返回了什么，全都留在同一条时间线上。

Conversation 很适合回答“发生过什么”，却不适合回答“现在做到哪里”。后者需要 Run State：一份紧凑、结构化、可版本化的当前执行状态。

如果没有 Run State，Agent 每一轮都要从历史中重新推导目标、进度和未决问题。推导结果会随 Context 裁剪变化，中断后也很难准确恢复。真正的任务连续性，不来自模型“记得”，而来自 Runtime 能够持久化当前有效事实。

## 术语来源与适用范围

执行系统维护“当前状态”并不是 Agent 领域新发明的概念。状态机、工作流引擎和 Durable Execution 系统都会保存或重建一次执行的当前状态。例如，[LangGraph](https://langchain-ai.github.io/langgraph/how-tos/state-reducers/) 使用带 Schema 和 Reducer 的 `State`，[Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/workflows/state) 使用 Workflow State，[Temporal](https://github.com/temporalio/temporal/blob/main/docs/architecture/history-service.md) 则可以从 Event History 重建 Workflow Execution 的 Mutable State。

本章沿用本部分对 `Run` 的定义：Run 是由明确目标触发、拥有独立 ID、生命周期和执行状态的一次 Agent 执行实例。它是本 Playbook 的统一设计术语，不是要求外部系统实现的标准资源；在其他体系中可能对应 Task、Workflow Execution、Invocation 或 Job。

`Run State` 是本 Playbook 为 Agent Engineering 统一使用的设计术语，指**作用域限定在一次 Agent Run 内、用于描述当前执行语义的结构化状态**。它不是现有框架或互操作协议共同定义的标准对象。本章给出的 Goal、Confirmed Facts、Hypotheses、Tasks、Waiting、Budget 等字段也是参考 Schema，不要求实现者使用相同字段名或存储结构。

它也不等于 [A2A 协议](https://a2a-protocol.org/latest/specification/)中的 `TaskState`。后者主要表达 `working`、`completed`、`input-required` 等对外生命周期状态；本章的 Run State 还包括 Agent 为继续执行而维护的内部事实、假设、任务和引用。

在具体系统中，Run State 可以映射为 Graph State、Workflow State、数据库中的执行文档，或由 Event History 计算得到的当前投影。使用这个名称的目的，是建立本书内部稳定的概念边界，而不是再造一项外部协议。

## Conversation 与 Run State 的责任不同

**代码块说明｜结构示意：** 这段文本把“Conversation 与 Run State 的责任不同”中的关键对象并列出来，帮助读者识别各自责任与边界。它用于概念建模，不代表唯一的产品命名或实现结构。

```text
Conversation：按时间记录谁说了什么、返回了什么
Run State：按语义保存当前目标、事实、任务和等待条件
```

同一条 Conversation 可能包含已经被纠正的需求、失败尝试和过期观察。Run State 则只保留当前版本，并引用重要证据。

例如用户先说“把登录超时改成 30 分钟”，随后改成 15 分钟。Conversation 应保留两次输入；Run State 只能把当前约束表示为 15 分钟，并记录它由后一条指令覆盖。

两者并不互相替代：Conversation 用于审计和还原交互，Run State 用于继续执行。

## Agent 的状态分布在多个层级

![Agent 状态分层：哪些进入模型，哪些留在环境](/playbook-images/agent/state-layers-memory.svg)

| 层级 | 保存内容 | 是否直接进入 Context | 恢复责任 |
| --- | --- | --- | --- |
| Conversation | 用户、模型、Tool 消息 | 只选相关部分 | 保留交互记录 |
| Run State | 目标、事实、任务、等待和预算 | 以紧凑投影进入 | 恢复任务语义 |
| Checkpoint | 某一安全点的完整运行快照 | 不直接进入 | 恢复执行位置 |
| Workspace | 文件、代码、浏览器和中间结果 | 按需读取 | 恢复工作现场 |
| External State | 数据库、订单、第三方系统 | 通过 Tool 观察 | 由外部系统保持真实 |
| Long-term Memory | 跨 Run 可复用信息 | 检索后进入 | 保持跨任务连续 |

这些层级之间通常通过 ID、版本和 Artifact 引用关联，而不是互相复制完整内容。下面是两个彼此独立的场景，用来说明这种关系。

**订单处理 Agent：Run State 保存观察，不取代业务系统。** Agent 通过 Tool 在订单系统中创建订单后，可以在 Run State 中记录：

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“Agent 的状态分布在多个层级”落成可检查的结构化记录，主要字段包括 `external_observation`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
external_observation:
  subject: order://order_9
  observed_status: created
  observed_at: 2026-08-11T16:24:00+08:00
  evidence: artifact://tool-result/create-order-9
```

这条记录表达的是“Agent 在这个时间观察到订单已经创建”。订单后续可能被支付、取消或由其他系统修改，因此订单系统仍然是它的权威事实源。Agent 恢复执行时，如果下一步依赖订单当前状态，就应该通过 Tool 重新查询，而不能只相信 Run State 中的旧观察。

**Coding Agent：Checkpoint 保存工作现场的定位信息，不复制整个仓库。** 代码仓库实际存在于 Workspace 中。Checkpoint 可以记录 `workspace_id`、基础 commit、当前 commit 或目录内容 hash：

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“Agent 的状态分布在多个层级”落成可检查的结构化记录，主要字段包括 `workspace_ref`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
workspace_ref:
  workspace_id: ws_71
  base_commit: 81a23f0
  current_commit: 3bc92e1
  uncommitted_changes: artifact://patch/run_128-step_18
```

恢复时，Runtime 根据这些引用找到 Workspace，并验证代码版本是否一致。Checkpoint 不需要把整个仓库编码进自己的 JSON；如果 Workspace 已丢失，则根据基础版本和补丁 Artifact 重建，或者明确报告无法恢复。

两个场景说明的是同一条原则：Run State 和 Checkpoint 保存继续执行所需的语义、引用与版本，真实业务对象和大体积工作内容仍由各自的权威系统保存。

## Run State 的参考结构

Run State 应该围绕“下一轮怎样安全继续”设计，而不是围绕“把所有信息存下来”设计。下面给出的是本 Playbook 的参考结构，用于展示必要语义，而不是标准 Schema：

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“Run State 的参考结构”落成可检查的结构化记录，主要字段包括 `run_state`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
run_state:
  schema_version: 3
  run_id: run_128
  revision: 18

  goal:
    statement: 修复依赖升级后的登录失败
    scope:
      include: [src/auth, tests/login]
      exclude: [public_api]
    acceptance:
      - test_login_refresh 通过
      - 公开 API 无变化

  phase: diagnose
  status: running
  active_task_id: task_3

  confirmed_facts:
    - id: fact_12
      statement: session token 实际使用 RS256
      evidence: artifact://test-output/47
      observed_at: 2026-08-11T16:22:10+08:00

  hypotheses:
    - id: hyp_4
      statement: 配置覆盖顺序在依赖升级后发生变化
      confidence: 0.66
      falsifier: 运行配置解析单测

  open_questions:
    - 测试 fixture 是否仍显式固定 HS256？

  tasks:
    - id: task_3
      title: 确认算法配置来源
      status: running
      depends_on: []

  last_transition:
    action: run_test
    result_ref: artifact://test-output/47

  waiting: null
  budgets:
    tokens_remaining: 84000
    deadline: 2026-08-11T18:00:00+08:00

  workspace_ref: workspace://ws_71@commit:3bc92e
  effect_ledger_ref: effects://run_128@rev4
```

不是每个 Agent 都需要全部字段，但以下语义通常不能缺失：目标与验收、当前状态、已确认事实、未决事项、活动任务、最近一次有效转换、预算和外部引用。

## 事实、假设与计划必须分开

Agent 容易把自己的解释写成事实。为了阻止这种漂移，State 至少应区分三类内容：

- **Confirmed Fact**：有可引用证据支持，或者由权威输入明确给出。
- **Hypothesis**：当前解释，带置信度和证伪方式。
- **Plan / Task**：准备采取的行动，不代表已经发生。

下面这三句话不能存成同一类型：

**代码块说明｜结构示意：** 这段文本把“事实、假设与计划必须分开”中的关键对象并列出来，帮助读者识别各自责任与边界。它用于概念建模，不代表唯一的产品命名或实现结构。

```text
测试输出显示签名算法不匹配。              # Fact
可能是依赖升级改变了默认算法。             # Hypothesis
下一步读取 config override。               # Plan
```

如果统一放进 `notes`，恢复后的 Agent 很可能把“可能”当成“已经确认”，又把“准备执行”当成“已经完成”。结构化类型本身就是一种认知约束。

## Task State 与 Environment State 也要分开

Run State 可以记录 Agent 对环境的最后观察，但不能把它当成外部真相的替代品。

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“Task State 与 Environment State 也要分开”落成可检查的结构化记录，主要字段包括 `environment_observations`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
environment_observations:
  - subject: file://src/auth/config.ts
    observed_version: sha256:9a2...
    observed_state: algorithm=RS256
    observed_at: 2026-08-11T16:20:02+08:00
```

这个记录表达的是“在某个时间、某个版本上看到什么”。如果文件可能被其他进程修改，高风险写入前必须重新读取并比较版本。

可以用一句话区分：

> Task State 决定 Agent 接下来想做什么；Environment State 决定这个动作现在是否仍然成立。

## State、Event 与 Reducer

State 保存当前值，Event 保存状态为什么变化，Reducer 则定义怎样从旧状态和事件得到新状态。三者来自状态管理与 Event Sourcing 的通用设计思想；下面的事件名和 Reducer 结构是本章示例，不是统一协议：

**代码块说明｜结构示意：** 这段文本把“State、Event 与 Reducer”中的关键对象并列出来，帮助读者识别各自责任与边界。它用于概念建模，不代表唯一的产品命名或实现结构。

```text
state@18 + ToolSucceeded(step_19, result_ref)
        ── reducer ──► state@19
```

**代码块说明｜伪代码：** 这段 Python 以 `reduce()` 为主要入口说明“State、Event 与 Reducer”怎样运行。它省略了持久化、并发、权限和完整错误处理，用于解释决策顺序，不是可直接部署的完整实现。

```python
def reduce(state, event):
    if event.type == "FactConfirmed":
        state.confirmed_facts[event.fact.id] = event.fact
        state.hypotheses.pop(event.replaces_hypothesis_id, None)
    elif event.type == "TaskBlocked":
        state.tasks[event.task_id].status = "blocked"
        state.tasks[event.task_id].blocked_by = event.reason
    elif event.type == "GoalChanged":
        state.goal = event.goal
        state.tasks = invalidate_out_of_scope_tasks(state.tasks, event.goal)
    state.revision += 1
    return state
```

Reducer 应保持确定性：相同旧 State 和相同 Event 必须产生相同新 State。模型可以提出事件，Runtime 必须校验事件是否合法，再执行 Reducer。

## Snapshot、Event Sourcing 与混合模式

有三种常见持久化方式：

| 方式 | 优点 | 风险 | 适合 |
| --- | --- | --- | --- |
| 只存 Snapshot | 读取快、实现简单 | 难以解释变化原因 | 短任务、低审计要求 |
| 只存 Event | 可完整重放和审计 | 重建慢，迁移复杂 | 强审计、状态较小 |
| Snapshot + Event | 恢复快且保留变化 | 需要维护一致性 | 多数生产 Agent |

混合模式通常在每次安全边界后追加 Event，并每隔若干 Step 或进入等待状态时生成 Snapshot。恢复时读取最近 Snapshot，再重放其后的 Event。

写入必须原子化。否则可能出现 State 已更新但 Event 丢失，或 Event 已发布但 State 仍是旧版本。常见做法是在同一事务中写 State 和 Outbox Event，再由异步进程发布 Event。

## 并发更新需要版本控制

即使是 Single Agent，也可能同时接收用户输入、Tool 返回和取消请求。多个 Worker 或 Agent 共写 State 时，问题更明显。

最小防线是乐观并发控制：

**代码块说明｜存储约束示例：** 这段 SQL 展示“并发更新需要版本控制”落到持久化层时必须守住的约束。它强调数据一致性意图；表名、字段名和数据库语法需要按实际实现调整。

```sql
UPDATE run_state
SET document = :new_state,
    revision = revision + 1
WHERE run_id = :run_id
  AND revision = :expected_revision;
```

如果影响行数为 0，说明 State 已被其他写入推进。调用方不能直接覆盖，必须重新读取，并决定：

- 可交换事件：重新基于新 State 应用，例如追加一条独立 Fact。
- 同一字段冲突：进入合并或仲裁，例如两个 Agent 同时占有一个 Task。
- 控制事件优先：取消、权限撤销和 Goal 变更通常使旧结果失效。

数组追加也不等于天然无冲突。每条 Fact、Task 和 Artifact 应有稳定 ID、作者与 revision，避免用“最后写入胜出”掩盖语义冲突。

## Schema 版本与迁移

长时间等待的 Run 可能跨过多次 Runtime 发布，因此 State 需要 `schema_version`。迁移应满足：

- 旧版本可以被显式识别，不能猜测结构。
- 迁移函数是确定性的，并能记录迁移来源。
- 删除字段前先定义它的替代语义。
- 无法安全迁移时进入 `MIGRATION_REQUIRED` 或人工恢复，而不是丢字段继续运行。

**代码块说明｜伪代码：** 这段 Python 以 `load_state()` 为主要入口说明“Schema 版本与迁移”怎样运行。它省略了持久化、并发、权限和完整错误处理，用于解释决策顺序，不是可直接部署的完整实现。

```python
MIGRATIONS = {
    1: migrate_v1_to_v2,
    2: migrate_v2_to_v3,
}

def load_state(raw):
    while raw["schema_version"] < CURRENT_SCHEMA:
        migrate = MIGRATIONS[raw["schema_version"]]
        raw = migrate(raw)
    validate(raw)
    return raw
```

除了 Schema 版本，还要记录 Agent Version。前者说明数据怎样读取，后者说明哪个 Prompt、Skill、Tool 和策略正在解释它们。

## 什么时候生成 Checkpoint

不是每次字段变化都需要创建完整 Checkpoint。合适的安全边界包括：

- 一组原子 Task 完成后。
- 即将等待用户、授权或外部事件时。
- 即将执行高成本或高副作用动作前。
- Workspace 已产生一个可识别版本时。
- Worker 租约即将释放时。

Checkpoint 除了 Run State，还需要包含恢复所需的版本、Workspace 引用、Effect Ledger 和未完成 Tool Call 信息。这里的 `Effect Ledger` 是本 Playbook 对“已经发生或正在进行的外部副作用记录”的工作名称，不是行业标准对象；副作用章节会进一步说明。Checkpoint 回答的不是“状态是什么”，而是“从这里恢复是否安全”。

## 贯穿案例：一次可靠的状态更新

Agent 运行配置测试后，Tool 返回 `fixture 固定 HS256，应用配置为 RS256`。Runtime 不应该让模型直接重写整份 State，而应提交一个受约束的状态补丁：

**代码块说明｜Playbook 参考 Schema：** 这段 JSON 把“贯穿案例：一次可靠的状态更新”落成可检查的结构化记录，主要字段包括 `expected_revision`、`events`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```json
{
  "expected_revision": 18,
  "events": [
    {
      "type": "FactConfirmed",
      "fact": {
        "id": "fact_13",
        "statement": "登录测试 fixture 固定使用 HS256",
        "evidence": "artifact://test-output/48"
      }
    },
    {
      "type": "TaskCompleted",
      "task_id": "task_3",
      "evidence": "artifact://test-output/48"
    }
  ]
}
```

Runtime 校验证据引用、Task 转换和 revision 后，再产生 `state@19`。这样模型负责提出语义变化，状态存储负责保证变化合法。

## 本章检查

- 是否可以不读取完整 Conversation 就回答“当前做到哪里”。
- Fact、Hypothesis、Plan 和 Environment Observation 是否类型分离。
- 每个关键事实是否带来源、时间和作用域。
- State 更新是否经过校验、Reducer 和 revision 控制。
- Checkpoint 是否包含 Workspace 与副作用恢复所需的引用。
- 旧 Run 是否有明确的 Schema 迁移或拒绝恢复策略。
