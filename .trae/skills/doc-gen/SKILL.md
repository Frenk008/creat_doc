---
name: "doc-gen"
description: "自动化软件文档生成编排器。协调多个子 Skill 完成从源码分析到多种文档(DOCX/PDF)的完整流水线,支持用户手册、数据库说明书、API文档。当用户需要根据项目源码自动生成各类文档时调用。"
---

# Doc Gen —— 文档生成编排器

你是文档生成系统的核心调度器。你的职责是协调以下子 Skill,完成从源码到多种文档的完整链路。

## 支持的文档类型

| 类型 | 参数 | 调用的 Writer | 输出文件 | PKB 依赖 |
|------|------|--------------|----------|----------|
| 用户手册 | `--type manual`(默认) | manual-writer | 用户使用手册.docx | modules, pages, roles, workflows |
| 数据库说明书 | `--type database` | database-spec-writer | 数据库设计说明书.docx | database.yaml |
| API 文档 | `--type api` | api-doc-writer | API接口文档.docx | apis.yaml |
| 全部 | `--type all` | 以上全部 | 3份文档 | 全部 |

## 系统架构

```
用户调用 doc-gen --type <文档类型>
       │
       ▼
┌─ 阶段1: 静态分析(只跑一次) ──────────────────┐
│  project-explorer  (扫描源码 → 完整 PKB)      │
│  runtime-explorer  (运行时探索, V1可选)        │
└──────────────────────────────────────────────┘
       │
       ▼ (PKB = knowledge/ 目录下所有 YAML)
┌─ 阶段2: 图表生成(按类型生成UML图) ─────────────┐
│  diagram-generator                             │
│  --type database → ER图                         │
│  --type api → 时序图                            │
│  --type manual → 流程图+功能总览图               │
│  --type all → 以上全部                          │
│  产出: output/diagrams/*.png + manifest.yaml   │
└──────────────────────────────────────────────┘
       │
       ▼
┌─ 阶段3: 文档生成(按类型调度) ─────────────────┐
│  --type manual:                              │
│    manual-writer + screenshot-planner        │
│  --type database:                            │
│    database-spec-writer                      │
│  --type api:                                 │
│    api-doc-writer                            │
│  --type all:                                 │
│    以上全部并行生成                            │
│  (writers 读取 manifest.yaml 引用图表)          │
└──────────────────────────────────────────────┘
       │
       ▼
┌─ 阶段4: 质量审核 ──────────────────────────┐
│  qa-reviewer (用户手册) / 直接通过(技术文档)   │
└───────────────────────────────────────────┘
       │
       ▼
┌─ 阶段5: 截图采集 (仅 manual, V1跳过) ──────────┐
│  webapp-testing + screenshot-reviewer         │
└──────────────────────────────────────────────┘
       │
       ▼
┌─ 阶段6: 文档渲染 ──────────────────────────┐
│  document-renderer (Markdown → DOCX/PDF)      │
│  (嵌入 diagrams/*.png)                        │
└───────────────────────────────────────────┘
```

## 执行流程

### Step 0: 初始化
1. 确认目标项目路径(默认为当前工作目录)
2. 确认输出路径(默认为 `./output/`)
3. 确认文档类型(默认 `manual`)
4. 创建 `knowledge/` 目录作为 PKB 存储

### Step 1: 静态源码分析 (调用 project-explorer)
- 调用 `project-explorer` Skill
- **无论生成什么文档,这一步只跑一次**
- project-explorer 会根据文档类型决定扫描深度:
  - `manual`: 扫描到 modules/pages/roles/workflows 即可
  - `database`: 额外执行阶段3.5数据库深度扫描
  - `api`: 额外执行阶段3.6 API深度扫描
  - `all`: 执行全部扫描阶段
- 产出: `knowledge/` 下的 YAML 文件
- **检查点**:根据文档类型校验必需的 PKB 文件存在

### Step 2: 运行时探索 (V1 可选,默认跳过)
- 如果用户明确要求 "深度分析",调用 `runtime-explorer`
- V1 默认跳过

### Step 2.5: 图表生成 (调用 diagram-generator)
- 在文档生成之前,先根据文档类型生成对应的 UML 图表
- `--type database`:从 database.yaml 生成 ER 图
- `--type api`:从 workflows.yaml + apis.yaml 生成时序图
- `--type manual`:从 workflow_chains 生成流程图 + 从 modules.yaml 生成功能总览图
- `--type all`:以上全部
- 产出: `output/diagrams/*.png` + `output/diagrams/manifest.yaml`
- **检查点**:确认 manifest.yaml 中列出的图表 PNG 文件均已生成
- **如果渲染失败**(无网络/服务器超时):跳过图表生成,writers 使用文字描述替代,继续后续流程

### Step 3: 按文档类型生成

#### 如果 --type manual 或 all:
1. 调用 `manual-writer` → `output/manual.md`(读取 manifest.yaml 在对应位置嵌入流程图和总览图)
2. 调用 `screenshot-planner` → `knowledge/screenshots.yaml`
3. 调用 `qa-reviewer` 审核 `output/manual.md`

#### 如果 --type database 或 all:
1. **前置检查**:确认 `knowledge/database.yaml` 存在且非空
2. 调用 `database-spec-writer` → `output/database-spec.md`

#### 如果 --type api 或 all:
1. **前置检查**:确认 `knowledge/apis.yaml` 存在且非空
2. 调用 `api-doc-writer` → `output/api-doc.md`

### Step 4: 文档渲染 (调用 document-renderer)
将所有生成的 Markdown 渲染为 DOCX:

| 输入 | 输出 |
|------|------|
| output/manual.md | output/用户使用手册.docx |
| output/database-spec.md | output/数据库设计说明书.docx |
| output/api-doc.md | output/API接口文档.docx |

## V1 版本简化规则

以下组件在 V1 中为占位状态,不实际执行:
- `runtime-explorer`: 不运行项目
- `webapp-testing`: 不启动浏览器,仅保留截图计划
- `screenshot-reviewer`: 不检查实际截图

## 输出物清单

### --type manual(默认)
1. `knowledge/*.yaml` —— 完整的 PKB
2. `output/diagrams/*.png` —— 流程图 + 功能总览图
3. `output/manual.md` —— 审核后的 Markdown 手册(含图表引用)
4. `output/用户使用手册.docx` —— 最终 DOCX
5. `knowledge/screenshots.yaml` —— 截图计划

### --type database
1. `knowledge/database.yaml` —— 数据库 PKB
2. `output/diagrams/er-diagram.png` —— ER 实体关系图
3. `output/database-spec.md` —— Markdown 数据库说明书(含 ER 图)
3. `output/数据库设计说明书.docx` —— 最终 DOCX

### --type api
1. `knowledge/apis.yaml` —— API PKB
2. `output/api-doc.md` —— Markdown API 文档
3. `output/API接口文档.docx` —— 最终 DOCX

### --type all
以上全部,共 3 份 DOCX 文档。

## 错误处理

- 任何阶段失败时,记录错误并询问用户是否继续
- PKB 为空 → 终止,提示用户检查项目结构
- database.yaml 不存在 → 跳过数据库文档,提示"未发现数据库结构"
- apis.yaml 不存在 → 跳过 API 文档,提示"未发现接口定义"
- 渲染失败 → 检查 pandoc/python-docx 是否安装

## 使用方式

### 生成用户手册(默认)
```
invoke_command:/doc-gen
```

### 生成数据库说明书
```
invoke_command:/doc-gen --type database
```

### 生成 API 文档
```
invoke_command:/doc-gen --type api
```

### 一键生成全部文档
```
invoke_command:/doc-gen --type all
```

### 指定项目路径
```
invoke_command:/doc-gen /path/to/project --type all
```

### 可选参数汇总
| 参数 | 可选值 | 默认值 | 说明 |
|------|--------|--------|------|
| `--type` | manual / database / api / all | manual | 文档类型 |
| `--deep` | - | 不启用 | 启用运行时探索(V1占位) |
| `--format` | docx / pdf / html | docx | 输出格式 |
| `--lang` | zh / en | zh | 文档语言 |
