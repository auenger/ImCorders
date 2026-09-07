# Workspace 与 Sandbox：执行环境也是状态

作者：杨正武
来源：https://imcoders.cn/playbook/agent/13-workspace-sandbox/
更新：2026-08-12T00:00:00.000Z

管理 Agent 跨工具调用使用的文件、代码、浏览器和中间产物，并控制隔离与生命周期。

---


Agent 不只在消息和 JSON State 中工作。它会下载文件、修改代码、打开浏览器、启动进程、生成图片、写入临时数据库，并在多个 Tool 调用之间继续使用这些结果。

这些持续存在的执行现场构成 Workspace。它既是 Agent 操作的环境，也是任务状态的一部分。如果 Runtime 只保存对话和 Run State，却在恢复时给 Agent 一个全新的目录或浏览器会话，Agent 看似回到了同一个 Step，实际已经失去了工作现场。

Sandbox 则回答另一个问题：这个 Workspace 能访问什么、能影响什么，以及如何与其他 Run 隔离。

## 术语来源与适用范围

Workspace 和 Sandbox 都是软件开发、IDE、容器与安全执行环境中的通用术语，但不同 Agent 产品对它们的范围定义差异很大：Workspace 可能只是一个目录，也可能包含代码仓库、浏览器会话、临时数据库和运行中的进程；Sandbox 可能指进程隔离，也可能同时覆盖文件、网络、身份和 Secret Policy。

本章沿用 `Run` 表示一次目标明确的 Agent 执行实例。讨论“Run 独占 Workspace”或“多个 Run 共享 Workspace”时，关注的是不同逻辑执行实例之间的资源隔离，不是不同操作系统进程之间的关系。外部系统即使把这种执行实例称为 Task、Job 或 Workflow Execution，本章的隔离问题仍然成立。

本章把 Workspace 提升为“一等 Runtime 对象”，是本 Playbook 的架构建议，不是现有协议要求。后文给出的 Workspace Schema、`ALLOCATED → PREPARED → ACTIVE` 生命周期和 Artifact Promotion 结构都属于参考设计；具体系统可以映射到容器、虚拟机、Git Worktree、浏览器 Profile 或远程开发环境。

本章所说的 Sandbox 也不是某个特定产品或容器技术，而是对执行隔离和权限边界的统称。安全保证最终取决于实际操作系统、容器、网络和身份控制，不能由这些概念名称本身提供。

## Workspace、Context 与 Run State 不同

三者可以用“看见、知道、拥有”来区分：

**代码块说明｜结构示意：** 这段文本把“Workspace、Context 与 Run State 不同”中的关键对象并列出来，帮助读者识别各自责任与边界。它用于概念建模，不代表唯一的产品命名或实现结构。

```text
Context：模型这一轮看见什么
Run State：Runtime 知道任务现在在哪里
Workspace：执行过程实际拥有哪些可操作资源
```

例如 Agent 修改 `src/auth.ts`：

- 文件内容存放在 Workspace。
- `workspace_ref`、当前 commit 和“补丁尚未验证”写入 Run State。
- 当前 Task 需要的代码片段才进入 Context。

把完整文件塞进 State 会造成复制与版本漂移；把文件只塞进 Context 会在下一轮裁剪后丢失；只保留路径而不记录版本，则无法判断恢复时是否仍是同一份文件。

## 将 Workspace 设计为一等 Runtime 对象

如果采用本章建议，一份 Workspace 记录可以包含：

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“将 Workspace 设计为一等 Runtime 对象”落成可检查的结构化记录，主要字段包括 `workspace`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
workspace:
  workspace_id: ws_71
  run_id: run_128
  type: git_worktree
  root: /workspaces/ws_71
  base:
    repository: git://example/auth-service
    revision: 81a23f0
  current_revision: 3bc92e1
  isolation_policy: code_sandbox_v3
  mounts:
    - source: artifact://requirements/18
      target: /inputs/requirements.md
      mode: read_only
  active_resources:
    browser_session: browser_14
    processes: [proc_22]
  quota:
    disk_mb: 2048
    process_count: 16
  expires_at: 2026-08-12T16:00:00+08:00
```

它不要求所有 Workspace 都是目录。数据分析 Agent 可能使用临时数据库和 Notebook，浏览器 Agent 可能主要依赖浏览器 Profile，设计 Agent 则可能围绕画布和素材库工作。关键在于 Runtime 能给现场一个稳定身份、生命周期和权限策略。

## 文件系统也是状态

Tool 调用经常把文件系统当成纯输入输出接口，但对于长任务，文件变化本身就是连续状态：

**代码块说明｜流程示意：** 这段文本图按箭头方向阅读，用来说明“文件系统也是状态”中的执行顺序、状态变化或责任流转。它表达逻辑关系，不代表组件必须按图中的数量和位置部署。

```text
base revision
   ↓ 生成诊断记录
workspace revision 1
   ↓ 修改配置
workspace revision 2
   ↓ 格式化与测试修正
workspace revision 3
   ↓ 验证通过
promoted artifact / commit
```

每个重要边界都应有可识别版本。Git Workspace 可以使用 commit 或 tree hash；普通目录可以使用文件清单和内容 hash；浏览器状态可以使用受控 session snapshot。这里的文件清单只是某个 Workspace 的版本记录，不是前文定义的 Context Assembly Manifest。恢复时先验证版本，再继续执行。

## Sandbox 控制影响范围

Workspace 说明资源在哪里，Sandbox Policy 说明 Agent 可以对它做什么。隔离至少包括：

| 维度 | 需要控制的内容 |
| --- | --- |
| 文件 | 可读写路径、只读挂载、文件大小、符号链接 |
| 进程 | 可执行命令、进程数、CPU、内存和超时 |
| 网络 | 允许访问的域名、端口、私网和出站策略 |
| 身份 | 使用用户、Agent 还是服务身份 |
| Secret | 哪个 Tool 在执行时可获得哪个 Secret |
| 设备 | 浏览器、GPU、摄像头或其他外设 |

安全边界不能只写在 Prompt 中。即使模型承诺“不访问 `/etc`”，执行器也必须用实际文件权限阻止它。

Sandbox 还应区分“可读取”和“可外发”。Agent 可能被允许读取私有仓库，却不应把代码发送给任意外部模型或网站。数据流向是权限模型的一部分。

## 多个 Run 是否共享 Workspace

默认策略应是隔离，因为共享带来隐式状态和写冲突。但不同场景可以采用不同模型：

| 模型 | 优点 | 风险 | 适用场景 |
| --- | --- | --- | --- |
| Run 独占 | 可复现、冲突少、清理简单 | 占用更多资源 | 代码修改、敏感任务 |
| Thread 共享 | 连续交互方便 | 多个 Run 相互污染 | 单用户探索性工作 |
| 只读共享 + 写时复制 | 复用大体积基础数据 | 实现复杂 | 大仓库、模型与数据集 |
| 显式共享区 | 协作 Agent 可交换 Artifact | 需要所有权和版本控制 | Multi-Agent 协作 |

不要因为两个 Run 属于同一 Thread 就自动共享可写目录。Thread 表示交互连续性，不代表执行可以无冲突地复用同一现场。

如果必须共享，至少需要：

- 资源所有权或文件租约。
- 基于版本的写入检查。
- 冲突检测和合并策略。
- 每次变化的作者、Run 和来源记录。

## 浏览器和进程也属于 Workspace

浏览器 Agent 的状态不只是 URL。登录 Cookie、页面历史、打开的 Tab、下载文件和页面内临时状态都可能影响下一步。恢复策略要明确：

- 能否恢复同一登录身份。
- 页面是否需要重新加载并再次观察。
- DOM 引用或元素坐标是否已经失效。
- 下载中的文件和未提交表单怎样处理。

长时间运行的进程也不能只存 PID。PID 在重启后没有意义，应记录启动命令摘要、工作目录、输入输出 Artifact、健康状态和可重建方式。能重建的资源优先重建，不能安全重建的资源应让 Run 进入等待或失败。

## Workspace 的参考生命周期

下面是一套用于说明资源分配、冻结和清理边界的参考生命周期，不是行业统一状态机：

**代码块说明｜层级示意：** 这段文本图按缩进和树枝符号阅读，用来展开“Workspace 的参考生命周期”中的父子关系与归属边界。它描述的是逻辑结构，不要求数据库或服务按同样层级拆分。

```text
ALLOCATED → PREPARED → ACTIVE → FROZEN → ARCHIVED
                           │          └──► DESTROYED
                           └─────────────► DESTROYED
```

- `ALLOCATED`：资源已经分配，但输入尚未装载。
- `PREPARED`：基础版本、只读输入和权限已经确认。
- `ACTIVE`：Run 可以读写和启动受控资源。
- `FROZEN`：暂停写入，用于验收、交接或生成 Checkpoint。
- `ARCHIVED`：保留 Workspace 文件清单、差异和必要 Artifact，工作现场不再运行。
- `DESTROYED`：临时资源已经删除，仅保留审计记录。

进入 `COMPLETED` 不应该立即删除 Workspace。正式 Artifact 可能尚未提升，用户也可能需要短期检查。保留时间应由数据敏感性、成本和恢复需求共同决定。

## 从中间文件提升为 Artifact 的参考流程

Workspace 中的文件默认只是中间状态。只有经过显式提升，才成为可以被其他 Run、用户或系统稳定引用的 Artifact。

**代码块说明｜Playbook 参考 Schema：** 这段 YAML 把“从中间文件提升为 Artifact 的参考流程”落成可检查的结构化记录，主要字段包括 `artifact_promotion`。除非正文另有说明，字段名和示例值用于解释设计语义，不是某个外部协议的标准格式。

```yaml
artifact_promotion:
  source:
    workspace_id: ws_71
    path: reports/login-regression.md
    content_hash: sha256:8be...
  artifact:
    artifact_id: artifact_93
    type: report
    media_type: text/markdown
    title: 登录回归诊断报告
  provenance:
    run_id: run_128
    task_id: task_6
    agent_version: agent_v7
  validation:
    status: passed
    evidence: artifact://test-output/52
```

提升过程通常要完成：

1. 冻结或读取确定版本的源文件。
2. 计算 hash 并扫描敏感信息。
3. 记录来源、作者、生成方式和验证证据。
4. 复制到受管理的 Artifact Store。
5. 在 Run State 中登记正式引用。

仅在最终 Response 中说“报告已生成”不够。Response 会变化，也可能被截断；Artifact 必须有独立身份和生命周期。

## 恢复时先校验现场

从 Checkpoint 恢复时，Runtime 应比较：

- Workspace 是否仍存在。
- 基础版本和当前版本是否与 Checkpoint 一致。
- 外部挂载和权限是否仍有效。
- 未完成进程是否可安全重建。
- 已发生的副作用是否已登记。

如果 Workspace 被用户手动修改，不应直接覆盖。可以创建新分支、重新应用补丁或要求人工选择。恢复的目标是继续同一份工作，不是把现场强行还原成 Runtime 记忆中的样子。

## 本章检查

- Workspace 是否拥有稳定 ID、基础版本、当前版本和生命周期。
- Run State 是否只引用 Workspace，而不是复制全部文件内容。
- Sandbox 是否用实际执行边界控制文件、网络、身份和 Secret。
- 多个 Run 的可写资源是否默认隔离，显式共享时是否有并发控制。
- 浏览器和进程状态是否有可恢复或可重建策略。
- 中间文件是否经过 hash、来源和验证登记后才成为正式 Artifact。
