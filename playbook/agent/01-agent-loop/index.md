# Agent Loop：一个 while 循环如何变成执行系统

作者：杨正武
来源：https://imcoders.cn/playbook/agent/01-agent-loop/
更新：2026-08-12T00:00:00.000Z

Agent 的计算内核可以写成一个 while 循环，但只有加入观察、状态、动作结果和终止语义，它才能成为可工作的执行系统。

---


如果把各种 Agent 框架的抽象全部剥掉，最核心的实现确实可以缩小成一个 `while` 循环：系统读取当前状态，选择下一次状态转换，执行转换，把结果写回状态，然后继续。

**代码块说明｜伪代码：** 这段 Python 以最小控制流程说明“Agent Loop：一个 while 循环如何变成执行系统”怎样运行。它省略了持久化、并发、权限和完整错误处理，用于解释决策顺序，不是可直接部署的完整实现。

```python
while not finished:
    transition = policy.decide(goal, state)
    result = execute(transition)
    state = update(state, result)
```

这几行代码已经表达了 Agent 和一次模型调用最本质的差别：模型的输出不只是最终答案，也可能影响下一步状态转换；执行结果不会直接丢弃，而会改变下一轮判断使用的状态。

但它还不是一个可以投入真实环境的 Agent。`finished` 由谁判断？Context 会不会无限增长？工具失败后应该重试还是换策略？进程被关闭以后从哪里继续？模型要求执行危险操作时谁负责拦截？这些问题构成了 Agent Loop 从 Demo 走向工程系统的过程。

## 动作级 Loop 的四个基本阶段

对于 ReAct 这类动作级 Agent，Loop 可以概括成四个不断重复的阶段：

**代码块说明｜流程示意：** 这段文本图按箭头方向阅读，用来说明“动作级 Loop 的四个基本阶段”中的执行顺序、状态变化或责任流转。它表达逻辑关系，不代表组件必须按图中的数量和位置部署。

```text
Observe → Decide → Act → Update
```

![Agent Loop 的运行与退出](/playbook-images/agent/agent-loop.svg)

### Observe：读取最新事实

Observe 不是让模型凭对话历史回忆发生过什么，而是主动获得当前状态和环境证据。

观察内容可能包括：

- 当前目标与未完成子任务。
- 上一轮执行了什么动作。
- Tool 返回的结构化结果。
- 文件、数据库或页面的最新状态。
- 剩余时间、Token 和调用预算。
- 是否出现了新的用户输入或外部事件。

环境可能在两轮之间被其他人或其他进程修改，因此 Agent 不应该把历史 Context 当成永远正确的事实。高风险动作前重新读取目标对象，是一种重要的观察策略。

### Decide：选择一个允许的下一步动作

Runtime 将目标、状态、观察结果、Skill 和可用 Tool 组装成 Context，交给模型判断。

模型输出最好不是任意文本，而是一个可以被程序检查的决策：

**代码块说明｜Playbook 参考 Schema：** 这段 JSON 把“Decide：选择一个允许的下一步动作”落成可检查的结构化记录，主要字段包括 `reason`、`action`、`arguments`、`expected_evidence`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```json
{
  "reason": "测试失败显示 users 表缺少 status 字段",
  "action": "read_file",
  "arguments": {
    "path": "db/migrations/20260811_add_status.sql"
  },
  "expected_evidence": "确认 migration 是否创建 status 字段"
}
```

Runtime 在执行前还要检查：Tool 是否存在，参数是否合法，动作是否超出任务范围，是否需要用户确认，以及剩余预算是否允许执行。

### Act：让动作在环境中真实发生

Act 是 Tool 的执行阶段。动作可能是只读观察，也可能产生副作用：

**代码块说明｜结构示意：** 这段文本把“Act：让动作在环境中真实发生”中的关键对象并列出来，帮助读者识别各自责任与边界。它用于概念建模，不代表唯一的产品命名或实现结构。

```text
只读：读取文件、查询数据库、搜索网页
可撤销：修改工作区文件、创建草稿
高风险：发送消息、删除数据、部署生产环境
```

执行器需要返回真实结果，而不是模型对结果的想象。即使 Agent 非常确信修改可以让测试通过，也必须实际运行测试后才能获得“测试通过”这个事实。

### Update：把证据写回状态

每一轮结束后，Runtime 应将动作和结果更新到任务状态中：

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“Update：把证据写回状态”落成可检查的结构化记录，主要字段包括 `goal`、`status`、`current_step`、`confirmed_facts`、`last_action`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
goal: 修复用户注册测试
status: running
current_step: 检查数据库 migration
confirmed_facts:
  - 注册测试失败，因为 users.status 不存在
last_action:
  tool: read_file
  target: db/migrations/20260811_add_status.sql
  outcome: 文件存在，但没有被迁移入口引用
next_candidates:
  - 检查 migration 注册表
  - 检查测试数据库初始化逻辑
```

Update 不是把所有工具输出永久追加到一段无限增长的对话。它需要把原始证据、当前结论和可恢复状态分开保存，下一轮只加载与当前决策有关的内容。

## 相同内核，不同循环粒度

Observe、Decide、Act、Update 最容易解释 ReAct，但 Agent Loop 不要求模型每一轮都直接选择 Tool。Plan、Todo 和 Event 模式使用的是同一个状态演进内核，只是每一轮处理的对象不同。

### ReAct：每轮选择一个动作

**代码块说明｜伪代码：** 这段 Python 以最小控制流程说明“ReAct：每轮选择一个动作”怎样运行。它省略了持久化、并发、权限和完整错误处理，用于解释决策顺序，不是可直接部署的完整实现。

```python
while not terminal(state):
    observation = observe_environment(state)
    action = model.select_action(observation, tools)
    result = execute_tool(action)
    state.record(action, result)
```

它把“行动—反馈”紧密交错，适合路径无法提前确定的探索任务。

### Plan-and-Execute：每轮推进一个计划步骤

**代码块说明｜伪代码：** 这段 Python 以最小控制流程说明“Plan-and-Execute：每轮推进一个计划步骤”怎样运行。它省略了持久化、并发、权限和完整错误处理，用于解释决策顺序，不是可直接部署的完整实现。

```python
plan = planner.create(goal)

while not terminal(plan):
    step = scheduler.select_next(plan)
    result = executor.execute(step)
    plan.update(step, result)

    if evaluator.should_replan(plan, result):
        plan = planner.revise(plan, result)
```

Plan 是显式状态。执行结果既可以推进当前步骤，也可以触发 Replan。只有“生成一次计划然后固定执行”时，系统更接近 LLM Planner 加 Workflow。

### Task-driven：每轮调度一个 Task

**代码块说明｜伪代码：** 这段 Python 以最小控制流程说明“Task-driven：每轮调度一个 Task”怎样运行。它省略了持久化、并发、权限和完整错误处理，用于解释决策顺序，不是可直接部署的完整实现。

```python
while task_graph.has_unfinished_work():
    task = scheduler.select_ready_task(task_graph)
    result = worker.execute(task)
    task_graph.update(task, result)
    task_graph.add_or_reorder(result.discovered_tasks)
```

Todo List 或 Task Graph 是主要状态。Agent 性体现在系统能够依据执行结果增删、重排、阻塞或恢复任务，而不是清单本身。

### Event-driven：每次事件只推进一轮

**代码块说明｜伪代码：** 这段 Python 以 `on_event()` 为主要入口说明“Event-driven：每次事件只推进一轮”怎样运行。它省略了持久化、并发、权限和完整错误处理，用于解释决策顺序，不是可直接部署的完整实现。

```python
def on_event(event):
    state = load_state(event.task_id)
    transition = decide(state, event)
    result = execute(transition)
    save_state(update(state, result))
```

它在代码里可能看不到连续的 `while`，但事件到达、恢复状态、推进一步、再次等待，组合起来仍然是一个跨时间展开的 Loop。

这些模式可以嵌套。一个 Plan-and-Execute Agent 可以用 Task Graph 调度步骤，每个步骤由一个 ReAct Worker 执行，整个系统再由事件驱动 Runtime 负责持久化和恢复。

## 最小可工作的 Agent Loop

一个更完整的最小实现可以写成：

**代码块说明｜伪代码：** 这段 Python 以 `run_agent()` 为主要入口说明“最小可工作的 Agent Loop”怎样运行。它省略了持久化、并发、权限和完整错误处理，用于解释决策顺序，不是可直接部署的完整实现。

```python
def run_agent(goal, runtime):
    state = runtime.create_or_load_state(goal)

    while state.status == "running":
        observation = runtime.observe(state)
        context = runtime.build_context(
            goal=goal,
            state=state,
            observation=observation,
            skills=runtime.select_skills(state),
            tools=runtime.allowed_tools(state),
        )

        decision = runtime.model.decide(context)
        decision = runtime.validate_decision(decision, state)

        if decision.type == "finish":
            evidence = runtime.verify_completion(goal, state)
            if evidence.passed:
                state.succeed(evidence)
            else:
                state.record_verification_failure(evidence)
            continue

        if decision.type == "ask_human":
            state.wait_for_human(decision.question)
            continue

        result = runtime.execute(decision.action)
        state.record(decision, result)

    return state
```

这个版本增加了几个不能省略的责任：

- 状态可以创建，也可以从中断位置恢复。
- Skill 和 Tool 根据当前任务选择，不是全部塞进 Context。
- 模型产生的决策在执行前要经过程序校验。
- 模型声称完成后，还要用证据验证。
- 等待人工输入是一种正式状态，不是执行失败。

## Loop 必须有完整的退出语义

只设置 `max_steps = 20` 不算完整退出设计。最大轮数只能阻止无限消耗，不能解释任务为什么停止。

一个 Agent 至少应该区分下面几种终态：

| 状态 | 含义 | 是否可以继续 |
| --- | --- | --- |
| SUCCESS | 目标已经通过证据验证 | 通常不需要 |
| FAILED | 已知原因导致任务无法完成 | 修改条件后可以重启 |
| WAITING | 正在等待时间或外部事件 | 事件到达后自动恢复 |
| NEEDS_HUMAN | 需要用户选择、确认或授权 | 收到输入后恢复 |
| CANCELLED | 用户或上层系统主动取消 | 通常终止 |

`BLOCKED` 也可以作为独立状态，表示当前路径无法推进，但并不等于任务本身已经失败。例如缺少某个系统权限、依赖服务不可用、输入材料不完整。

这些状态会影响上层系统如何处理 Agent。WAITING 不应该被任务调度器当成失败反复重启，NEEDS_HUMAN 应该把明确问题和必要上下文交给用户，FAILED 则应该保留可诊断的原因。

## 完成必须由证据决定

模型非常容易把“我已经执行了修改”表达成“任务已经完成”。但动作完成和目标完成不是一回事。

**代码块说明｜结构示意：** 这段文本把“完成必须由证据决定”中的关键对象并列出来，帮助读者识别各自责任与边界。它用于概念建模，不代表唯一的产品命名或实现结构。

```text
动作：修改了登录逻辑
目标：修复登录失败，而且不破坏已有登录方式
证据：相关测试通过，兼容性用例通过，变更范围符合约束
```

因此，`finish` 更适合被理解为模型提出的“完成申请”，而不是最终状态：

**代码块说明｜流程示意：** 这段文本图按箭头方向阅读，用来说明“完成必须由证据决定”中的执行顺序、状态变化或责任流转。它表达逻辑关系，不代表组件必须按图中的数量和位置部署。

```text
模型提出 finish
       ↓
Runtime 执行验收检查
       ↓
通过 → SUCCESS
失败 → 把证据写回状态，继续 Loop
```

验证方式应该尽量独立于产生方案的那次模型判断，例如运行测试、查询真实状态、检查输出 schema，或者要求人工验收无法自动判断的部分。

## 失败后不能只重复同一个动作

最差的 Agent Loop 是：工具失败，模型再次调用同一个工具，直到达到最大轮数。

Runtime 应区分不同失败类型：

| 失败类型 | 合理处理 |
| --- | --- |
| 临时网络错误 | 有退避的有限重试 |
| 参数错误 | 修正参数后重试 |
| 权限不足 | 请求授权或切换只读方案 |
| 目标对象不存在 | 重新观察并修正假设 |
| 连续得到相同结果 | 更换策略或升级人工处理 |
| 不可逆动作失败 | 停止并报告当前外部状态 |

除了记录“失败了几次”，还应该识别 Agent 是否正在产生实质进展。一个实用判断是：每轮动作是否减少了目标与当前状态之间的差距，或者至少减少了关键不确定性。

如果连续几轮既没有改变环境，也没有获得新证据，Loop 很可能已经失去收敛性。

## 状态让 while 循环可以恢复

只存在进程内变量中的 Agent，一旦进程退出就失去任务位置。生产 Runtime 需要把关键状态持久化：

**代码块说明｜结构示意：** 这段文本把“状态让 while 循环可以恢复”中的关键对象并列出来，帮助读者识别各自责任与边界。它用于概念建模，不代表唯一的产品命名或实现结构。

```text
任务标识
目标和约束
当前生命周期状态
已经确认的事实
已经执行的高影响动作
等待的事件或人工输入
剩余预算
最后一个可恢复检查点
```

恢复时，不应该简单重放全部历史对话，而是读取最新检查点、重新观察可能变化的环境，再继续决策。

这也是 State 与 Conversation History 的区别：历史记录用于审计和回溯，当前状态用于继续工作。完整历史可能很长，但恢复 Agent 所需的信息应该是有限、明确并经过整理的。

## while 只是实现形式之一

本地脚本可以直接使用同步 `while` 循环。长期运行的 Agent 通常会采用事件驱动的实现：

**代码块说明｜流程示意：** 这段文本图按箭头方向阅读，用来说明“while 只是实现形式之一”中的执行顺序、状态变化或责任流转。它表达逻辑关系，不代表组件必须按图中的数量和位置部署。

```text
收到任务事件
  → 执行一轮
  → 保存状态
  → 发出 Tool 请求
  → 暂停

收到 Tool 结果事件
  → 恢复状态
  → 执行下一轮
```

两种实现的逻辑内核相同，都是 Observe、Decide、Act、Update。区别只在于同步循环把所有阶段放在一个进程中连续执行，事件驱动 Runtime 可以在等待外部结果时释放资源，并在数分钟甚至数天后恢复。

因此更准确的说法是：

> `while` 循环是 Agent 的概念内核；状态机和事件系统是它在生产环境中的运行形态。

## 本章检查

- 每轮是否从最新状态和环境证据开始，而不是只依赖对话历史。
- 模型输出是否被解析成可以校验的决策。
- 动作执行结果是否被写回任务状态。
- SUCCESS 是否有独立证据，而不是模型自行宣布。
- 是否区分成功、失败、等待、取消和人工介入。
- 连续失败后是否会更换策略，而不是机械重复。
- 进程中断后是否可以从持久化状态恢复。
