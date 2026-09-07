# Tool Protocol：动作空间的稳定接口

作者：杨正武
来源：https://imcoders.cn/playbook/agent/15-tool-protocol/
更新：2026-08-12T00:00:00.000Z

通过明确的语义、参数、结果和错误契约，让 Agent 能够可靠地读取和改变外部环境。

---


模型只能生成候选动作，Tool 才把动作连接到真实环境。Tool 的名称、描述、参数、返回值和错误语义共同定义了 Agent 的动作空间；其中任何一项含糊，都会让模型更容易选错动作、填错参数或误判执行结果。

本章把 Tool 看作 Runtime 暴露给 Agent 的稳定动作契约，而不是某段函数代码：

> Tool Definition 描述“可以请求什么”，Tool Call 表示“一次动作请求”，Tool Result 则说明“这次请求实际发生了什么”。

## 术语来源与适用范围

Tool Calling、Function Calling 和 Structured Output 已被多种模型 API 与 Agent Framework 使用，但行业没有一份覆盖所有 Runtime 的统一 Tool 对象模型。JSON Schema 常被用来表达参数约束；[Model Context Protocol 的 Tool 规范](https://modelcontextprotocol.io/specification/2025-06-18/server/tools) 定义了 Tool 发现、调用和结果传输；[OpenAI Agents SDK Tools](https://openai.github.io/openai-agents-python/tools/) 则展示了 Hosted Tool、Function Tool、Runtime Tool、MCP Tool 和 Agent-as-Tool 等实现形态。

这些资料说明“结构化描述能力、让模型请求调用、由 Runtime 执行”是常见工程模式，但本章的 `Tool Definition`、`Tool Result`、错误分类和副作用字段是本 Playbook 的参考契约，不是对 MCP 或某个 SDK Schema 的复刻。接入 MCP 时应遵守 MCP 自身规范；在内部 Registry 中可以扩展风险、权限、幂等和审计元数据。

## Tool 的四个层次

**代码块说明｜流程示意：** 这段文本图按箭头方向阅读，用来说明“Tool 的四个层次”中的执行顺序、状态变化或责任流转。它表达逻辑关系，不代表组件必须按图中的数量和位置部署。

```text
Logical Tool       send_email(to, subject, body)
      ↓
Protocol Adapter   MCP / HTTP / SDK / CLI Adapter
      ↓
Executor           认证、超时、重试、结果规范化
      ↓
Environment        邮件服务中的真实消息与状态
```

- **Logical Tool** 是模型看到的领域动作。
- **Adapter** 把逻辑动作映射到外部协议。
- **Executor** 承担真实执行、凭证注入、超时和观测。
- **Environment** 保存动作读取或改变的真实状态。

不要让模型直接拼接鉴权 Header、Shell 转义和分页 Token。这些属于 Adapter 与 Executor，而不是推理任务。

## Tool 粒度：围绕决策，而不是围绕底层接口

过细的 Tool 会迫使模型自己重建业务协议：

**代码块说明｜流程示意：** 这段文本图按箭头方向阅读，用来说明“Tool 粒度：围绕决策，而不是围绕底层接口”中的执行顺序、状态变化或责任流转。它表达逻辑关系，不代表组件必须按图中的数量和位置部署。

```text
set_header() → post_json() → parse_response() → poll_job()
```

过粗的 Tool 又会隐藏关键选择：

**代码块说明｜结构示意：** 这段文本把“Tool 粒度：围绕决策，而不是围绕底层接口”中的关键对象并列出来，帮助读者识别各自责任与边界。它用于概念建模，不代表唯一的产品命名或实现结构。

```text
manage_customer_everything(request)
```

更稳定的粒度通常是一个可描述、可授权、可验收的领域动作，例如：

**代码块说明｜结构示意：** 这段文本把“Tool 粒度：围绕决策，而不是围绕底层接口”中的关键对象并列出来，帮助读者识别各自责任与边界。它用于概念建模，不代表唯一的产品命名或实现结构。

```text
get_customer(customer_id)
create_refund(payment_id, amount, reason)
get_refund_status(refund_id)
```

判断粒度时可以问：它是否具有单一业务意图；参数是否能在调用前确定；权限和副作用是否一致；结果是否能独立验证。如果一个 Tool 内部同时包含“读取订单”和“退款”，两个动作的风险不同，就应该拆开。

## 名称与描述是路由界面

Tool 描述不是普通 API 注释，它是模型选择动作时看到的路由信息。至少应说明：

- Tool 完成什么动作，以及明确不做什么。
- 什么时候使用，哪些相邻 Tool 更合适。
- 关键参数的业务含义、单位和边界。
- 是否产生外部副作用，是否需要审批。
- 结果中的权威字段和新鲜度。

假设一个客服 Agent 收到任务：“把客户 `customer_42` 的收货地址改成上海新地址，不要修改账单地址。”当前 Registry 同时存在客户、订单和支付记录的更新能力。如果其中只暴露下面这个 Tool：

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“名称与描述是路由界面”落成可检查的结构化记录，主要字段包括 `name`、`description`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
name: update_record
description: 更新一条记录
```

Agent 无法从名称和描述判断它更新哪类记录，也不知道 `record_id` 指客户、订单还是支付记录，更无法确认它会不会把收货地址和账单地址一起覆盖。模型只能结合参数名称猜测，选错 Tool 后也很难在执行前发现问题。

更清晰的定义是：

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“名称与描述是路由界面”落成可检查的结构化记录，主要字段包括 `name`、`description`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
name: update_customer_shipping_address
description: >
  更新指定客户的默认收货地址。只修改 shipping address，
  不修改 billing address，也不修改已经创建订单中的地址快照。
```

这里的名称明确了对象是 `customer`、动作是 `update`、修改范围是 `shipping_address`；描述进一步交代不会发生的相邻动作。当任务要求修改“已经创建的订单地址”时，Agent 就应该寻找 `update_order_shipping_address`，而不是误用这个 Tool。

结果描述也必须符合 Executor 真正能观察到的提交阶段。假设 `request_production_deployment` 只负责向部署平台提交异步任务，返回：

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“名称与描述是路由界面”落成可检查的结构化记录，主要字段包括 `deployment_id`、`status`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
deployment_id: deploy_91
status: accepted
```

这只证明部署平台已经接受请求，不证明新版本已经在生产环境运行。因此 Tool 描述应该写“提交生产部署请求并返回任务 ID”，不能写成“完成生产部署”。Agent 需要继续调用 `get_deployment_status(deployment_id)`，观察到 `status: succeeded` 并完成必要验证后，才能报告部署完成。

## Tool Definition 参考 Schema

下面是本 Playbook 的扩展设计，用于表达标准参数 Schema 之外的运行时治理信息：

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“Tool Definition 参考 Schema”落成可检查的结构化记录，主要字段包括 `tool`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
tool:
  name: create_refund
  version: 3.1.0
  description: 为已完成支付创建退款；不负责取消未支付订单

  input_schema:
    type: object
    required: [payment_id, amount, currency, reason]
    properties:
      payment_id: { type: string }
      amount: { type: integer, minimum: 1, description: 最小货币单位 }
      currency: { type: string, enum: [CNY, USD] }
      reason: { type: string, maxLength: 500 }
    additionalProperties: false

  output_schema:
    type: object
    required: [refund_id, status]

  execution:
    timeout_ms: 10000
    side_effect: write
    idempotency: supported
    approval_policy: conditional

  governance:
    required_scopes: [payments.refund]
    sensitivity: financial
    audit: required
```

`execution` 与 `governance` 不是 JSON Schema 或 MCP 的通用必选字段，而是 Registry 可以维护的控制面元数据。它们不必全部暴露给模型，但 Runtime 执行前必须能够读取。

## 参数 Schema 要限制错误空间

好的 Schema 不只检查类型，还尽量把业务不变量前移：

- 使用 `enum`，不要让模型自由生成状态值。
- 明确金额单位、时区、路径根目录和 ID 类型。
- 对互斥参数使用 `oneOf` 或在 Executor 中显式验证。
- 默认拒绝未声明字段，防止模型“顺手”添加危险选项。
- 不把 Secret 放进模型生成的参数；由 Runtime 根据身份注入。

Schema 验证成功只代表输入形状合法，不代表调用已获授权，也不代表外部对象仍处于允许操作的状态。

## Tool Result 应是 Observation，不只是文本

一次成功调用至少要区分业务结果、外部对象标识和证据时间：

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“Tool Result 应是 Observation，不只是文本”落成可检查的结构化记录，主要字段包括 `tool_result`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
tool_result:
  tool_call_id: call_81
  outcome: succeeded
  data:
    refund_id: rf_902
    status: pending
    amount: 6800
    currency: CNY
  observed_at: 2026-08-12T13:20:00+08:00
  external_effect_id: rf_902
  retryable: false
```

自然语言摘要可以作为 `message` 辅助模型理解，但不能替代结构化字段。`status: pending` 与“退款成功”不同；Agent 必须据此决定等待、轮询还是结束。

## Error-as-Data 与 Error-as-Exception

[MCP Schema](https://modelcontextprotocol.io/specification/2025-06-18/schema) 明确区分 Tool 自身执行错误和协议级异常：Tool 执行错误应放在 `CallToolResult` 中并标记 `isError`，而找不到 Tool、协议方法不支持等异常由协议错误表达。这个边界可以推广到内部 Tool 层：

| 情况 | 建议表达 | Agent 是否可据此调整 |
| --- | --- | --- |
| 参数业务校验失败 | Tool Result Error | 可以修正参数 |
| 权限不足 | Tool Result Error / Approval Required | 可以请求授权 |
| 资源不存在 | Tool Result Error | 可以重新查询 |
| 上游限流或超时 | Tool Result Error，标记可重试 | 可以按策略重试 |
| Tool 名称不存在 | Protocol / Runtime Exception | 通常是注册或版本错误 |
| Result 无法反序列化 | Protocol / Adapter Exception | 不应让模型猜测成功与否 |

参考错误对象：

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“Error-as-Data 与 Error-as-Exception”落成可检查的结构化记录，主要字段包括 `error`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
error:
  code: rate_limited
  category: transient
  message: 上游服务限制请求频率
  retryable: true
  retry_after_ms: 3000
  details_ref: trace://run_42/call_81
```

`retryable` 只表示技术上允许再次尝试，不代表重试一定安全。写操作还必须检查幂等与副作用契约。

## 外部协议怎样映射进 Registry

**代码块说明｜层级示意：** 这段文本图按缩进和树枝符号阅读，用来展开“外部协议怎样映射进 Registry”中的父子关系与归属边界。它描述的是逻辑结构，不要求数据库或服务按同样层级拆分。

```text
MCP tools/list ─┐
OpenAPI Spec ───┼→ Adapter → Normalize → Internal Tool Registry
SDK Function ───┤                         ├─ model-visible fields
CLI Wrapper ────┘                         └─ control-plane metadata
```

映射时需要保留来源和版本，不能只复制名称：

- `provider_ref`：Tool 来自哪个 Server、API 或 Package。
- `provider_version`：外部 Schema 的版本或摘要。
- `adapter_version`：规范化逻辑版本。
- `availability`：当前环境是否可达。
- `trust_level`：来源是否经过审核。

外部 Server 宣称一个 Tool 是只读，不足以成为安全事实。Runtime 应根据实际实现、凭证范围和审计结果设置内部风险等级。

## 本章检查

- Tool 是否围绕单一领域动作，而不是泄漏底层协议步骤。
- 名称和描述是否能帮助模型区分相邻能力。
- 参数是否包含单位、枚举、范围和互斥约束。
- Secret 是否由 Runtime 注入，而非进入模型参数。
- Result 是否区分接受、进行中、成功和失败。
- Tool Error 与 Protocol Exception 是否分开。
- Retryable 是否与幂等安全分别判断。
- 外部 Tool 是否经过来源、版本、风险和权限规范化。
