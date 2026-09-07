# Prompt、Skill、Model 与 Agent Version

作者：杨正武
来源：https://imcoders.cn/playbook/agent/23-agent-versioning/
更新：2026-08-12T00:00:00.000Z

把一次 Run 使用的模型、Prompt、Skill、Tool Schema、策略和 Runtime 版本完整固定下来。

---


“Agent v7 的质量下降了”通常不是足够的诊断。模型可能没变，但 Prompt、Skill、Tool Schema、检索索引、权限策略或 Runtime 调度器已经变化。只有把一次 Run 实际解析出的资产组合固定下来，质量变化才有可能被归因。

> Agent Version 是发布身份，Version Manifest 是一次执行实际使用的依赖锁文件；两者相关，但不是同一个对象。

## 术语来源与适用范围

[Semantic Versioning](https://semver.org/)用 `MAJOR.MINOR.PATCH` 表达公共 API 的兼容性变化，内容寻址和 Lockfile 则来自软件供应链。模型、Prompt 和数据集并不天然拥有 SemVer 所要求的公共 API，因此不能机械地把每次文案调整称为 Patch。

本章的 `Agent Version Manifest`、兼容性维度与实验比较结构是 Playbook 参考设计，不是模型厂商或 Agent 协议的统一标准。它适用于由多项动态资产组合而成的 Agent；单文件脚本也可以采用简化 Manifest。

## 发布版本与解析版本分开

**代码块说明｜流程示意：** 这段文本图按箭头方向阅读，用来说明“发布版本与解析版本分开”中的执行顺序、状态变化或责任流转。它表达逻辑关系，不代表组件必须按图中的数量和位置部署。

```text
Agent Release: support-agent@7.2
        ↓ resolve at Run start
Agent Version Manifest avm_42
  model: provider/model@revision
  prompt: sha256:...
  skills: [...]
  tools: schema digests
  policy: refund-policy@4
  runtime: 2.8.1
  retrieval index: kb@2026-08-10
```

发布版本可以包含范围，例如“允许使用 `refund-skill ^3.0`”；Run 开始时必须解析成精确版本并写入 Manifest。运行中热更新 Registry 不应悄悄改变已在执行的 Run，除非通过显式迁移或 Replan 事件。

## Agent Version Manifest

![Agent Version Manifest：从发布身份到可复现执行组合](/playbook-images/agent/agent-version-manifest.svg)

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“Agent Version Manifest”落成可检查的结构化记录，主要字段包括 `agent_version_manifest`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
agent_version_manifest:
  manifest_id: avm_42
  agent_release: support-agent@7.2.0
  created_at: 2026-08-12T09:30:00Z

  model:
    provider: example
    model_id: reasoning-large
    revision: 2026-07-28
    parameters_digest: sha256:ab12...

  prompts:
    system: {uri: prompt://support/system@12, digest: sha256:91e...}
  skills:
    - {id: refund-assistance@3.1.2, digest: sha256:7cd...}
  tools:
    - {id: create_refund@3.1, schema_digest: sha256:8fa...}

  runtime:
    version: 2.8.1
    context_policy: context-budget@5
    router: capability-router@9
    permission_policy: refund-policy@4
  data:
    retrieval_index: support-kb@2026-08-10
  environment:
    region: cn
    feature_flags: {new_refund_flow: treatment}
```

完整 Prompt、Skill 和 Tool 内容可以保存在 Artifact Store，Manifest 保存不可变引用与摘要。模型供应商若不暴露精确权重版本，应记录供应商 Model ID、请求参数、调用时间和返回的系统标识，并承认复现边界。

## 每类资产有不同兼容性

| 资产 | 需要观察的变化 | 可能的破坏 |
| --- | --- | --- |
| Prompt | 指令、示例、优先级 | 行为与格式漂移 |
| Skill | 触发条件、方法、完成标准 | 路由和执行路径变化 |
| Tool Schema | 名称、参数、结果、错误 | 调用失败或错误解释 |
| Model | 能力、上下文、价格、策略 | 质量、成本、安全变化 |
| Policy | 权限、阈值、审批人 | 可执行范围变化 |
| Runtime | 调度、重试、Context Assembly | 轨迹与副作用变化 |
| Retrieval Data | 内容、切分、Embedding、索引 | 事实与召回变化 |

Agent Release 的 Major / Minor / Patch 可以由团队定义，但必须写清“公共行为契约”是什么。例如：Major 表示 Tool 或 Artifact 契约不兼容，Minor 表示新增能力，Patch 表示不改变验收契约的修复。模型升级即使名称相近，也应先视为独立依赖变更。

## 单变量实验是理想，交互效应是真实世界

如果同时更换模型、Prompt 和 Tool Schema，实验只能评价整个 Bundle，不能声称“新模型提升 8%”。优先一次改变一个主要变量；必须组合迁移时，设置 Factorial 或至少增加消融组。

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“单变量实验是理想，交互效应是真实世界”落成可检查的结构化记录，主要字段包括 `experiment_comparison`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
experiment_comparison:
  experiment_id: exp_refund_17
  baseline_manifest: avm_41
  candidate_manifest: avm_42
  intended_changes: [prompt.system]
  unexpected_differences: []
  dataset: support-regression@12
  evaluators: eval-suite@8
  slices: [read_only, financial_write, recovery]
```

实验运行前比较两个 Manifest；出现未声明差异时，应阻断或把结果标记为 Bundle Comparison。

## 发布、灰度与回滚

**代码块说明｜层级示意：** 这段文本图按缩进和树枝符号阅读，用来展开“发布、灰度与回滚”中的父子关系与归属边界。它描述的是逻辑结构，不要求数据库或服务按同样层级拆分。

```text
Offline Regression → Shadow → 1% Canary → 10% → 50% → Full
                          └──── 任一硬门禁失败 → Stop / Rollback
```

流量分组必须稳定，避免同一用户在 Baseline 与 Candidate 间反复切换。Canary 同时看质量、成本、延迟和安全；低频高风险动作需要最小样本量或延长观察窗。回滚不仅切回 Agent Release，还要处理已创建的 Run：固定旧 Manifest 继续、迁移到新版本，或在安全点重新开始，必须由策略明确决定。

## 实施检查表

- 每个 Run 是否绑定解析后的不可变 Manifest。
- Prompt、Skill、Tool Schema、Policy、Runtime 和检索数据是否独立版本化。
- 实验差异是否可机器比较，未声明差异是否会被发现。
- 模型版本不可精确固定时，是否记录了复现限制。
- Canary 是否使用稳定分组并覆盖高风险切片。
- 回滚是否定义了在途 Run 的处理方式，而不只切换新流量。
