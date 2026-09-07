# Identity、Permission、Guardrail 与 Human-in-the-Loop

作者：杨正武
来源：https://imcoders.cn/playbook/agent/18-permission-hitl/
更新：2026-08-12T00:00:00.000Z

认证用户、Agent 与 Runtime Workload 的多重身份，并把委托授权、审批和风险控制放进 Runtime 状态机。

---


Agent 知道怎样退款，不代表它有权退款；Router 选中了 `create_refund`，也不代表这次调用已经获批。在 User 驱动的 Agent 中，还必须回答：用户是谁、哪个 Agent 正代表他行动、真正连接支付系统的是哪个 Runtime Workload，以及用户究竟把多大权限委托给了这次 Run。

权限判断必须发生在身份链、真实参数和目标资源已经明确之后，并由 Runtime 控制面执行。

> Skill 描述方法，Tool 声明动作，Router 选择候选，Policy 决定许可，Human-in-the-Loop 处理无法自动决定的风险。

## 术语来源与适用范围

Authentication、Authorization、Delegation、Least Privilege、Policy Enforcement 和 Human-in-the-Loop 都是既有安全或自动化概念，但 Agent Runtime 没有统一的身份与权限状态机。[OAuth 2.0 Token Exchange（RFC 8693）](https://www.rfc-editor.org/rfc/rfc8693.html) 区分 Subject 与 Actor，可以表达“Actor 代表 Subject 行动”；[SPIFFE](https://spiffe.io/docs/latest/spiffe/concepts/) 为进程或服务提供可验证的 Workload Identity。它们分别覆盖委托授权和运行工作负载认证的一部分，但都没有定义完整的 Agent Definition、Run 或 Tool Call 身份模型。

[OpenAI Agents SDK Human-in-the-loop](https://openai.github.io/openai-agents-python/human_in_the_loop/) 展示了一种明确模式：Tool 声明审批要求，Run 以 interruption 暂停，审批决定写入状态，然后恢复原 Run。[OpenAI Agents SDK Guardrails](https://openai.github.io/openai-agents-python/guardrails/) 则说明 Guardrail 可以作用于输入、输出或 Tool 调用，但不同 Tool 类型与 Handoff 的覆盖边界并不相同。

本章的风险等级、Permission Policy、Approval Request 和 Resume Token 是 Playbook 参考设计。它们说明 Runtime 必须保存哪些语义，不是某个 SDK 的原生字段或行业统一协议。

## Permission、Guardrail 与 Approval 不是一回事

| 机制 | 回答的问题 | 示例 |
| --- | --- | --- |
| Authentication | 每个参与主体是谁，凭什么相信 | 用户登录凭证、Agent 版本证明、Workload Credential |
| Authorization | 是否有权对目标执行动作 | 能否退款 payment_9 |
| Delegation | 谁把哪些权限委托给谁 | user_42 允许 support-agent 在本 Run 发起退款 |
| Guardrail | 输入、输出或调用是否满足规则 | 邮件正文不得包含 Secret |
| Approval | 是否由有资格的人接受本次风险 | 财务负责人批准退款 6800 元 |
| Validation | 动作参数和前置条件是否仍有效 | 支付仍可退款、币种一致 |

审批不能替代权限：无权操作的人点了“同意”，动作仍不应执行。Guardrail 也不是只写一句 Prompt；如果规则必须强制执行，应落到确定性校验或 Policy Enforcement Point。

![用户驱动 Agent 的多重身份与委托链](/playbook-images/agent/agent-identity-chain.svg)

## Agent 场景不是一个身份，而是一条 Actor Chain

一次 User 驱动的 Tool Call 通常涉及五个可以独立变化的主体：

- **User Identity**：谁提出目标，原本拥有哪项业务权限。
- **Agent Definition Identity**：哪个版本化 Agent、配置和发布物做出决策。
- **Run Identity**：哪一次有边界的执行正在使用该委托。
- **Runtime Workload Identity**：哪个可验证的进程、容器或服务实际发出网络请求。
- **Approver Identity**：高风险动作由谁批准，他是否具备批准资格。

外部系统还拥有自己的 **Resource Identity**：例如请求到达的是支付生产环境，而不是测试环境。认证只有同时绑定正确 Audience、Environment 和 Resource，才不会把给测试系统的凭证误用到生产系统。

这里最容易误解的是“Agent Identity”。逻辑上的 `support-agent@7` 不是天然的密码学主体：一个名称和 Prompt 不能向支付系统证明身份。真正完成 mTLS 或 Token 认证的通常是 `agent-runtime-prod` 这个 Workload；Runtime 再通过签名发布记录、不可变版本摘要和 Run Trace，证明此次请求由哪个 Agent Definition 发起。

因此需要同时保留两种证据：

**代码块说明｜结构示意：** 这段文本把“Agent 场景不是一个身份，而是一条 Actor Chain”中的关键对象并列出来，帮助读者识别各自责任与边界。它用于概念建模，不代表唯一的产品命名或实现结构。

```text
Execution authentication：哪个 Workload 真的建立了连接
Decision attribution：哪个 Agent Definition / Run 产生了动作决定
```

SPIFFE 等 Workload Identity 机制可以解决前者的一部分，但不会自动证明某个 Prompt、Skill 或 Agent Version 被加载；后者仍需要 Runtime 自己的发布与审计链。

## 四类常见执行关系

### 用户本人直接操作

用户在产品界面中点击退款，后端代表该用户调用支付系统。这里仍有 User 与 Service 两个身份，但没有 Agent 决策者。

### 用户驱动的 Agent 代表用户操作

用户要求客服 Agent 处理重复扣款。用户是 Subject，Agent 是当前 Actor，Runtime Workload 是技术调用方。系统既要证明用户身份，也要证明用户确实将“对 `payment_9` 退款、金额不超过 6800 元”的权限委托给这次 Run。

### 自治或定时 Agent 以组织身份操作

夜间巡检 Agent 没有当前在线用户，不应该伪造 `user_id`。它的权限应来自 Service / Organization Principal、预先批准的 Job Policy 和有限资源范围。审计要明确写成“系统任务触发”，而不是“代表最近登录的用户”。

### Agent 向子 Agent 或远程 Agent 委派

父 Agent 只能向下传递自己的权限子集。子 Agent 的有效权限不能因为换了执行者而扩大，也不能只复制父级 Token。每次 Handoff / Agent-as-Tool 都应创建新的 Delegation Edge，绑定任务、目标、Scope 和期限。

## 用户驱动 Agent 需要“双重认证 + 委托证明”

“双重认证”在这里不是指用户登录时的 MFA，而是至少验证两个不同主体：

1. **验证 User**：通过企业 IdP、Session、OAuth/OIDC 等确认用户身份及认证强度。
2. **验证 Runtime Workload**：通过 mTLS、云 Workload Identity 或 SPIFFE SVID 等确认真正发出请求的服务。
3. **验证 Agent Definition**：确认 Agent 版本、Tool/Skill 配置和部署摘要属于获准发布物。
4. **验证 Delegation**：确认该用户允许这个 Agent 在本 Run、目标资源和期限内代表自己行动。

只有用户登录凭证，没有 Agent / Workload 身份，外部系统无法区分可信 Runtime 与窃取 Token 的其他程序；只有 Agent Service Account，没有 User 与 Delegation，系统又无法证明它为什么有权操作 `payment_9`。

[RFC 8693](https://www.rfc-editor.org/rfc/rfc8693.html) 中的 `subject_token`、`actor_token` 以及签发 Token 中的 `sub` / `act` Claim 为 On-Behalf-Of 场景提供了一种标准表达。不过 RFC 并不规定 Agent Version、Run ID 和 Tool Call ID；这些仍需在 Runtime 审计上下文中记录，或通过受信任的扩展 Claim / 外部记录关联。

## 身份链参考模型

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“身份链参考模型”落成可检查的结构化记录，主要字段包括 `actor_chain`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
actor_chain:
  subject:
    type: user
    id: user_42
    issuer: https://id.example.com
    authentication_time: 2026-08-12T13:10:00+08:00
    authentication_strength: phishing_resistant_mfa

  actors:
    - type: agent_definition
      id: support-agent@7
      artifact_digest: sha256:agent...
    - type: run
      id: run_128
    - type: workload
      id: spiffe://example.com/prod/agent-runtime

  delegation:
    grant_id: grant_73
    delegated_by: user_42
    delegated_to: support-agent@7
    scopes: [payments.refund]
    resource_scope: payment_9
    constraints:
      max_amount: 6800
      currency: CNY
    expires_at: 2026-08-12T14:00:00+08:00

  audience: payments-prod
```

`actor_chain`、`agent_definition`、`run` 和 `delegation` 的组合是本 Playbook 的参考审计模型，不是 OAuth Token 或 SPIFFE SVID 的标准格式。生产实现可以让 Token 只携带必要 Claim，把完整链条保存在不可篡改的授权与审计系统中，以避免 Token 过大或泄露内部结构。

## 有效权限取身份链的交集

User 驱动 Agent 的有效权限不应该等于用户权限，也不应该等于 Runtime Service Account 的权限上限，而是多层限制的交集：

**代码块说明｜关系式：** 这段表达式把“有效权限取身份链的交集”压缩成便于比较的组成关系。它是分析模型，不是可执行代码，也不是要求实现者采用的行业标准公式。

```text
Effective Permission
  = User Entitlement
  ∩ Agent Allowed Capabilities
  ∩ Delegation Grant for this Run
  ∩ Runtime Workload Permission
  ∩ Resource / Environment Policy
  ∩ Current Approval Scope
```

这个公式是 Playbook 的分析表达，不是标准授权算法。它强调任何一层收窄都必须生效：用户有全额退款权，不代表 Agent 被允许使用；Runtime 技术上能访问所有支付，也不能突破用户只对 `payment_9` 的委托；审批只接受本次风险，不能把原本没有的基础权限凭空增加出来。

## 身份必须在每个信任边界重新验证

**代码块说明｜流程示意：** 这段文本图按箭头方向阅读，用来说明“身份必须在每个信任边界重新验证”中的执行顺序、状态变化或责任流转。它表达逻辑关系，不代表组件必须按图中的数量和位置部署。

```text
User → Product UI：验证 User Session 与认证强度
UI → Agent Runtime：绑定 User、Goal、Run 与 Delegation Grant
Runtime → Tool Executor：验证 Agent Version、Policy 与 Tool Call
Executor → External System：使用面向目标 Audience 的短期凭证
Parent Agent → Child Agent：衰减 Scope，建立新的 Delegation Edge
Approver → Runtime：验证审批人身份、角色与参数摘要
```

身份链不是由上游传来一个 `X-User-Id` Header 就算完成。每跨越一个信任域，都应验证签发者、签名、Audience、有效期和防重放条件，并决定是否信任上游提供的 Agent / Run Claim。

## 不要让全能 Service Account 吞掉身份语义

如果所有 Agent 都共享一个全能 Service Account，外部系统看到的只是“平台管理员”，无法表达用户和任务边界。更安全的做法是使用短期、降权、带 Audience 和 Scope 的凭证，并把代表关系记录进审计：

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“不要让全能 Service Account 吞掉身份语义”落成可检查的结构化记录，主要字段包括 `delegation_context`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
delegation_context:
  user_id: user_42
  agent_definition_id: support-agent@7
  run_id: run_128
  workload_id: spiffe://example.com/prod/agent-runtime
  grant_id: grant_73
  scopes: [payments.refund]
  resource_scope: payment_9
  expires_at: 2026-08-12T14:00:00+08:00
```

这份精简的 `delegation_context` 同样是参考审计模型，不是 OAuth 标准 Token 格式。真实系统可以用 OAuth Token Exchange、云 IAM、SPIFFE 或内部 Capability Token 组合实现，但不要让模型看到原始凭证。

![权限检查、审批与副作用提交](/playbook-images/agent/permission-effect-flow.svg)

## 动作风险分级

风险不是 Tool 的永久常数，同一个 Tool 会因参数、对象和环境变化：

| 等级 | 典型动作 | 默认处理 |
| --- | --- | --- |
| R0：只读低敏 | 读取公开文档 | 自动执行，记录 Trace |
| R1：可恢复局部写 | 修改隔离 Workspace 文件 | Policy 自动允许，可撤销 |
| R2：外部可见或敏感 | 发单封邮件、改共享任务 | 参数预览，按策略审批 |
| R3：财务/生产/批量 | 退款、生产发布、群发 | 强审批、职责分离、重新验证 |
| R4：禁止或不可委托 | 导出 Secret、绕过审计 | 拒绝，不提供审批绕过 |

该分级是本 Playbook 的示例，不是行业标准。实现时应结合影响范围、可逆性、数据敏感度、金额、环境和受众计算风险。

## Permission Policy 示例

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“Permission Policy 示例”落成可检查的结构化记录，主要字段包括 `policy`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
policy:
  policy_id: refund-v4
  match:
    tool: create_refund
    environment: production
  rules:
    - when: amount <= 10000 and user.has_scope("payments.refund")
      decision: require_approval
      approver_role: finance_operator
    - when: amount > 10000
      decision: require_approval
      approver_role: finance_manager
      require_separation_of_duties: true
    - when: currency != payment.currency
      decision: deny
```

这里的表达式语言是说明性的。生产 Policy Engine 需要确定性求值、版本化、测试和默认拒绝；模型可以提供分类信号，但不应成为高风险授权的唯一裁决者。

## 审批请求必须描述将要发生的动作

“Agent 请求继续，是否同意？”不是有效审批。请求至少应包含：

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“审批请求必须描述将要发生的动作”落成可检查的结构化记录，主要字段包括 `approval_request`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
approval_request:
  approval_id: apr_39
  run_id: run_128
  tool_call_id: call_81
  action: create_refund
  target: payment_9
  parameter_digest: sha256:51a...
  preview:
    amount: 6800
    currency: CNY
    reason: 重复扣款
  risk: R3
  policy_version: refund-v4
  expires_at: 2026-08-12T14:00:00+08:00
```

批准应绑定不可变参数摘要。审批后如果 Agent 把 6800 改成 68000、改变收件人或环境，原批准必须失效并重新请求。

## Approval 是可恢复协议状态

**代码块说明｜层级示意：** 这段文本图按缩进和树枝符号阅读，用来展开“Approval 是可恢复协议状态”中的父子关系与归属边界。它描述的是逻辑结构，不要求数据库或服务按同样层级拆分。

```text
RUNNING
   ↓ policy: approval required
WAITING_APPROVAL
   ├─ reject / expire → RUNNING with rejection observation 或终止
   └─ approve
          ↓ revalidate identity + parameters + external preconditions
       RUNNING → execute exact Tool Call
```

等待期间 Worker 可以释放，但 Run、Tool Call、参数摘要、Policy 版本和审批上下文必须持久化。恢复时不能只依赖一条聊天消息“已同意”。

`WAITING_APPROVAL` 是本 Playbook 的语义名称；具体 Runtime 可能使用 interruption、input required 或 suspended。关键是审批成为可序列化、可过期、可审计的状态转换。

## 拒绝不是 Tool 故障

用户拒绝表示这条执行路径没有授权，不代表外部服务出错。Runtime 应把它作为结构化 Observation 返回给 Agent：

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“拒绝不是 Tool 故障”落成可检查的结构化记录，主要字段包括 `approval_result`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
approval_result:
  decision: rejected
  reason_code: user_declined
  tool_call_id: call_81
  reusable: false
```

Agent 可以提供草稿、建议其他无副作用方案或结束任务；不能改名、拆分参数后偷偷重试同一动作。

## Secret 不进入不必要的 Context

模型通常只需要知道“凭证可用”和它允许的 Scope，而不需要看到 Token 内容：

**代码块说明｜流程示意：** 这段文本图按箭头方向阅读，用来说明“Secret 不进入不必要的 Context”中的执行顺序、状态变化或责任流转。它表达逻辑关系，不代表组件必须按图中的数量和位置部署。

```text
Model generates Tool Call without credential
              ↓
Runtime validates identity and policy
              ↓
Credential Broker issues short-lived secret
              ↓
Executor injects credential out of model context
```

Trace 中也应记录 Credential Reference、Scope 和签发结果，而不是 Secret 本身。向子 Agent 委派时重新计算最小权限，不应复制父 Agent 的全部凭证。

## Human-in-the-Loop 不只用于批准

人工介入还可能承担：补充缺失输入、选择歧义方案、核实身份、编辑参数和接管任务。协议应区分 `approval_required`、`input_required`、`review_required` 与 `takeover_required`，因为它们的 UI、权限和恢复语义不同。这组名称仍属于参考分类。

## 本章检查

- Authentication、Delegation、Authorization、Guardrail、Approval 是否分开。
- User、Agent Definition、Run、Runtime Workload 与 Approver Identity 是否可以审计关联。
- 是否同时保留 Workload 的执行认证和 Agent Definition 的决策归因证据。
- 用户驱动 Agent 是否验证 User、Workload、Agent Version 与 Delegation Grant。
- 自治 Agent 是否使用明确的组织或服务身份，而不是伪造用户身份。
- 子 Agent 是否只获得衰减后的权限，并建立新的 Delegation Edge。
- 有效权限是否取用户权限、Agent 能力、委托、Workload 权限与 Policy 的交集。
- 风险是否结合真实参数、资源、环境和可逆性计算。
- 高风险 Policy 是否确定性求值、版本化并默认拒绝。
- Approval 是否绑定 Tool Call 与参数摘要，并设置有效期。
- Resume 前是否重新验证身份、权限和外部前置条件。
- 拒绝是否作为正式结果处理，而不是被 Agent 绕过。
- Secret 是否由 Executor 注入，并从 Context、Artifact 和 Trace 中剔除。
