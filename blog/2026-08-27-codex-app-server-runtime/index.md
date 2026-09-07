# Codex 开源 App Server：当 Agent Runtime 不再绑定 UI

作者：杨正武
来源：https://imcoders.cn/blog/2026-08-27-codex-app-server-runtime/
发布：2026-08-27T00:00:00.000Z
更新：2026-08-27T00:00:00.000Z

Codex 开放 App Server 后，认证、会话、审批、工具调用与流式事件都可以被新的客户端复用。本文结合 zcode-tui 的实践，讨论如何把官方 Agent 内核变成 TUI、IDE、移动端和自动化系统背后的通用 Runtime。

---


最近我在看 [Codex App Server 的开源实现](https://github.com/openai/codex/tree/main/codex-rs/app-server)，越看越觉得这不是一次普通的“开放接口”。

它真正开放的，是 Codex 的运行时边界。

过去我们使用一个 Coding Agent，通常只能在它提供的 CLI、IDE 插件或桌面 App 里工作。模型、Agent Loop、会话、工具调用、权限审批和 UI 被打包在一起。你可以调用模型 API，但如果想复用一整套成熟的 Coding Agent 能力，往往还得自己把 Runtime 重写一遍。

App Server 改变了这件事。Codex 官方文档把它定义为驱动富客户端的接口：认证、会话历史、审批和流式 Agent 事件都可以通过协议交给外部客户端。换句话说，**Codex 不再只是一个别人做好了界面的工具，它也可以成为我们自己产品背后的 Agent Runtime。**

这让我想到自己刚做完的另一个项目：[zcode-tui](https://github.com/xhls008/zcode-tui)。它解决的正是同一类问题：保留官方 ZCode 内核和官方账号通道，只把缺失的终端交互层补出来。

![一个开放的 App Server 核心连接终端、IDE、移动端与桌面端，底层 Runtime 不再被单一 UI 绑定](/blog-images/codex-app-server/hero-runtime-ui.jpg)

*UI 可以变化，Runtime 保持连续：App Server 把同一个 Agent 内核连接到不同的工作入口。*

## App Server 开放的不是模型，而是完整工作循环

如果只看第一眼，App Server 很容易被理解成“用 JSON 发 Prompt，再用 JSON 收答案”。如果只是这样，它和一次普通模型 API 调用没有本质区别。

真正有价值的是，它开放了一个 Agent 完成工作的全过程。

Codex App Server 使用双向消息协议。默认通过 `stdio` 传输 JSONL，也支持实验性的 WebSocket 和 Unix Socket。客户端连接后先完成 `initialize`，再创建或恢复 Thread，启动 Turn，并持续接收 Item 与状态事件。

```text
你的 UI / 产品 / 自动化系统
          ↕
      App Server
          ↕
认证 · Thread · Turn · Item · Approval · Tool · Sandbox
          ↕
      Codex Runtime
```

其中有三个很重要的运行对象：

- **Thread**：一段可以持续、恢复或分叉的对话；
- **Turn**：用户的一次请求，以及 Agent 为完成请求所做的工作；
- **Item**：一次用户消息、Agent 消息、命令执行、文件修改或工具调用。

客户端不再只能等一个最终字符串。它可以实时收到 `item/started`、`item/completed`、消息增量、工具进度和 `turn/completed`；可以中断当前 Turn，也可以在 Agent 正在运行时继续 `turn/steer`。

更关键的是，审批不是 UI 自己猜出来的弹窗，而是协议中的双向请求。当 Agent 想执行命令、修改文件或申请额外权限时，客户端可以展示风险，收集人的决定，再把结果交还 Runtime。这样换掉 UI 之后，安全边界并没有一起被换掉。

一个最小客户端的骨架其实很简单：

```typescript
const proc = spawn("codex", ["app-server"]);

send({
  method: "initialize",
  id: 0,
  params: {
    clientInfo: {
      name: "my_tui",
      title: "My Codex TUI",
      version: "0.1.0"
    }
  }
});

send({ method: "initialized", params: {} });
send({ method: "thread/start", id: 1, params: {} });

// 获得 threadId 后启动一次工作
send({
  method: "turn/start",
  id: 2,
  params: {
    threadId,
    input: [{ type: "text", text: "检查这个仓库并修复测试" }]
  }
});
```

难点从来不在于把这几条消息发出去，而在于正确消费一整条事件流：正文如何增量渲染，工具调用如何分组，审批如何阻塞与恢复，会话如何持久化，断线后如何处理，以及版本变化时如何兼容 Schema。

但只要这层协议存在，这些都变成了**客户端工程问题**，不再要求我们重写 Agent 本身。

## App Server、SDK 和 MCP 不是同一件事

这三种概念经常被放在一起，但它们解决的是三个方向的问题。

| 能力 | 谁驱动谁 | 更适合什么场景 |
|---|---|---|
| App Server | 你的产品驱动 Codex Runtime | 自定义 TUI、IDE、桌面端、移动端和富交互产品 |
| Codex SDK | 你的程序发起 Agent 任务 | CI、批处理、自动化任务和后端工作流 |
| MCP Server | Codex 调用外部工具与数据 | 数据库、业务系统、搜索、企业软件能力接入 |

MCP 是让 Runtime 向外长出手脚，App Server 是让我们给 Runtime 换一张脸。SDK 则更像在程序里发起一项工作，而不是完整接管交互生命周期。

理解这个边界之后，新玩法就出现了：**一个 Runtime 可以连接很多 MCP 能力，也可以同时拥有很多种客户端。** Agent 的大脑、工具生态和用户界面开始独立演进。

## zcode-tui：我为什么给官方 App 做了一层终端 UI

智谱的 ZCode 在国内有一个很现实的使用矛盾。

官方主要交付的是桌面 App，但很多程序员真正高频的工作环境是终端：SSH、tmux、无桌面 Linux 服务器，或者纯键盘工作流。想在这些环境里使用 ZCode，体验就会变得比较别扭。

另一方面，在我开发这个项目时，官方 App 通道又有 150% 的额度加成。于是问题变成了：**我想保留官方账号、官方内核和官方通道，但不想为了写代码一直开着桌面 UI，怎么办？**

我的答案是 `zcode-tui`。

它不是重新做一个 Coding Agent，也不是绕开官方服务直连模型。它是一个 Rust 编写的终端客户端：启动 ZCode 自带的 `app-server`，完成会话握手，把协议事件还原成终端里的流式对话、工具状态、权限确认、模型切换、上下文用量和 Agent Inspector。

```text
SSH / tmux / Terminal
        ↓
   zcode-tui
输入 · Markdown · 工具状态 · 审批 · 会话 · Agent Inspector
        ↓
ZCode app-server
        ↓
官方内核 · 官方认证 · 官方模型目录 · 官方服务通道
```

用户看到的是 TUI，但真正执行任务的仍然是官方内核。

![终端工作台通过流式事件管道连接底层官方 Runtime，桌面界面可以保持关闭](/blog-images/codex-app-server/zcode-tui-runtime.jpg)

*`zcode-tui` 负责终端交互，官方内核继续负责认证、会话、模型与工具执行。*

这层代理带来了几个直接收益：

- 不打开桌面 App，也能在终端里进行多轮对话；
- 正文、推理阶段和工具调用可以持续流式展示；
- 写文件等有副作用的工具仍会触发权限确认；
- 可以恢复会话、切换模型、压缩上下文、中断或转向当前回合；
- SSH 和 tmux 变成一等工作环境，而不是桌面端的降级版本；
- 认证和服务请求仍由官方内核处理，TUI 不需要自己保存一套供应商凭据。

![zcode-tui 实机界面展示流式对话、父 Agent、Subagent 与 Background Inspector](/blog-images/codex-app-server/zcode-tui-agent-inspector.png)

*概念图之外的真实界面：终端里可以查看流式输出、会话状态以及只读的 Agent Inspector。*

需要特别说明：`zcode-tui` 借鉴的是 App Server 这种架构思想，并不是 Codex App Server 的兼容客户端。ZCode 有自己的协议、事件和版本差异，两者不能混用。但它证明了同一个结论：**只要官方 Agent 把 Runtime 以 App Server 形式开放出来，社区就能在不复制内核的情况下补齐新的使用界面。**

## 有了 App Server，我们还能怎么玩

TUI 只是最直接的一种客户端。把 UI 和 Runtime 拆开以后，真正有想象力的是下面这些组合。

### 第一种：做面向具体人群的客户端

同一个 Codex Runtime，可以拥有完全不同的交互外壳。

运维工程师可以要一个只突出 Shell、日志和审批的终端界面；产品经理可以要一个隐藏命令细节、只展示计划和交付物的桌面端；代码评审者可以要一个以 Diff、证据和风险为中心的 Review Client；视障用户也可以拥有为读屏和语音优化的客户端。

过去做这些产品，需要顺便养一套 Agent 内核。现在可以把精力集中在目标用户真正需要的交互上。

### 第二种：让 Agent 进入原有软件，而不是让人迁移到 Agent App

很多企业不会因为 Agent 出现，就立刻放弃现有 IDE、研发平台、工单系统和内部工作台。

App Server 允许我们反过来做：把 Codex 嵌入用户已经在使用的产品。原系统继续负责账号、项目和业务流程，Codex Runtime 负责理解目标、执行工具和产出修改，客户端负责把过程呈现在原工作空间里。

这比“在每个页面右下角加一个聊天框”更进一步。聊天框只增加了入口，App Server 则允许产品接管会话、审批、状态和交付结果。

### 第三种：一个 Runtime，多块屏幕

开发者可以在终端启动任务，在手机上查看进度和处理审批，回到电脑后在 Diff 界面审查结果。监控大屏只展示正在运行的 Thread、耗时和失败状态，真正的输入仍来自个人客户端。

App Server 已经把工作过程变成结构化事件，因此多端同步不必靠抓取终端文本来猜测状态。

### 第四种：做 Agent Control Plane

当多个 Agent 同时工作时，单个聊天窗口很快就不够用了。团队需要看到谁在处理哪个仓库、哪些任务正在等待批准、哪些命令失败、产生了哪些文件修改，以及一次运行到底消耗了多少上下文。

这时 App Server 可以成为控制面的底层 Runtime 接口，上层再构建任务队列、审计、通知、人工接管和交付看板。

需要注意的是，控制面不能只做“更漂亮的多 Agent UI”。它还要把 Thread、Turn、Item、审批和最终 Artifact 对齐到团队自己的 Task、Run 和责任模型，否则只是同时打开了更多聊天窗口。

### 第五种：让领域 App 复用成熟 Agent Runtime

数据库工具、测试平台、低代码平台和运维系统，都可以把自己的领域能力通过 MCP 或 Tool 暴露出来，再用 App Server 把 Codex 深度嵌入产品。

这里会形成一个很有意思的分工：

```text
领域 App：数据、权限、业务规则、审计
Codex Runtime：推理、规划、上下文、工具编排
App Server Client：交互、展示、审批、通知
MCP / Tool：连接 Runtime 与领域能力
```

这条路径能避免每个 App 都从零重建模型适配、Agent Loop、会话存储和工具调度。产品真正要守住的，是领域权限和业务责任，而不是重复制造一个通用 Agent Runtime。

## 真正困难的地方，是把协议当成产品契约

App Server 给了入口，但一个可用客户端仍然要面对大量工程细节。

第一，**协议会演进**。Codex 可以按当前安装版本生成 TypeScript 或 JSON Schema，客户端应该锁定兼容版本，使用生成的类型，并对未知事件保持前向兼容。`zcode-tui` 的实践也反复证明，不能看到 CLI 版本号没变，就假设 App Server Schema 一定没变。

第二，**流式 UI 不是拼字符串**。一个 Turn 里可能交错出现正文、命令、文件变化、MCP 调用、审批和错误。客户端要维护明确的状态机，不能把所有事件都塞进一个聊天气泡。

第三，**审批权属于用户**。自定义 UI 不能为了“更自动”而吞掉 Runtime 发出的审批请求。权限、沙箱和高风险操作必须被清楚展示，批准结果也要可追溯。

第四，**认证通道和协议能力要分开看**。App Server 可以复用官方 Runtime 的认证流程，但具体套餐、额度、可用模型和客户端政策仍由服务提供方决定，而且可能变化。客户端不应该把某项阶段性权益写成永久协议承诺。

第五，**不要把实验能力直接当生产 SLA**。Codex 官方目前明确标注 WebSocket Transport 为实验能力；跨机器使用时还必须处理 TLS、鉴权、连接中断、背压和重试。最稳妥的起点仍然是本机 `stdio` 客户端。

## 我对 App Server 的判断

过去我们讨论 Coding Agent 生态，关注点通常是模型、Prompt、MCP 和 Skill。App Server 补上了另一块经常被忽略的拼图：**谁可以接管一个成熟 Agent Runtime 的交互生命周期。**

它让 Agent 产品第一次可以像数据库一样分层：内核负责稳定执行，协议负责暴露能力，上层可以长出很多不同的客户端和业务系统。

对开发者来说，这意味着不必在“接受官方 UI”和“从零重写 Agent”之间二选一。我们可以保留官方 Runtime，把终端、IDE、桌面端、移动端、企业工作台甚至语音界面做成自己的客户端。

`zcode-tui` 是我对这个方向的一次具体实践：我需要终端，于是给官方内核补了一个终端外壳。它没有创造新的模型，也没有重写 Agent Loop，只是把已经存在但被桌面 UI 包住的能力重新组织出来。

而 Codex 把 App Server 正式开源之后，这种玩法不再只是对某个产品协议的探索。它正在变成一条清晰的产品路径：

> **未来真正有生命力的 Agent，不会只拥有一个官方界面。它会成为 Runtime，被不同的人、不同的设备和不同的业务系统，以最适合自己的方式调用。**

## 再往前一步：App Server 与 DSH Plugin 是一体两面

写到这里，我又想到最近一直在研究的 [DeepSeek Harness（DSH）](/blog/deepseek-harness)。

DSH 走的是一条看起来不同、底层思想却高度一致的路线。Codex App Server 选择保留一套完整、稳定的 Runtime，再把认证、Thread、Turn、Item、审批和事件流开放给外部客户端；DSH 则把 Runtime 本身拆成插件系统：模型适配器是 Plugin，工具注册表是 Plugin，会话、上下文压缩、UI 集成乃至 Agent Loop 都可以被替换和组合。

两者开放的是 Runtime 的不同方向。

| 开放方式 | 开放的边界 | 生态会长出什么 |
|---|---|---|
| Codex App Server | Runtime 的上行交互面 | TUI、IDE、桌面端、移动端、企业工作台 |
| DSH Plugin | Runtime 的下行能力面与内部组装点 | 模型适配器、工具、业务连接器、Agent 策略、UI 扩展 |

App Server 回答的是：**谁可以驱动这个 Runtime，以及如何接住它完整的工作生命周期？**

DSH Plugin 回答的是：**这个 Runtime 由什么组成，以及第三方能力如何成为它的一等公民？**

可以把两条路径放进同一张结构图：

```text
终端 · IDE · 桌面端 · 移动端 · 企业工作台
                    ↕
                App Server
                    ↕
              Agent Runtime
                    ↕
                 Plugin
                    ↕
模型 · Tool · MCP · Skill · 领域 App · 业务控制面
```

上半部分解决“入口不应该只有一个”，下半部分解决“能力不应该全部写死在内核”。一个方向让客户端可以自由创新，另一个方向让 Runtime 的能力和产品形态可以自由组合。

这也是为什么我认为 App Server 和 Plugin 不是竞争关系，更不是二选一。

只有 App Server，没有插件化能力，第三方虽然可以做很多新界面，却仍然只能消费一套固定 Runtime；只有 Plugin，没有稳定的 App Server，Runtime 虽然可以装入很多能力，却仍可能被锁在一个官方交互入口里。

当两者同时存在时，Agent 才真正从“一个软件产品”变成“一层平台”：上面可以接不同的人、设备和工作流，下面可以接不同的模型、工具和领域系统，中间由 Runtime 统一处理会话、推理、权限和执行生命周期。

### 对传统 App 来说，这意味着两条转型路径

在之前那篇 [不重写 App，如何用 DSH Plugin 完成 Agent 化转型](/blog/app-to-agent-runtime-dsh-plugin)里，我讨论的是第一条路径：传统 App 保留自己的数据、权限、审批和审计，把领域能力通过 Plugin 交给外部 Agent Runtime。用户不必再逐页操作 App，Agent 可以在业务边界内直接调用它。

App Server 又提供了第二条路径：传统 App 不只是把能力交给 Runtime，还可以直接成为 Runtime 的新客户端。它可以在自己的产品界面里接住 Agent 会话、工具进度、审批请求和交付结果，而不是把用户赶到另一个 Coding Agent 窗口。

于是，一个成熟 App 可以同时扮演两种角色：

- **作为 Plugin，它向 Runtime 提供专业能力；**
- **作为 App Server Client，它为用户提供领域化交互。**

例如 Chat2DB 可以通过 Plugin 向 Agent 提供元数据发现、SQL 执行、DataWiki、审批和审计能力；同时，它也可以在自己的数据库工作台里接入一个 App Server Client，把 Agent 的计划、工具调用和结果直接呈现在用户熟悉的上下文中。

这时，App、Plugin 和 Runtime 不再是谁取代谁，而是形成一条完整链路：

```text
用户
  ↕
领域 App UI（App Server Client）
  ↕
Agent Runtime
  ↕
领域 Plugin / MCP
  ↕
App 的数据、权限、审批与审计
```

这里最有价值的变化是：**UI 不再垄断能力，Runtime 不再吞掉业务，Plugin 也不再只是几个 API 的包装。**

UI 负责让人理解和决策；Runtime 负责推理、规划与执行；Plugin 负责把领域能力、授权状态和业务语义带进工作循环；原 App 的控制面继续对最终业务结果负责。

### 开放 Runtime，可能比开放模型更重要

模型开放解决的是“谁来推理”，Runtime 开放解决的是“推理如何进入真实工作”。

真正可用的 Agent 不只有一个模型。它还有会话、上下文、工具、文件、权限、审批、事件、恢复和交付。App Server 把这条工作生命周期开放给客户端，DSH Plugin 把能力组装权开放给生态。它们共同指向一个判断：

> **下一阶段 Agent 生态的竞争，不只是模型能力的竞争，而是谁能提供一个上下都开放、又能守住生命周期和责任边界的 Runtime。**

从这个角度看，`zcode-tui`、Codex App Server 和 DSH Plugin 并不是三个孤立的项目。它们分别验证了同一件事：终端可以替换，官方 UI 可以替换，模型和工具也可以替换，但一套可靠的 Agent 工作生命周期不需要被每个产品重新发明。

---

## 参考资料

- [Codex App Server 官方文档](https://developers.openai.com/codex/app-server)
- [Codex App Server 开源实现](https://github.com/openai/codex/tree/main/codex-rs/app-server)
- [zcode-tui：ZCode 的终端 TUI fallback](https://github.com/xhls008/zcode-tui)
- [DeepSeek Harness：Agent 内核全开源，套皮就是商业软件](/blog/deepseek-harness)
- [不重写 App，如何用 DSH Plugin 完成 Agent 化转型](/blog/app-to-agent-runtime-dsh-plugin)
