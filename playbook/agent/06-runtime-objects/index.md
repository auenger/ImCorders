# Agent Definition、Thread、Run、Attempt 与 Step

作者：杨正武
来源：https://imcoders.cn/playbook/agent/06-runtime-objects/
更新：2026-08-12T00:00:00.000Z

用一组稳定对象描述 Agent 版本、长期上下文、一次执行、重试尝试和内部步骤。

---


一次聊天消息、一次模型调用和一次 Agent 执行不是同一个对象。如果全部塞进 `conversation`，系统很快会遇到几个问题：无法判断任务是否仍在运行，重试覆盖了原始错误，多次执行共享了错误状态，也无法还原某个结果究竟由哪一版 Agent 产生。

Runtime 需要一组比“会话”更精确的对象语言。

## 五个对象分别回答什么

![Agent Runtime 核心对象关系](/playbook-images/agent/runtime-objects.svg)

| 对象 | 回答的问题 | 典型生命周期 |
| --- | --- | --- |
| Agent Definition / Version | 谁以什么能力和规则执行？ | 多个 Run 复用 |
| Thread | 哪些交互共享一段长期上下文？ | 跨多个 Run |
| Run | 这一次要完成什么目标？ | 从提交到终态 |
| Run Attempt | 这是 Run 的第几次实际尝试？ | 一次领取或重试 |
| Step | Attempt 内发生了哪次状态转换？ | 一次模型、工具或控制动作 |

这不是要求数据库必须建立五张表，而是要求五种身份和生命周期不要互相覆盖。

## Agent Definition 必须版本化

Agent Definition 描述一个可执行配置：系统指令、默认模型、可加载 Skill、可用 Tool、权限策略和完成验证器。只保存 `agent_id` 不够，因为这些内容都会变化。

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“Agent Definition 必须版本化”落成可检查的结构化记录，主要字段包括 `agent_version`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
agent_version:
  agent_id: coding_agent
  version: agent_v7
  system_prompt_digest: sha256:8b71...
  model_policy: coding-balanced-v3
  skills:
    - repo-debug@2.1.0
  tools:
    - read_file@1
    - apply_patch@2
    - run_tests@1
  permission_policy: workspace-safe@4
  completion_policy: test-and-diff@3
```

Run 创建时应绑定不可变版本或配置摘要。否则同一个 Run 恢复后加载了新 Prompt 或新 Tool Schema，行为已经改变，审计记录却仍显示为同一个 Agent。

模型供应商可能不保证底层权重永久不变，因此系统至少要记录当时请求的模型标识、参数和路由策略。能够记录多少，取决于平台能力，但不能只写“用了大模型”。

## Thread 是上下文容器，不是执行状态

Thread 组织一段长期交互。例如用户先要求调查登录失败，Run 完成后又要求补充回归测试；两个 Run 可以共享此前消息和 Artifact。

**代码块说明｜层级示意：** 这段文本图按缩进和树枝符号阅读，用来展开“Thread 是上下文容器，不是执行状态”中的父子关系与归属边界。它描述的是逻辑结构，不要求数据库或服务按同样层级拆分。

```text
Thread thread_42
├── Message：登录接口返回 500
├── Run run_128：定位并修复
├── Artifact：修复补丁
├── Message：再补一个兼容性测试
└── Run run_131：补充测试
```

Thread 不应该拥有唯一的 `running/completed` 生命周期。对话可以持续存在，而其中某个 Run 已经失败；同一 Thread 甚至可能按策略允许多个 Run 并发。把状态写在 Thread 上，会导致“这段对话完成了吗”这种没有明确答案的问题。

Thread 也不等于 Context。Thread 可以保存大量消息和引用，Runtime 每一轮只从中选择与当前决策有关的部分组装 Context。

## Run 是一次目标明确的执行

Run 从创建开始，到成功、失败、取消或超时结束。它拥有稳定目标、约束、生命周期和产物集合。

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“Run 是一次目标明确的执行”落成可检查的结构化记录，主要字段包括 `run`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
run:
  run_id: run_128
  thread_id: thread_42
  agent_version: agent_v7
  goal: 修复登录失败，并保持旧版 Token 兼容
  status: running
  current_attempt: 2
  input_revision: 4
  created_at: 2026-08-11T15:00:00+08:00
  deadline_at: 2026-08-11T17:00:00+08:00
  budget:
    max_steps: 40
    max_model_tokens: 120000
    max_cost_usd: 8
  latest_checkpoint_id: cp_019
```

Goal 应尽量结构化保存范围和完成标准，而不是只留一句聊天消息。用户后续补充约束时，可以增加 `input_revision` 并记录 Event，不应该悄悄覆盖原目标。

Run 还应拥有自己的预算、优先级、租约和终态原因。这些字段是调度和治理需要，不属于 Thread。

## Attempt 保留重试边界

Retry 不应该清空 Run 再假装第一次错误没有发生。Run 表示用户眼中的同一次任务，Attempt 表示基础设施或策略进行的一次实际尝试。

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“Attempt 保留重试边界”落成可检查的结构化记录，主要字段包括 `attempt`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
attempt:
  attempt_id: attempt_002
  run_id: run_128
  number: 2
  reason: worker_lost
  resume_from: cp_019
  status: running
  worker_id: worker_17
  lease_epoch: 3
  started_at: 2026-08-11T15:24:10+08:00
  ended_at: null
```

拆分 Attempt 有三个直接收益：

- 第一次失败的错误、成本和 Trace 不会被覆盖。
- 可以区分 Worker 故障重试与 Agent 策略主动换路。
- 迟到 Worker 的写入可以通过 `lease_epoch` 被拒绝。

并非所有 Retry 都适合留在同一个 Run。若用户改变目标、权限范围或输入材料，语义已经变成新任务，更适合创建新 Run，并通过 `parent_run_id` 或 `derived_from` 关联原 Run。

## Step 是可审计的最小状态转换

Step 不必等于模型的思考过程。它是 Runtime 能够观察和记录的一次执行动作，例如模型决策、Tool 调用、授权请求、Checkpoint 写入或完成验证。

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“Step 是可审计的最小状态转换”落成可检查的结构化记录，主要字段包括 `step`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
step:
  step_id: step_037
  attempt_id: attempt_002
  sequence: 12
  type: tool_call
  status: succeeded
  operation: run_tests
  input_ref: blob://inputs/8d2a
  output_ref: blob://outputs/91c4
  idempotency_key: run_128:test:auth-regression:v2
  started_at: 2026-08-11T15:31:04+08:00
  ended_at: 2026-08-11T15:31:42+08:00
```

Step 至少应记录：所属 Attempt、单调序号、类型、状态、输入输出引用、时间、错误分类和副作用标识。大段 Tool 输出可以放在 Blob 或 Artifact Store 中，Step 只保存引用与摘要。

Step 粒度要服务于恢复和审计。把每个 token 都当 Step 会制造噪声；把“分析并修复项目”当一个 Step 又无法定位失败。一个实用边界是：当动作可以独立失败、重试、授权或产生副作用时，应成为独立 Step。

## 一次执行怎样绑定所有版本

仅绑定 Agent Version 仍可能不够，因为 Runtime 可能动态选择 Skill、模型或 Tool。可以在 Run 保存初始 Definition，在每个 Step 保存实际解析后的版本：

**代码块说明｜结构示意：** 这段文本把“一次执行怎样绑定所有版本”中的关键对象并列出来，帮助读者识别各自责任与边界。它用于概念建模，不代表唯一的产品命名或实现结构。

```text
Run 固定：Agent Definition、目标、权限上限、Runtime 版本
Step 固定：实际模型、Prompt 摘要、Skill 版本、Tool Schema、输入输出摘要
```

这样既允许 Runtime 按场景路由，又能回答：“为什么第 12 步使用了这个模型？它看到哪一版 Skill？调用的 Tool 参数当时怎样定义？”

版本记录最好使用不可变 ID 或内容摘要。只记录 `latest`、文件路径或工具名称，未来无法还原。

## 贯穿案例：修复登录失败

对象拆分后，执行历史会变得清晰：

**代码块说明｜层级示意：** 这段文本图按缩进和树枝符号阅读，用来展开“贯穿案例：修复登录失败”中的父子关系与归属边界。它描述的是逻辑结构，不要求数据库或服务按同样层级拆分。

```text
agent_v7
└── thread_42
    ├── run_128：修复登录失败
    │   ├── attempt_001：Worker 进程丢失
    │   │   └── step_001 ... step_018
    │   └── attempt_002：从 cp_019 恢复并完成
    │       └── step_019 ... step_044
    └── run_131：补充旧版 Token 回归测试
        └── attempt_001
```

产品界面可以按 Thread 展示连续对话，任务平台按 Run 管理进度，基础设施按 Attempt 调度，工程师按 Step 定位问题。每个视角使用不同对象，却仍能沿父子关系回到同一条执行链。

## 本章检查

- Agent 的 Prompt、Skill、Tool、模型和策略是否拥有可还原版本。
- Thread 是否只负责长期上下文，而不承担 Run 生命周期。
- 每个 Run 是否有独立目标、预算、状态和终态原因。
- Retry 是否保留原 Attempt，而不是覆盖失败历史。
- Step 粒度是否足以支持错误定位、授权和副作用审计。
- 动态路由后的实际模型与能力版本是否记录在执行现场。
- 用户改变目标时，系统是否创建新 Run 或显式记录输入修订。
