# 不重写 App，如何用 DSH Plugin 完成 Agent 化转型

作者：杨正武
来源：https://imcoders.cn/blog/app-to-agent-runtime-dsh-plugin/
发布：2026-08-25T00:00:00.000Z
更新：2026-08-25T00:00:00.000Z

以 Chat2DB 与 DeepSeek Harness Plugin 的真实实践为例：保留原 App 的业务、权限与审计，把 DSH 作为外部 Agent Runtime，通过授权后的能力映射，让传统软件逐步变成 Agent 可驱动的应用。

---


最近我一直在同时改两个项目：一个是 Chat2DB App，另一个是我为 Chat2DB 和 DeepSeek Harness（DSH）写的 Plugin。

一开始看，它们像是一次普通集成：Chat2DB 提供数据库能力，DSH 通过插件调用这些能力。但真正把授权、工具注册、SQL 审批和审计链路跑通以后，我发现这件事的意义比“接一个 MCP”更大。

它提供了一条传统 App 转向 Agent 应用的新路径：

> **不必先把整个 App 重写成一套内置 Agent Runtime。保留原来的业务系统，把 DSH 作为外部 Runtime，再通过 Plugin 将 App 已经验证过的能力映射给 Agent。**

这不是在 App 旁边加一个聊天框，而是在改变 App 的驱动方式。

过去，人打开页面、理解状态、点击按钮、串联步骤。现在，Agent 可以在明确授权和业务约束下发现能力、组合步骤、等待审批并交付结果。原 App 没有消失，它从“人操作的软件”进一步变成了“人和 Agent 都可以调用的业务能力节点”。

![DeepSeek Harness 作为外部 Agent Runtime，通过 Plugin 驱动仍然保留业务控制权的 Chat2DB App](/blog-images/dsh-app-runtime/hero.png)

*Runtime 获得推理与编排能力，App 保留权限、审批与审计；Plugin 连接两侧，但不取代任何一侧。*

## 很多 App 缺的不是 AI，而是一个可插拔的 Runtime

传统 App 通常已经积累了大量真正值钱的东西：领域模型、业务规则、账号体系、数据权限、审批流程、操作日志，以及用户长期形成的使用习惯。

它真正缺少的，往往不是再接一个模型 API，而是下面这组 Agent 运行能力：

- 理解一个不完全明确的目标；
- 根据当前状态规划多步操作；
- 在执行中连续调用不同工具；
- 保留会话、上下文和中间状态；
- 遇到高风险动作时暂停并请求人类决策；
- 在失败、取消或恢复后继续收敛任务。

如果每一个 App 都在内部重写一遍模型适配、Agent Loop、上下文管理、工具调度、会话存储和审批交互，成本很高，而且很容易把原来的业务系统改得越来越重。

DSH 提供了另一种可能。它已经拥有 Agent Runtime 所需的通用底座，App 不需要再造一套。App 要做的，是把自己的领域能力以受控方式交给这个 Runtime。

这和给 App 增加一个 AI 功能有本质区别。

| 方式 | 核心变化 | 主要问题 |
|---|---|---|
| App 内加聊天框 | 增加一个自然语言入口 | 人仍然逐轮驱动，业务状态难以闭环 |
| App 内置 Agent Runtime | 在 App 内重建完整 Agent 栈 | 改造重、演进慢、每个 App 重复建设 |
| 外部 Runtime + Plugin | 保留 App 业务内核，外挂通用 Agent Runtime | 需要设计好授权、能力协议和责任边界 |

第三条路并不是对所有系统都更简单，但它非常适合已经有成熟业务能力、又没有内置 Agent Runtime 的 App。

## Chat2DB 与 DSH，不是谁集成谁

Chat2DB 和 DSH 的关系不是简单的上下游，更像是两套系统各自拿出自己最擅长的部分。

DSH 负责推理与执行：模型、Agent Loop、上下文、会话、工具调度和交互界面。Chat2DB 负责数据库领域控制：Agent 定义、数据源、DataWiki、有效数据范围、SQL Proposal、人工 Approval、ToolAttempt 和审计记录。

Plugin 位于两者之间，完成授权和能力映射。

![DSH Runtime、Plugin、Chat2DB Control Plane 与数据库领域能力之间的职责分工](/blog-images/dsh-app-runtime/architecture.png)

*DSH 决定下一步想做什么，Chat2DB 决定这一步能不能做、如何执行，以及执行后如何负责。*

```text
用户提出目标
     ↓
DSH Agent Runtime
推理 · 规划 · 会话 · 工具编排
     ↓
Chat2DB DSH Plugin
App 授权 · Token 管理 · 工具映射 · 状态桥接
     ↓
Chat2DB Agent Control Plane
Agent 身份 · DataScope · DataWiki · Approval · Audit
     ↓
数据库专业能力
元数据 · SQL · 查询 · 结果 · 变更控制
```

这条链路里，DSH 没有获得数据库账号密码，也没有复制 Chat2DB 的权限模型。它得到的是一个由用户在 Chat2DB 中明确选择、明确授权的 Agent 身份，以及这个身份当前允许使用的能力。

反过来，Chat2DB 也不需要知道 DSH 如何选择模型、如何维护上下文、如何规划下一步。对 Chat2DB 来说，DSH 是一个外部 Agent Runtime；对 DSH 来说，Chat2DB 是一个可授权的领域能力提供方。

两者不是互相侵入，而是通过 Plugin 形成闭环。

## Plugin 更像“App 授权”，而不是“API 包装”

传统插件经常只是把几个 HTTP API 改名后注册成工具。这样虽然能跑 Demo，却没有回答最重要的问题：**这个外部 Agent 凭什么使用 App 里的能力？**

Chat2DB DSH Plugin 的连接过程更接近一次 App 授权：

![DSH Plugin 从本机配对、用户选择 Agent、Token 交换到动态注册工具的完整 App 授权流程](/blog-images/dsh-app-runtime/authorization-flow.png)

*用户授权的是一个有明确能力与数据边界的 Chat2DB Agent，而不是整个 App 或底层数据库凭据。*

1. DSH 发起本机配对请求；
2. Chat2DB App 弹出授权窗口；
3. 用户不是简单点“同意”，而是选择一个具体的 Chat2DB Agent；
4. Chat2DB 检查这个 Agent 是否有效、是否属于当前用户、是否至少拥有一个数据范围或 DataWiki；
5. 双方使用一次性交换码建立 Connector Session；
6. Plugin 获得短期 Access Token 和可轮换的 Refresh Token；
7. DSH 根据授权结果动态注册 `chat2db_*` 工具。

这个过程授权的不是“整个 Chat2DB”，也不是某个数据库连接，而是一个带边界的 Agent。

这一区别很关键。因为一个 Agent 背后可以绑定：

- 允许访问的数据源、Database、Schema 和表；
- 排除访问的表；
- 最大返回行数和执行超时；
- 是否允许访问生产环境；
- SQL 的审批模式；
- 可以读取的 DataWiki；
- 可以调用的能力集合。

授权之后，这些权限也不是被复制到 Plugin 里冻结起来。Chat2DB 会在每次工具调用时重新计算有效权限。管理员收紧了数据范围，下一次调用立即受新的范围约束。

所以 Plugin 的本质不是搬运权限，而是**持有一份可撤销的委托关系**。

## 反方观点：HTTP MCP 加 OAuth，为什么还需要 Plugin？

这里有两个非常合理的质疑。

第一个质疑是：**“链接器背后的本质就是一套 HTTP MCP，外加 OAuth 链接。”**

从协议层看，这个判断基本成立。DSH Plugin 的远程调用最终就是通过 HTTP 访问 MCP Endpoint，授权过程也采用了配对、一次性交换码、短期 Access Token 和 Refresh Token 这套 OAuth2 很熟悉的思路。把它抽象成标准协议，确实比发明一套只能被 DSH 理解的私有 RPC 更有生命力。

但这里需要保持技术上的精确：当前实现是**OAuth2 风格的本机授权与 Token 交换**，并不等于已经完整实现了所有 OAuth2/OIDC 标准流程。它的授权界面在 Chat2DB App 内，访问对象是本机 Connector Session，授权主体是一个 Chat2DB Agent；这和面向互联网第三方应用的标准 OAuth Authorization Server 仍有边界差异。

第二个质疑是：**“任何 Agent 通过 OAuth2 做授权，再通过 MCP 连接就行了，没必要再做一个 DSH Plugin。”**

这个结论在一个前提下完全正确：如果所有 Agent 都能稳定支持同一套 MCP Transport、OAuth/OIDC、工具 Schema、审批状态、长任务恢复、会话关联和 UI 呈现，那么 Chat2DB 直接提供一个标准 MCP Server 就够了，不需要为每个 Runtime 单独写 Plugin。

所以，Plugin 不是协议的替代品。更准确的分层是：

| 层次 | 解决的问题 | 是否应该标准化 |
|---|---|---|
| HTTP MCP | Agent 如何发现和调用工具 | 应该尽量标准化 |
| OAuth2/OIDC | 调用方如何获得、刷新和撤销授权 | 应该尽量标准化 |
| Chat2DB Control Plane | Agent、DataScope、Approval、Audit 如何执行 | 由业务 App 负责 |
| DSH Plugin | DSH 如何把授权、工具、状态和 UI 接入自身 Runtime | 属于 Runtime 适配层 |

问题在于，**协议互通不等于产品接入完成**。

一个裸 MCP Client 通常只解决“能不能发出 `tools/call`”。而一个真正可用的 DSH Connector 还要处理：

- 在 DSH 的授权服务和凭据存储中登记连接；
- 把 Chat2DB 授权结果转换成 DSH 能理解的能力状态；
- 动态注册和注销 `chat2db_*` 工具；
- 在 Access Token 过期时安全地轮换 Refresh Token；
- 把 DSH 的会话 ID、调用 ID 映射到 Chat2DB Task、Run 和审计上下文；
- 将 `approval_required` 转成 DSH 中可等待、可恢复的工具状态；
- 把 Chat2DB 的 SQL Proposal、风险等级和执行结果渲染成 DSH 能展示的工具卡片；
- 处理本机 App 离线、授权撤销、重复调用和旧会话兼容。

这些工作不是 MCP 协议本身的职责，也不是 OAuth2 能自动完成的事情。它们属于**Runtime 语义适配**：把一个通用的远程能力服务，接入某个 Agent Runtime 的身份、生命周期、交互和观测模型。

因此，Plugin 的价值不是“让 DSH 才能访问 Chat2DB”。如果 Chat2DB 提供标准 MCP + OAuth，任何合规的 Agent 都应该能够访问它。Plugin 的价值是让这次访问在 DSH 里成为一个完整的一等公民能力，而不是让用户手工填 URL、复制 Token、自己处理审批轮询和错误状态。

也可以把两种方式放在一起比较：

| 接入方式 | 优点 | 代价 |
|---|---|---|
| 通用 MCP + OAuth | 跨 Agent、低耦合、标准生态容易复用 | 每个 Runtime 自己补齐授权 UI、状态和交互语义 |
| DSH Plugin | 深度接入 DSH 的授权、凭据、Tool UI 和生命周期 | 需要维护 DSH 适配代码，存在版本演进成本 |
| 两者同时提供 | 协议开放，体验又能针对 Runtime 优化 | 需要明确标准接口与 Plugin 的边界 |

我认为第三种方式更适合 Chat2DB：**底层能力以标准 MCP + OAuth 对外开放，Plugin 作为可选的 Runtime 体验适配层。**

这样不会把 Chat2DB 锁死在 DSH 生态里，也不会要求 DSH 用户放弃原生的授权和审批体验。未来接入 Codex、Claude、Hermes 或其他 Agent 时，可以先走通用协议；需要深度集成某个 Runtime 时，再增加对应 Plugin。

换句话说，Plugin 是“产品连接器”，不是“协议连接器”。协议连接器回答“能不能连”，产品连接器回答“连上以后，用户能不能安全、顺畅、可观测地完成一项工作”。

## 能力可以映射，责任不能外包

当前 Plugin 会把 Chat2DB 的数据库工具映射成 DSH 原生工具，例如数据源发现、数据库与表结构读取、SQL 执行、DataWiki 查询等。

但“注册成工具”不等于“把控制权全部交给 Runtime”。真正高风险的业务规则仍然留在 Chat2DB。

以 SQL 执行为例，一次调用并不是 DSH 把 SQL 直接发给数据库：

```text
DSH 生成工具调用
  → Plugin 携带 Connector Session、对话 ID 和调用 ID
  → Chat2DB 校验 Agent 与实时 DataScope
  → 创建 SQL Proposal 和 ToolAttempt
  → 低风险操作继续执行
  → 高风险操作返回 approval_required
  → Plugin 将当前工具调用切换为等待审批
  → 用户在 Chat2DB 中批准或拒绝
  → 同一个调用恢复并幂等重试
  → 结果与审计状态返回 DSH
```

这里有一个很重要的设计原则：

> **Runtime 决定下一步想做什么，App 决定这一步能不能做、怎样做，以及做完以后如何负责。**

DSH 可以规划“先读表结构，再查询昨日订单，最后分析异常分布”。但哪张表可见、SQL 是否越界、是否需要审批、执行结果如何留痕，仍由 Chat2DB 决定。

这让旧 App 的既有业务资产得以保留。Agent 获得了驱动力，却没有绕过 App 多年积累的安全边界。

## 从“功能菜单”到“Agent 可用能力”

传统 App 的功能组织方式主要面向人：页面、菜单、表单、按钮和弹窗。Agent 不适合操作这套表现层，它需要的是稳定的能力契约。

因此，App Agent 化的核心工作不是把所有按钮做成 Tool，而是重新识别业务中的能力单元。

一个合格的 Agent Tool 至少要回答五个问题：

| 问题 | 对应设计 |
|---|---|
| Agent 如何发现它？ | 清晰的名称、描述、输入 Schema 和能力元数据 |
| 谁可以调用？ | 用户身份、Agent 身份、数据范围与能力授权 |
| 调用会产生什么副作用？ | 风险等级、预览、幂等键和事务边界 |
| 什么时候必须停下来？ | Approval、Policy 和 Human-in-the-loop |
| 调用以后如何追溯？ | Task、Run、ToolAttempt、事件和 Artifact |

以 Chat2DB 为例，“执行 SQL”不是把编辑器的运行按钮远程按一下。它必须被重新建模为一个包含数据范围校验、Proposal、Approval、执行状态和结果证据的业务动作。

这也是 App 转 Agent 最容易低估的部分：**API 是技术接口，Tool 是带语义、权限、风险和责任的能力接口。**

## 一套可复用的 App Agent 化路径

从 Chat2DB 这个案例往外抽象，我认为一个已有 App 可以按六步逐渐完成 Agent 化，不必一开始推翻重做。

### 第一步：盘点真正的领域能力

不要从页面和按钮开始，而要从用户最终想完成的工作开始。

例如数据库 App 的能力不是“打开 SQL Console”，而是“发现数据结构”“查询数据”“解释执行计划”“提交数据变更”。项目管理 App 的能力不是“点击新建”，而是“创建任务并分配负责人”“变更任务状态”“发起评审”。

先把能力从 UI 操作中剥离出来，才能形成稳定的 Agent 接口。

### 第二步：定义可授权对象

不要直接授权整个 App。应该找到一个足够小、又能表达业务边界的授权对象。

它可以是 Chat2DB 中的 Agent，也可以是工作区、项目角色、业务账号或一组 Capability。关键是用户能理解自己授权了什么，App 也能在后续调用中重新校验。

### 第三步：建立 Plugin 与 App 的配对关系

Plugin 不应该保存主账号密码或数据库凭据。更合理的方式是由 App 完成交互式授权，发放短期 Access Token、可轮换 Refresh Token，并允许用户随时撤销 Session。

对于桌面本地应用，还要限制 loopback 访问，避免本地授权令牌被发送到远程地址。

### 第四步：把能力映射为 Tool，而不是裸 API

每个 Tool 都需要输入输出 Schema、超时、错误语义、风险信息和可展示的状态。对长耗时或需要审批的调用，还要支持暂停、轮询、恢复和取消。

Tool 名称只是最表层，真正的工作是把领域动作变成 Runtime 能可靠编排的协议。

### 第五步：保留 App 的控制面

身份、权限、业务规则、审批、审计和数据凭据应尽量留在原 App。Runtime 可以变化，模型可以变化，Plugin 也可以升级，但业务控制面必须继续作为唯一事实源。

这样，同一套 App 能力以后不仅可以接 DSH，也可以接 Codex、Hermes、Claude 或其他 Runtime，而不必为每一个 Runtime 重写安全规则。

### 第六步：让一次调用进入完整工作生命周期

真正进入生产以后，只有 Tool Call 还不够。系统还需要知道一次调用属于哪个外部会话、哪个任务、哪一次执行，是否等待过审批，是否发生重试，最后交付了什么。

Chat2DB Plugin 会透传 DSH 对话 ID 和调用 ID：一个外部对话对应一个可审计 Task，一次工具调用对应一个独立 Run。这个映射让 Agent 的自由规划最终落在可治理的工作记录上。

## 不是所有逻辑都应该搬进 DSH

外部 Runtime 很有吸引力，但不能因此把 App 退化成一组没有边界的 CRUD API。

以下能力适合留在 DSH：

- 自然语言目标理解；
- 多步规划与工具选择；
- 跨工具的信息整合；
- 会话上下文与推理过程；
- 通用 Skill 和 Agent 协作。

以下能力更应该留在 App：

- 领域数据和凭据；
- 权限与租户边界；
- 确定性的业务校验；
- 高风险动作的审批策略；
- 幂等、事务和副作用控制；
- 审计证据与最终业务状态。

判断标准很简单：**变化快、依赖推理和组合的部分放到 Runtime；必须确定、必须可信、必须由业务负责的部分留在 App。**

Plugin 不是用来掏空 App，而是用来重新划分 App 与 Agent Runtime 的边界。

## DSH Plugin 生态真正可能改变什么

如果这种模式成立，DSH 的 Plugin 生态就不只是增加几个模型、工具或 UI 组件。它可能成为传统软件进入 Agent 时代的一层分发协议。

过去，一个 App 的生态扩张依赖人去安装、学习和操作。未来，一个 App 可以通过 Plugin 同时获得两种新能力：

第一，**它可以把自己的业务能力授权给外部 Agent Runtime**。Agent 不需要理解 App 的页面，也不需要接触底层凭据，就能在业务边界内驱动它。

第二，**它可以复用 DSH 已有的 Agent 能力**。模型、Loop、上下文、Skills、工具编排和交互界面不再由每个 App 重复建设。

这会形成一种新的软件生态关系：

```text
过去：用户 ↔ App

现在：用户 ↔ Agent Runtime ↔ Plugin ↔ App
                         ↑             ↓
                     推理与编排     业务与治理
```

App 不再争夺唯一入口，而是努力成为 Agent 最愿意调用、用户最敢授权的专业能力节点。Plugin 也不再只是扩展包，而是一份包含授权、能力、状态和治理语义的生态契约。

## App 转型，不一定从重写开始

很多团队讨论 Agent Native 时，第一反应是重新设计产品、重建 Runtime、把原来的功能全部 Agent 化。这样做当然可能得到一套更彻底的新系统，但也可能在真正产生业务价值之前，就被庞大的基础设施改造拖住。

Chat2DB 与 DSH Plugin 给我的启发是，Agent 化可以从一条更现实的路径开始：

> **保留 App 已经做对的部分，外接一个成熟 Runtime，再把最有价值的业务能力逐个变成可授权、可编排、可审批、可审计的 Agent Tool。**

这条路径不是“给旧软件套 AI 壳”。它真正改变的是软件的调用者、能力边界和工作生命周期。

当一个 App 不仅能被人操作，也能被外部 Agent 在明确授权下可靠驱动；当 Runtime 不仅会推理，也愿意服从 App 的业务权限与审批；当 Plugin 能把两者连接成一条可撤销、可恢复、可追溯的链路，App 才真正开始从工具转向 Agent 时代的业务节点。

## 一个更理性的结论：Plugin 是加速器，不是魔法

写到这里，容易产生一个过于乐观的判断：把 App 打包成一个 DSH Plugin，放进生态里，很快就变成一个新产品。

这个判断有一半是对的。

如果原 App 已经拥有成熟的领域能力、权限模型和业务流程，那么 Plugin 确实可以快速提供一个新的 Agent 入口。模型、Agent Loop、上下文、工具编排和交互工作台由 DSH 提供，原 App 不需要重建整套 Runtime。对于做垂直软件的人来说，这是一条很有吸引力的产品化路径：**用较小的增量开发，把已有业务能力接到一个更大的 Agent 生态里。**

但另一半不能忽略：Plugin 并不会消除开发成本，只会改变成本的分布。

| 成本位置 | 需要解决的问题 |
|---|---|
| 协议接入 | MCP Transport、工具 Schema、错误和版本兼容 |
| 身份授权 | OAuth2/OIDC、Token 生命周期、撤销和权限范围 |
| 业务适配 | Agent、DataScope、Capability、审批和审计映射 |
| Runtime 体验 | 工具注册、状态卡片、等待恢复、取消和错误呈现 |
| 生产治理 | 幂等、重试、限流、观测、数据泄露和升级回滚 |

如果只是把几个 HTTP API 包成 MCP Tool，确实可以很快；但那得到的只是一个“能调用”的 Demo，不一定是一个用户敢长期授权、业务敢承担责任的新产品。

反过来，如果 Chat2DB 已经提供了标准的 MCP + OAuth2/OIDC 接口，那么 DSH Plugin 就不应该重复实现一套业务授权中间层。它可以变薄，只负责 DSH 的凭据接入、工具发现、状态呈现和生命周期适配。其他 Agent Runtime 也可以直接复用同一个标准接口。

因此，是否值得做 DSH Plugin，不应该问“Plugin 是不是比 MCP 更高级”，而应该问三个问题：

1. 原 App 是否已经有可以复用的、稳定的业务能力和控制面？
2. DSH 是否能显著降低 Runtime、交互和分发成本？
3. Plugin 带来的 DSH 原生体验，是否足以抵消额外的适配和维护成本？

可以用下面的判断来决定路径：

| 场景 | 更合适的选择 |
|---|---|
| 只需要让多个 Agent 调用能力 | 标准 MCP + OAuth2/OIDC |
| 需要快速在 DSH 中做出垂直 Agent 产品 | MCP + DSH Plugin |
| App 本身还没有权限、审批和任务控制面 | 先补 App 控制面，再谈 Plugin |
| 需要深度接入 DSH 的工具 UI 和运行生命周期 | 保留 DSH Plugin，但让业务规则仍在 App |

所以最终结论不是“有了 Plugin 就不用做协议”，也不是“有了 MCP 就不需要 Plugin”。更合理的架构是：

> **用标准 MCP + OAuth2/OIDC 保证生态互通，用 DSH Plugin 提供 Runtime 级产品体验，用原 App 的 Control Plane 守住业务责任。**

Plugin 的真正价值，是把已有能力更快地变成一种新的 Agent 产品形态；它的真正边界，是不能把协议、授权和业务治理重复造三遍。

这可能就是 DSH Plugin 生态最值得期待、也最需要克制的方向：**不是让每个 App 都重新开发一套 Agent 平台，而是让成熟 App 以最低必要的适配成本，获得新的驱动力。**

---

延伸阅读：[DeepSeek Harness：Agent 内核全开源，套皮就是商业软件](/blog/deepseek-harness) · [把 Chat2DB 变成一名数据库员工](/blog/database-agent-chat2db-work-os)
