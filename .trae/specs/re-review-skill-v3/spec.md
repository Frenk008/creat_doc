# Skill 体系三轮审查与修复 Spec

## Why
前两轮修复了 Docker 逻辑、字段名、死代码等问题，但本轮深度交叉审计（聚焦 project-explorer 产出完整性、脚本逻辑正确性、执行顺序、大纲模板与生成规则一致性）又发现 21 项残留问题，其中 3 项会直接导致流水线产出错误结果（重复条目数据损坏、补拍闭环断裂、执行顺序错误）。

## What Changes
- **P1 数据正确性**：修复 generate_screenshots.py 多角色重复截图、补拍逻辑未实现、retake 格式不匹配
- **P1 执行顺序**：修正 doc-gen 中 qa-reviewer 与 screenshot-planner 的顺序
- **P1 文件名/字段不匹配**：功能总览图文件名、er_relations 缺 via_field、workflow_chains 未产出
- **P1 大纲模板违规**：manual-outline.md 残留 `- ` 列表语法
- **P2 编号/结构/健壮性**：架构图编号对齐、输出物清单补图表、PDF 方案、qa-reviewer 图表检查、脚本健壮性

## Impact
- 受影响：project-explorer、doc-gen、webapp-testing、manual-writer、api-doc-writer、qa-reviewer、generate_screenshots.py、pkb-schema.yaml、manual-outline.md、database-spec-outline.md、screenshot-config.yaml
- 不涉及业务源码

## ADDED Requirements

### Requirement: project-explorer 补全 workflow_chains 产出
project-explorer SHALL 在阶段 3 增加"推导 workflow_chains"步骤，并在自检清单中验证（当 --type manual/all 时）。

#### Scenario: workflow_chains 产出
- **WHEN** project-explorer 完成 workflows.yaml
- **THEN** workflows.yaml 包含 workflow_chains 段，且 manual-writer/diagram-generator 能读取

### Requirement: 修复 generate_screenshots.py 多角色重复截图
通用截图（无 roles 字段）SHALL 只截取一次，不因多角色循环而重复。results 写入 screenshots.yaml 和 capture-result.json 前 SHALL 去重。

#### Scenario: 通用截图不重复
- **WHEN** 配置 3 个角色且某截图无 roles 字段
- **THEN** 该截图在 results 中只出现 1 次

### Requirement: 实现 retake-list.yaml 读取逻辑
generate_screenshots.py SHALL 支持 `--retake` 参数读取 retake-list.yaml 并过滤 plan。webapp-testing SKILL.md 的伪代码 SHALL 与 screenshot-reviewer 产出的 retake 格式（`{retakes: [{id, ...}]}`）匹配。

#### Scenario: 补拍过滤生效
- **WHEN** retake-list.yaml 存在且传入 --retake
- **THEN** 脚本仅采集 retakes 列表中的截图 ID

### Requirement: 统一 screenshot-config.yaml 与脚本消费
screenshot-config.yaml 中未被脚本消费的字段（default_mode / page_timeout / action_delay / expected_redirect）SHALL 被脚本读取，或在配置注释中标注"当前不支持"。

#### Scenario: 配置字段消费
- **WHEN** 截图脚本运行
- **THEN** page_timeout / action_delay 从 config 读取（覆盖硬编码），或配置文件标注不支持

### Requirement: 修正 doc-gen 执行顺序为 manual-writer → qa-reviewer → screenshot-planner
screenshot-planner SHALL 读取 qa-reviewer 审核后的最终版 manual.md，确保 qa-reviewer 新增的图片占位被纳入截图计划。

#### Scenario: 审核后截图规划
- **WHEN** qa-reviewer 审核后新增了图片占位
- **THEN** screenshot-planner 为新增占位生成截图计划

### Requirement: 修复功能总览图文件名不匹配
manual-writer SHALL 从 manifest.yaml 读取实际文件路径，不硬编码 `功能总览.png`。

#### Scenario: 图表路径正确
- **WHEN** manual-writer 嵌入功能总览图
- **THEN** 引用路径为 manifest.yaml 中的 file 字段值（diagrams/module-overview.png）

### Requirement: 修复 er_relations 缺 via_field
database-spec-outline.md 的 4.1 表 SHALL 不引用 schema 中不存在的 `{via_field}`，或 pkb-schema.yaml 的 er_relations 增加该字段。

### Requirement: 修复 manual-outline.md 残留列表语法
manual-outline.md 中所有 `- ` 无序列表 SHALL 改为 manual-writer 允许的格式（`（N）` 或顿号段落）。

### Requirement: 统一 doc-gen 架构图与执行步骤编号
架构图阶段编号 SHALL 与执行 Step 编号对齐，或架构图改用 Step 编号。

### Requirement: 补全 doc-gen 输出物清单
--type api 输出清单 SHALL 包含时序图和 manifest.yaml。

### Requirement: document-renderer 明确 PDF 方案
document-renderer SHALL 增加 PDF 渲染方案说明，或 doc-gen 删除 --format pdf 选项。

### Requirement: qa-reviewer 增加图表引用完整性检查
qa-reviewer SHALL 验证手册中所有 `![](diagrams/...)` 引用在 manifest.yaml 中存在且 status 为 rendered。

### Requirement: generate_screenshots.py 健壮性修复
- `config["screenshot"]` 改为 `.get()` 防止 KeyError
- `--role` 预过滤逻辑与角色循环过滤逻辑统一（包含通用截图）

## MODIFIED Requirements
无。

## REMOVED Requirements
无。
