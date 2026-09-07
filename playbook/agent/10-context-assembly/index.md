# Context Assembly：Agent 这一轮看见什么

作者：杨正武
来源：https://imcoders.cn/playbook/agent/10-context-assembly/
更新：2026-08-12T00:00:00.000Z

把目标、状态、Skill、观察和记忆组装成当前模型调用所需的有限工作集。

---


Agent 每次做决定时，并不是在“读取自己的全部记忆”，而是在读取 Runtime 为这一轮临时准备的一组输入。它可能包含系统规则、用户目标、当前任务状态、刚刚获得的观察、被选中的 Skill、工具定义、检索出的记忆和一小段对话历史。

这组输入就是当前 Context。它决定模型此刻能看见什么，也决定模型会忽略什么。

因此，Context Assembly 不是把已有内容拼接起来的模板工作，而是一条带有选择、排序、冲突处理和预算分配的运行时流水线。Agent 的很多“推理问题”，本质上都是组装问题：关键约束没有进入 Context，过期事实占据了高优先级，工具输出被截断，或检索结果虽然相关却不适用于当前任务。

## 术语来源与适用范围

`Prompt`、`Context`、Token Budget、检索和缓存都是 LLM 应用中的通用概念，但不同模型服务和 Agent 框架对它们的对象边界并不完全一致。

本部分统一使用 `Run` 表示**由一个明确目标触发、拥有独立 ID、生命周期和执行状态的一次 Agent 执行实例**。Run 可以持续一次模型调用，也可以跨越许多 Step、等待和恢复；它是逻辑执行边界，不等于某个操作系统进程或模型请求。

`Run` 是本 Playbook 选用的统一设计术语，不是跨框架标准对象。其他 Runtime 或协议可能使用 Task、Workflow Execution、Invocation 或 Job 表达相近概念。阅读本部分时，应按语义进行映射，而不是要求外部系统采用相同名称。

本章使用 `Context Assembly` 作为一个描述性工程术语，指 Runtime 在模型调用前选择、处理并排列输入材料的过程。这个问题和实践广泛存在，但业界没有一条必须遵守的统一 Context Assembly Pipeline。本章给出的六步流水线、预算比例和缓存键都是可落地的参考设计，不是某项协议的标准算法。

本章还引入 `Context Assembly Manifest`。它是本 Playbook 扩展的建议性对象，而不是行业标准；后文会单独解释它的设计动机和边界。

## Prompt 只是 Context 的一个来源

Prompt 通常指开发者或用户显式提供的指令；Context 指模型这一轮能够看见的完整输入。两者的关系可以写成：

**代码块说明｜关系式：** 这段表达式把“Prompt 只是 Context 的一个来源”压缩成便于比较的组成关系。它是分析模型，不是可执行代码，也不是要求实现者采用的行业标准公式。

```text
Context = Instructions
        + Goal
        + Run State
        + Current Observation
        + Selected Skill
        + Available Tools
        + Retrieved Memory
        + Relevant History
        + Output Contract
```

不同来源承担不同责任：

| 来源 | 回答的问题 | 典型更新频率 |
| --- | --- | --- |
| System / Policy | 必须遵守什么 | Agent 版本变化时 |
| Goal / Acceptance | 要完成什么，怎样算完成 | 用户修改目标时 |
| Run State | 当前做到哪里，还有什么未解决 | 每个有效 Step |
| Observation | 外部世界现在是什么样 | 每次读取或动作后 |
| Skill | 这类任务通常怎样做 | 能力选择变化时 |
| Tool Schema | 现在能执行哪些动作 | 权限或环境变化时 |
| Memory | 过去哪些信息可能改变本次判断 | 按需检索 |
| History | 之前说过和做过什么 | 按相关性选取 |

这张表带来一个重要结论：对话历史不是 Context 的主干，Goal、约束、当前 State 和新鲜 Observation 才是。把全部历史消息原样追加，既不能保证任务连续，也不能保证关键事实仍然有效。

## 本章采用的 Context Assembly 参考流水线

![Context Assembly：从信息源到当前工作集](/playbook-images/agent/context-assembly.svg)

一条可工作的组装流水线通常包含六步。

### 1. 固定不可牺牲的信息

首先预留系统规则、当前目标、验收标准、安全边界和输出契约。这些内容不能因为 Token 紧张而被随意截断。它们构成这一轮决策的边界。

### 2. 读取结构化 Run State

加载当前阶段、已确认事实、未决问题、活动 Task、最近动作结果和预算。State 应该以结构化摘要进入 Context，而不是要求模型从历史消息中重新推导进度。

### 3. 获得当前 Observation

如果下一步依赖外部环境，先读取最新事实。例如修改文件前重新读取目标片段，提交订单前重新读取订单状态。Observation 的新鲜度通常高于历史中的同名信息。

### 4. 选择能力和按需材料

Router 先选择少量相关 Skill 和 Tool，再根据当前 Task 检索文档、代码、历史 Artifact 或长期记忆。能力发现应先于最终 Context 组装，否则大量无关 Tool Schema 会直接消耗预算并扩大误选空间。

### 5. 解决冲突与标记来源

内容不能只按相似度排序。Runtime 还需要比较来源权威性、时间、作用域和证据级别。无法自动消解的冲突应显式保留，而不是让后出现的文本静默覆盖前者。

### 6. 在预算内排序、压缩和装配

最后按优先级分配 Token，必要时先删除低价值内容，再压缩可以压缩的内容。装配完成后生成 Context Assembly Manifest，记录这一轮究竟使用了哪些来源和版本。

## Token Budget 应该按责任分配

“所有内容统一截断到窗口上限”是最危险的预算策略，因为它会让长工具输出挤掉目标或安全约束。更稳妥的做法是为不同责任设置保底和上限。

例如，一个 32k Token 的模型调用可以采用类似分配：

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“Token Budget 应该按责任分配”落成可检查的结构化记录，主要字段包括 `budget`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
budget:
  total: 32000
  reserved_output: 5000
  immutable_instructions: 2500
  goal_and_acceptance: 1500
  run_state: 2500
  current_observation: 7000
  selected_skills_and_tools: 4500
  retrieved_material: 6000
  recent_history: 3000
```

这不是固定比例。代码修复任务会把更多预算给代码与测试输出，客服 Agent 会保留更多近期对话，研究 Agent 会扩大检索材料。但三条原则基本稳定：

- 先为输出和不可牺牲信息预留空间。
- 当前任务证据优先于低相关历史。
- 超预算时先移除，再摘要；摘要会引入信息损失，不能假装等价于原文。

## 哪些信息应该常驻，哪些应该按需加载

每轮常驻的信息应尽量短，而且只有在缺失时会系统性改变行为：

- Agent 身份和不可违反的政策。
- 当前 Goal、范围和验收标准。
- Run State 的紧凑投影。
- 当前 Task 与剩余预算。
- 这一轮输出的结构契约。

按需加载的信息包括：

- 某个 Skill 的完整操作说明。
- 与当前 Task 相关的文件片段或文档。
- 少量候选 Tool Schema。
- 长期记忆与旧 Artifact。
- 较早的对话和历史 Tool 结果。

判断标准不是“它是否有用”，而是：

> 如果这一轮看不到它，是否会明显改变下一步决策？

如果答案是否定的，就不应该为它支付当前 Context 的成本。

## 冲突信息不能靠排列顺序解决

假设 Context 中同时出现：

**代码块说明｜结构示意：** 这段文本把“冲突信息不能靠排列顺序解决”中的关键对象并列出来，帮助读者识别各自责任与边界。它用于概念建模，不代表唯一的产品命名或实现结构。

```text
用户偏好：默认使用 PostgreSQL 15        （三个月前的 Memory）
项目文件：postgres:16                    （本轮 Workspace Observation）
部署文档：生产环境仍为 PostgreSQL 15      （昨天更新的 Artifact）
```

三个事实并不一定互相否定，它们可能属于不同作用域。Runtime 应保留来源与范围，再交给 Agent 判断：本地测试面向 16，生产兼容性仍要覆盖 15。

冲突解析至少考虑：

1. **作用域**：组织、用户、项目、环境还是当前 Run。
2. **新鲜度**：信息何时被观察或验证。
3. **权威性**：实时系统状态通常高于历史摘要，明确用户指令高于推测。
4. **证据级别**：实际读取结果高于模型推断。
5. **可覆盖性**：安全政策不能被普通消息覆盖。

如果仍然无法确定，应把冲突写成未决问题：

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“冲突信息不能靠排列顺序解决”落成可检查的结构化记录，主要字段包括 `open_questions`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
open_questions:
  - question: 生产发布应以 PostgreSQL 15 还是 16 为兼容目标？
    candidates:
      - value: "15"
        source: artifact://deployment-guide@2026-08-11
      - value: "16"
        source: workspace://compose.yaml@sha256:...
    resolution: user_input_required
```

## Context Assembly Manifest 让输入可复现

`Context Assembly Manifest`（上下文组装清单）是本 Playbook 为 Context Assembly 扩展出的设计概念，不是某个现有 Agent 框架的标准对象，也不是 MCP、A2A、OpenTelemetry 等协议已经定义的通用术语。

> 概念来源说明：这是本 Playbook 为表达“Context 的来源与组装过程需要可追溯”而定义的建议性对象。后文给出的名称、字段和 Schema 都属于参考设计，不代表外部系统之间必须遵守的协议。

这里使用 `Manifest`，是因为它不负责保存另一份完整 Context，而是像一张配料清单一样，描述一次模型调用的 Context 由哪些来源组装而成，以及每项内容经过了什么选择和变换。具体系统完全可以把它实现为 Trace Metadata、Context Build Record 或内部审计记录，不需要照搬这个对象名称或 Schema。

引入这一设计概念，是为了补上“只记录最终输入”留下的解释缺口：保存最终 Prompt 文本可以回看模型看到了什么，却很难说明这些内容为什么被选中、来自哪个版本、哪些候选被排除，以及摘要是否造成了信息损失。因此，Context Assembly Manifest 应记录来源、版本、选择原因、Token 占用和裁剪方式。

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“Context Assembly Manifest 让输入可复现”落成可检查的结构化记录，主要字段包括 `context_assembly_manifest`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
context_assembly_manifest:
  context_id: ctx_8f2a
  run_id: run_128
  step_id: step_19
  model: model-x-2026-08
  token_budget:
    input_limit: 27000
    used: 18340
  entries:
    - kind: goal
      ref: run://run_128/goal@rev3
      priority: required
      tokens: 184
      transform: none
    - kind: run_state
      ref: state://run_128@rev18
      priority: required
      tokens: 732
      transform: compact_projection_v2
    - kind: observation
      ref: workspace://src/auth.ts@sha256:9a2...
      priority: high
      tokens: 2410
      transform: lines_40_132
    - kind: memory
      ref: memory://mem_77@rev2
      priority: medium
      tokens: 96
      transform: none
      reason: "项目数据库版本偏好"
  omitted:
    - ref: conversation://thread_42/messages/1..38
      reason: superseded_by_run_state
```

Context Assembly Manifest 不一定把敏感正文复制到 Trace 中，但必须让工程师知道用了什么，并能在权限允许时重新解析来源。它描述的是一次 Context 组装结果的来源和处理过程，不承担 Run State、Checkpoint 或长期记忆的职责。

## Context Cache 缓存什么

`Context Cache` 在本章中只是对 Context 组装过程中各类缓存的统称，不是一个标准化的 Runtime 组件。实际系统可能直接使用模型服务的 Prompt Cache、应用侧内容缓存或检索缓存。

Context Cache 有两种不同含义：

- **内容缓存**：缓存文档切片、Tool Schema 或 Skill 内容，避免重复读取和解析。
- **前缀缓存**：复用模型输入中稳定的 Token 前缀，降低延迟和成本。

不建议缓存“最终组装结果”并长期复用。因为 Run State、权限、环境 Observation 和 Memory 可能已经变化。即使使用缓存，也应该让缓存键包含来源版本：

**代码块说明｜关系式：** 这段表达式把“Context Cache 缓存什么”压缩成便于比较的组成关系。它是分析模型，不是可执行代码，也不是要求实现者采用的行业标准公式。

```text
cache_key = hash(
  agent_version,
  policy_version,
  run_state_revision,
  capability_set_version,
  source_content_hashes
)
```

缓存命中只说明输入可复用，不说明外部事实仍然新鲜。对时效敏感的 Observation 仍要执行 TTL 或重新读取策略。

## 贯穿案例：修复登录失败

Agent 正在修复“升级依赖后登录失败”。低质量 Context 可能包含 60 轮历史聊天、整个仓库 README 和 80 个 Tool，却没有最新测试错误。高质量 Context 则只包含：

**代码块说明｜结构示意：** 这段文本把“贯穿案例：修复登录失败”中的关键对象并列出来，帮助读者识别各自责任与边界。它用于概念建模，不代表唯一的产品命名或实现结构。

```text
目标与验收：登录集成测试通过，不能改变公开 API
当前状态：依赖升级已完成；失败发生在 session 解码
最新观察：test_login_refresh 期望 HS256，实际返回 RS256
活动 Task：确认签名算法配置来源
相关代码：auth/config.ts 与测试 fixture 的目标片段
Skill：依赖升级回归排查
Tool：read_file、search_code、run_test
```

模型能力没有变化，但可行动作会从“重新安装依赖、阅读 README、猜测配置”收敛为“读取算法配置的覆盖顺序”。这就是 Context Assembly 对 Agent 质量的直接影响。

## 本章检查

- Context 是否与完整对话历史明确分离。
- Goal、约束、当前 State 和输出预算是否有保底空间。
- 检索内容是否保留来源、版本、作用域和选择理由。
- 冲突事实是否被标记，而不是按文本顺序静默覆盖。
- 超预算时是否优先删除低价值信息，再进行有损摘要。
- 每次模型调用是否可以通过 Context Assembly Manifest 或等价记录解释输入构成。
