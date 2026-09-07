# Agent 任务生命周期

作者：杨正武
来源：https://imcoders.cn/playbook/agent/08-run-lifecycle/
更新：2026-08-12T00:00:00.000Z

设计 Run 从提交、排队、运行到等待、取消、失败和完成的完整状态机。

---


Agent 任务不是一个更慢的 HTTP 请求。它可能排队数分钟，等待用户补充文件，等待系统授权，或者在外部构建结束后继续。若 Runtime 只有 `running` 和 `done`，所有这些情况都会被误判成卡死或失败。

生命周期的价值，是让每种暂停和结束都拥有明确语义、负责人和合法下一步。

## 一套可工作的 Run 状态机

![Agent Run 生命周期状态机](/playbook-images/agent/run-lifecycle.svg)

| 状态 | 含义 | 谁能推动下一步 |
| --- | --- | --- |
| SUBMITTED | 请求已被接受，尚未进入调度 | Runtime |
| QUEUED | 已满足基本校验，等待执行资源 | Scheduler |
| RUNNING | Worker 正在推进 Run | Worker / Runtime |
| INPUT_REQUIRED | 缺少用户提供的信息或选择 | 用户 |
| AUTH_REQUIRED | 动作需要额外授权 | 用户 / 审批系统 |
| WAITING | 等待已知外部事件或时间条件 | 事件源 / Timer |
| CANCEL_REQUESTED | 已接受取消请求，正在停止 | Worker / Runtime |
| COMPLETED | 目标通过完成验证 | 终态 |
| FAILED | 确定性错误使本次 Run 无法继续 | 终态 |
| TIMED_OUT | 超过 Run 的时间边界 | 终态 |
| CANCELED | 取消已经完成，结果不再被接受 | 终态 |

Run Status 应该是对外稳定语义。内部可以有更细的 Worker 状态，但不能要求调用者理解 `planner_node_4` 才知道任务是否仍需等待。

## 从提交到真正运行

`SUBMITTED` 表示 Runtime 已经接收并持久化请求。此时可以完成幂等去重、Schema 校验、配额检查和 Agent Version 解析。

`QUEUED` 表示任务可以执行，只是在等待资源。将两者分开后，系统能区分“请求还在校验”与“调度拥堵”。如果创建接口同步完成这些工作，也可以快速从 `SUBMITTED` 转入 `QUEUED`，但事件历史仍保留两个语义。

Worker 获取带租约的 Attempt 后，Run 才进入 `RUNNING`。租约到期不等于 Run 失败；Scheduler 可以创建新 Attempt 恢复执行。

## INPUT_REQUIRED 不是失败

Agent 发现缺少复现账号时，任务没有失败。它已经成功识别阻塞条件，并把下一步责任交给用户。

一个完整的输入请求应该包括：

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“INPUTREQUIRED 不是失败”落成可检查的结构化记录，主要字段包括 `required_input`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
required_input:
  request_id: req_09
  type: structured_input
  prompt: 提供一个能复现登录失败的测试账号
  schema:
    account_id: string
    environment: [staging, test]
  reason: 当前日志已脱敏，无法关联失败用户
  expires_at: 2026-08-12T15:36:10+08:00
```

提交输入时必须携带 `request_id`。如果 Run 已经因其他输入恢复，迟到答案不能被静默应用到新的等待点。

`AUTH_REQUIRED` 与它相似，但责任和审计不同。前者缺少信息，后者需要扩大动作权限。授权响应应该绑定具体动作、资源、范围和有效期，不能把“允许这一次修改配置”解释成永久权限。

## WAITING 表示系统知道自己在等什么

等待构建完成、等待某个时间窗口或等待 Webhook，都属于 `WAITING`。Runtime 应保存明确等待条件：

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“WAITING 表示系统知道自己在等什么”落成可检查的结构化记录，主要字段包括 `wait_condition`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
wait_condition:
  type: external_event
  event: build.finished
  correlation_id: build_782
  wake_at: null
  timeout_at: 2026-08-11T16:20:00+08:00
```

如果系统不知道下一步由谁推动，也没有可观察的恢复条件，那不是 WAITING，而是设计缺失。可以将其诊断为阻塞原因，最终进入 FAILED 或升级人工处理。

`BLOCKED` 是否作为独立状态取决于产品需要。若使用它，必须定义解除者和恢复条件。不能把所有无法解释的停滞都放进 `BLOCKED`。

## 请求取消不等于已经取消

用户点击取消时，Worker 可能正在调用外部 Tool。Runtime 首先进入 `CANCEL_REQUESTED`，发布取消信号，并阻止创建新的普通 Step。

只有完成以下处理后，Run 才进入 `CANCELED`：

- Worker 已停止推进，或租约已失效。
- 未开始的 Tool 调用已经撤销。
- 在途结果即使迟到也会被版本栅栏拒绝。
- 已经发生的副作用被记录并对用户可见。

外部系统未必支持撤销。取消一个已发送的邮件不会让收件箱里的邮件消失。因此 `CANCELED` 表示 Runtime 不再继续目标，不表示现实世界回到了 Run 开始前。

## COMPLETED 必须经过验证

模型产生最终回答时，Run 仍不应该直接完成。它只是提出完成申请。Runtime 应运行与目标相匹配的验证：测试、Schema 校验、真实状态查询或人工验收。

**代码块说明｜层级示意：** 这段文本图按缩进和树枝符号阅读，用来展开“COMPLETED 必须经过验证”中的父子关系与归属边界。它描述的是逻辑结构，不要求数据库或服务按同样层级拆分。

```text
RUNNING
  └── 模型请求完成
        ├── 验证通过 → COMPLETED
        └── 验证失败 → 记录证据并回到 RUNNING
```

`COMPLETED` 最好保存完成原因、主要 Artifact 和证据引用。这样上层系统不需要解析最终 Response 才能判断目标是否满足。

## FAILED、TIMED_OUT 与等待超时

`FAILED` 表示本次 Run 在当前目标、输入和权限下无法继续，并且有明确错误分类。例如 Tool Schema 不兼容、必须资源不存在、预算已经耗尽。

`TIMED_OUT` 表示达到 Run 的整体截止时间。它与单次 Tool Timeout 不同：Tool 超时可以重试或换策略，Run 超时则是生命周期终态。

等待也可以有局部超时。等待构建 20 分钟未收到事件，Runtime 可以先从 WAITING 恢复，让 Agent 决定重新查询、延长等待或失败；不必自动把整个 Run 标记为 TIMED_OUT。

## 状态转换需要条件和副作用

状态机不是一张展示图，而是一组可以检查的规则：

**代码块说明｜伪代码：** 这段 Python 以 `transition()` 为主要入口说明“状态转换需要条件和副作用”怎样运行。它省略了持久化、并发、权限和完整错误处理，用于解释决策顺序，不是可直接部署的完整实现。

```python
def transition(run_id, expected_revision, target, cause):
    state = load_for_update(run_id)

    assert state.revision == expected_revision
    assert target in ALLOWED_TRANSITIONS[state.status]
    assert guard_passed(state, target, cause)

    save_state_and_event(
        state.with_status(target),
        event=f"run.{target.lower()}",
        cause=cause,
    )
```

例如 `INPUT_REQUIRED → RUNNING` 的 Guard 应验证 `request_id`、输入 Schema 和有效期；`RUNNING → COMPLETED` 应验证完成证据；任何非终态转入 `CANCELED` 都要检查取消代次。

## 同一个 Thread 是否允许并发 Run

Thread 共享消息和 Artifact，并发策略必须显式选择。

| 策略 | 行为 | 适合场景 | 风险 |
| --- | --- | --- | --- |
| Reject | 已有活动 Run 时拒绝新 Run | 强一致任务 | 用户需要等待 |
| Queue | 新 Run 排在旧 Run 之后 | 连续编辑、客服会话 | 后续输入可能过时 |
| Cancel-and-replace | 取消旧 Run 后启动新 Run | 搜索、实时建议 | 旧副作用不能自动撤回 |
| Fork | 从某个 Thread Revision 创建分支 | 方案探索、独立研究 | 需要后续合并 |
| Allow with isolation | 并发运行，各自绑定快照 | 相互独立的任务 | 仍可能争用外部资源 |

默认串行通常最安全，但不是唯一答案。即使允许并发，每个 Run 也应绑定创建时的 `thread_revision`。合并结果前检查 Thread 是否已经变化，避免旧 Run 覆盖新输入。

## 本章检查

- Run 是否区分提交、排队、运行、等待和不同终态。
- INPUT_REQUIRED 与 AUTH_REQUIRED 是否携带可验证的请求身份和恢复条件。
- WAITING 是否明确等待事件、关联 ID 和超时策略。
- CANCEL_REQUESTED 是否先于 CANCELED，并处理在途结果。
- COMPLETED 是否由独立证据驱动。
- Tool Timeout、等待超时和 Run Timeout 是否分开处理。
- 每个状态转换是否拥有合法来源、Guard、Event 和原子更新。
- Thread 并发 Run 策略是否显式，并对旧快照写入进行检查。
