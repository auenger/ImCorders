# Interrupt、Resume、Cancel 与 Retry

作者：杨正武
来源：https://imcoders.cn/playbook/agent/09-interrupt-resume-cancel-retry/
更新：2026-08-12T00:00:00.000Z

让暂停、恢复、取消和重试成为可持久化、可审计的 Runtime 控制操作。

---


暂停等待用户、取消任务和故障后重试，表面上都是“停下来再处理”，实际承诺完全不同。Interrupt 希望未来继续，Cancel 希望停止目标，Retry 希望在保留历史的前提下再次尝试。

如果 Runtime 只会终止进程和重新启动，这三种语义就会混在一起，并把最危险的问题留给外部副作用。

## 四个控制操作的边界

| 操作 | 是否保留原 Run | 是否预期继续 | 是否创建新 Attempt | 核心依据 |
| --- | --- | --- | --- | --- |
| Interrupt | 是 | 是 | 通常否 | 安全暂停点与输入请求 |
| Resume | 是 | 已在继续 | 视 Worker 是否存活 | Checkpoint + 新输入 |
| Cancel | 是 | 否 | 否 | Cancel Epoch 与停止确认 |
| Retry | 是 | 是 | 是 | 失败分类与恢复点 |

控制操作必须是持久化命令，不只是发给某个 Worker 的进程内信号。Worker 可能已经崩溃，用户仍然需要看到取消请求已被系统接受。

## Interrupt 是一次受控暂停

Interrupt 常由三类原因触发：Agent 主动请求信息或授权，Runtime 在风险动作前设置门禁，外部系统要求临时暂停。

**代码块说明｜流程示意：** 这段文本图按箭头方向阅读，用来说明“Interrupt 是一次受控暂停”中的执行顺序、状态变化或责任流转。它表达逻辑关系，不代表组件必须按图中的数量和位置部署。

```text
Agent / Runtime       Run Store         Client
      |                   |               |
      |-- save checkpoint>|               |
      |-- input request ->|               |
      |                   |-- event ----->|
      |                   |  INPUT_REQUIRED
      |<------ ack -------|               |
      |  release worker   |               |
```

正确顺序是先完成当前原子动作，再保存 Checkpoint 和等待请求，最后释放 Worker。不能在 Tool 副作用执行到一半时随意截断，再假设 Resume 能从代码行继续。

可以把 Interrupt 设计为一个声明：

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“Interrupt 是一次受控暂停”落成可检查的结构化记录，主要字段包括 `interrupt`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
interrupt:
  run_id: run_128
  request_id: req_09
  reason: input_required
  checkpoint_id: cp_024
  prompt: 请选择需要保持兼容的 Token 版本
  accepted_schema:
    versions: string[]
  expires_at: 2026-08-12T16:00:00+08:00
```

如果进程仍然持有内存状态，也应以持久化记录为准。这样即使原 Worker 消失，其他 Worker 仍能继续。

## Resume 不是把回答追加到聊天末尾

Resume 必须回到准确的等待点，并验证这份输入仍然适用：

**代码块说明｜伪代码：** 这段 Python 以 `resume()` 为主要入口说明“Resume 不是把回答追加到聊天末尾”怎样运行。它省略了持久化、并发、权限和完整错误处理，用于解释决策顺序，不是可直接部署的完整实现。

```python
def resume(run_id, request_id, checkpoint_id, value):
    state = load_for_update(run_id)

    assert state.status in {"input_required", "auth_required", "waiting"}
    assert state.pending_request_id == request_id
    assert state.latest_checkpoint_id == checkpoint_id
    validate(value, state.pending_input_schema)

    record_input_event(run_id, request_id, value)
    clear_pending_request(state)
    enqueue(state.with_status("queued"))
```

三个 ID 都很重要：`run_id` 定位任务，`request_id` 定位哪次提问，`checkpoint_id` 防止旧页面对已经推进的 Run 提交答案。

恢复后 Runtime 加载 Checkpoint，应用新输入，再重新观察易变环境。例如用户等待期间代码已经被同事修改，Agent 应重新读取相关文件，而不是继续使用数小时前的文件内容。

若原 Worker 仍在等待，可以继续原 Attempt；若 Worker 已释放、租约过期或进程丢失，通常创建新 Attempt 更清晰。对用户仍然是同一个 Run。

## Cancel 需要版本栅栏

取消最容易产生“界面显示已取消，后台仍然写入结果”的竞态。解决它需要一个只增不减的 Cancel Epoch 或 Run Revision。

**代码块说明｜伪代码：** 这段 Python 以 `request_cancel()` 为主要入口说明“Cancel 需要版本栅栏”怎样运行。它省略了持久化、并发、权限和完整错误处理，用于解释决策顺序，不是可直接部署的完整实现。

```python
def request_cancel(run_id):
    state = load_for_update(run_id)
    state.cancel_epoch += 1
    state.status = "cancel_requested"
    save_state_and_event(state)
    publish_cancel_signal(run_id, state.cancel_epoch)
```

Worker 领取任务时保存当前代次：

**代码块说明｜伪代码：** 这段 Python 以最小控制流程说明“Cancel 需要版本栅栏”怎样运行。它省略了持久化、并发、权限和完整错误处理，用于解释决策顺序，不是可直接部署的完整实现。

```python
lease = {
    "run_id": "run_128",
    "attempt_id": "attempt_002",
    "lease_epoch": 3,
    "cancel_epoch": 0,
}
```

提交 Step 结果前再次比较：

**代码块说明｜伪代码：** 这段 Python 以 `commit_result()` 为主要入口说明“Cancel 需要版本栅栏”怎样运行。它省略了持久化、并发、权限和完整错误处理，用于解释决策顺序，不是可直接部署的完整实现。

```python
def commit_result(lease, result):
    state = load_for_update(lease.run_id)

    if state.cancel_epoch != lease.cancel_epoch:
        reject(result, reason="stale_after_cancel")
        return

    if state.lease_epoch != lease.lease_epoch:
        reject(result, reason="stale_worker")
        return

    save_result_and_event(result)
```

取消信号负责尽快停止，版本栅栏负责保证即使没停住，迟到结果也不能改变正式状态。两者缺一不可。

## Retry 应该创建新 Attempt

Retry 的第一步不是重跑，而是分类失败：

| 失败 | 是否适合重试 | 恢复方式 |
| --- | --- | --- |
| 临时网络错误 | 是，有限退避 | 从失败 Step 前继续 |
| Worker 丢失 | 是 | 从最新安全 Checkpoint 新建 Attempt |
| 参数或 Tool Schema 错误 | 修正后再试 | 回到决策步骤 |
| 权限不足 | 获得授权后继续 | Resume，不是机械 Retry |
| 预算耗尽 | 需要新预算或缩小目标 | 通常新 Run 或显式扩展 |
| 确定性验证失败 | 相同输入不应原样重试 | 改策略后新 Attempt |
| 已发生不可逆副作用 | 谨慎 | 先对账，再决定补偿或继续 |

新 Attempt 应保存 `reason`、`resume_from` 和新的租约。旧 Attempt 保持失败或中止状态，成本、Trace 与错误都可追溯。

**代码块说明｜伪代码：** 这段 Python 以 `retry()` 为主要入口说明“Retry 应该创建新 Attempt”怎样运行。它省略了持久化、并发、权限和完整错误处理，用于解释决策顺序，不是可直接部署的完整实现。

```python
def retry(run_id, from_checkpoint, reason):
    run = load_for_update(run_id)
    assert run.status in RETRYABLE_STATES
    assert checkpoint_belongs_to(from_checkpoint, run_id)
    assert retry_policy_allows(run, reason)

    attempt = create_attempt(
        run_id=run_id,
        number=run.current_attempt + 1,
        resume_from=from_checkpoint,
        reason=reason,
    )
    enqueue(attempt)
```

Retry 预算也应有限制。指数退避能降低临时故障压力，却不能解决确定性错误。连续得到相同错误时，系统应停止并要求新信息或换策略。

## Worker 崩溃后的重新领取

Worker 通过租约拥有 Attempt，而不是永久拥有 Run：

**代码块说明｜流程示意：** 这段文本图按箭头方向阅读，用来说明“Worker 崩溃后的重新领取”中的执行顺序、状态变化或责任流转。它表达逻辑关系，不代表组件必须按图中的数量和位置部署。

```text
领取 Attempt → 获得 lease_epoch=3，有效期 60 秒
每 20 秒续租 → Runtime 更新 expires_at
Worker 崩溃 → 租约到期
Scheduler 创建或领取新 Attempt → lease_epoch=4
旧 Worker 恢复并提交 → 因 epoch 过期被拒绝
```

租约解决“谁现在可以写入”，Checkpoint 解决“从哪里继续”，幂等键解决“外部动作是否可以安全重放”。三者不能互相替代。

## 外部副作用不会随状态回滚

数据库事务回滚不了已经发出的邮件、创建的工单或触发的部署。Runtime 必须维护副作用账本：

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“外部副作用不会随状态回滚”落成可检查的结构化记录，主要字段包括 `side_effect`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
side_effect:
  operation_id: op_731
  run_id: run_128
  step_id: step_028
  tool: update_auth_config
  idempotency_key: run_128:update_auth_config:v1
  target: staging/auth/config
  status: confirmed
  external_reference: change_992
  compensating_action: restore_config_version
```

执行前生成幂等键，执行后保存外部引用。恢复或 Retry 时先查询账本和真实环境：

**代码块说明｜流程示意：** 这段文本图按箭头方向阅读，用来说明“外部副作用不会随状态回滚”中的执行顺序、状态变化或责任流转。它表达逻辑关系，不代表组件必须按图中的数量和位置部署。

```text
没有记录 → 可以发起动作
状态 pending → 使用幂等键向外部系统查询
状态 confirmed → 复用已有结果，不重复执行
状态 unknown → 停止自动重试，先人工或自动对账
```

补偿动作也不是“回滚魔法”。恢复配置可以撤销文件变化，但无法抹去该配置已经造成的请求影响。最终报告应明确列出已发生、已补偿和无法撤销的副作用。

## 控制操作也需要幂等

网络重试可能让客户端重复发送 Resume、Cancel 或 Retry。Protocol 应支持操作级幂等键：

**代码块说明｜接口示例：** 以 `POST /runs/run_128/cancel` 为例，这段报文说明“控制操作也需要幂等”如何通过系统边界表达。它用于解释操作语义；真正实现应采用并锁定所选 Protocol 的版本、认证与错误约定。

```http
POST /runs/run_128/cancel
Idempotency-Key: cancel-ui-7f31
```

相同键与相同请求应返回同一操作结果；相同键却携带不同参数应拒绝。这样按钮连点、代理重试和消息重复投递不会创建多个 Attempt 或多次推进状态。

## 本章检查

- Interrupt 是否发生在原子动作边界，并先持久化 Checkpoint 和等待请求。
- Resume 是否校验 Run、Request、Checkpoint 和输入 Schema。
- 恢复后是否重新观察可能变化的外部环境。
- Cancel 是否同时使用停止信号和只增版本栅栏。
- Retry 是否基于失败分类创建新 Attempt，并保留旧历史。
- Worker 是否通过有期限的租约获得写入权，迟到结果能否被拒绝。
- 外部副作用是否有幂等键、真实引用、状态与补偿策略。
- Resume、Cancel 和 Retry 命令本身是否支持幂等。
