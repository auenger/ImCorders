# Skill：可执行知识的工程结构

作者：杨正武
来源：https://imcoders.cn/playbook/agent/16-skill-engineering/
更新：2026-08-12T00:00:00.000Z

把领域方法、操作步骤、资源和检查标准封装成可版本化、可选择和可评估的能力包。

---


Skill 把一次成功任务背后的方法、检查顺序、资源和完成标准从临时对话中提取出来，使它能够被重复选择、版本化和评估。它不是“给模型再加一段 Prompt”，也不会因为被安装就自动拥有 Tool 或权限。

> Prompt 表达当前指令，Skill 封装可复用方法，Tool 提供外部动作，Workflow 固化控制流。

## 术语来源与适用范围

“Skill”在不同产品中可能表示插件、动作、提示模板或能力包，并不是只有一种行业定义。[Agent Skills Specification](https://agentskills.io/specification) 给出了一种开放目录格式：以 `SKILL.md` 为必需入口，可选包含 `scripts/`、`references/` 和 `assets/`；其 Frontmatter 规定 `name`、`description` 等字段，并把 `allowed-tools` 标记为实验字段。

本章借鉴这种“渐进加载的目录能力包”形态，但下面的依赖声明、完成契约、测试矩阵和发布流程是本 Playbook 的工程扩展建议。文中称为“参考结构”而不是通用标准；实现具体 Agent Skills 格式时，仍应以其当前规范为准。

## Skill、Prompt、Tool 与 Workflow 的边界

| 对象 | 核心问题 | 是否直接执行动作 | 典型变化频率 |
| --- | --- | --- | --- |
| Prompt | 这一次怎样理解和回答 | 否 | 每个 Run |
| Skill | 这一类任务通常怎样做好 | 通过 Agent 间接执行 | 随方法演进 |
| Tool | 可以对环境做什么 | 是 | 随接口版本变化 |
| Workflow | 步骤和分支必须怎样流转 | 是，由 Runtime 编排 | 随业务流程变化 |

如果步骤允许 Agent 根据证据调整顺序，更像 Skill；如果顺序、审批点和参与方必须确定，更像 Workflow。Skill 可以引用 Workflow，也可以要求调用 Tool，但不能替代它们。

## Skill Package 参考结构

**代码块说明｜层级示意：** 这段文本图按缩进和树枝符号阅读，用来展开“Skill Package 参考结构”中的父子关系与归属边界。它描述的是逻辑结构，不要求数据库或服务按同样层级拆分。

```text
pr-review/
├── SKILL.md              # 触发条件、方法与完成标准
├── references/           # 按需加载的领域资料
│   ├── security.md
│   └── compatibility.md
├── scripts/              # 可重复执行的确定性辅助程序
│   └── collect-diff.sh
├── assets/               # 报告模板、示例或静态资源
│   └── review-template.md
└── tests/                # 本 Playbook 建议的扩展目录
    ├── cases.yaml
    └── expected/
```

前三类可选目录来自 Agent Skills 规范的常见结构；`tests/` 是本 Playbook 为版本治理提出的扩展，并非该规范的必需目录。

## SKILL.md 应回答什么

一个可执行的 Skill 至少要让 Agent知道：

1. **何时触发**：正例、反例和相邻 Skill。
2. **开始条件**：必要输入、环境和可用 Tool。
3. **操作方法**：步骤、关键判断和可调整部分。
4. **风险边界**：禁止事项、审批点和敏感数据处理。
5. **完成标准**：必须产生什么 Artifact，怎样验证。
6. **按需资料**：什么时候读取哪个 Reference、运行哪个 Script。

推荐把 Frontmatter 保持精简，让 `name` 与 `description` 承担发现职责，详细方法放在正文。不要在描述里塞完整操作手册，否则每次能力发现都会污染 Context。

## 依赖声明不等于权限授予

可以用独立的参考清单表达 Skill 依赖：

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“依赖声明不等于权限授予”落成可检查的结构化记录，主要字段包括 `skill_requirements`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
skill_requirements:
  skill: pr-review
  tools:
    required: [get_pull_request, read_diff]
    optional: [run_test]
  environment:
    workspace: repository
    network: optional
  permissions:
    minimum: [repository.read]
    conditional:
      - when: run_test
        require: workspace.execute
  compatibility:
    agent_runtime: ">=2.4"
```

`skill_requirements` 是本 Playbook 的说明性 Schema，不是 Agent Skills 标准字段。即使 Skill 声明需要 `repository.write`，Runtime 仍必须基于当前身份和任务重新授权；包作者不能自行授予权限。

## 渐进加载：把 Context 留给当前任务

Skill 通常分三层进入 Context：

**代码块说明｜流程示意：** 这段文本图按箭头方向阅读，用来说明“渐进加载：把 Context 留给当前任务”中的执行顺序、状态变化或责任流转。它表达逻辑关系，不代表组件必须按图中的数量和位置部署。

```text
发现阶段：name + description
     ↓ 命中
执行阶段：SKILL.md 方法正文
     ↓ 确有需要
资源阶段：specific reference / script / asset
```

这不是越懒加载越好。开始执行前必须读取的安全约束和完成标准应留在主入口，不能藏在模型“可能不会打开”的 Reference 中。大型范例、厂商手册和边缘场景才适合按需加载。

## Script、Reference 与 Asset 的职责

- **Script**：处理确定性、重复性高的操作，例如解析、校验和格式转换。必须可审计输入输出，不能把 Secret 写进日志。
- **Reference**：提供模型判断所需的领域知识。需要注明版本、适用范围和权威来源。
- **Asset**：提供模板、样式或静态材料。它是输入资产，不应被误认为已经完成的 Artifact。

脚本成功退出也不等于任务完成。Skill 的验收需要同时检查脚本结果、目标 Artifact 和外部环境状态。

## 版本化什么

Skill 版本变化至少分三类：

| 变化 | 例子 | 建议影响 |
| --- | --- | --- |
| 方法修订 | 增加一项安全检查 | Minor，重新跑回归集 |
| 契约变化 | 新增必需输入或更换输出结构 | Major，检查调用方兼容性 |
| 说明修正 | 修复错字、不改变行为 | Patch，运行基础校验 |

版本号规则是团队政策，不是 Skill 的天然标准。重要的是每次 Run 能追溯实际加载的 Skill 内容摘要、版本及依赖资源版本，而不是只记录可变目录名。

## 怎样测试 Skill

Skill 测试不能只检查 Markdown 能否解析，还要比较它是否改变执行质量：

**代码块说明｜结构示意：** 这段文本把“怎样测试 Skill”中的关键对象并列出来，帮助读者识别各自责任与边界。它用于概念建模，不代表唯一的产品命名或实现结构。

```text
Trigger Evaluation   应用时是否命中，不应用时是否避开
Method Evaluation    是否执行关键步骤和风险检查
Outcome Evaluation   Artifact 是否达到验收标准
Efficiency           Tool Call、Token、延迟是否合理
Safety               是否越权、泄密或跳过审批
Robustness           缺少 Tool、输入异常时是否正确降级
```

推荐在相同模型、Tool 和数据集下做有 Skill / 无 Skill或新旧版本对比。成功率提高但副作用违规率上升，不能算升级成功。

## 何时不要做成 Skill

- 只对当前请求成立的一次性说明，应留在 Prompt。
- 只有一个稳定 API 动作，应做成 Tool。
- 必须严格顺序执行、不能由模型调整的业务流程，应做成 Workflow。
- 尚未验证的经验，应先留在 Memory Candidate 或实验说明中。
- 需要强隔离和独立生命周期的专业执行者，可能更适合 Agent，而不是无限膨胀的 Skill。

## Skill 质量检查表

- 名称和描述能否准确触发，并说明不适用场景。
- 是否声明必要输入、依赖 Tool、环境与兼容性。
- 权限要求是否只是依赖说明，而非自我授权。
- 主入口是否包含不能漏读的安全边界与完成标准。
- Reference、Script 和 Asset 是否各司其职并可追溯。
- 是否避免加载与当前任务无关的大量内容。
- 是否有正例、反例、失败和降级测试。
- 发布后能否还原某次 Run 使用的确切版本。
