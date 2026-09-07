# Plan、Todo 与 Task Graph

作者：杨正武
来源：https://imcoders.cn/playbook/agent/12-plan-task-graph/
更新：2026-08-12T00:00:00.000Z

把计划视为可修改的执行假设，通过 Task 生命周期、依赖和调度持续推进目标。

---


复杂任务很少能靠连续选择一个 Tool 直接完成。Agent 需要先形成对路径的判断，再把它外化为可执行、可阻塞、可重排和可验收的工作单元。

这时最容易出现的误区，是把一段自然语言 Plan 当成执行状态。模型写下“分析问题、修改代码、运行测试”，看起来已经有了计划，但 Runtime 不知道哪一步已经完成、谁在执行、依赖是否满足，也不知道失败后应该重试、阻塞还是重新规划。

Plan 是对未来路径的假设；Task Graph 才是 Runtime 可以调度的状态。

## 术语来源与适用范围

Plan、Task、依赖图和 Scheduler 都是规划、项目管理和工作流系统中的通用概念，但业界没有一套跨 Agent 框架通用的对象边界。某些系统把一次 Tool 调用称为 Task，某些系统把完整的异步 Agent 请求称为 Task；Todo 也可能只是用户界面中的文本列表。

本章继续使用 `Run` 表示一次目标明确的 Agent 执行实例。一个 Run 可以包含一张 Task Graph，而 Task 是 Run 内部可调度、可验收的工作单元。这个层级关系是本 Playbook 的参考模型；如果外部协议把整个执行实例称为 Task，就需要区分“协议 Task”和本章的“内部 Task”，不能只按名称判断它们是否相同。

本章对 Plan、Todo、Task 和 Step 的区分，是本 Playbook 为保持后续讨论一致而采用的工作定义，不是外部协议标准。特别是：

- 把 Plan 定义为“可被新证据推翻的执行假设”，是本书的设计原则。
- 把 Todo 定义为 Task Graph 的人类可读投影，是本书建议的产品实现方式。
- `PENDING`、`READY`、`RUNNING`、`NEEDS_REPLAN` 等状态组成的是参考生命周期；具体 Runtime 可以使用不同名称或增加状态。
- 后文的 Task Schema、调度排序和 Replan 记录都是参考设计，不要求与 A2A Task 或某个框架的 Task 对象一一对应。

## Plan、Todo、Task、Step 分别是什么

| 概念 | 责任 | 典型生命周期 |
| --- | --- | --- |
| Plan | 描述当前认为可行的路径和理由 | 随新事实修订或废弃 |
| Todo | 面向人或 Agent 展示的轻量待办 | 未开始、进行中、完成 |
| Task | 可调度、可分配、带依赖和验收的工作单元 | Pending 到终态 |
| Step | 实际发生的一次状态转换 | 发生后不可覆盖 |

一项 Task 可能包含多个 Step：读取文件、调用模型、修改代码、运行测试。一次 Step 也可能发现原 Task 的前提不成立，从而触发 Replan。

Todo 更像界面投影。简单任务中它可以直接对应 Task，但复杂系统不能只靠 Todo 文本表达依赖、所有权、预算和完成证据。

## Plan 是可证伪的执行假设

好的 Plan 不只列动作，还说明关键假设和验证点：

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“Plan 是可证伪的执行假设”落成可检查的结构化记录，主要字段包括 `plan`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
plan:
  plan_id: plan_7
  revision: 2
  objective: 修复依赖升级后的登录失败
  assumptions:
    - id: assumption_1
      statement: 失败来自签名算法配置不一致
      validation_task: task_2
  strategy:
    - 定位配置差异
    - 以最小变更恢复兼容
    - 运行定向测试和完整回归
  replan_if:
    - task_2 证明签名算法一致
    - 修改需要改变公开 API
    - 完整回归出现新的失败类别
```

Plan 不应该把未知情况伪装成确定路径。越早说明“什么证据会推翻当前计划”，Agent 越容易在错误路径上及时停下。

## Task 必须能够被独立调度和验收

在本章的参考模型中，一个可调度、可验收的 Task 可以包含以下字段：

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“Task 必须能够被独立调度和验收”落成可检查的结构化记录，主要字段包括 `task`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
task:
  task_id: task_4
  title: 修正测试 fixture 的算法配置来源
  objective: fixture 与应用读取同一配置，不硬编码算法
  status: pending
  depends_on: [task_2]
  owner: agent://coding
  inputs:
    - artifact://diagnosis/12
    - workspace://ws_71@commit:3bc92e
  constraints:
    - 不改变公开 API
    - 不降低生产签名算法
  acceptance:
    - fixture 不再硬编码 HS256
    - test_login_refresh 通过
  budget:
    max_steps: 12
    deadline: 2026-08-11T17:20:00+08:00
  outputs:
    - kind: patch
    - kind: test_evidence
```

Task 的粒度应满足两个条件：它可以被一个明确责任方推进；完成时可以用证据判断。过大的 Task 不能定位阻塞，过小的 Task 会让调度成本超过执行收益。

“打开文件”“思考原因”通常是 Step，不是 Task。“修复整个认证系统”通常太大，需要拆成诊断、实现和验证等可验收单元。

## Task Graph 表达依赖，而不是展示顺序

**代码块说明｜层级示意：** 这段文本图按缩进和树枝符号阅读，用来展开“Task Graph 表达依赖，而不是展示顺序”中的父子关系与归属边界。它描述的是逻辑结构，不要求数据库或服务按同样层级拆分。

```text
task_1 复现失败
   │
   ▼
task_2 确认配置来源
   ├──────────────┐
   ▼              ▼
task_3 修正 fixture   task_4 检查生产兼容性
   └──────┬───────┘
          ▼
task_5 定向测试
          │
          ▼
task_6 完整回归与目标验收
```

图中的横向位置不代表执行先后，边才表示依赖。`task_3` 和 `task_4` 在 `task_2` 完成后都可进入 Ready，因此可以并行；`task_5` 必须等两者都完成。

Task Graph 应保持无环。如果新增依赖形成循环，Runtime 必须拒绝更新或要求重写计划。循环依赖不是“都在等待”，而是计划结构本身不可执行。

## 本章采用的 Task 参考生命周期

**代码块说明｜层级示意：** 这段文本图按缩进和树枝符号阅读，用来展开“本章采用的 Task 参考生命周期”中的父子关系与归属边界。它描述的是逻辑结构，不要求数据库或服务按同样层级拆分。

```text
PENDING ──依赖满足──► READY ──领取──► RUNNING
   │                    │                ├──► COMPLETED
   │                    │                ├──► BLOCKED
   │                    │                ├──► FAILED
   │                    │                ├──► CANCELED
   │                    │                └──► NEEDS_REPLAN
   └────目标变化────────────────────────► CANCELED
```

在本章的参考模型中，各状态具有以下语义：

- `PENDING`：依赖尚未满足，不能执行。
- `READY`：所有硬依赖已满足，具备执行条件。
- `RUNNING`：已被 Worker 或 Agent 领取，并持有有效租约。
- `BLOCKED`：知道阻塞原因，等待输入、权限、资源或外部事件。
- `FAILED`：在当前策略和重试预算下无法完成。
- `NEEDS_REPLAN`：Task 的前提或目标已经变化，不能原样继续。
- `COMPLETED`：Task 验收证据通过。

`BLOCKED` 不是模糊的失败。它必须带 `blocked_by`、解除条件和可选截止时间，否则 Scheduler 无法知道何时重新检查。

## Scheduler 只选择 Ready Task

Scheduler 的职责不是替 Agent 推理，而是在合法候选中选择下一项工作。下面的排序逻辑只是说明调度因素的伪代码，不是通用调度算法：

**代码块说明｜伪代码：** 这段 Python 以 `refresh_ready()`、`choose_next()` 为主要入口说明“Scheduler 只选择 Ready Task”怎样运行。它省略了持久化、并发、权限和完整错误处理，用于解释决策顺序，不是可直接部署的完整实现。

```python
def refresh_ready(graph, state):
    for task in graph.pending_tasks():
        if all(graph.get(dep).status == "completed"
               for dep in task.depends_on):
            if preconditions_hold(task, state):
                task.status = "ready"

def choose_next(graph, resources):
    candidates = [
        task for task in graph.ready_tasks()
        if resources.can_run(task)
    ]
    return max(candidates, key=lambda task: (
        task.priority,
        task.unblocks_count,
        -task.estimated_cost,
        -task.created_at.timestamp(),
    ), default=None)
```

生产 Scheduler 还要考虑：

- Tool、模型、Workspace 和权限是否可用。
- Task 是否与其他 Task 争用同一资源。
- 并发上限和预算。
- 截止时间、关键路径和公平性。
- 是否需要保持 Reviewer 与 Executor 的上下文隔离。

Task 从 Ready 进入 Running 时应原子领取，并记录 owner 和 lease。租约过期后，Runtime 才能安全地重新分配，避免两个 Worker 同时执行有副作用的 Task。

## Replan 是对假设失效的响应

不应该每执行一步都重写整个 Plan，也不应该直到所有任务失败才 Replan。常见触发条件包括：

- 关键假设被新证据证伪。
- Goal、范围或验收标准发生变化。
- 当前路径需要未授权能力。
- 一个 Task 超过重试、成本或时间预算。
- 外部环境版本变化，使原输入失效。
- 新发现的 Task 改变关键路径。

Replan 不是删除历史重新开始。它应该生成新的 Plan revision，并明确保留、替换或取消哪些 Task：

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“Replan 是对假设失效的响应”落成可检查的结构化记录，主要字段包括 `plan_change`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
plan_change:
  from_revision: 2
  to_revision: 3
  reason: 配置一致，原假设被 task_2 证伪
  keep: [task_1, task_2]
  cancel: [task_3, task_4]
  add: [task_7, task_8]
  invalidated_artifacts: []
```

已经产生的 Artifact 和外部副作用不能随着 Plan 被覆盖而消失。新 Plan 必须显式决定它们是否仍然有效。

## 所有 Task 完成不等于 Goal 完成

Task Graph 只表示系统执行了计划中的工作，无法证明计划本身覆盖了目标。

**代码块说明｜结构示意：** 这段文本把“所有 Task 完成不等于 Goal 完成”中的关键对象并列出来，帮助读者识别各自责任与边界。它用于概念建模，不代表唯一的产品命名或实现结构。

```text
All Tasks Completed  ≠  Goal Completed
```

例如，Agent 完成了“修改 fixture”和“运行定向测试”，但用户要求“完整回归无失败”。如果计划漏掉完整回归，Task 全绿仍然不能完成 Run。

因此需要两层验收：

1. **Task Acceptance**：每项 Task 的局部输出符合要求。
2. **Goal Acceptance**：正式 Artifact 和环境结果满足原始目标。

最终验证器应该直接读取 Goal Acceptance，而不是只统计 Task 状态：

**代码块说明｜伪代码：** 这段 Python 以 `can_complete_run()` 为主要入口说明“所有 Task 完成不等于 Goal 完成”怎样运行。它省略了持久化、并发、权限和完整错误处理，用于解释决策顺序，不是可直接部署的完整实现。

```python
def can_complete_run(state, artifacts):
    if not all(t.status in TERMINAL for t in state.tasks):
        return False
    evidence = collect_goal_evidence(state.goal.acceptance, artifacts)
    return goal_verifier.verify(state.goal, evidence).passed
```

如果所有 Task 完成但 Goal 未通过，正确结果通常是 `NEEDS_REPLAN`，而不是继续创建没有依据的随机 Task。

## Todo 是 Task Graph 的人类投影

用户不需要看到所有调度字段。界面可以把 Task Graph 投影为更容易理解的 Todo：

**代码块说明｜流程示意：** 这段文本图按箭头方向阅读，用来说明“Todo 是 Task Graph 的人类投影”中的执行顺序、状态变化或责任流转。它表达逻辑关系，不代表组件必须按图中的数量和位置部署。

```text
✓ 复现登录失败
✓ 确认算法配置来源
→ 修正测试 fixture
○ 检查生产兼容性（可并行）
○ 运行完整回归（等待前两项）
```

投影必须可追溯回 Task ID。用户勾选、取消或修改 Todo 时，Runtime 才能把操作转换为合法的 Task 状态变化，而不是只改一段展示文本。

## 本章检查

- Plan 是否记录关键假设和 Replan 条件，而不只是动作列表。
- Task 是否具有依赖、所有者、输入、约束、预算和验收证据。
- Scheduler 是否只领取 Ready 且前置条件仍成立的 Task。
- Blocked Task 是否说明阻塞来源和解除条件。
- Replan 是否保留 revision，并处理旧 Task、Artifact 与副作用。
- Run 完成是否独立验证 Goal，而不是只检查 Task 是否全部完成。
