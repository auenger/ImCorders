# Router 与能力发现

作者：杨正武
来源：https://imcoders.cn/playbook/agent/17-capability-routing/
更新：2026-08-12T00:00:00.000Z

根据任务动态选择 Skill、Tool、模型、Agent 或 Workflow 分支，同时管理置信度和回退。

---


当系统只有三个 Tool 时，可以全部放进 Context；当它拥有数百个 Tool、Skill、模型和远程 Agent 时，“全部展示给模型”会同时增加 Token 成本、误选概率和攻击面。Router 的职责不是替 Agent 完成任务，而是先缩小候选动作空间。

![能力发现、路由与执行控制面](/playbook-images/agent/tool-skill-routing.svg)

> Discovery 回答“系统里有什么”，Routing 回答“这次优先考虑什么”，Authorization 回答“当前是否允许执行”。

## 术语来源与适用范围

Router、Registry 和 Capability Discovery 是服务架构、插件系统和 Agent Framework 中常见的工程概念，但没有统一的 Agent Capability Registry 标准。有的系统只路由模型，有的选择 Tool 或 Agent；[OpenAI Agents SDK Handoffs](https://openai.github.io/openai-agents-python/handoffs/) 把专业 Agent 暴露为可选择的交接目标，[OpenAI Agents SDK Tools](https://openai.github.io/openai-agents-python/tools/) 也支持延迟发现大规模 Tool 集合。

本章把 Tool、Skill、Model、Agent 与 Workflow Branch 统一称为“Capability”，用于讨论共同的发现和选择问题。这是本 Playbook 的上位抽象；`Capability Registry` Schema、评分因素和回退状态同样是参考设计，而非外部标准对象。

## Router 路由的不是一种对象

| Capability | Router 决定什么 | 选择后发生什么 |
| --- | --- | --- |
| Skill | 当前任务采用哪套方法 | 加载 Skill 指令与资源索引 |
| Tool | 哪个动作接口进入候选集 | Tool Definition 暴露给模型 |
| Model | 使用哪个模型执行某一步 | Runtime 配置模型与预算 |
| Agent | 由哪个专业执行者处理 | 作为 Tool 调用或 Handoff |
| Workflow Branch | 进入哪条确定性流程 | Runtime 转换到对应节点 |

这些对象可以共享发现入口，但不能假装拥有相同调用语义。选择 Skill 是加载知识；选择 Agent 可能转移控制；选择 Tool 只是把动作加入候选，最终仍要产生合法 Tool Call。

## Capability Registry 参考 Schema

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“Capability Registry 参考 Schema”落成可检查的结构化记录，主要字段包括 `capability`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
capability:
  capability_id: tool://payments/create-refund@3.1
  kind: tool
  name: create_refund
  summary: 为已完成支付创建部分或全额退款
  intents: [refund_payment]
  domains: [payment, customer_support]

  requirements:
    inputs: [payment_id, amount, currency]
    environment: [payments_api]
    scopes: [payments.refund]

  behavior:
    side_effect: financial_write
    latency_class: interactive
    cost_class: low
    supports_dry_run: false

  compatibility:
    agent_runtime: ">=2.4"
    regions: [cn, us]

  provenance:
    provider: mcp://payments-server
    schema_digest: sha256:8fa...
    reviewed_at: 2026-08-01
```

这份 Schema 是 Playbook 扩展设计。Registry 中既有模型可见的发现信息，也有仅供 Runtime 使用的权限、成本和风险元数据；实际实现可以拆成多个索引，而不必放进同一张表。

## 先硬过滤，再软排序

Router 不应该让模型在明显不可用的能力中“凭感觉选择”。推荐管线是：

**代码块说明｜流程示意：** 这段文本图按箭头方向阅读，用来说明“先硬过滤，再软排序”中的执行顺序、状态变化或责任流转。它表达逻辑关系，不代表组件必须按图中的数量和位置部署。

```text
Goal + Task + Current State
          ↓
Intent / Entity Extraction
          ↓
Hard Filters
  environment / compatibility / tenant / region
          ↓
Candidate Retrieval
  keyword / embedding / taxonomy
          ↓
Rerank
  fit / confidence / latency / cost / reliability
          ↓
Expose a small candidate set
          ↓
Agent decision → Permission check → Execute
```

Hard Filter 只使用可以确定的约束；相似度、历史成功率和成本属于软排序。权限可以用于提前隐藏明显无权发现的能力，但最终授权仍必须在执行时针对真实参数重新检查。

## 规则路由、模型路由与混合路由

### 规则路由

适合高确定性、输入结构明确或合规要求固定的场景，例如文件扩展名为 `.pdf` 时加载 PDF Skill。优点是可解释、便宜；缺点是难覆盖自然语言长尾。

### 模型路由

适合意图模糊、候选语义接近或需要理解长上下文的场景。模型应输出结构化候选、理由和不确定性，而不是直接执行高风险动作。

### 混合路由

先用规则排除不兼容和越界项，再用检索与模型排序，通常更适合生产环境：

**代码块说明｜流程示意：** 这段文本图按箭头方向阅读，用来说明“混合路由”中的执行顺序、状态变化或责任流转。它表达逻辑关系，不代表组件必须按图中的数量和位置部署。

```text
Deterministic Gate → Semantic Retrieve → Model Rerank → Runtime Verify
```

“模型置信度 0.91”不是天然可信概率。只有在标注数据上做过校准，它才可以用于阈值决策；否则更适合作为相对排序信号。

## 低置信度不是错误，应有正式回退

Router 至少需要以下结果：

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“低置信度不是错误，应有正式回退”落成可检查的结构化记录，主要字段包括 `route_decision`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
route_decision:
  decision: clarify
  candidates:
    - { id: skill://invoice-analysis, score: 0.54 }
    - { id: skill://expense-audit, score: 0.49 }
  missing_information: [用户希望提取发票还是审计报销]
  reason_code: ambiguous_intent
```

参考回退顺序：

1. 用低成本 Observation 补齐事实。
2. 向用户提出一个能真正区分候选的问题。
3. 退回更通用、只读的能力。
4. 转给人工或专业 Agent。
5. 明确拒绝，而不是随机选择。

Router 也可以返回 `no_match`、`unavailable`、`incompatible` 或 `policy_hidden`。这些状态是本 Playbook 建议的内部语义，不是统一协议枚举。

## 发现不等于授权

一个用户可以知道系统存在“退款”能力，但没有权执行退款；也可能由于最小披露原则，连能力详情都不应看到。需要区分三道门：

**代码块说明｜结构示意：** 这段文本把“发现不等于授权”中的关键对象并列出来，帮助读者识别各自责任与边界。它用于概念建模，不代表唯一的产品命名或实现结构。

```text
Discoverable?  是否允许看到名称和描述
Selectable?    是否适合当前任务与环境
Executable?    当前身份、参数和授权是否允许执行
```

Router 的命中不能生成权限。执行时仍要检查用户身份、Agent 身份、Tool 风险、资源所有权和本次批准。

## 路由结果怎样进入 Context

只暴露最小候选集，并保留为什么命中：

**代码块说明｜结构示意：** 这段文本把“路由结果怎样进入 Context”中的关键对象并列出来，帮助读者识别各自责任与边界。它用于概念建模，不代表唯一的产品命名或实现结构。

```text
[Selected Skill Candidate]
pr-review — 因任务包含 PR URL 且目标是合并判断

[Available Tools]
get_pull_request — 读取 PR 元数据
read_diff — 读取变更内容
get_ci_status — 查询 CI 当前状态
```

不要把 Registry 中的 Secret 引用、内部风险策略和所有隐藏 Capability 一起放进模型 Context。

## 怎样评估 Router

Router 评估至少包括：

- **Top-k Recall**：正确能力是否进入候选集。
- **Top-1 Accuracy**：首选是否正确。
- **Abstention Quality**：不确定时是否正确澄清或拒绝。
- **Forbidden Exposure Rate**：是否泄露不可发现能力。
- **Downstream Success**：路由是否真正提高任务成功率。
- **Cost / Latency**：路由本身是否比任务还昂贵。
- **Calibration**：置信度区间是否对应实际正确率。

只测分类准确率会遗漏最危险的失败：选到了语义相似但权限、区域或副作用不兼容的能力。

## 本章检查

- Discovery、Routing 与 Authorization 是否分别建模。
- Registry 是否记录种类、来源、版本、依赖、风险和兼容性。
- 是否先做确定性过滤，再做语义排序。
- 是否限制暴露给模型的候选数量与信息范围。
- 低置信度是否进入澄清、降级或拒绝流程。
- Router 分数是否经过校准，而不是伪装成概率。
- 最终执行是否重新检查真实参数和权限。
- 是否用下游成功、安全、成本与校准共同评估路由。
