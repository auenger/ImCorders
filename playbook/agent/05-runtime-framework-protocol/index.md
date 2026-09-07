# Framework、Runtime 与 Protocol

作者：杨正武
来源：https://imcoders.cn/playbook/agent/05-runtime-framework-protocol/
更新：2026-08-12T00:00:00.000Z

区分开发框架、执行环境、外部协议与 Harness，建立不依赖具体产品的 Agent 系统分层。

---


前三部分已经定义了 Agent 的执行内核、状态连续性、行动能力与控制边界。接下来要回答更具体的问题：这个系统由谁持续承载？当一次执行跨越多个模型调用、工具调用和人工等待时，外部产品又怎样知道它正在运行、需要输入，还是已经结束？

这些问题不能只靠一段 Agent Loop 代码回答。`while` 循环描述计算内核，Runtime 才负责让这个循环在真实环境中获得身份、状态、资源和生命周期。

## 术语来源与适用范围

Framework、Runtime、Protocol 和 Harness 都不是 Agent 领域独有的词，也没有一套被所有产品共同采用的分层标准。真实产品经常同时跨越多层：例如 [LangGraph](https://langchain-ai.github.io/langgraph/index.html)把自己描述为 orchestration framework 与 runtime，[OpenAI Agents SDK](https://openai.github.io/openai-agents-python/)既提供 Agent、Tool 等构造抽象，也内置 Agent Loop、Session 和 Tracing。因而，本章按**责任**区分概念，不按产品名称给厂商或开源项目归类。

本章所说的 `Framework`，指开发者用于声明和组合 Agent 的编程抽象；`Runtime` 指让一次执行持续推进并管理其生命周期的系统责任。两者可以由同一个库实现，也可以分别位于 SDK、应用进程和远程服务中。这里的边界用于架构分析，不表示 Framework 只能参与构建阶段，也不表示 Runtime 必须是独立部署的常驻服务。

`Protocol` 在这里是“系统边界上的外部契约”这一类概念，不是名为 Agent Protocol 的单一标准。现有协议各自覆盖不同边界：[MCP](https://modelcontextprotocol.io/docs/learn/architecture)聚焦 AI 应用与 Tool、Resource 等外部能力之间的上下文交换，[A2A](https://a2a-protocol.org/latest/specification/)定义远程 Agent 之间的 Message、Task 与 Artifact，[AG-UI](https://docs.ag-ui.com/concepts/architecture)定义 Agent 后端与用户界面之间的 Run 和 Event。本文使用 `Runtime Protocol` 作为描述性统称，具体实现可以采用其中一项、多项或自定义 API。

`Harness` 原本广泛用于测试和工具系统；在 Agent Engineering 中，它又被用来描述模型之外让 Agent 能够可靠工作的脚手架、约束和反馈回路。[OpenAI 的 Harness Engineering 实践](https://openai.com/index/harness-engineering/)涵盖仓库结构、工具、文档、验证和可观测性。本 Playbook 进一步把它限定为**面向特定工作域的工作方式**：它把 Runtime 能力与仓库规则、默认 Tool、权限和交付流程组合起来。Harness 的实现可能分布在仓库、CLI、CI 和平台中，不要求对应一个独立进程或产品。

因此，后文首字母大写的 Framework、Runtime、Protocol 和 Harness 是本 Playbook 的工作定义。阅读其他系统文档时，应比较它实际承担的责任，而不是只按术语名称做一一映射。

## 四个容易混用的概念

Framework、Runtime、Protocol 和 Harness 经常被放在同一句话中，但它们服务于不同角色。

| 概念 | 服务对象 | 核心职责 | 常见形态 |
| --- | --- | --- | --- |
| Framework | Agent 开发者 | 提供构造 Agent 的代码抽象 | SDK、Graph DSL、Agent 基类 |
| Runtime | 正在执行的 Agent | 承载状态转换与生命周期 | Worker、队列、状态存储、调度器 |
| Protocol | Runtime 的调用者 | 暴露稳定对象、操作与状态语义 | HTTP API、事件流、消息协议 |
| Harness | 使用 Agent 的工程团队 | 把能力组织成默认可用的工作方式 | 权限策略、工作区、检查点、验证门禁 |

![Framework、Runtime、Protocol 与 Harness 分层](/playbook-images/agent/runtime-layers.svg)

**Framework 是构造工具。** 它可以帮助开发者声明 Tool、拼装 Prompt、定义 Graph，或者实现模型供应商切换。程序构建完成以后，一部分 Framework 代码可能留在进程中，也可能只在开发阶段生成配置。

**Runtime 是执行环境。** 它接收目标，创建 Run，组装 Context，调用模型和 Tool，保存状态，处理等待、重试、取消与恢复。只要任务还没有进入终态，Runtime 就必须知道下一步由谁负责。

**Protocol 是外部契约。** 网页、命令行、调度平台或另一个 Agent 不应该依赖 Runtime 内部用了哪一种 Graph。它们需要依赖的是：怎样创建 Run，怎样提交输入，怎样订阅 Event，怎样取消，以及每个状态代表什么。

**Harness 是工作方式。** 它把 Runtime 的原始能力与仓库规范、默认 Tool、权限规则、验证命令和交付流程组合起来。Runtime 可能允许任意命令，Harness 则规定在某个代码库里应该先读什么、能改哪里、完成前必须运行哪些检查。

## Runtime 不等于一个常驻进程

本地 Demo 常把 Agent Runtime 写成一个 Python 进程：HTTP 请求进来，循环运行，最后返回文本。进程一旦退出，任务也随之消失。

生产 Runtime 更像一组协作责任：

**代码块说明｜流程示意：** 这段文本图按箭头方向阅读，用来说明“Runtime 不等于一个常驻进程”中的执行顺序、状态变化或责任流转。它表达逻辑关系，不代表组件必须按图中的数量和位置部署。

```text
API / Event Gateway
        ↓
Run Store ← Scheduler → Worker
    ↑                    ↓
Checkpoint Store     Model / Tool Executor
    ↑                    ↓
Artifact Store ← Event / Trace Pipeline
```

这些责任可以部署在一个进程中，也可以拆成多个服务。判断 Runtime 是否完整，不看服务数量，而看任务是否拥有独立于单个进程的持续身份和状态。

例如修复登录失败的 Run 在执行到一半时等待用户授权。此时 Worker 应该释放计算资源，Run 保持 `AUTH_REQUIRED`。数小时后授权到达，另一个 Worker 可以从 Checkpoint 恢复。对用户来说，这是同一次执行；对基础设施来说，它已经跨越了两个进程。

## Protocol 是 Runtime 的稳定边界

假设产品前端直接读取某个框架的内部节点：

**代码块说明｜Playbook 参考 Schema：** 这段 JSON 把“Protocol 是 Runtime 的稳定边界”落成可检查的结构化记录，主要字段包括 `node`、`next`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```json
{ "node": "tool_executor_3", "next": "planner_2" }
```

一旦团队把 ReAct 改成 Plan-and-Execute，前端、审计系统和任务平台都会跟着失效。更稳定的 Protocol 应暴露业务可依赖的语义：

**代码块说明｜Playbook 参考 Schema：** 这段 JSON 把“Protocol 是 Runtime 的稳定边界”落成可检查的结构化记录，主要字段包括 `run_id`、`status`、`required_input`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```json
{
  "run_id": "run_128",
  "status": "input_required",
  "required_input": {
    "type": "choice",
    "prompt": "是否允许修改认证配置？"
  }
}
```

Protocol 应该稳定的通常包括：

- 核心对象的身份与父子关系。
- Run 的状态、终态和合法转换。
- 创建、观察、输入、取消和重试等操作。
- Event 的顺序、幂等和断线补收语义。
- Artifact 的引用、类型和完整性信息。
- 错误分类、权限要求和兼容性规则。

内部应该保留自由的包括：

- 使用哪一种模型或推理提示。
- Agent 内部采用 ReAct、Graph 还是 Task List。
- Context 的具体裁剪算法。
- Worker、队列和数据库的部署方式。
- 内部 Step 的拆分粒度。

好的 Protocol 不会把实现细节冻结成公共 API，但也不能只返回一段含糊的自然语言。

## “Agent Protocol”不是某一个标准的专有名称

Agent 系统会同时使用多类协议：Tool 协议描述怎样调用能力，Agent-to-Agent 协议描述多个执行者怎样交换任务，UI 协议描述怎样向用户流式展示状态，Runtime Protocol 则描述一次执行怎样被创建和控制。

MCP、A2A、AG-UI 或某个云厂商的 Run API 都可能覆盖其中一部分，但不能因此把它们等同于 Agent 的全部协议层。一个 Runtime 甚至可以同时使用：

**代码块说明｜流程示意：** 这段文本图按箭头方向阅读，用来说明““Agent Protocol”不是某一个标准的专有名称”中的执行顺序、状态变化或责任流转。它表达逻辑关系，不代表组件必须按图中的数量和位置部署。

```text
前端 ← UI Event Protocol → Runtime
Runtime ← Tool Protocol → MCP Server
Runtime ← Agent Protocol → Remote Agent
业务平台 ← Run Protocol → Runtime
```

设计时先写清楚需要交换的对象和语义，再选择标准或实现方式。标准负责互操作，不替代系统建模。

## 怎样判断一个框架是否拥有完整 Runtime

“支持 Agent”可能只表示 SDK 能自动执行 Tool Call。可以用下面的能力检查表进一步判断：

| 能力 | 需要回答的问题 |
| --- | --- |
| 执行身份 | 每次 Run 是否有稳定 ID，断线后能否再次定位？ |
| 生命周期 | 是否区分排队、运行、等待、取消、成功和失败？ |
| 持久状态 | 进程退出后，目标、进度和等待条件是否仍然存在？ |
| 恢复 | 能否从明确 Checkpoint 继续，而不是从头重跑？ |
| 控制 | 外部能否安全地输入、暂停、取消和重试？ |
| 事件 | 状态变化能否订阅、排序、去重和补收？ |
| 产物 | 代码、报告等结果是否有独立引用和元数据？ |
| 副作用 | 是否记录幂等键、授权和不可逆动作结果？ |
| 可观测性 | 能否把一次 Run 关联到模型、Tool、成本和错误？ |
| 版本 | 能否还原这次执行使用的 Agent、Skill、Tool 和模型版本？ |

一个库即使没有内建这些能力，也可以成为 Runtime 的组成部分。真正危险的是系统实际没有这些语义，却因为用了 Agent Framework 而误以为已经具备生产能力。

## Harness 与 Runtime 在哪里相遇

Runtime 提供机制，Harness 提供面向具体工作域的默认政策。

例如 Runtime 支持 `request_approval(action)`，代码仓库 Harness 决定“修改测试文件可以自动执行，改 CI 配置需要确认，发布生产必须由指定角色批准”。Runtime 支持 Checkpoint，Harness 决定在修改前、测试通过后和提交前自动保存。

同一套 Runtime 可以承载代码 Agent、研究 Agent 和客服 Agent；不同 Harness 会给它们完全不同的能力边界。这个分层让执行基础设施保持通用，同时让工作规约贴近真实场景。

## 本章检查

- 系统是否明确区分构造代码、执行环境、外部契约和工作规约。
- Run 是否能脱离单个请求和单个 Worker 持续存在。
- Protocol 是否暴露稳定业务语义，而不是内部 Graph 节点。
- 是否按对象和操作选择协议，而不是把某个标准当成全部答案。
- Runtime 是否具备生命周期、持久化、恢复、控制、事件和副作用治理能力。
- Harness 是否把通用机制落实为当前环境的默认规则。
