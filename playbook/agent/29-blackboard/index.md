# Blackboard、共享状态与并发控制

作者：杨正武
来源：https://imcoders.cn/playbook/agent/29-blackboard/
更新：2026-08-12T00:00:00.000Z

用结构化共享状态连接多个 Agent，并通过版本、所有权、租约和证据引用控制并发写入。

---


多个 Agent 需要共享信息，但“共享”不等于把每个 Agent 的完整 Conversation 广播给所有参与者。全量同步会迅速放大噪声、敏感信息和过期结论，也让任何一个 Agent 都难以判断哪些内容已经被验证。

> Blackboard 是受治理的共享工作状态。它保存可引用的事实、假设、任务、决策和 Artifact，不保存所有 Agent 的完整思考过程。

## 术语来源与适用范围

Blackboard Architecture 来自早期人工智能系统。Hayes-Roth 的相关工作把 Blackboard 描述为多个知识源围绕共享结构协作的架构思想，而不是一个固定的数据协议；[Stanford 的 BB1 Blackboard Architecture for Control 报告](https://i.stanford.edu/pub/cstr/reports/cs/tr/86/1123/CS-TR-86-1123.pdf)进一步讨论了控制问题。

今天的 Agent 框架也可能把共享消息历史、共享 Store 或 Graph State 称为 Blackboard，但它们的并发和一致性保证并不相同。本章的 Record 类型、Owner、Lease 与版本控制是 Playbook 扩展设计，不是经典 Blackboard 文献或 A2A Protocol 的标准 Schema。

Lease 与乐观并发是通用分布式系统机制。例如 [Kubernetes Lease](https://kubernetes.io/docs/concepts/architecture/leases/)用于协调成员与 Leader Election，但这不意味着 Agent Blackboard 应直接复用 Kubernetes API。本章借用其“持有者、续约和到期”语义管理 Task 所有权。

## 共享什么，隔离什么

适合进入 Blackboard：

- 已确认事实及其 Evidence Reference。
- 明确标记的假设、置信度与验证状态。
- Task、依赖、Owner、Lease 和进展状态。
- Artifact Reference、Schema、Version 和校验结果。
- 决策、批准、否决和原因。
- 面向协作方的短消息与 Input Request。

不应默认进入 Blackboard：

- 完整 System Prompt、私有 Skill 内容和 Secret。
- 每一步隐藏推理或未经整理的内部草稿。
- 与其他 Agent 无关的完整 Conversation。
- 没有来源、Owner 和时间的自然语言结论。
- 大型二进制文件正文，应该保存 Artifact Reference。

共享状态是 Context 来源之一，不是所有参与者的完整 Context。每个 Agent 仍由 Runtime 按当前 Task、权限和 Token Budget 组装局部视图。

## Blackboard 参考 Schema

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“Blackboard 参考 Schema”落成可检查的结构化记录，主要字段包括 `blackboard_id`、`root_run_id`、`revision`、`records`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
blackboard_id: bb_run_100
root_run_id: run_100
revision: 184

records:
  - record_id: fact_41
    kind: fact
    subject: api.status_field
    value: required
    status: confirmed
    evidence_refs:
      - artifact://requirements/api-v4#line-82
    author_run_id: run_101
    version: 2
    created_at: 2026-08-12T10:02:00Z
    valid_until: null

  - record_id: task_52
    kind: task
    status: running
    owner_run_id: run_102
    lease:
      lease_id: lease_90
      fencing_token: 7
      expires_at: 2026-08-12T10:20:00Z
    depends_on: [fact_41]

  - record_id: artifact_73
    kind: artifact
    ref: artifact://migration-review/44
    schema: migration_review_v2
    producer_run_id: run_102
    status: candidate
```

`revision` 表示 Blackboard 全局修订号，Record 自己也有 `version`。高并发系统可以按 Partition 或 Record 使用局部版本，避免所有写入争用一个全局计数器。

## 读取与写入路径必须分开

![Blackboard 共享状态与并发控制](/playbook-images/agent/blackboard-concurrency.svg)

**代码块说明｜流程示意：** 这段文本图按箭头方向阅读，用来说明“读取与写入路径必须分开”中的执行顺序、状态变化或责任流转。它表达逻辑关系，不代表组件必须按图中的数量和位置部署。

```text
Agent Local Context
    ↓ propose(record, expected_version)
Validation / Authorization / Conflict Check
    ↓ commit
Blackboard Revision N+1
    ↓ publish event
Subscriber 按权限重新组装 Context
```

Agent 不直接覆盖共享文档。它提交带类型和前置版本的 Proposal，State Service 检查 Schema、权限、证据与并发条件后提交。订阅者收到的是“某条记录已更新”的 Event，再按需读取，而不是把整个 Blackboard 自动塞入 Context。

## 事实、假设和决策不能互相覆盖

| Record Kind | 写入要求 | 更新规则 |
| --- | --- | --- |
| Fact | 必须有 Evidence Reference | 新证据可以 supersede，保留旧版本 |
| Hypothesis | 标记置信度和验证任务 | 验证后转为 Fact 或 Rejected，不原地伪装成事实 |
| Task | Owner、状态、依赖与 Lease | 只能按状态机转换 |
| Artifact | Producer、Schema、Digest | Candidate 经验证后提升为 Accepted |
| Decision | Decision Owner、依据与范围 | 通过新 Decision 撤销，不删除历史 |

同一 Subject 出现矛盾 Fact 时，不要最后写入者获胜。系统应创建 Conflict Record，保存双方证据，阻止依赖任务使用“已确认”状态，直到完成 Reconcile。

## 乐观并发控制

更新请求携带 `expected_version`：

**代码块说明｜伪代码：** 这段 Python 以 `update_record()` 为主要入口说明“乐观并发控制”怎样运行。它省略了持久化、并发、权限和完整错误处理，用于解释决策顺序，不是可直接部署的完整实现。

```python
def update_record(record_id, expected_version, patch):
    current = store.get(record_id)
    if current.version != expected_version:
        raise VersionConflict(current=current)
    validated = validate_transition(current, patch)
    return store.compare_and_swap(current, validated)
```

版本冲突后，Agent 必须读取最新记录，再决定合并、放弃或升级仲裁。对 Artifact 描述、评论和独立 Fact，可以按字段或追加合并；对 Task Owner、审批结论和外部副作用状态，不能自动进行自然语言合并。

## Task 所有权、Lease 与 Fencing Token

只写 `owner = agent_a` 不足以处理 Agent 崩溃。Lease 允许所有权在超时后回收：

**代码块说明｜流程示意：** 这段文本图按箭头方向阅读，用来说明“Task 所有权、Lease 与 Fencing Token”中的执行顺序、状态变化或责任流转。它表达逻辑关系，不代表组件必须按图中的数量和位置部署。

```text
acquire(task) → lease_id + fencing_token + expires_at
renew(lease)  → new expires_at
complete(task, fencing_token)
```

`fencing_token` 每次重新分配时单调增加。即使旧 Agent 在网络恢复后继续提交，State Service 也能拒绝旧 Token，避免两个 Worker 同时完成同一 Task。

Lease 到期不代表旧 Worker 的外部动作从未发生。接管者必须先读取 Step Effect Record，确认是否存在 unknown 或 confirmed 副作用，再从安全 Checkpoint 继续。

## 孤儿任务怎样回收

Task 可能因 Worker 崩溃、Parent 被取消或消息丢失成为 Orphan。Sweeper 可以定期检查：

1. Lease 是否过期。
2. Owner Run 是否仍处于可执行状态。
3. Parent Contract 是否有效。
4. 是否存在未确认外部副作用。
5. Task 可否重分配、需要人工确认，或应该取消。

不要看到 Lease 过期就直接重跑。带副作用的 Task 必须先 Reconcile。

## Blackboard 不是所有系统的默认答案

简单的 Orchestrator-Worker 系统，如果 Worker 只返回一次结构化 Artifact，Parent State 已足够，不需要额外 Blackboard。只有多个持续参与者需要读写共享事实、Task 和 Artifact，且协作关系不是简单父子返回时，Blackboard 才能抵消它带来的治理成本。

## 本章检查

- Blackboard 是否只保存结构化共享状态，而不是广播完整 Conversation。
- Fact、Hypothesis、Task、Artifact 和 Decision 是否使用不同更新规则。
- 每个共享结论是否有 Author、Version、Evidence 和有效范围。
- 写入是否经过 Schema、权限和前置版本检查。
- 冲突是否成为显式 Record，而不是最后写入者获胜。
- Task 是否使用 Lease、续约、到期与 Fencing Token 管理所有权。
- Lease 到期后的接管是否先确认外部副作用。
