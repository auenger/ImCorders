# Workflow 与 Agent：谁来决定下一步

作者：杨正武
来源：https://imcoders.cn/playbook/agent/02-workflow-agent/
更新：2026-08-12T00:00:00.000Z

使用了 LLM 和 Tool 的系统不一定是 Agent。固定流程与动态决策的真正分界，在于下一步动作究竟由程序还是模型决定。

---


一个程序读取文档、调用 LLM 生成摘要、把摘要写入数据库，最后发送通知。它使用了模型，连接了多个外部系统，也执行了真实动作。它是不是 Agent？

不一定。判断的关键不在于系统用了多少 LLM、Tool 或 Skill，而在于执行过程中谁决定下一步。

如果每一步和每一条分支都由程序提前写好，这是 Workflow。如果系统根据最新观察，在多个可行动作中动态选择下一步，它才具有 Agent 的核心特征。

## Workflow 的路径由程序决定

Workflow 把任务拆成一组预先定义的步骤：

**代码块说明｜伪代码：** 这段 Python 以最小控制流程说明“Workflow 的路径由程序决定”怎样运行。它省略了持久化、并发、权限和完整错误处理，用于解释决策顺序，不是可直接部署的完整实现。

```python
document = read_document(path)
summary = llm(summarize_prompt, document)
record_id = save_to_database(summary)
send_notification(record_id)
```

这里的 LLM 负责生成摘要，但它不决定摘要完成后应该做什么。无论摘要内容是什么，程序都会继续保存数据库，然后发送通知。

Workflow 也可以拥有条件分支和重试：

**代码块说明｜伪代码：** 这段 Python 以最小控制流程说明“Workflow 的路径由程序决定”怎样运行。它省略了持久化、并发、权限和完整错误处理，用于解释决策顺序，不是可直接部署的完整实现。

```python
if document.language == "zh":
    summary = summarize_chinese(document)
else:
    summary = summarize_english(document)

for attempt in range(3):
    if save(summary):
        break
```

有 `if` 和 `for` 不会让 Workflow 自动变成 Agent，因为所有可能路径仍然由开发者提前列举。运行时只是在确定性地执行规则。

Workflow 的优势也正来自这里：

- 路径容易理解和测试。
- 成本与延迟相对可预测。
- 权限边界可以精确绑定到步骤。
- 失败位置容易定位。
- 相同输入更容易得到一致过程。

当任务结构稳定、输入差异有限、步骤可以提前枚举时，Workflow 通常比 Agent 更合适。

## Agent 的下一步由当前状态决定

考虑另一个任务：“找出这个项目构建失败的原因并修复。”

系统无法在运行前写死完整路径。失败可能来自依赖缺失、类型错误、环境变量、测试冲突或构建工具版本。不同观察结果会产生不同动作：

**代码块说明｜层级示意：** 这段文本图按缩进和树枝符号阅读，用来展开“Agent 的下一步由当前状态决定”中的父子关系与归属边界。它描述的是逻辑结构，不要求数据库或服务按同样层级拆分。

```text
运行构建
├── 依赖缺失 → 检查依赖声明
├── 类型错误 → 读取相关代码
├── 环境变量缺失 → 检查配置说明
├── 测试失败 → 运行失败用例
└── 构建成功 → 验证改动并结束
```

这里的路径无法被一个小型固定流程穷举。Agent 需要根据每次工具返回的最新证据，在允许的动作空间里选择下一步。

可以把两者的核心差异写成：

**代码块说明｜关系式：** 这段表达式把“Agent 的下一步由当前状态决定”压缩成便于比较的组成关系。它是分析模型，不是可执行代码，也不是要求实现者采用的行业标准公式。

```text
Workflow：next_step = program(current_step, predefined_rules)

Agent：next_action = model(goal, state, observation, available_actions)
```

Agent 不是完全没有程序规则。目标、可用 Tool、权限、预算和终止条件仍然由程序控制。动态的是在这些边界内，模型根据当前状态选择下一步动作。

## 一张实用的判断表

| 维度 | Workflow | Agent |
| --- | --- | --- |
| 下一步由谁决定 | 预先编写的程序 | 模型根据当前状态选择 |
| 路径是否提前已知 | 基本已知 | 执行中逐步形成 |
| 适合的任务 | 稳定、重复、规则明确 | 开放、探索、路径难以穷举 |
| 可预测性 | 较高 | 较低 |
| 测试方式 | 覆盖步骤与分支 | 同时评估决策过程与结果 |
| 成本和延迟 | 较稳定 | 受循环轮数影响 |
| 常见风险 | 流程僵化、覆盖不全 | 漂移、循环、越权、成本失控 |

一个系统调用了十次模型，只要调用顺序由程序固定，它仍然可以是 Workflow。另一个系统可能只调用两次模型，但第二次动作由第一次观察动态决定，它已经具有 Agent 性。

## Agent 不是 Workflow 的升级版

把 Workflow 和 Agent 排成“低级到高级”的关系会导致过度设计。两者解决的是不同类型的问题。

适合 Workflow 的任务包括：

- 将固定格式发票抽取成结构化字段。
- 按模板生成周报并发送到指定群组。
- 每晚备份数据库并检查校验值。
- 用户注册后依次创建账户、发送验证邮件。

适合 Agent 的任务包括：

- 调查一个原因未知的线上故障。
- 在大型代码库中定位并修复缺陷。
- 根据多个来源研究一个开放问题。
- 在约束条件下寻找可行的会议安排。

如果一个任务可以画出稳定、完整的流程图，就优先使用 Workflow。如果关键路径取决于执行中才出现的信息，而且这些路径难以提前穷举，再考虑使用 Agent。

## 生产系统通常是 Hybrid

真实系统很少需要“全部由程序控制”或“全部交给模型决定”。更常见、也更可靠的方式是 Hybrid：外层用 Workflow 控制阶段和边界，局部开放问题交给 Agent。

例如一个代码修改流程：

**代码块说明｜流程示意：** 这段文本图按箭头方向阅读，用来说明“生产系统通常是 Hybrid”中的执行顺序、状态变化或责任流转。它表达逻辑关系，不代表组件必须按图中的数量和位置部署。

```text
Workflow：接收任务并检查权限
    ↓
Agent：探索代码并提出修改方案
    ↓
Workflow：等待人工批准方案
    ↓
Agent：在限定目录中实施修改
    ↓
Workflow：运行固定测试与安全检查
    ↓
Agent：分析失败并尝试修复
    ↓
Workflow：生成报告并请求合并
```

这套设计把确定性的部分交给程序，把无法提前枚举的局部决策交给模型。

可以用一个简单原则划分边界：

> 确定性骨架由 Workflow 控制，不确定性节点由 Agent 处理。

登录鉴权、预算检查、审批、事务提交、最终验收等高风险环节，通常适合保留为确定性步骤。资料探索、故障诊断、方案生成等开放环节，可以允许 Agent 动态选择动作。

## Tool Calling 不自动产生 Agent

很多框架支持模型生成结构化 Tool Call：

**代码块说明｜Playbook 参考 Schema：** 这段 JSON 把“Tool Calling 不自动产生 Agent”落成可检查的结构化记录，主要字段包括 `tool`、`arguments`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```json
{
  "tool": "get_weather",
  "arguments": {
    "city": "Shanghai"
  }
}
```

这表示模型能够选择或填写一个工具调用，却不能仅凭这一点判断系统是不是 Agent。

下面这个程序仍然更接近一次工具增强调用：

**代码块说明｜伪代码：** 这段 Python 以最小控制流程说明“Tool Calling 不自动产生 Agent”怎样运行。它省略了持久化、并发、权限和完整错误处理，用于解释决策顺序，不是可直接部署的完整实现。

```python
tool_call = llm(user_request, tools=[get_weather])
tool_result = execute(tool_call)
return llm(user_request, tool_result)
```

它有一次“模型—工具—模型”的往返，但目标简单、动作空间有限，也没有持续任务状态。工程上没有必要为了名称把它包装成复杂 Agent。

当系统开始维护一个未完成目标，允许模型根据多轮观察反复选择动作，并由明确终止条件控制执行时，Agent 的概念才真正有用。

## 自主性存在连续谱

Workflow 和 Agent 之间不是一条绝对分界线，而是一条连续谱：

**代码块说明｜流程示意：** 这段文本图按箭头方向阅读，用来说明“自主性存在连续谱”中的执行顺序、状态变化或责任流转。它表达逻辑关系，不代表组件必须按图中的数量和位置部署。

```text
固定程序
  → 程序调用 LLM
  → LLM 选择固定分支
  → LLM 选择单次 Tool
  → LLM 在局部阶段循环行动
  → LLM 在广泛动作空间中持续行动
```

系统越向右移动，处理未知情况的能力通常越强，但可预测性、成本控制和安全审查也越困难。

设计时应该问的不是“我们能不能做得更 Agentic”，而是：

- 哪些决策真的无法提前写成规则？
- 动态决策带来的收益是否高于不确定性成本？
- Agent 的动作空间能否被限制在安全范围？
- 最终结果是否可以被独立验证？

最好的 Agent 系统往往不是自主性最高的系统，而是在恰当位置使用自主性的系统。

## 不要把设计维度误认为演进阶梯

讨论 Agent 架构时，经常会看到 Single Agent、ReAct、Plan-and-Execute、Multi-Agent、Router + Skill、Blackboard 和 Graph/Workflow 被并列成七种模式，甚至被排列成从简单到复杂的升级路线。

这七个名称并不处于同一个分类层次。它们分别在回答不同的设计问题：

| 常见名称 | 实际回答的问题 | 应归属的设计维度 |
| --- | --- | --- |
| Single Agent | 系统中有几个决策执行者？ | 执行拓扑 |
| ReAct | Agent 每一轮怎样选择动作？ | 决策模式 |
| Plan-and-Execute | 计划和执行怎样交替？ | 决策模式 |
| Multi-Agent | 任务是否拆给多个独立 Agent？ | 执行拓扑 |
| Router + Skill | 怎样选择本次需要的能力和 Context？ | 能力组织 |
| Blackboard | 多个执行者怎样共享状态？ | 状态协调 |
| Graph / Workflow | 整体流程怎样编排、恢复和观测？ | Runtime 编排 |

因此，一个系统不需要从七种模式中单选一个。一个 Multi-Agent 系统可以使用 Plan-and-Execute，由 Router 为每个 Agent 选择 Skill，通过 Blackboard 共享状态，再运行在 Graph Runtime 上；每个工作 Agent 内部还可以使用 ReAct。

所谓“Agent 架构”，更准确地说是一组跨维度设计选择的组合。

## 维度一：决策模式

决策模式定义系统根据当前状态怎样产生下一次状态转换：

| 模式 | 循环单位 | 适合的问题 |
| --- | --- | --- |
| ReAct | 一次动作或 Tool 调用 | 探索、搜索、诊断 |
| Plan-and-Execute | 一个计划步骤 | 有阶段、有依赖的长任务 |
| Task-driven | 一个 Todo 或 Task | 任务持续生成、重排和调度 |
| Rule-based | 一次规则匹配 | 边界明确、高确定性决策 |
| Event-driven | 一个外部事件 | 等待时间较长、异步推进的任务 |

这些模式也可以组合。例如，Planner 负责生成 Task Graph，Scheduler 选择下一个任务，执行单个任务时再运行一个局部 ReAct Loop。

决策模式主要在 Agent Loop 中实现，下一章会详细展开。

## 维度二：执行拓扑

执行拓扑定义系统里有几个相对独立的决策上下文，以及责任怎样分配：

**代码块说明｜流程示意：** 这段文本图按箭头方向阅读，用来说明“维度二：执行拓扑”中的执行顺序、状态变化或责任流转。它表达逻辑关系，不代表组件必须按图中的数量和位置部署。

```text
Single Agent

Orchestrator → Worker A / Worker B / Worker C

Planner → Executor → Reviewer

Peer A ↔ Peer B ↔ Peer C
```

Single Agent 不代表只能处理简单任务。它可以拥有复杂 Plan、多个 Skill 和大量 Tool。Multi-Agent 也不天然更高级，只有任务能够并行、上下文需要隔离、权限需要分离，或者结果需要独立审查时，拆分才可能产生净收益。

“单 Agent”和“多 Agent”回答的是数量、所有权和通信问题，不回答每个 Agent 内部怎样决策。

## 维度三：能力组织

能力组织定义 Agent 如何获得完成任务所需的方法和行动空间：

**代码块说明｜流程示意：** 这段文本图按箭头方向阅读，用来说明“维度三：能力组织”中的执行顺序、状态变化或责任流转。它表达逻辑关系，不代表组件必须按图中的数量和位置部署。

```text
固定 Prompt + 固定 Tool Set
        ↓
按任务加载 Skill
        ↓
Router 选择 Skill 与 Tool
        ↓
运行时发现外部能力
```

Router + Skill 属于这一维度。它的价值是控制 Context 和动作空间，而不是创造一种新的 Agent Loop。

同一个 Single Agent 可以根据任务选择不同 Skill；Multi-Agent 中也可以让 Router 选择合适的专业 Agent。路由目标不一定只是 Skill，还可能是模型、Tool、Agent 或 Workflow 分支。

## 维度四：状态协调

状态协调定义执行者之间怎样保存和交换工作进度：

| 状态方式 | 适用情况 |
| --- | --- |
| 会话内状态 | 短任务、单次运行 |
| 持久化 Agent State | 跨会话恢复的单 Agent |
| Todo List | 线性或弱依赖任务 |
| Task Graph | 存在依赖、并行和阻塞关系 |
| Blackboard | 多个 Agent 围绕共享事实和产物协作 |

Blackboard 不是独立的 Agent 类型，而是一种共享状态模式。它需要定义写入权限、数据版本、所有权、冲突解决和事实生命周期。单 Agent 跨会话使用的外部状态文件，也可以看作一个简化的 Blackboard。

## 维度五：Runtime 编排

Runtime 编排定义状态转换怎样被真正调度和运行：

**代码块说明｜流程示意：** 这段文本图按箭头方向阅读，用来说明“维度五：Runtime 编排”中的执行顺序、状态变化或责任流转。它表达逻辑关系，不代表组件必须按图中的数量和位置部署。

```text
同步 while Loop
    → State Machine
    → Graph / DAG
    → Event-driven Workflow
    → Durable Workflow
```

Graph 是流程的表达和运行方式。Graph 中的一个节点可以是普通函数、一次 LLM 调用、一个完整 Agent Loop、人工审批或者另一个子图。

如果节点和边全部由程序预先固定，Graph 仍然是 Workflow。如果某个节点能够根据当前状态动态选择动作、生成任务或修改后续路径，这些局部才具有 Agent 性。

因此，Graph 不应该被当成 Agent 的最终进化形态。它更像承载 Workflow 和 Agent 节点的 Runtime 骨架。

## 用架构配置代替架构名称

设计具体系统时，可以用一张配置卡代替含糊的“我们采用某某 Agent 架构”：

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“用架构配置代替架构名称”落成可检查的结构化记录，主要字段包括 `decision_mode`、`execution_topology`、`capability_routing`、`state_coordination`、`runtime_orchestration`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
decision_mode: task_driven + local_react
execution_topology: single_agent
capability_routing: skill_router
state_coordination: task_list + workspace
runtime_orchestration: event_driven_loop
```

例如，一个 Coding Agent 可以选择：

**代码块说明｜结构示意：** 这段文本把“用架构配置代替架构名称”中的关键对象并列出来，帮助读者识别各自责任与边界。它用于概念建模，不代表唯一的产品命名或实现结构。

```text
决策模式：Task-driven，单个任务内部使用 ReAct
执行拓扑：Single Agent
能力组织：Router + Skill
状态协调：Todo List + Git Workspace
Runtime：Event-driven Loop
```

一个企业研究系统则可能选择：

**代码块说明｜结构示意：** 这段文本把“用架构配置代替架构名称”中的关键对象并列出来，帮助读者识别各自责任与边界。它用于概念建模，不代表唯一的产品命名或实现结构。

```text
决策模式：Plan-and-Execute
执行拓扑：Orchestrator + 多个研究 Agent
能力组织：按领域路由 Skill、Tool 和 Agent
状态协调：Task Graph + Blackboard
Runtime：Graph Workflow
```

这两个系统都不能被一个单独的架构名称完整描述。把设计拆回各自维度之后，团队才能分别讨论：是否真的需要多 Agent、路由是否准确、共享状态怎样治理，以及哪些流程必须保持确定性。

## 本章检查

- 是否明确了下一步动作由程序还是模型决定。
- 可以提前枚举的稳定路径是否优先使用 Workflow。
- Agent 是否只负责路径不确定、需要根据反馈探索的部分。
- 权限、审批、预算和验收是否保留在确定性边界中。
- 是否因为使用了 Tool Calling 就过早把系统定义为 Agent。
- 动态决策带来的收益是否足以覆盖额外的不确定性。
- 是否把 ReAct、Multi-Agent、Router、Blackboard 和 Graph 错当成互斥选项。
- 是否分别明确了决策模式、执行拓扑、能力组织、状态协调和 Runtime 编排。
- 是否能用一张架构配置卡准确描述当前系统。
