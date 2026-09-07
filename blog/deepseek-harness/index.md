# DeepSeek Harness：Agent 内核全开源，套皮就是商业软件

作者：杨正武
来源：https://imcoders.cn/blog/deepseek-harness/
发布：2026-08-17T00:00:00.000Z
更新：2026-08-17T00:00:00.000Z

DeepSeek Harness 开源了，插件在疯狂涌现，软件行业已死。模型、loop、上下文、对话与 Session 管理全部插件化，套一层皮加插件就是产品。

---


DeepSeek Harness 开源了。

基于 [Cordis](https://github.com/cordiverse/cordis)，MIT 协议，一句话概括：**一切皆插件**。模型适配器是插件，工具注册表是插件，会话日志是插件，连 agent loop 本身都是插件。没有特权内核，每一层都能换，卸载时副作用自动撤销。

然后插件开始疯狂涌现。官方在 GitHub 上鼓励插件仓库打 `dsh-plugin` topic 方便被发现，Discord 社区开起来了，模型适配器、行业工具包、UI 集成，各路插件正在往这个生态里挂。开源没几天，已经能看到生态在起势。

**软件行业已死。** 这话不是危言耸听——是那 80% 人人重复造的内核，不会再有人从头写了。

我跟我朋友说过一句话，现在越来越觉得是这事的注脚：

> 核心模型、loop、上下文、对话管理、session 管理全都有了，直接套皮开发所有的插件，打包就是商业软件。

![两个 Q 版开发者把模型、会话、工具与工作流插件组装到同一个 Agent 内核上](/blog-images/deepseek-harness/plugin-ecosystem.webp)

*一个内核，周围挂满可替换的能力插件。*

## 内核不只有那六样

那句话拆开，每个词在文档里都有对应：

| 我说的 | 对应模块 | 职责 |
|---|---|---|
| 模型 | `llm/llm` | 消息与流式词汇表，适配器 seam（`ctx.llm`） |
| loop | `core/agent-loop` | 默认的 agent 驱动器（`ctx.agentLoop`） |
| 上下文 | `core/system-prompt` | 提示词片段与工具 schema 的组装（`ctx.systemPrompt`） |
| 对话管理 | `core/agent` | Agent 接口、活跃 agent 注册表、`agent/*` 事件（`ctx.agents`） |
| session 管理 | `core/session` | 仅追加的 SessionEvent 日志和内存存储（`ctx.sessions`） |
| 工具 | `core/tools` | 作用域化的工具注册表和带把关的执行流水线（`ctx.tools`） |

一个不缺。这不是巧合——这是 Agent 系统的最小公分母，任何人做 Agent 产品都得重写这六样，现在全开源了。

![两个 Q 版工程师把工具、对话、上下文、审批与连接能力叠成透明的模块化内核](/blog-images/deepseek-harness/core-layers.webp)

*模型、loop、上下文、会话与工具，不再是焊死的黑盒，而是可以重新组合的透明积木。*

但这只是明面上的清单。dsh 真正值得看的，是这六样底下藏着的东西。

### 会话日志是唯一事实源

上下文不是"攒变量"，而是**从日志投影**：会话日志是模型所见上下文的唯一来源，`deriveMessages()` 从日志投影出模型历史，fork、恢复、回放、遥测全派生自同一份事件流。它还立了一条运行时不变量：**模型可见即已记录**——抵达模型请求的一切都必须能从日志重建。这意味着调试、回放、审计是同一件事：你永远能回答"模型当时到底看到了什么"。这比上下文变量满天飞的方案严谨一个量级。

### 能力 seam：换一个提供方，换掉整个能力

seam 是"可替换能力"，三种角色分工：**Service Definition** 声明接口，**Service Provider** 实现它，**Consumer** 使用它（通常是面向模型的工具）。为什么换一个提供方就能改变整个产品？因为文件系统与进程提供方共享同一个执行世界——把它们指向远程沙箱，Bash、PTY、LSP 就全部跟着搬过去了，不需要为每个提供方写专属 fork。subagent 提供方也藏在同一接口后面：从"新建一个子 agent"到"把整轮委派给另一个产品"，都只是换实现。

### 上下文压缩：一个可选的 seam

长会话跑久了，上下文会失控。dsh 把压缩做成了**可选能力**：`dsh-compaction-basic` 是后端，`dsh-command-compact` 是命令，不属于 loop 主干。它用锁把整个操作包住：`compaction/start` → 生成摘要 → 写入摘要事件 + 用 `user/message` 的 replace 操作回写 → `compaction/end`。中途崩溃会表现为可检测的遗留锁，而不是虚假声称压缩完成。摘要通过日志里的 replace 落地——压缩前后，模型看到的仍是一份连续的会话日志，只是中间一段被摘要替换了。

### 审批与沙箱：fail-closed 的 HITL

`ctx.approval` 回答一个问题：这个具体操作能不能继续？结果域是闭合的：`allowed-once` / `rejected` / `cancelled` / `unavailable`——应答者缺失、不负责、抛异常，一律 `unavailable`，调用方 **fail-closed**：拿不到授权就是拒绝，不会放行。按会话策略只有两档：`ask`（问人）和 `never`（CI、无人值守，确定性拒绝）。审批事件成对落审计（`approval/asked` + `approval/decided`），UI 通道提供人类应答者，ACP 桥接层给自动化 agent 做机器决策。再加上 `pwsh-sandbox` 沙箱和 fs 意图守卫，这一整层就是给企业客户准备的。

### 工具执行流水线：一次调用过五关

一次工具调用不是"调就完了"：`tools/pre-execute`（钩子、权限、沙箱）→ 单调守卫 → `tools/execute`（超时、重试、指标）→ fs 意图守卫 → `tools/post-execute`（接受、拦截、替换、加上下文）→ 最终结果不可变、JSON 无损落库。钩子可以跨工具系列工作，而工具本身不需要耦合任何策略服务。Code Mode 的 `run_code` 也走同一条流水线，子调用携带父级 token——多步程序组合和单次工具调用受同一套治理。

### 生态互通：MCP、Skills、子代理、目标、工作流

这层亮点藏在包列表里：`dsh-mcp-client` 直接接 MCP 生态，Skills 是一等公民，subagent 提供方加 workflow worker-thread 支持并行编排，goal 子系统支撑跨轮次的长目标。回到标准模式预设的那句描述——文件编辑、Shell、检索、Skills、计划、目标、子代理、工作流——那不是口号，是这些子系统一一落地后的清单。

## "套皮"的技术实现

套皮在 dsh 里有正式名字：**Profile 与组合包（bundle）**。

一个 profile 是一份具名组装：列出叠放的组合包、存放插件、保存 patch 层。官方带 `web`（浏览器 UI）和 `headless`（一次性运行器）两个模板：

```bash
npx @deepseek-ai/dsh web        # 启动 Web UI
npx @deepseek-ai/dsh headless "跑一下测试"   # 一次性会话
```

配置树以空根为起点按序叠加：profile 列出的组合包 → profile 的 `cordis.patch.yml` → home 级 patch → 命令行 `--patch`。任何一层都能被下一层按 id 替换或插入。

所以"套皮"的完整技术栈是：**拿官方组合包打底（模型、loop、工具、session 全在里面），往上叠你自己的 patch，再加自己的插件包，就是一个新产品**。`dsh --profile web --dump-config` 能打印实际启动的整棵配置树，树上的任何条目都能被你换掉。透明到这个程度，没有"内核黑盒"可言。

![同一个发光 Agent 内核连接浏览器工作台、终端控制台和行业服务站三种产品外壳](/blog-images/deepseek-harness/product-shells.webp)

*同一份内核，接上不同的壳、工具与治理插件，就长成不同的产品。*

## 内置模式与自定义模式

dsh 开箱带两种模式，本质是两个 profile 模板：

| 模式 | 命令 | 干什么 |
|---|---|---|
| `web` | `dsh web`（或 `dsh --profile web`） | 浏览器 Agent 工作台，默认 `http://127.0.0.1:3080` |
| `headless` | `dsh --profile headless "跑一下测试"` | 无服务器的一次性运行器，跑完打印答案退出 |

`web` 和 `headless` 首次使用时从随附模板自动初始化，区别只在叠的组合包：`web` = `dsh-base` + `dsh-web-app`，`headless` = `dsh-base` + `dsh-headless`。**同一个 `dsh-base` 内核，接不同的壳就是不同的产品形态**——这句话就是套皮论的字面实现。

其他模式全是自定义的，用 `dsh plugin` 建：

```bash
dsh plugin --profile <name> <pnpm args>
```

它会往 `$DSH_HOME/profiles/<name>` 写一个 profile：`package.json` 里的 `dsh.profile` 字段声明叠哪些组合包，`cordis.patch.yml` 存你自己的 patch 层。我机器上已经这么干了一个：官方只有 web 和 headless，我自己装了个终端 UI 模式，package.json 长这样：

```json
{
  "name": "dsh-profile-dsh-tui",
  "dependencies": {
    "@deepseek-harness-tui/dsh-tui": "0.8.0"
  },
  "dsh": {
    "profile": {
      "bundles": [
        "@deepseek-ai/dsh-base",
        "@deepseek-harness-tui/dsh-tui"
      ]
    }
  }
}
```

内核还是那一份 `dsh-base`，只是把 web 壳换成终端壳。同样的路子，给某个行业加一套工具插件、审批策略、私有数据源，`bundles` 里多列几项——这就是"面向 X 行业的 Agent 平台"的出生方式。社区插件现在就是这么长的，连官方 web 模式也有人往上挂 `dsh-better-sidebar` 这类增强插件。

## Agent 预设：会话里的组装

上面说的模式管"启动"，预设管"会话"——**预设即一个会话的 Agent 所运行的插件组装：它的工具、提示词与能力**。复制一份既有预设改成自己的，或用"创造模式"让 Agent 帮你创建。

内置四个：

| 预设 | 标识 | 干什么 |
|---|---|---|
| 标准模式 | `standard` | 功能完整的编码 Agent：文件编辑、Shell、文件与网页检索、Skills、计划、目标、子代理和工作流 |
| PTC 模式 | `code` | 标准模式全部能力 + Code Mode SDK 呈现工具，让模型用一个 TypeScript 程序组合多步操作 |
| 极简模式 | `minimal` | 只有持久 bash 和 str_replace_editor 两个工具的编码 Agent |
| 创造模式 | `cordis` | 造预设用的预设：标准模式全部能力 + 运行时检查、插件实验、preset 创作指导 |

第四个最妙：**造预设的预设，本身也是个预设**。你在创造模式里调插件、做实验、让 Agent 帮你写 preset，跑通了复制一份就是新预设——预设的生产工具被预设化了，这比"预设不可编程"的框架高一个层级。

自定义的就更有意思了。比如"梁神模式"：主 Agent 与子 Agent 首轮都保持极简双工具，首次工具调用后才开放完整目录，压缩后重新锚定。先小口径开局、确认方向后再放开权限，肉眼可见地在控制上下文成本——这就是把"上下文管理"策略做成一个预设，变成可分发、可复用的产品形态。

所以 dsh 的"插件化"是两层的：**profile 管壳**（web / headless / tui），**preset 管行为**（标准 / PTC / 极简）。两层都是插件组装，都能复制改造。套皮论也是两层的：壳是套出来的，Agent 的行为方式同样是套出来的。

## 内核免费，什么值钱

内核开源了，套皮免费了，那商业价值在哪？三个地方：

**垂直化套件。** 通用内核是底座，赚钱的是行业场景。制造、金融、医疗、法律，每个行业的工具、审批流、数据源都不一样。内核 + 一套行业插件组合包，就是"面向 X 行业的 Agent 平台"，和做通用平台是两个量级的竞争。

**治理与服务。** 企业客户买的从来不只是软件，是权限管控、审计、合规、SLA。dsh 的沙箱、审批策略、会话日志天然是治理抓手——事件流完整，审计就有据可依。谁的插件把"可治理"做深了，谁就拿得到企业订单。

**生态位先占。** 插件生态是典型的赢家通吃。谁先做出高频、高质的插件，谁就定义了分发渠道。现在做工具插件、UI 集成、模型适配的人，吃到的是平台起飞的红利。

内核解决的是人人都要写的那 80%，剩下 20%——领域理解、信任、服务——最难复制，也最值钱。所以那句话应该加个后缀：**套皮只是入场券，插件和服务才是生意。**

## 十分钟跑起来

有 Node.js 就行，不用克隆仓库：

```bash
npx @deepseek-ai/dsh web
```

起的就是上面说的 `web` 模式。想加能力，官方有分步指南，几个高频扩展点：

- **加工具**：在 `ctx.tools` 上注册，schema 自动进提示词组装
- **加模型提供方**：在 `ctx.llm` 上注册适配器
- **加 UI 节点**：注册 `ConversationNodeDefinition` + keyed renderer
- **加持久会话状态**：扩展 `SessionEventMap`，从日志渲染和回放

开发者预览阶段官方明说了"会有破坏性变更"，现在适合尝鲜和做原型，不适合把生产系统押上去。但反过来，越早进场越早理解这套插件模型，等它稳定了，你的积累就是先发优势。

## 收尾

软件行业已死——字面意思：那 80% 的内核不会再有人从头写了。但做插件、做垂直、做服务的人，刚刚出生。

进一步阅读：

- [DeepSeek Harness 仓库](https://github.com/deepseek-ai/deepseek-harness)
- [官方架构文档（中文）](https://github.com/deepseek-ai/DeepSeek-Harness/blob/master/docs/architecture.zh.md)
- [Cordis 插件框架](https://github.com/cordiverse/cordis)
- [半天训练营：AI 研发转型的五堂课](/blog/harness-engineering-training)
- [Feature Workflow：融合 Bmad 与 OpenSpec 的 AI 工作流](/blog/feature-workflow)
