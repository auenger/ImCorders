# 理解 DSH Super-Agent 的编排思想

作者：杨正武
来源：https://imcoders.cn/blog/2026-11-03-deepseek-superagent-software-factory/
发布：2026-11-03T00:00:00.000Z
更新：2026-11-03T00:00:00.000Z

分析 DSH Super-Agent 的 Router、宿主任务系统和多个 Worker 如何协作，解释它与 Agent–Subagent 委派的区别，并结合 Silieco 讨论持续任务管理、工作归属与交接。

---


一个 Agent 正在修复问题时，团队又提出了新的需求，评审意见和 CI 消息也陆续到来。这些事情应该继续排在同一个对话里，还是分别交给不同的执行者？谁来判断它们属于已有任务，还是需要另开一项工作？

DSH Super-Agent 最值得关注的一条设计主线，就是把持续接收和分配工作的 Router，与具体推进任务的多个 Worker 分开。入口继续处理新消息，各个执行会话围绕自己的任务工作，问题和结果再回到协作现场。但只看“一个调度者带多个执行者”，很容易把它理解成普通的 Agent 调用 Subagent。要看清差别，还需要把负责保存任务、安排执行和恢复工作的宿主系统放进来。

本文讨论公开原型的设计思想，依据截至 2026 年 11 月 3 日的项目说明、设计文档与关键调用路径核对，没有实际运行效果或性能测试数据。[项目 README](https://github.com/deepseek-ai/dsh-superagent-prototype)明确说明，它是研究原型，非正式 DeepSeek 产品，公开版本与内部实现及文章描述存在差异。

## Router 接住持续到来的工作

Super-Agent 运行在 DeepSeek Harness 上，面向一个 GitHub 仓库，可选连接飞书。Harness 提供会话和工具等运行能力，Super-Agent 在其上组织常驻的任务处理。[项目说明](https://github.com/deepseek-ai/dsh-superagent-prototype)

Router 是负责路由的主会话。它面对的是不断变化的工作现场：有人直接提出请求，有人补充已有需求，还有一些消息只是讨论或执行背景。

它需要判断几个问题：这条消息是否值得启动工作？有没有已经负责这件事的任务？应该创建新任务，还是附加给原来的执行者？遇到停止请求，应该影响哪项工作？这些判断发生在具体编码之前，也会贯穿后续跟进。[授权与路由设计](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/main/docs/002-authorization.md)

假设三个互相独立的请求先后到来：修复导出错误、补充另一组接口测试、更新使用文档。Router 可以分别作出接受决定，宿主系统据此建立三个 Ticket，再启动对应的 Worker 会话。修复任务耗时较长，不必让另外两件事一直等在同一个执行对话后面。

下面的图把这条主线展开：Router 提交路由决定，宿主管理任务和派工，多个 Worker 独立推进；Worker 还可以在自己的任务内部委派 Subagent。三个任务只是示例，实际运行数量受并发上限控制。

<iframe src="/blog-assets/dsh-superagent/flow.html" title="Router 分配任务与多 Worker 并行执行流程图" width="100%" height="760" loading="lazy" style="border: 1px solid #8884; border-radius: 12px;"></iframe>

[单独打开交互流程图](/blog-assets/dsh-superagent/flow.html)，可放大查看 Router、宿主任务系统、Worker 与 Subagent 的关系。

## 多个 Worker 围绕各自的任务推进

每个 Ticket 都有自己的执行会话和工作目录。Worker 读取任务上下文，调用工具，推进工作，并报告进展、问题或结果。系统通过并发槽位管理执行，容量不足时任务排队；一个任务准备环境较慢，也不会要求其他任务的准备过程跟着停下。[执行设计](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/main/docs/003-execution.md)

独立会话让不同任务可以保留各自的工作上下文。修复导出问题的 Worker 不需要持续消化文档任务的所有细节，负责接口测试的 Worker 也不必等待另一个会话完成推理。各自的状态仍由共同的任务系统跟踪。

Worker A、B、C 也不代表预先固定好的开发、测试、文档岗位。公开原型按 Ticket 组织执行会话。图中的岗位内容只是便于理解的例子，不能据此推断系统已经具备按专业能力自动匹配人员的机制。

这种并行还保留着现实约束。不同 Worker 修改同一仓库时，仍可能发生代码冲突或需求冲突。独立目录有助于分别开展工作，但不会自动解决最终集成，也不构成操作系统层面的安全隔离。

## Router–Worker 与 Agent–Subagent 处于不同层次

两种结构都可以表现为一个 Agent 协调多个 Agent，都可以并行执行，也都可能拥有独立的上下文。并行数量和会话数量不足以区分它们。

Router–Worker 描述的是工作如何被组织：不断到来的请求归到哪项任务，谁负责推进，后续消息应该送给谁。Agent–Subagent 描述的是执行者如何委派：一个 Agent 为完成当前工作，把一部分研究或执行交给另一个 Agent。两种关系可以在同一系统里同时存在。

| 观察角度 | Super-Agent 的 Router–Worker | DSH 的 Agent–Subagent |
| --- | --- | --- |
| 工作从哪里来 | 外部消息经过准入和路由，形成 Ticket | 父 Agent 发起委派，给出执行要求 |
| 执行者归谁管理 | 宿主按 Ticket 创建或恢复 Worker | Subagent 服务维护父子会话关系 |
| 工作身份 | Ticket 独立于某一轮执行存在 | 子会话具有自己的身份，并与父会话关联 |
| 后续消息 | 任务订阅、人工跟进和宿主通知 | 父 Agent 或受控的子会话消息入口 |
| 完成后还要做什么 | 跟进交付、评审和任务状态 | 返回委派结果，必要时接受继续执行 |

这张表描述的是当前 DSH 和 Super-Agent 的职责划分。其他框架完全可以在 Subagent 机制上增加工单、授权和恢复能力，名称本身不构成限制。

### Worker 由宿主创建，并不挂在 Router 的父子会话树下

公开原型接受任务之后，会建立 Ticket、授权依据和第一轮 Assignment，再由 Executor 启动工作。Worker 会话使用与 Ticket 对应的稳定标识；需要继续执行时，系统可以找到或恢复这个会话。这条创建路径没有把 Router 设置为 Worker 的父会话。[任务创建与派工](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/6337fc823ce20251c8de8085948165c81aaa701e/src/core/tickets.ts#L37)、[Worker 会话创建](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/6337fc823ce20251c8de8085948165c81aaa701e/src/app/sessions.ts#L138)

这意味着“Router 分配任务”包含两部分动作。模型判断工作归属并提交路由决定；宿主检查规则、保存状态、安排执行。Worker 何时获得槽位、重启后如何恢复，不需要 Router 在对话里逐项记住并手动兑现。

Router 自身也被要求保持轻量。它负责评估和路由，Worker 负责调查和实施；没有待处理事项时，Router 应结束当前轮次，等待消息到来，避免用轮询和长时间等待占住入口。[Router 的职责约定](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/6337fc823ce20251c8de8085948165c81aaa701e/prompts/orchestrator.md)

这使它与常见的“主 Agent 拆解一道题，等待多个子 Agent，最后汇总答案”有所区别。Router 面对持续变化的任务集合，通常不承担每一项任务的完整解题和汇总过程。

### Worker 内部仍然可以委派 Subagent

修复导出错误的 Worker，可以请一个 Subagent 检查解析逻辑，再请另一个分析测试缺口。两个子 Agent 返回的信息用于推进原来的修复工作。它们不会因为被创建，就自动获得独立 Ticket 或独立的外部请求授权。

Super-Agent 会沿子会话的父子关系识别所属 Worker，把其工具使用约束到对应 Ticket；执行轮次结束时，也会清理相应的后台子 Agent 工作。[子会话归属与工具限制](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/6337fc823ce20251c8de8085948165c81aaa701e/src/app/sessions.ts#L299)、[后台执行管理](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/6337fc823ce20251c8de8085948165c81aaa701e/src/executor/background.ts)

于是，系统里同时存在两层协作：宿主围绕多个 Ticket 组织 Worker；每个 Worker 再决定怎样完成自己的工作，包括是否委派子 Agent。外层维护工作归属，内层分担执行过程。

### 长期运行并非 Worker 独有的能力

不能把这两层关系简化成“Worker 长期存在，Subagent 用完即走”。DSH 的子 Agent 支持单次执行，也支持可继续的会话；它可以后台运行、接收后续消息，并保留自己的会话记录。[DSH Subagent 设计](https://github.com/deepseek-ai/deepseek-harness/blob/main/docs/subsystems/subagent.md)

独立上下文也不构成充分区别。子 Agent 可以从新的上下文开始，也可以按提供方的机制继承父上下文。一个子 Agent 即使持续运行很久，仍可能只是在父 Agent 的委派关系下推进工作。

更有解释力的问题是：这项工作在系统中有没有独立的任务身份？外部消息能否持续找到它？谁决定它的授权、暂停、恢复和完成？Super-Agent 把这些责任交给了围绕 Ticket 运转的宿主机制。持久化会话解决“对话能否继续”，任务管理还要解决“这件工作应该怎样继续”。

## 任务分配之后，还要持续跟进

Router 将任务交出去，只完成了工作关系的建立。接下来会出现新的评论、测试失败、补充要求和人工回答，系统还得把这些信息送到合适的位置。

对于已有任务负责的跟进消息，原型通常让对应 Worker 先判断是否属于自己的范围。属于原任务，就继续处理；超出范围，再交回路由。这能减少同一条消息同时被多个执行者当成新需求的情况。[消息归属设计](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/main/docs/002-authorization.md)

例如，修复导出错误的 PR 收到“空数据时仍然失败”的评论，这条反馈应该回到负责修复的 Worker。如果评论又提出“顺便重做整个导出页面”，就需要重新判断范围。让执行者保留连续的任务上下文，同时允许它把新工作交回 Router，比每条消息都重新创建任务更符合实际协作。

反馈也有不同含义。Worker 可能正在执行，可能等待外部消息，可能提出问题需要人回答，也可能已经交付 PR，等待评审。`ready` 表示结果已准备好时，工作仍可能没有结束。[任务阶段设计](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/main/docs/003-execution.md)

多 Worker 编排包含分配、执行和跟进三个连续环节。 如果只画出 Router 向多个 Agent 发出指令，就看不到长期任务里很重要的那一半：谁接住问题，谁继续处理反馈，以及什么时候才算交付完成。

## 授权与状态支撑这套分工持续运行

Router 能不断分配任务，就需要明确哪些请求可以进入。DSH 区分明确请求和从消息中推断出的候选工作。推断候选默认处于 `observe` 模式，只记录判断；切换到 `auto` 后，匹配已启用规则的候选才可能被接受。明确请求在这些模式下仍可处理，所以 `observe` 不能理解为整个系统停止执行。[准入设计](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/main/docs/002-authorization.md)

授权回答的是工作为什么可以开始，状态记录则让系统知道工作已经走到哪里。Ticket 保存工作身份，Assignment 表示一轮执行，Mandate 保留授权依据。一个会话中断后，任务本身仍然存在，系统可以依据保存的状态继续跟进，而不必把它当成全新的需求。[领域模型](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/main/docs/001-domain.md)

从编排思想看，这些机制服务于同一条主线：Router 持续接任务，Worker 可以独立运行，执行暂停或失败之后，双方仍然找得到原来的工作关系。持久化和权限边界让这种分工有机会长期运转，但它们本身不等于外部操作永不重复，也不等于执行过程已经完全隔离。

## 与 Silieco 的协作思想互相印证

此前讨论 [Silieco 的人机协作思想](/blog/human-agent-collaboration-work-os/)时，我关注的是把人和 Agent 放进同一个工作系统：任务有负责人，复杂工作按 SOP 推进，遇到关键决定交给合适的人，产物和讨论留在共同的上下文里。

DSH Super-Agent 给这套思考提供了一个更聚焦的场景。面对仓库里持续到来的工作，它把路由和执行分开，让多个 Worker 各自负责具体任务。Silieco 关注的范围则延伸到团队协作：哪些工作交给 Agent，哪些交给人，前一阶段的结果如何成为下一阶段的输入。

| 设计问题 | DSH Super-Agent 的侧重点 | Silieco 的侧重点 |
| --- | --- | --- |
| 工作交给谁 | Router 判断任务归属，组织独立 Worker 执行 | 任务可以分配给人或 Agent，并进入团队流程 |
| 怎样同时推进多件事 | 不同 Ticket 由不同执行会话处理 | 不同负责人围绕各自任务协作，必要时按阶段交接 |
| 遇到新情况怎么办 | 跟进消息回到原 Worker，超范围交回路由 | 在任务上下文中补充信息，通过流程与人工判断调整工作 |
| 怎样确认交付 | 报告结果，继续跟进 PR 和评审 | 围绕阶段产物与 Gate 完成验收和交接 |

从 Router–Worker 与 Subagent 的区别再回头看，Silieco 的 Task 和 SOP 也更接近外层的工作组织。一个 Agent 为某个阶段调用几个子 Agent，属于阶段内部的执行选择；团队仍然需要知道整个任务交给谁、当前在哪个阶段、结果由谁验收。不能仅凭子 Agent 已经返回答案，就认定业务工作完成。

两者共同重视的是任务归属。Agent 接到工作之后，应当知道自己负责哪件事、做到什么程度、遇到问题找谁；协作系统也应当知道当前由谁推进。这使多个执行者能够同时工作，又能在需要交接时重新接上。

它们也保留着不同的组织方式。DSH 的 Router 更强调对持续到来的消息进行动态判断；Silieco 的 SOP 更强调可复用的阶段关系、责任分工和验收节点。临时修复任务可能只需要明确归属后直接执行，跨角色的业务工作则可能需要先约定好阶段和交接条件。

这种互相印证停留在设计思想上，不意味着 Silieco 采用了完全相同的 Router，也不意味着 Super-Agent 已经提供了完整的组织流程。对我而言，最有参考价值的是它把“接住工作”和“完成工作”分给了不同角色，并让任务在这些角色之间保持连续。
