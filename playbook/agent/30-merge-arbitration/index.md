# 结果合并、冲突仲裁与最终责任

作者：杨正武
来源：https://imcoders.cn/playbook/agent/30-merge-arbitration/
更新：2026-08-12T00:00:00.000Z

把多个候选结果经过校验、去重、冲突分类、仲裁和组合验证，提升为唯一正式产物。

---


多个 Agent 都返回结果，只说明并行执行结束，不说明总目标已经完成。局部结果可能使用不同假设、重复覆盖同一范围，或分别通过检查却在组合后破坏接口。Multi-Agent 的最后一个工程问题不是“收齐答案”，而是决定什么能进入正式 Artifact，以及谁对这个决定负责。

> Merge 组合相容结果，Review 判断结果是否达标，Arbitration 处理无法直接合并的冲突。三者是不同阶段。

## 术语来源与适用范围

Merge、Conflict Resolution 与 Code Review 来自版本控制和软件工程；Consensus、Quorum 与 Voting 来自分布式系统和群体决策。LLM Multi-Agent 研究也常使用 Debate、Critic、Judge 或 Majority Vote，但这些方法的正确性依赖任务、独立性与评估器，不能把“多数”当成事实证明。

[Anthropic 的多 Agent Research 系统](https://www.anthropic.com/engineering/multi-agent-research-system)强调并行 Subagent 的结果仍需由 Lead Agent 综合，并指出多 Agent 评估和可靠性更复杂。[OpenAI Agents SDK 的 Manager 模式](https://openai.github.io/openai-agents-python/multi_agent/)也把最终合并责任保留给 Manager。这些实现支持本章的责任原则，但不定义统一的 Merge Schema。

本章的 Pipeline、冲突分类、证据优先级和 Multi-Agent Evaluation Matrix 是 Playbook 参考设计。对可执行代码，应优先使用编译、测试和策略检查；对开放式研究，才需要更多人工或模型 Judge。

## 从候选结果到正式 Artifact

![Merge、Review 与 Arbitration Pipeline](/playbook-images/agent/merge-arbitration-pipeline.svg)

**代码块说明｜流程示意：** 这段文本图按箭头方向阅读，用来说明“从候选结果到正式 Artifact”中的执行顺序、状态变化或责任流转。它表达逻辑关系，不代表组件必须按图中的数量和位置部署。

```text
Candidate Artifacts
    ↓ Schema / Scope / Provenance Validation
Normalized Candidates
    ↓ Deduplicate and Detect Conflict
Compatible Set + Conflict Set
    ↓ Merge              ↓ Arbitration
Composite Candidate
    ↓ Integration Verification
Accepted Artifact or Rework
```

正式产物必须有明确的状态：

- `candidate`：某个 Agent 提交，尚未被 Root 接受。
- `validated`：Schema、范围和来源检查通过。
- `conflicted`：与其他候选存在待解决冲突。
- `accepted`：通过组合验证，成为当前正式版本。
- `rejected`：有记录地拒绝，保留原因与证据。
- `superseded`：被更新版本替代。

不要让“最后返回的结果”自动变成 Accepted。

## 先验证每个候选的契约

合并前检查：

1. `delegation_id` 与 `contract_version` 是否仍然有效。
2. 输出是否符合约定 Schema。
3. 是否覆盖了 Scope 中要求的对象，没有越界修改。
4. Required Evidence 是否齐全且可读取。
5. Artifact Digest、生成者、版本和时间是否可追踪。
6. 是否包含未声明假设或未知副作用。

不合格候选应退回 Rework，不要由 Aggregator 猜测缺失字段并静默补齐。

## 冲突至少分成四类

| 冲突类型 | 示例 | 默认处理 |
| --- | --- | --- |
| Fact Conflict | 两个 Agent 对同一 API 是否存在给出相反结论 | 回到原始来源或重新观察 |
| Requirement Conflict | 性能目标与合规要求无法同时满足 | 交给拥有业务权责的人或 Policy |
| Plan Conflict | 两种实现方案互斥 | 按约束、风险和实验比较 |
| Artifact Conflict | 两个 Patch 修改同一区域 | 三方合并、测试，必要时重新分工 |

Fact Conflict 不能靠语言更自信的一方获胜。Requirement Conflict 也不能由 Agent 擅自改写用户优先级。冲突类型决定谁有权仲裁和需要什么证据。

## 多数投票为什么不等于正确

多数投票只有在参与者判断近似独立、单个判断优于随机、问题可以明确判定时才可能提高可靠性。LLM Agent 常共享同一模型、Prompt、检索源和错误假设，输出高度相关；三个 Agent 一致可能只是同一偏差被复制三次。

更可靠的证据顺序通常是：

**代码块说明｜结构示意：** 这段文本把“多数投票为什么不等于正确”中的关键对象并列出来，帮助读者识别各自责任与边界。它用于概念建模，不代表唯一的产品命名或实现结构。

```text
外部真实状态 / 确定性测试
    > 权威原始来源
    > 任务专用验证器
    > 独立 Reviewer + 可检查证据
    > 多 Agent 一致意见
    > 单 Agent 自述
```

这不是跨任务绝对排序。例如需求解释最终可能由 Product Owner 决定，而不是测试决定。关键是先为每种冲突声明 Authority，而不是临时让 Judge 自由裁决。

## Arbitration Record

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“Arbitration Record”落成可检查的结构化记录，主要字段包括 `arbitration_id`、`root_run_id`、`conflict_type`、`subject`、`candidates`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
arbitration_id: arb_71
root_run_id: run_100
conflict_type: fact
subject: api.supports_status_filter
candidates:
  - artifact://api-review/12
  - artifact://ui-review/19
authority:
  type: executable_probe
  ref: test://contract/status-filter
decision: candidate_api_review
reason: 集成测试与当前 OpenAPI 均确认支持该字段
evidence_refs:
  - artifact://test-results/882
  - artifact://openapi/current#line-418
decided_by: policy:contract-verification-v3
created_at: 2026-08-12T10:22:00Z
```

仲裁记录必须保留被拒候选。后续环境变化或发现验证器错误时，团队需要知道当时有哪些选择和依据。

## 组合验证不能省略

局部通过不代表组合通过：

- 前端与后端分别通过测试，但字段名称不同。
- 两个 Patch 分别可编译，合并后产生依赖冲突。
- 两份研究分别可靠，合并摘要却把适用范围写成普遍结论。
- 三个操作都被授权，组合后却超过总预算或风险阈值。

因此 Root Owner 必须对 Composite Candidate 运行集成级 Acceptance。验证范围至少包括接口、不变量、权限、预算和最终 Goal Completion。

## 最终责任属于谁

每棵 Task Tree 应声明一个 `root_owner`。它可以是 Agent、确定性 Workflow、服务或人，但必须唯一。Root Owner 负责：

- 定义或确认总体验收标准。
- 接受、拒绝或要求重做候选 Artifact。
- 选择冲突的 Authority 与升级路径。
- 执行组合验证。
- 提交最终完成申请并附带证据。

Worker 对局部契约负责，Reviewer 对审查结论与证据负责，Arbiter 对冲突决定负责；它们都不能让 Root Owner 的总责消失。对于高风险外部副作用，最终执行权限仍由 Permission Policy 与人工审批控制。

## Multi-Agent Evaluation Matrix

| 层次 | 核心问题 | 指标或验证 |
| --- | --- | --- |
| Decomposition | 子任务是否完整且低重叠 | Coverage、Overlap、遗漏率 |
| Delegation | Contract 是否清楚且最小充分 | 返工率、Input Required、越界率 |
| Coordination | 等待和消息是否合理 | Critical Path、空等时间、消息放大 |
| Local Quality | 每个候选是否满足局部验收 | Artifact Pass、Evidence Completeness |
| Merge Quality | 是否正确处理重复与冲突 | Merge Failure、Conflict Escape |
| Global Outcome | 组合结果是否完成 Root Goal | Integration Pass、Goal Completion |
| Safety and Cost | 权限、预算与副作用是否受控 | 越权、重复 Effect、总 Token 与延迟 |

评估不能只比较 Multi-Agent 的最终质量，还要与 Single Agent Baseline 比较同一 Dataset 上的质量、成本和延迟。如果质量提升很小，却显著增加消息、Token 和恢复复杂度，拆分没有通过工程验收。

## 本章检查

- Candidate、Validated、Conflicted、Accepted 与 Rejected 是否明确区分。
- 合并前是否校验 Delegation Contract、Scope、Schema、来源和 Evidence。
- Fact、Requirement、Plan 与 Artifact Conflict 是否采用不同 Authority。
- 是否避免把多数投票当成正确性证明。
- 是否保留 Arbitration Record 与被拒候选。
- 局部结果合并后是否执行集成级验证。
- 是否存在唯一 Root Owner 对正式 Artifact 和 Goal Completion 负责。
- Multi-Agent 是否与 Single Agent Baseline 比较质量、成本与延迟。
