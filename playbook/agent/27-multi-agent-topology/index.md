# Orchestrator、Worker、Reviewer 与 Peer

作者：杨正武
来源：https://imcoders.cn/playbook/agent/27-multi-agent-topology/
更新：2026-08-12T00:00:00.000Z

比较集中编排、阶段流水线、独立审查和对等协作拓扑，并明确角色、控制权与最终责任。

---


决定使用多个 Agent 后，下一步不是给它们起不同名字，而是决定控制权、信息和责任怎样流动。相同的四个 Agent，可以组成一个中心化 Orchestrator，也可以形成 Planner 与 Executor 的阶段流水线，或以 Handoff 方式让控制权在 Peer 之间移动。

> Topology 描述控制权和消息怎样流动，Role 描述一个 Agent 对什么负责。二者必须分开设计。

## 术语来源与适用范围

Orchestrator、Worker、Planner、Executor 和 Reviewer 借用了分布式系统、工作流与软件工程中的通用角色语言。[Anthropic 的多 Agent Research 系统](https://www.anthropic.com/engineering/multi-agent-research-system)公开描述了 Lead Agent 协调并行 Subagent 的 Orchestrator-Worker 实现。[OpenAI Agents SDK](https://openai.github.io/openai-agents-python/multi_agent/)区分 Manager 调用 Agents-as-Tools 与 Handoff；[AutoGen Teams](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/teams.html)还提供 SelectorGroupChat 与 Swarm 等框架对象。

这些名称不是跨产品一致的协议术语。例如某个框架的 Supervisor 可能只负责选择下一位发言者，另一个系统的 Supervisor 还负责计划、预算和最终答案。本章使用的四类拓扑与角色模板是 Playbook 参考模型，实施时必须映射到具体 Runtime 的控制语义。

## 四类常用拓扑

![Multi-Agent Topology 对比](/playbook-images/agent/multi-agent-topology.svg)

| 拓扑 | 谁选择下一步 | Context 流动 | 适用场景 | 主要风险 |
| --- | --- | --- | --- | --- |
| Orchestrator-Worker | Orchestrator | 中心按任务裁剪后下发 | 多个可并行、可合并的子任务 | 中心瓶颈、摘要失真 |
| Planner-Executor | Planner 或确定性 Scheduler | Plan 与 Step Contract 逐阶段传递 | 计划与执行能力需要分离 | 计划过期、反馈链过长 |
| Executor-Reviewer | Executor 产出，Reviewer 判定 | Artifact 加证据，不共享草稿推理 | 高风险产物、独立质量门禁 | Reviewer 被执行者叙述锚定 |
| Peer / Handoff | 当前 Agent 或 Router | 控制权与精选 Context 转移 | 专业接力、对话路由 | 责任漂移、循环转交 |

真实系统可以组合拓扑。一个 Orchestrator 可以并行调用三个 Worker，再把组合 Artifact 交给独立 Reviewer；一个接待 Agent 可以 Handoff 给领域 Owner，领域 Owner 再把局部任务作为 Agent-as-Tool 调用。

## Orchestrator-Worker：中心拥有全局责任

Orchestrator 负责：

- 把 Goal 分解为可委派 Task。
- 为每个 Worker 选择最小必要 Context、Tool 和权限。
- 管理依赖、并发、预算、超时与取消。
- 收集 Artifact，处理缺失和冲突。
- 验证组合结果并决定 Root Run 是否完成。

Worker 不应该默认承担总目标。它只对 Delegation Contract 中的局部目标和验收标准负责。否则每个 Worker 都会重复规划全局任务，产生范围重叠。

Orchestrator 的瓶颈通常不是模型调用次数，而是它必须读完所有 Worker 输出。控制方法包括：

1. Worker 输出结构化 Artifact，而不是完整对话转储。
2. 结果使用摘要加证据引用，Root 可以按需读取原始材料。
3. 采用分层聚合，但限制树深，避免每层摘要继续丢失信息。
4. Scheduler、超时和状态归并尽量由确定性 Runtime 承担。

## Planner-Executor：把假设与执行证据分开

Planner 产出的是可修订 Plan，不是不可改变的命令。Executor 执行当前 Ready Step，并返回观察、Artifact 和阻塞原因。Runtime 根据证据推进或触发 Replan。

**代码块说明｜层级示意：** 这段文本图按缩进和树枝符号阅读，用来展开“Planner-Executor：把假设与执行证据分开”中的父子关系与归属边界。它描述的是逻辑结构，不要求数据库或服务按同样层级拆分。

```text
Planner → Plan v1 → Executor → Observation
   ↑                                |
   └──────── Replan Trigger ────────┘
```

适合拆分 Planner 与 Executor 的情况包括：规划需要大范围 Context，而执行只需要局部材料；执行身份拥有更高风险权限；或 Planner 使用高推理成本模型，Executor 使用便宜模型与确定性 Tool。

如果每个 Step 都必须回到 Planner 才能继续，Planner 会成为串行瓶颈。可把无争议的 Step 选择交给 Scheduler，只在依赖变化、验收失败或预算越界时触发 Replan。

## Executor-Reviewer：独立性来自信息和权限边界

Reviewer 不是让 Executor 再问自己一次。有效独立审查至少满足一项：

- 使用不同验证方法，例如测试而不是自然语言判断。
- 读取原始需求与 Artifact，而不是只读取执行者总结。
- 使用不同模型、Skill 或数据切片，降低共同失效。
- 没有修改生产对象的权限，只能给出 verdict 和 evidence。

Reviewer 的输出应至少包含 `verdict`、`failed_criteria`、`evidence_refs` 和 `confidence`。它不应直接把模糊建议改写成“通过”。高风险场景下，Reviewer 只能提出完成申请，最终门禁由确定性策略或人类批准。

## Peer 与 Handoff：控制权会移动

Peer 拓扑没有永久中心，但仍需要协议规则。当前 Owner 必须知道可以把控制权交给谁、交付什么 Context、何时取回或结束。

OpenAI Agents SDK 中，Handoff 让目标 Agent 接管后续对话；Agent-as-Tool 则让 Manager 保持控制。这一区分很好地说明：调用形式都可能表现为 Tool，但所有权语义不同。

Peer 模式适合领域接力，例如接待 Agent 识别退款问题后转给 Refund Agent。它不适合需要多个并行结果统一合并的任务，因为没有明确 Aggregator 时，最终责任容易随最后一次 Handoff 漂移。

必须设置：

- `current_owner`：当前对用户与 Run 状态负责的 Agent。
- `allowed_handoffs`：允许转移的目标集合与原因。
- `max_handoff_depth`：防止循环转交。
- `return_policy`：完成后返回上级、直接结束或继续转交。
- `final_owner`：谁可以提交最终完成申请。

## 角色应该按什么拆分

| 拆分依据 | 适用情况 | 示例 |
| --- | --- | --- |
| 专业领域 | Context 和方法显著不同 | 法务、数据、前端 |
| 权限边界 | 风险与身份必须隔离 | 只读审计、部署执行 |
| 执行阶段 | 输入输出契约稳定 | Planner、Executor、Reviewer |
| 环境边界 | Workspace 或外部系统独立 | Repo Worker、Browser Worker |

不要只按人格拆分，例如“严谨 Agent”“创意 Agent”。如果它们没有不同证据、能力、权限或责任，角色只是 Prompt 风格，而不是架构边界。

## 角色责任模板

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“角色责任模板”落成可检查的结构化记录，主要字段包括 `role_id`、`purpose`、`receives`、`may_read`、`may_write`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
role_id: migration_reviewer
purpose: 验证数据库迁移的可回滚性与兼容性
receives:
  - migration_diff
  - schema_snapshot
  - acceptance_criteria
may_read:
  - migration_test_results
may_write:
  - artifact:migration_review
must_not:
  - apply_production_migration
completion:
  schema: migration_review_v2
  required_evidence:
    - backward_compatibility_result
    - rollback_test_result
escalates_when:
  - production_schema_unavailable
  - destructive_change_detected
```

角色说明必须能被 Runtime 检查。只写“你是一名资深 Reviewer”无法约束输入、输出、权限和完成条件。

## 选择拓扑的顺序

1. 先确定最终 Owner 和 Artifact。
2. 再根据 Task Graph 判断并行还是接力。
3. 按 Context、权限与验证方法划分角色。
4. 决定控制权保留在中心，还是通过 Handoff 转移。
5. 最后选择框架对象与 API。

倒过来从“框架支持 Swarm”开始设计，容易让系统迁就库的抽象，而不是任务本身。

## 本章检查

- Topology 是否明确谁选择下一步、谁拥有当前 Run、谁判断最终完成。
- Orchestrator 是否只接收结构化结果和证据引用，而不是所有完整对话。
- Planner 的计划是否允许基于执行证据修订。
- Reviewer 是否具有真实的信息、方法或权限独立性。
- Handoff 是否更新 `current_owner` 并限制深度与回转规则。
- Role 是否声明输入、输出、权限、禁区、完成标准和升级条件。
