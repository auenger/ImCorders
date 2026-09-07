# Memory Architecture：Session、User、Agent 与 Long-term Memory

作者：杨正武
来源：https://imcoders.cn/playbook/agent/14-long-term-memory/
更新：2026-08-12T00:00:00.000Z

从时间跨度、归属范围和内容类型拆解 Agent Memory，并建立读取、写入、遗忘与修正机制。

---


“让 Agent 记住一切”听起来很有吸引力，工程上却通常意味着把对话历史、任务进度、用户资料、领域知识、临时观察和模型猜测全部塞进同一个 Memory Store。

问题不只是信息太多，而是这些信息的归属和生命周期完全不同：本次对话里刚刚确定的称呼，应该留在 Session；用户长期声明的语言偏好，可以进入 User Memory；多个用户都适用的工具经验，可能进入 Agent Memory；当前任务做到哪一步，则根本不应该由 Memory 承担。

因此，设计 Memory 的第一步不是选择向量数据库，而是先回答三个问题：

**代码块说明｜结构示意：** 这段文本把“Memory Architecture：Session、User、Agent 与 Long-term Memory”中的关键对象并列出来，帮助读者识别各自责任与边界。它用于概念建模，不代表唯一的产品命名或实现结构。

```text
它要保留多久？    Working / Run / Session / Long-term
它属于谁？        Session / User / Agent / Project / Organization
它保存什么？      Fact / Preference / Episodic / Summary / Procedural
```

这三个维度不能压成一条分类。`User Memory` 回答“属于谁”，`Long-term Memory` 回答“能否跨当前交互继续存在”，二者不是互斥类型。一条用户偏好可以同时是 User-scoped、Long-term、Preference Memory。

本书采用下面这条记忆治理原则：

> Long-term Memory 只保存跨 Run 仍可能改变未来决策的信息，并且必须知道它来自哪里、适用于哪里、可信到什么程度、什么时候需要重新验证。

长期记忆不能承担当前任务恢复。Agent 中断后从哪里继续，属于 Run State 和 Checkpoint；本次任务生成的正式结果，属于 Artifact；完整交互发生了什么，属于 Conversation 和 Event。

## 术语来源与适用范围

Memory 是认知科学和 Agent 系统都会使用的上位概念，但当前 Agent 工程并不存在统一的 Memory 对象模型、类型集合或读写协议。不同实现可能把对话摘要、用户偏好、向量检索库、知识图谱、跨 Thread Store，甚至项目说明文件都称为 Memory。

一些主流 Runtime 已经明确区分了其中的部分边界：[OpenAI Agents SDK Session](https://openai.github.io/openai-agents-python/sessions/) 保存特定 Session 的对话历史，并在多次 Run 之间自动加载；其 [Sandbox Agent Memory](https://openai.github.io/openai-agents-python/sandbox/memory/) 则明确与 Session Memory 分离，用于让未来 Run 复用提炼出的经验。[LangGraph Persistence](https://langchain-ai.github.io/langgraph/concepts/time-travel/) 用 Checkpointer 保存 Thread 范围的短期状态，用 Store 保存跨 Thread 的长期信息。[Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/agents/conversations/session) 也把 AgentSession 定义为跨多次 Agent Run 使用的 Conversation State Container。

这些实现证明 Session Continuity 与 Cross-session Memory 是不同问题，但它们没有形成统一命名。本章的分层是对这些工程边界的归纳，不是某个框架 API 的复制。

本章所说的“跨 Run”是指信息可以越过一次目标明确的 Agent 执行实例，在后续独立执行中再次被检索。`Run` 是本 Playbook 的统一设计术语；其他系统可能将同一层级称为 Task、Workflow Execution、Invocation 或 Job。长期记忆是否跨 Run，与底层采用哪个对象名称无关。

本章使用 Session、User、Agent 等名称描述**归属范围**，使用 Working、Session、Long-term 描述**时间跨度**，再使用 Fact、Preference、Episodic、Summary 和 Procedural 描述**内容类型**。这是结合常见记忆分类与工程存储需求形成的 Playbook 分析框架，不是公认且排他的标准分类。

本章提出的写入门槛、Memory Candidate、Memory Record Schema、读取排序公式以及 `supersedes`、`contradicts` 等关系，都是用于说明治理要求的参考设计。实现者可以使用数据库记录、向量索引、图结构或文件，但需要保留来源、作用域、时效和权限这些工程语义。

## 先把四个维度分开

Memory 设计至少包含四个正交维度：

| 维度 | 核心问题 | 常见取值 |
| --- | --- | --- |
| 时间跨度 | 信息什么时候失效 | Working、Run、Session、Long-term |
| 归属范围 | 信息属于谁，对谁可见 | Session、User、Agent、Project、Organization |
| 内容类型 | 保存的究竟是什么 | Fact、Preference、Episodic、Summary、Procedural |
| 存储与读取 | 怎样保存并重新进入 Context | Message Store、KV、Document、Vector、Graph、File |

向量数据库只回答第四个维度中的部分问题。它不能自动决定一条信息属于用户还是组织、应该保留一天还是一年，也不能判断模型推测是否有资格成为事实。

一条完整 Memory 应当能同时回答四个维度。例如：

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“先把四个维度分开”落成可检查的结构化记录，主要字段包括 `statement`、`temporal_scope`、`owner_scope`、`owner_id`、`content_type`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
statement: 用户希望技术报告先给结论
temporal_scope: long_term
owner_scope: user
owner_id: user_42
content_type: preference
storage: document_with_embedding_index
```

如果只保存最后一行的 embedding，就丢失了决定安全读取和正确使用所需的大部分语义。

## 按时间跨度拆解 Memory

### Working Memory：当前模型调用的临时工作集

Working Memory 通常对应当前 Context 中真正被模型看见的材料。它可能来自 Run State、当前 Observation、Session History 和长期检索结果，但只在当前一次或相邻几次决策中保持活跃。

它的核心操作是选择、排序、裁剪和压缩，前面的 Context Assembly 章节已经讨论。Working Memory 不等于持久化存储；内容离开 Context 后，模型就不再直接拥有它。

### Run Memory：当前任务的执行连续性

“Run Memory”有时被框架当作宽泛说法，但本 Playbook 不把它作为独立 Memory Store。当前目标、已确认事实、活动 Task、等待条件和恢复位置由 Run State 与 Checkpoint 承担。

这样划分是为了避免把“完成当前任务所必需的状态”和“未来可能复用的经验”混在一起。Run 完成后，Run State 不应整体晋升为长期记忆，只能从已验证结果中提取少量 Memory Candidate。

### Session Memory：保持一段连续交互

Session Memory 服务于同一个 Conversation 或交互会话的连续性。典型内容包括：

- 当前 Session 的消息历史和工具交互。
- 对较早消息生成的 Session Summary。
- 只在这次对话中有效的称呼、指代和临时约定。
- 多次 Run 之间需要延续、但不应带到其他 Session 的上下文。

例如用户在本次对话中说“后面把这个迁移项目简称为 Phoenix”，这是一条 Session Memory。除非用户明确希望长期保留，否则新 Session 不应自动知道这个简称。

Session Memory 可以存储在持久数据库中，以支持断线重连或跨设备继续；但“物理上长期保存”不代表“语义上可以跨 Session 使用”。它仍然受 `session_id` 限制。保留期限与可见范围必须分开建模。

### Long-term Memory：允许跨 Session 或 Thread 复用

Long-term Memory 指经过选择、可以跨当前 Session 或 Thread 在未来独立执行中重新检索的信息。它可能属于用户、Agent、项目或组织，并不天然属于某一种主体。

进入 Long-term Memory 的门槛应该明显高于 Session History：需要来源、作用域、写入理由、时效和治理策略。持久化一份完整聊天记录不等于已经形成长期记忆；只有当系统能选择性提取、在正确范围检索并允许修正时，它才具备长期记忆的工程语义。

## 按归属范围拆解 Memory

### Session Memory：只属于一次连续交互

Session Scope 是最窄、最容易解释的范围。读取时必须绑定 `session_id` 或等价的 Conversation / Thread 标识。Session A 的内容不应因为语义相似而被 Session B 召回。

适合保存：消息、Session Summary、临时称呼、当前对话的局部选择。通常不适合保存：跨用户规则、长期个人画像和全局工具经验。

### User Memory：围绕一个用户保持跨 Session 连续

User Memory 保存只对特定用户成立、并且未来交互仍可能有用的信息：

- 用户明确声明的语言、格式或无障碍偏好。
- 经授权保存的稳定个人事实。
- 跨 Session 延续的目标、项目关系或工作习惯。
- 用户对 Agent 结果做出的可复用纠正。

User Memory 必须绑定稳定的 `user_id`，不能用设备、Cookie 或相似姓名猜测身份。它还需要支持查看、纠正、导出和删除。涉及健康、财务、身份和位置等敏感事实时，应有更高写入门槛和更短保留策略。

“用户曾经这样选择”不等于“用户永远授权这样做”。User Memory 可以影响表达与建议，不能替代发送、购买、删除、发布等动作的本次权限检查。

### Agent Memory：围绕一个 Agent 配置复用经验

`Agent Memory` 是一个高度歧义的术语。有些资料用它泛指 Agent 的全部 Memory；本章在讨论 Scope 时，专指绑定到某个版本化 Agent Definition 或 Agent Family、可被它的多个 Run 使用的记忆。

适合进入 Agent Memory 的内容包括：

- 多次任务验证过的领域启发式规则。
- 某个 Tool 的稳定行为、限制和常见失败模式。
- 经过审核、尚未成熟到升级为 Skill 的程序性经验。
- Agent 自身评估得到的、对后续执行有用的非用户专属经验。

Agent Memory 默认不应该保存某个用户的私有事实。否则当同一个 Agent 服务多个用户时，就可能发生跨用户泄漏。需要用户信息时，应从 User Scope 显式读取，并继续受该用户权限约束。

Agent Memory 还必须绑定 Agent Version 或兼容范围。一条针对旧 Tool Schema 的经验，不能在 Tool 已升级后无条件继续生效。

### Project、Team 与 Organization Memory：共享知识需要治理

项目规范、团队约定和组织政策也常被称为 Memory。它们的共同点是作用域大于单个用户或 Agent：

- Project Memory：架构决策、仓库约束、部署兼容性。
- Team Memory：共同流程、术语和协作经验。
- Organization Memory：政策、合规要求和内部知识。

范围越大，写入权越不应该由单次 Agent Run 自动获得。组织政策通常应来自正式 Artifact 或权威系统，并经过审批，而不是由模型从几次对话中归纳后直接写入。

## User、Agent 与 Long-term 不是并列类型

下面这张矩阵展示了“归属范围”和“时间跨度”的组合关系：

| 归属范围 | Session 内使用 | 跨 Session 的 Long-term 使用 |
| --- | --- | --- |
| Session | 消息历史、临时称呼、Session Summary | 通常不允许；跨 Session 后应重新定范围 |
| User | 本 Session 中的用户选择 | 用户偏好、授权保存的稳定事实、长期目标 |
| Agent | 当前 Run 产生的候选经验 | Agent 专属启发式、Tool 经验、程序性知识 |
| Project / Organization | 当前任务加载的规则 | 架构决策、团队知识、正式政策 |

因此下面这些说法都可以成立：

**代码块说明｜结构示意：** 这段文本把“User、Agent 与 Long-term 不是并列类型”中的关键对象并列出来，帮助读者识别各自责任与边界。它用于概念建模，不代表唯一的产品命名或实现结构。

```text
User Long-term Preference Memory
Agent Long-term Procedural Memory
Project Long-term Fact Memory
Session-scoped Episodic Summary
```

设计数据库表或 API 时，不要用一个 `memory_type` 字段在 `session`、`user`、`episodic`、`long_term` 之间四选一。它们属于不同维度，应该分别建模。

## 作用域决定读取顺序，但不自动决定权威性

同一主题可能在不同 Scope 中出现。例如：

**代码块说明｜结构示意：** 这段文本把“作用域决定读取顺序，但不自动决定权威性”中的关键对象并列出来，帮助读者识别各自责任与边界。它用于概念建模，不代表唯一的产品命名或实现结构。

```text
Organization Policy：外部报告不得包含客户标识
Project Memory：本项目报告使用内部模板
User Memory：用户偏好先给结论
Session Memory：用户本轮要求输出详细附录
```

Context Assembly 需要同时加载相关内容，并按照约束强度、当前明确指令、作用域和新鲜度解决冲突。一个可用的参考优先级是：

**代码块说明｜结构示意：** 这段文本把“作用域决定读取顺序，但不自动决定权威性”中的关键对象并列出来，帮助读者识别各自责任与边界。它用于概念建模，不代表唯一的产品命名或实现结构。

```text
System / Organization Policy
    > 当前明确指令与本次授权
    > 当前环境中的权威事实
    > Session 内已经确认的约定
    > User Preference
    > Agent / Project 经验性 Memory
```

这只是参考决策顺序，不是通用协议。User Memory 不能覆盖组织安全政策，Agent Memory 不能覆盖用户本轮明确要求，历史偏好也不能覆盖当前环境事实。

## Memory 与其他对象的边界

![Agent 状态分层与长期记忆读写路径](/playbook-images/agent/state-layers-memory.svg)

| 对象 | 回答的问题 | 典型生命周期 |
| --- | --- | --- |
| Run State | 当前任务做到哪里 | 单个 Run |
| Checkpoint | 从哪个安全点恢复 | 单个 Run / Attempt |
| Artifact | 产生了什么可引用结果 | 可跨 Run 长期保存 |
| Conversation | 交互中说过和返回过什么 | Thread |
| Long-term Memory | 哪些过去信息值得影响未来决策 | 跨 Run，允许修正和遗忘 |

Artifact 可以成为 Memory 的来源，但两者不是同一个对象。例如一份架构决策记录是 Artifact；“这个项目禁止引入第二个消息队列”可以从中抽取为项目作用域的 Memory。Memory 应引用原 Artifact，而不是复制后失去来源。

## 按内容拆解：本 Playbook 使用的五类 Memory

下面切换到第三个维度：Memory 保存的内容是什么。这套分类的目的不是声明一套心理学或行业标准模型，而是为写入、检索和更新选择不同策略。同一种内容可以出现在不同 Scope，例如 Preference 既可以是本 Session 的临时选择，也可以是 User Long-term Memory。

### Fact：可验证事实

例如“生产环境使用 PostgreSQL 15”。Fact 需要来源、作用域和有效期。实时系统状态通常不适合长期缓存，除非明确规定重新验证策略。

### Preference：用户或组织偏好

例如“代码示例默认使用 TypeScript”“报告先给结论”。偏好不等于权限，也不能覆盖本次显式指令。

### Episodic：过去发生过的有用情节

例如“上次升级 auth-sdk 时，测试 fixture 的算法硬编码导致回归”。情节记忆保存的是可供类比的事件摘要，不应让一次偶然失败变成永远适用的规则。

### Summary：对一组历史内容的压缩

例如项目背景、长期协作上下文。Summary 是有损信息，需要记录覆盖范围和生成版本，不能当作原始证据。

### Procedural：经过验证的方法经验

例如“依赖升级后先运行配置差异检查，再执行定向回归”。如果方法足够稳定、完整并带工具和验收标准，它更适合升级为 Skill；Memory 可以保存轻量经验或 Skill 的选择信号。

## Session History 写入与长期记忆写入是两条路径

Session Memory 的主要写入通常是保存消息、Tool Result 和 Session Summary，以保证同一交互可以继续。它可以自动发生，但仍需要消息保留期限、敏感内容处理和压缩策略：

**代码块说明｜流程示意：** 这段文本图按箭头方向阅读，用来说明“Session History 写入与长期记忆写入是两条路径”中的执行顺序、状态变化或责任流转。它表达逻辑关系，不代表组件必须按图中的数量和位置部署。

```text
Current Turn
    ↓
Append Conversation Items
    ↓
Session Store
    ↓
Limit / Compact / Summarize
    ↓
Next Run in the same Session
```

User、Agent、Project 等跨 Session Memory 则需要“从一次经历中提取可复用信息”，写入风险更高：

**代码块说明｜层级示意：** 这段文本图按缩进和树枝符号阅读，用来展开“Session History 写入与长期记忆写入是两条路径”中的父子关系与归属边界。它描述的是逻辑结构，不要求数据库或服务按同样层级拆分。

```text
Run / Session / Artifact
          ↓
    Memory Candidate
          ↓
Evidence + Owner Scope + Consent + Risk Check
    ├── reject
    ├── human review
    └── merge / supersede / create
                  ↓
       Cross-session Memory Store
```

不要把每条 Session 消息都自动向量化后称为 User Memory。那只是一个可以跨 Session 搜索的聊天档案，尚未解决归属、准确性、写入意图和删除边界。

## 写入路径：先产生候选，再决定是否记住

下面进一步讨论跨 Session Memory 的治理路径。长期记忆不应该由模型在任意 Step 中直接写入正式存储。更安全的写入路径是：

**代码块说明｜层级示意：** 这段文本图按缩进和树枝符号阅读，用来展开“写入路径：先产生候选，再决定是否记住”中的父子关系与归属边界。它描述的是逻辑结构，不要求数据库或服务按同样层级拆分。

```text
Run / Conversation / Artifact
            ↓
      Memory Candidate
            ↓
  Extract + Normalize + Redact
            ↓
  Evidence / Scope / Risk Check
       ├── reject
       ├── human review
       └── merge / supersede / create
                    ↓
              Memory Store
```

写入通常包含六步：

1. **触发**：Run 完成、用户明确要求记住，或稳定模式重复出现。
2. **抽取**：从有来源的内容中提取一个最小、可独立判断的候选。
3. **定范围**：明确它属于 User、Agent、Project 还是 Organization，不能只靠内容相似度推断。
4. **规范化与风险检查**：统一实体、时间和类别，并处理 Secret、个人敏感信息、授权和保留期限。
5. **一致性检查**：搜索现有 Memory，决定新增、合并、冲突或替代。
6. **提交**：写入版本化记录，并保留证据引用。

### 同一事实应该写到哪个 Scope

可以用下面的参考路由判断：

| 候选信息 | 建议 Scope | 原因 |
| --- | --- | --- |
| “本轮把项目简称为 Phoenix” | Session | 临时约定，不应建立长期画像 |
| “用户明确要求以后默认中文回答” | User | 跨 Session 的个人表达偏好 |
| “这个 Tool 在 429 后必须读取 Retry-After” | Agent | 非用户专属的稳定执行经验 |
| “auth-service 生产环境兼容 PostgreSQL 15” | Project | 只对特定项目成立 |
| “客户数据不得进入公共模型” | Organization Policy / Artifact | 高权威规则，不应由普通 Memory 自动生成 |

如果无法判断 Owner Scope，默认留在较窄范围或进入人工审核，不要为了提高召回率写到更广范围。

## 什么信息达到写入门槛

可以用五个问题判断：

1. 它是否会在当前 Run 之外再次有用？
2. 它是否可能实际改变未来的选择、参数或输出？
3. 它是否有可信来源，而不是模型自己的未验证推测？
4. 它是否拥有明确作用域和生命周期？
5. 保存它是否符合隐私、安全和用户预期？

下面通常不应写入：

- 一次性的 Tool 输出和临时文件路径。
- 未验证的假设。
- 已经由权威系统实时提供、且变化频繁的数据。
- 可以从正式 Artifact 轻易重新推导的冗余长文本。
- Secret、访问令牌和不必要的个人敏感信息。
- “用户喜欢这个回答”之类无法稳定推断的偏好。

用户明确说“记住”会提高写入意图，但仍不能绕过安全和作用域检查。

## Memory Record 的参考 Schema

下面的 Schema 用于展示一条可治理 Memory 所需的语义，不是外部协议定义；实际字段名和存储方式可以不同，但不应只剩下 `text + embedding`：

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“Memory Record 的参考 Schema”落成可检查的结构化记录，主要字段包括 `memory`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
memory:
  memory_id: mem_77
  revision: 2
  content_type: fact
  statement: 生产部署必须兼容 PostgreSQL 15

  scope:
    owner_type: project
    owner_id: auth-service
    tenant_id: org_9
    environment: production
    session_id: null
    user_id: null
    agent_family: deployment-agent

  lifetime:
    temporal_scope: long_term
    valid_from: 2026-07-01
    expires_at: 2026-10-01
    verify_before_use: true

  provenance:
    source_type: artifact
    source_ref: artifact://deployment-guide/12
    source_revision: 6
    extracted_by: agent_v7
    observed_at: 2026-08-11T10:00:00+08:00

  confidence: 0.96
  status: active

  retrieval:
    keywords: [PostgreSQL, production, compatibility]
    embedding_ref: embedding://mem_77@v3

  governance:
    sensitivity: internal
    readable_by: [project_member, deployment_agent]
    writable_by: [project_owner, deployment_agent]
    retention_policy: project_lifetime

  supersedes: mem_61
```

`statement` 用于决策，`provenance` 用于追溯，`scope` 明确归属和可见范围，`lifetime` 控制时间跨度，`governance` 约束谁能读写。`agent_family` 表示哪些 Agent 可以消费这条 Project Memory，但不会把它变成 Agent 所有。Embedding 只是检索索引，不是 Memory 的事实主体。

## 读取路径：相关不等于可直接使用

Memory Read 路径也需要多阶段过滤：

**代码块说明｜流程示意：** 这段文本图按箭头方向阅读，用来说明“读取路径：相关不等于可直接使用”中的执行顺序、状态变化或责任流转。它表达逻辑关系，不代表组件必须按图中的数量和位置部署。

```text
Goal + Current Task + Entities
              ↓
 Resolve Session / User / Agent / Project Identity
              ↓
   Scope Filter + Permission Filter
              ↓
 Hybrid Retrieve（关键词 / 向量 / 图关系）
              ↓
  Rerank by relevance + authority + recency
              ↓
 Conflict / Expiry / Verification Check
              ↓
      Context Candidate
              ↓
     Context Assembly Budget
```

先解析当前 Session、User、Agent、Project 和 Organization 身份，再按作用域与权限过滤，最后做语义检索。否则一个与查询高度相似、但属于另一个用户、客户或项目的 Memory 可能排在最前面。

最终排序不应只看向量相似度。下面的公式只是表达需要综合考虑的因素，不是标准评分公式：

**代码块说明｜关系式：** 这段表达式把“读取路径：相关不等于可直接使用”压缩成便于比较的组成关系。它是分析模型，不是可执行代码，也不是要求实现者采用的行业标准公式。

```text
score = semantic_relevance
      × scope_match
      × authority_weight
      × freshness_weight
      × confidence
```

实际系统不一定使用乘法，但必须体现这些因素。一个 0.95 相似度的过期猜测，不应压过 0.78 相似度的最新权威记录。

## 检索结果以候选身份进入 Context

Memory 进入 Context 时要携带元数据和语气：

**代码块说明｜结构示意：** 这段文本把“检索结果以候选身份进入 Context”中的关键对象并列出来，帮助读者识别各自责任与边界。它用于概念建模，不代表唯一的产品命名或实现结构。

```text
[Project Memory | fact | verified 2026-08-11 | verify-before-use]
生产部署必须兼容 PostgreSQL 15。
Source: artifact://deployment-guide/12@rev6
```

不要把所有 Memory 包装成系统指令。Fact、Preference、Episodic 和 Summary 的权威性不同。特别是模型生成的情节摘要，应写成“过去曾出现……”而不是“必须……”。

需要重新验证的 Memory 可以先触发 Observation：读取部署配置，确认数据库版本，再把新事实写入 Run State。如果无法验证，则保留不确定性。

## 冲突、修正与遗忘

长期记忆系统必须允许过去的内容失效。常见关系包括：

- `supersedes`：新记录明确替代旧记录。
- `contradicts`：两个来源冲突，尚未完成仲裁。
- `narrows`：新记录把适用范围缩小。
- `confirms`：独立来源加强同一事实。

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“冲突、修正与遗忘”落成可检查的结构化记录，主要字段包括 `memory_change`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
memory_change:
  new_memory: mem_91
  relation: supersedes
  target: mem_77
  reason: 生产环境已完成 PostgreSQL 16 升级
  evidence: artifact://change-record/2026-09-14
```

不建议直接覆盖原记录。保留 revision 和关系，才能解释旧 Run 为什么做出了当时合理、现在过时的选择。

“遗忘”也不一定等于物理删除：

- **到期**：默认不参与检索，必要时可重新验证。
- **降权**：情节随着时间降低召回概率。
- **归档**：保留审计但不进入在线索引。
- **删除**：根据用户请求、隐私政策或保留期限彻底清除。

对于法律或隐私要求的删除，向量索引、缓存、备份和派生 Summary 都要纳入范围。

## User Preference 不能变成静默控制

偏好记忆经常被过度使用。Agent 从两次交互中推断“用户永远喜欢简短回答”，可能在需要完整报告时错误裁剪内容。

偏好至少区分：

- 用户明确声明，还是系统推断。
- 全局偏好，还是项目或任务偏好。
- 表达偏好，还是会改变外部动作的决策偏好。

涉及发送、购买、删除、发布等副作用的选择，不能仅凭长期偏好跳过本次授权。

## Agent Procedural Memory 何时升级为 Skill

当一条方法经验具备以下特征时，应从 Memory 升级为版本化 Skill：

- 被多个 Run 重复验证。
- 有明确触发条件和不适用条件。
- 依赖固定 Tool、资源或脚本。
- 有可以自动检查的完成标准。
- 变化需要评估和发布治理。

Memory 可以说“这个项目升级依赖后要重点检查配置覆盖”；Skill 则应包含检查步骤、脚本、所需 Tool 和验收方式。二者的工程强度不同。

## 贯穿案例：一次写入与下一次读取

登录问题修复后，系统可以把完整交互留在原 Session 的 History 中，但不会把全部 200 条消息直接提升为长期记忆。它从已验证 Artifact 中产生候选，并将 Owner Scope 明确为 Project：

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“贯穿案例：一次写入与下一次读取”落成可检查的结构化记录，主要字段包括 `content_type`、`statement`、`owner_scope`、`temporal_scope`、`source_ref`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
content_type: episodic
statement: auth-sdk 升级后，测试 fixture 的签名算法硬编码曾导致登录回归
owner_scope: project/auth-service
temporal_scope: long_term
source_ref: artifact://incident-report/93
confidence: 0.94
expires_at: 2027-02-11
```

三个月后另一次依赖升级开始。Router 在“认证依赖回归”任务中检索到它，但只把它作为候选线索。Agent 先检查当前 fixture；如果已经没有硬编码，就把该假设标记为不适用，而不是机械重复上次修复。

好的 Memory 缩短探索路径，但不会替代本轮证据。

## 本章检查

- 是否把时间跨度、归属范围和内容类型作为不同维度建模。
- Session Memory 是否只服务于同一连续交互，跨 Session 读取是否需要重新定范围。
- User Memory 是否绑定稳定身份，并允许用户查看、纠正和删除。
- Agent Memory 是否排除用户私有事实，并绑定 Agent Version 或兼容范围。
- Long-term Memory 是否只保存跨 Run 可能改变决策的信息。
- 每条记录是否有来源、Owner Scope、置信度、时效和治理属性。
- 未验证推测、临时输出和 Secret 是否被排除在长期写入之外。
- 检索是否先做权限与作用域过滤，再进行相似度排序。
- Memory 是否作为带来源的候选进入 Context，而不是伪装成系统规则。
- 冲突、替代、到期、归档和删除是否都有明确机制。
