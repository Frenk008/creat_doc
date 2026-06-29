# Skill 体系二轮审查与修复 Spec

## Why
一轮修复（review-skill-gaps）解决了 5 类问题，但本次全量复审发现：上一轮修复存在**回归残留**（`prerequisite_action` 仍在），同时引入了新的**Docker 逻辑矛盾**（webapp-testing 声明"不负责启动项目"却保留了 Docker 清理/错误处理/约束），此外还暴露出多条**跨 Skill 数据流断裂**（runtime.yaml 无人消费、retake-list.yaml 无下游、writers 不读 manifest.yaml 嵌入图表）。

## What Changes
本轮修复聚焦"让数据真正流通 + 消除逻辑矛盾 + 补全字段契约"，共 28 项，按严重度分级：

- **P0 回归残留**：webapp-testing 伪代码仍用 `prerequisite_action`，与脚本/schema/planner 不一致
- **P0 Docker 逻辑矛盾**：doc-gen / webapp-testing / runtime-explorer 三处对"谁启动项目"的描述互相矛盾
- **P1 数据流断裂**：runtime.yaml 无消费者、retake-list.yaml 无下游、writers 不嵌入图表、字段名不一致
- **P2 文档/脚本缺陷**：路径前缀不一致、枚举值缺失、dead code、编号重复、模板语法违规

## Impact
- 受影响 Skill 文档：doc-gen、webapp-testing、runtime-explorer、screenshot-planner、screenshot-reviewer、manual-writer、api-doc-writer、database-spec-writer、document-renderer
- 受影响模板/脚本：pkb-schema.yaml、screenshot-config.yaml、generate_screenshots.py、manual-outline.md
- 不涉及任何业务源码

## ADDED Requirements

### Requirement: 消除 Docker 逻辑矛盾，统一"用户自行启动项目"
整套 Skill 对项目启动方式 SHALL 保持一致表述：项目由用户自行启动，doc-gen/webapp-testing/runtime-explorer 均不负责通过 Docker 启动项目。

已核实的矛盾点（必须全部修复）：
- doc-gen `--deep` 参数说明（行 260）写"Docker 启动 + chrome-devtools-mcp"，但行 96-103 和行 184 写"用户需自行启动项目，不依赖 Docker 自动启动" → 删除"Docker 启动"
- webapp-testing 前置条件（行 12）声明"不负责启动项目"，但残留：Step 6 Docker 清理（行 179-186，含未定义的 `{compose_file}` 变量）、采集报告含 Docker 状态（行 195）、错误处理含 Docker 未安装/启动失败/端口冲突（行 216-218）、约束"只通过 Docker 启动和浏览器操作"（行 231）→ 全部清理
- runtime-explorer 前置条件（行 12）引用"webapp-testing Step 2 已执行"作为 Docker 启动依据，但 webapp-testing Step 2 是"连接性检测"不是 Docker 启动 → 改为"目标项目已由用户自行启动"

#### Scenario: Docker 表述一致性
- **WHEN** 通读 doc-gen / webapp-testing / runtime-explorer 三个 SKILL.md
- **THEN** 不存在任何"Docker 自动启动项目"的表述，不存在 Docker 清理/Docker 错误处理的残留逻辑

### Requirement: 修复 prerequisite_action 回归残留
webapp-testing SKILL.md 的伪代码 SHALL 与其引用的实际脚本 generate_screenshots.py、screenshot-planner 产出、pkb-schema.yaml 保持字段一致，统一使用 `action`。

- 行 99 `if shot.get("prerequisite_action"):` → `if shot.get("action"):`
- 行 101 `execute_action(page, shot["prerequisite_action"])` → `execute_action(page, shot["action"])`

#### Scenario: 字段名一致性
- **WHEN** grep webapp-testing SKILL.md 中 `prerequisite_action`
- **THEN** 无任何匹配

### Requirement: runtime.yaml 定义明确的消费方
runtime-explorer 产出的 runtime.yaml SHALL 有下游消费者，或被明确声明为仅用于 Step 6 PKB 回写合并的中间产物。

- manual-writer SHALL 将 runtime.yaml 列为**可选输入**，在生成功能说明时补充运行时发现的表单校验提示（discovered_validation_rules）和操作反馈信息（discovered_feedback_messages）
- 如不消费，则 doc-gen/runtime-explorer SHALL 明确标注"runtime.yaml 为中间产物，结构化发现已合并回 pages.yaml/workflows.yaml"

#### Scenario: runtime.yaml 消费
- **WHEN** runtime-explorer 产出 runtime.yaml
- **THEN** 至少有一个 writer 将其列为可选输入，或 SKILL 中明确声明其为中间产物

### Requirement: retake-list.yaml 建立下游消费契约
webapp-testing SHALL 将 `output/retake-list.yaml` 列为可选输入，并定义补拍模式逻辑。

- webapp-testing 输入章节增加 `output/retake-list.yaml`（可选）
- 执行流程增加补拍分支：若 retake-list.yaml 存在，仅采集其中列出的截图 ID，覆盖原文件

#### Scenario: 补拍闭环
- **WHEN** screenshot-reviewer 产出 retake-list.yaml
- **THEN** webapp-testing 可读取该文件并仅补拍不合格截图

### Requirement: writers 声明并使用 manifest.yaml 嵌入图表
manual-writer 和 api-doc-writer SHALL 将 `output/diagrams/manifest.yaml` 列为可选输入，并在文档中嵌入对应图表。

- manual-writer 输入章节增加 manifest.yaml，生成规则增加"在对应功能章节嵌入流程图和功能总览图"
- api-doc-writer 输入章节增加 manifest.yaml，生成规则增加"在接口分组中嵌入时序图 sequence-*.png"

#### Scenario: 图表嵌入
- **WHEN** diagram-generator 产出 manifest.yaml 和 PNG 图表
- **THEN** manual-writer 和 api-doc-writer 读取 manifest.yaml 并在文档对应位置嵌入图表引用

### Requirement: 统一 manifest.yaml 图片路径前缀
manifest.yaml 中的 file 字段路径 SHALL 与 writer 在 Markdown 中嵌入的路径一致。

- 统一为相对于 output/ 目录的路径（如 `diagrams/er-diagram.png`），或在 writer 嵌入时做路径转换

#### Scenario: 路径一致
- **WHEN** writer 读取 manifest.yaml 的 file 字段嵌入 Markdown
- **THEN** 图片路径在最终 Markdown 中能正确解析

### Requirement: manifest.yaml 增加图表渲染状态字段
manifest.yaml 的每个图表条目 SHALL 包含 `status` 字段（rendered/failed），以便 writer 判断是否嵌入或用文字替代。

#### Scenario: 渲染失败降级
- **WHEN** 某图表渲染失败
- **THEN** manifest.yaml 中该条目 status 为 failed，writer 使用文字描述替代

### Requirement: 统一 runtime-explorer 内部字段名
runtime-explorer SKILL.md 的 Step 3.3 记录弹窗信息 SHALL 使用与 Step 5 和 pkb-schema.yaml 一致的字段名。

- Step 3.3 的 `submit_button_text` / `cancel_button_text` → `submit_button` / `cancel_button`

#### Scenario: 字段名一致
- **WHEN** 对比 runtime-explorer Step 3.3 与 Step 5 的弹窗字段名
- **THEN** 完全一致（submit_button / cancel_button）

### Requirement: 统一 runtime.yaml status 枚举值
runtime.yaml 的 status 字段合法值 SHALL 在 pkb-schema.yaml、runtime-explorer SKILL.md、doc-gen SKILL.md 三处保持一致。

- pkb-schema.yaml 增加合法值 `timeout`
- runtime-explorer Step 5 注释列出全部合法值

#### Scenario: 枚举值一致
- **WHEN** 检查 status 字段的合法值集合
- **THEN** 三处定义完全一致

### Requirement: screenshot-planner 输出示例补全字段
screenshot-planner 的输出示例 SHALL 包含 pkb-schema.yaml 定义的标准字段：`full_page`、`wait_after_action`、`roles`。

#### Scenario: 示例完整
- **WHEN** 阅读 screenshot-planner 输出示例
- **THEN** 包含 full_page / wait_after_action / roles 字段及使用说明

### Requirement: generate_screenshots.py 角色过滤
generate_screenshots.py 的角色循环 SHALL 按 shot 的 `roles` 字段过滤，避免重复截图。

#### Scenario: 角色过滤
- **WHEN** 配置多个测试账号
- **THEN** 每张截图仅由相关角色的账号采集一次

### Requirement: document-renderer 描述泛化
document-renderer 的描述 SHALL 覆盖全部三种文档（manual/database/api），而非仅用户手册。

#### Scenario: 描述覆盖
- **WHEN** 阅读 document-renderer 描述和输入章节
- **THEN** 明确接受任意 output/*.md 文件，不限于 manual.md

### Requirement: 修复文档编号与模板语法
- doc-gen `--type database` 输出物清单 SHALL 编号连续（修复两个"3"）
- manual-outline.md 操作步骤示例 SHALL 使用 `步骤N：` 格式，不使用被 manual-writer 禁止的 `1. 2. 3.` 语法

### Requirement: 清理 webapp-testing 未定义变量
webapp-testing 伪代码中引用的 `dashboard_route` 变量 SHALL 有定义来源，或替换为从 screenshot-config.yaml 读取的 `expected_redirect`。

## MODIFIED Requirements
无。

## REMOVED Requirements
无。
