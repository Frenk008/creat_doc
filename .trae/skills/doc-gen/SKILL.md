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

### Step 3.5: 运行时探索 (仅 --deep 模式)
- 如果用户传了 `--deep` 参数,调用 `runtime-explorer`
- 使用 chrome-devtools-mcp 连接已运行的项目,探索弹窗/表单/校验规则
- 更新 `knowledge/runtime.yaml` + 回写 pages.yaml/workflows.yaml
- 探索完成后,PKB 信息更完整,manual-writer 生成的手册质量更高
- **如果未传 --deep**:跳过,runtime.yaml 标记为 `not_explored`

### Step 4: 截图采集 (调用 webapp-testing + screenshot-reviewer)
**仅对 --type manual 或 all 执行,需要 Docker 环境。**

#### 4.1 Docker 启动
- 读取 `knowledge/screenshot-config.yaml`
- 执行 `docker compose up -d` 启动项目
- 等待 healthcheck 或轮询 base_url 确认就绪

#### 4.2 批量截图
- 调用 `webapp-testing`,使用 Playwright 按 `screenshots.yaml` 批量截图
- 产出: `output/screenshots/*.png` + `output/capture-result.json`

#### 4.3 截图审核
- 调用 `screenshot-reviewer` 检查截图质量
- 不合格截图生成补拍清单,最多补拍 2 轮
- 最终更新 `screenshots.yaml` 中每张图的 status

#### 4.4 Docker 清理
- `docker compose down` 关闭容器(除非用户要求保留)

**截图采集失败处理:**
- Docker 不可用 → 跳过截图,手册保留占位标记
- Playwright 未安装 → 提示安装后重试,手册保留占位标记
- 部分截图失败 → 成功的图嵌入文档,失败的保留占位

### Step 5: 文档渲染 (调用 document-renderer)
将所有生成的 Markdown 渲染为 DOCX:

| 输入 | 输出 |
|------|------|
| output/manual.md | output/用户使用手册.docx |
| output/database-spec.md | output/数据库设计说明书.docx |
| output/api-doc.md | output/API接口文档.docx |

渲染时:
- 如果 `output/screenshots/` 存在已审核的截图,将手册中的占位标记替换为实际图片引用
- 如果截图不存在或未审核,保留占位标记

## V2 版本增强(对比 V1)

V2 相比 V1,以下组件从占位状态升级为实际执行:

| 组件 | V1 状态 | V2 状态 | 触发条件 |
|------|---------|---------|---------|
| runtime-explorer | ⬜ 占位 | ✅ chrome-devtools-mcp 探索 | `--deep` 参数 |
| webapp-testing | ⬜ 占位 | ✅ Docker + Playwright 截图 | 自动(manual/all 模式) |
| screenshot-reviewer | ⬜ 占位 | ✅ 程序化 + MCP 审核 | 截图完成后 |

**V2 新增依赖:**
- Docker + Docker Compose(启动项目)
- Playwright(`pip install playwright && playwright install chromium`)
- chrome-devtools-mcp(本环境已内置)

**V2 完整执行链路:**
```
Step 1:   project-explorer  → PKB
Step 2:   (runtime-explorer → --deep 模式才执行)
Step 2.5: diagram-generator → UML 图表
Step 3:   writers           → Markdown
Step 3.5: (runtime-explorer → --deep 模式)
Step 4:   webapp-testing    → Docker 启动 + Playwright 截图
Step 4.3: screenshot-reviewer → 截图审核 + 补拍
Step 5:   document-renderer → DOCX(嵌入实际截图)
```

## 输出物清单

### --type manual(默认)
1. `knowledge/*.yaml` —— 完整的 PKB
2. `output/diagrams/*.png` —— 流程图 + 功能总览图
3. `output/manual.md` —— 审核后的 Markdown 手册(含图表引用)
4. `output/screenshots/*.png` —— 实际界面截图(V2)
5. `output/用户使用手册.docx` —— 最终 DOCX(含 UML 图 + 界面截图)
6. `knowledge/screenshots.yaml` —— 截图计划(含采集状态)

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
