---
name: "doc-gen"
description: "自动化软件文档生成编排器。支持从项目源码生成用户手册、数据库说明书和API文档，也支持仅凭已部署网站与测试账号冷启动生成用户手册。读取各Skill契约并动态决定执行顺序、条件依赖、缓存跳过和分段执行。当用户需要根据源码或网站自动生成文档时调用。"
---

# Doc Gen —— 契约驱动编排器

你是文档生成系统的核心调度器。你通过读取各 Skill 的契约声明,动态决定执行顺序、缓存跳过、分段执行。

## 编排原理

```
1. 收集所有 Skill 的契约(从各 SKILL.md 的 "## Skill 契约" 段落)
2. 根据 --source、--type 和 --stage 过滤要执行的 Skill
3. 检查 cache_key 文件哈希,跳过未变更的 Skill
4. 按 depends_on 拓扑排序,无依赖关系的并行执行
5. 逐阶段推进
```

## Skill 契约注册表

以下是所有 Skill 的契约汇总(编排依据):

### explorer 阶段
```yaml
project-explorer:
  inputs: [项目源码目录]
  outputs: [knowledge/project.yaml, knowledge/modules/, knowledge/pages/, knowledge/roles/, knowledge/workflows/, knowledge/workflow-chains.yaml]
  depends_on: []
  cache_key: [源码文件哈希]
  stage: explorer

database-extractor:
  inputs: [项目源码(数据库相关文件), knowledge/project.yaml]
  outputs: [knowledge/database/]
  depends_on: [project-explorer]
  cache_key: [源码中的数据库文件(**/*.sql, **/entity/*.java, **/model/*.go)]
  stage: explorer

api-extractor:
  inputs: [项目源码(接口相关文件), knowledge/project.yaml, knowledge/roles/]
  outputs: [knowledge/apis/]
  depends_on: [project-explorer]
  cache_key: [源码中的接口文件(**/*Controller.java, **/*handler.go, **/swagger.json)]
  stage: explorer
```

### runtime 阶段
```yaml
runtime-explorer:
  modes:
    bootstrap:
      inputs: [knowledge/screenshot-config.yaml]
      outputs: [knowledge/project.yaml, knowledge/modules/, knowledge/pages/, knowledge/roles/, knowledge/workflows/, knowledge/workflow-chains.yaml, knowledge/runtime/]
      depends_on: []
      cache_key: []
    enrich:
      inputs: [knowledge/screenshot-config.yaml, knowledge/pages/, knowledge/modules/, knowledge/workflows/]
      outputs: [knowledge/runtime/, knowledge/pages/, knowledge/workflows/]
      depends_on: [project-explorer 或 runtime-explorer:bootstrap]
      cache_key: [knowledge/pages/**/*.yaml, knowledge/modules/**/*.yaml, knowledge/workflows/**/*.yaml]
  stage: runtime
```

### diagram 阶段
```yaml
diagram-generator:
  inputs: [knowledge/database/, knowledge/apis/, knowledge/workflows/, knowledge/modules/]
  outputs: [output/diagrams/*.png, output/diagrams/manifest.yaml]
  depends_on: [project-explorer]
  cache_key: [knowledge/database/**/*.yaml, knowledge/apis/**/*.yaml, knowledge/workflows/**/*.yaml, knowledge/modules/**/*.yaml]
  stage: diagram
```

### writer 阶段(按 --type 选择)
```yaml
manual-writer:
  inputs: [knowledge/project.yaml, knowledge/modules/, knowledge/pages/, knowledge/roles/, knowledge/workflows/, output/diagrams/manifest.yaml]
  outputs: [output/manual.md]
  depends_on: [project-explorer, diagram-generator]
  cache_key: [knowledge/modules/**/*.yaml, knowledge/pages/**/*.yaml, knowledge/roles/**/*.yaml, knowledge/workflows/**/*.yaml, knowledge/workflow-chains.yaml]
  stage: writer

database-spec-writer:
  inputs: [knowledge/database/, output/diagrams/manifest.yaml]
  outputs: [output/database-spec.md]
  depends_on: [database-extractor, diagram-generator]
  cache_key: [knowledge/database/**/*.yaml]
  stage: writer

api-doc-writer:
  inputs: [knowledge/apis/, knowledge/roles/, output/diagrams/manifest.yaml]
  outputs: [output/api-doc.md]
  depends_on: [api-extractor, diagram-generator]
  cache_key: [knowledge/apis/**/*.yaml, knowledge/roles/**/*.yaml]
  stage: writer
```

### review 阶段
```yaml
qa-reviewer:
  inputs: [output/manual.md, knowledge/]
  outputs: [output/manual.md, output/qa-report.md, output/visual-coverage-report.json]
  depends_on: [manual-writer]
  cache_key: [output/manual.md]
  stage: review
```

### screenshot 阶段(仅 manual/all)
```yaml
screenshot-planner:
  inputs: [output/manual.md, output/visual-coverage-report.json, knowledge/pages/, knowledge/workflows/, knowledge/roles/, knowledge/runtime/ (如存在)]
  outputs: [knowledge/screenshots.yaml]
  depends_on: [qa-reviewer]
  cache_key: [output/manual.md, output/visual-coverage-report.json, knowledge/pages/**/*.yaml, knowledge/workflows/**/*.yaml, knowledge/runtime/**/*.yaml]
  stage: screenshot

webapp-testing:
  inputs: [knowledge/screenshots.yaml, knowledge/screenshot-config.yaml]
  outputs: [output/screenshots/*.png, output/capture-result.json]
  depends_on: [screenshot-planner]
  cache_key: [knowledge/screenshots.yaml]
  stage: screenshot

screenshot-reviewer:
  inputs: [output/capture-result.json, output/screenshots/]
  outputs: [output/screenshot-review-report.md, output/retake-list.yaml]
  depends_on: [webapp-testing]
  cache_key: [output/capture-result.json]
  stage: screenshot
```

### render 阶段
```yaml
document-renderer:
  inputs: [output/manual.md, output/database-spec.md, output/api-doc.md, output/screenshots/]
  outputs: [output/用户使用手册.docx, output/数据库设计说明书.docx, output/API接口文档.docx]
  depends_on: []  # 由下方类型化依赖表注入
  cache_key: [output/manual.md, output/database-spec.md, output/api-doc.md, knowledge/screenshots.yaml, output/screenshots/**/*.png]
  stage: render
```

## 阶段依赖图

### 源码模式(`--source code`)

```
explorer ┌─ project-explorer ──┬── database-extractor ──────────────────────────┐
         │                     ├── api-extractor ───────────────────────────────┤
         │                     │                                                  │
         │              runtime-explorer (仅 --deep)                              │
         │                     │                                                  │
         │                     ▼                                                  │
         │              diagram-generator ──┬── manual-writer ──→ qa-reviewer ──┤
         │                                  ├── database-spec-writer ───────────┤
         │                                  └── api-doc-writer ─────────────────┤
         │                                                                     ▼
         └── manual-writer ──→ screenshot-planner ──→ webapp-testing           │
                                                   ──→ screenshot-reviewer      │
         │                                                                     │
         └─────────────────────────────────────────────────────────────────────┴──→ render
```

### 网站模式(`--source website`)

```text
runtime-explorer:bootstrap
    └──→ runtime-explorer:enrich (仅 --deep)
                 │
                 ▼
        diagram-generator ──→ manual-writer ──→ qa-reviewer
                                                   │
                                                   ▼
                                           screenshot-planner
                                                   │
                                                   ▼
                                            webapp-testing
                                                   │
                                                   ▼
                                         screenshot-reviewer
                                                   │
                                                   ▼
                                          document-renderer
```

未传 `--deep` 时 bootstrap 直接连接 diagram-generator；传入时 diagram-generator 必须等待 enrich 完成，以使用补充后的 workflows/pages。

**--type 决定哪些 Extractor 执行:**

| --type | project-explorer | database-extractor | api-extractor |
|--------|-----------------|-------------------|---------------|
| manual | ✅ | ❌ | ❌ |
| database | ✅ | ✅ | ❌ |
| api | ✅ | ❌ | ✅ |
| all | ✅ | ✅ | ✅ |

**类型化依赖(覆盖注册表中无法表达的条件依赖):**

| --type | diagram-generator 额外依赖 | document-renderer 依赖 |
|--------|----------------------------|------------------------|
| manual | project-explorer | screenshot-reviewer |
| database | database-extractor | database-spec-writer |
| api | api-extractor | api-doc-writer |
| all | database-extractor, api-extractor | screenshot-reviewer, database-spec-writer, api-doc-writer |

构建执行图时先应用此表，再进行拓扑排序。不得让 database/api 渲染依赖手册专属审核任务。

**--source 条件依赖覆盖:**

| --source | 允许的 --type | 知识入口 | diagram-generator 依赖 | manual-writer 依赖 |
|----------|---------------|----------|--------------------------|--------------------|
| code | manual / database / api / all | project-explorer | project-explorer 或对应 Extractor | project-explorer, diagram-generator |
| website | manual | runtime-explorer:bootstrap | bootstrap；--deep 时改为 enrich | runtime-explorer:bootstrap, diagram-generator；--deep 时同时等待 enrich |

`--source website` 与 `--type database/api/all` 组合必须在构建执行图前终止，说明网站界面无法可靠提供数据库和完整 API 事实，不得自动降级或生成推断内容。

## 执行流程

### Step 0: 解析参数

```
--source code(默认) / website
--type   manual(默认) / database / api / all
--stage  all(默认) / explorer / runtime / diagram / writer / review / screenshot / render
--deep   启用运行时探索(默认不启用)
--format docx(默认) / pdf / html
--lang   zh(默认) / en
```

1. 校验参数组合；website 只允许 manual。
2. 初始化 .gitignore: 如项目根目录无 `.gitignore`,从 `templates/.gitignore.template` 复制;如已存在,提示用户手动补充 `knowledge/screenshot-config.yaml` 和 `.cache/` 等敏感路径。
3. website 模式在执行任何 Skill 前校验 screenshot-config 的 URL、测试账号和环境变量凭据。

### Step 1: 构建执行计划

根据 `--type` 和 `--stage` 决定要执行哪些 Skill:

**按 --source 选择知识入口:**

| --source | --stage explorer | --stage runtime | --stage all |
|----------|------------------|-----------------|-------------|
| code | project-explorer + 对应 Extractor | runtime-explorer:enrich，需 --deep | 原有源码完整流程；仅 --deep 时加入 enrich |
| website | runtime-explorer:bootstrap | runtime-explorer:enrich，要求已有 PKB | bootstrap 后进入 manual 流程；仅 --deep 时再执行 enrich |

**按 --type 选择 Writer:**

| --type | 执行的 Writer |
|--------|-------------|
| manual | manual-writer |
| database | database-spec-writer |
| api | api-doc-writer |
| all | 三个全部 |

**按 --stage 过滤:**

| --stage | 执行哪些阶段的 Skill |
|---------|---------------------|
| all(默认) | 执行所选 source 的完整流程 |
| explorer | code 扫描源码；website 执行 runtime-explorer:bootstrap |
| runtime | 只执行 runtime-explorer:enrich；code 需 --deep，website 要求已有 PKB |
| diagram | 只执行 diagram-generator |
| writer | 只执行对应 Writer |
| review | 只执行 qa-reviewer |
| screenshot | 执行 screenshot-planner + webapp-testing + screenshot-reviewer |
| render | 只执行 document-renderer |

**--stage 的使用场景:**
- `--stage explorer`: 根据 source 从源码扫描或网站冷启动生成 PKB,不生成文档
- `--stage writer`: 只生成 Markdown(前提 PKB 已存在)
- `--stage render`: 只渲染 DOCX(前提 Markdown 已存在)
- `--stage screenshot`: 只截图(前提手册已生成)

### Step 1.5: dry-run 输出(仅 --dry-run 模式)

如用户传入 `--dry-run`，输出 Skill、阶段、是否执行、缓存状态和 depends_on 后直接退出，不调用任何 Skill。输出格式与缓存判定细节见 [references/orchestration-details.md](references/orchestration-details.md)。

website dry-run 必须显示 `runtime-explorer:bootstrap`，不得显示 project-explorer、database-extractor 或 api-extractor；bootstrap 的缓存列固定显示“—（线上状态，每次执行）”。

### Step 2: 缓存检查

对计划中的每个 Skill,检查其 `cache_key` 文件是否变更:

```
1. 读取 .cache/{skill-name}.hash(上次执行时的文件哈希)
2. 计算当前 cache_key 文件的哈希
3. 如哈希一致 → 跳过该 Skill,输出"⏭ {skill-name}: 缓存命中,跳过"
4. 如哈希不一致或无缓存 → 执行该 Skill
5. 执行完成后,保存新的哈希到 .cache/{skill-name}.hash
```

**缓存文件结构:**
```
.cache/
├── project-explorer.hash    # 记录源码文件哈希
├── diagram-generator.hash   # 记录 PKB 相关 YAML 哈希
├── manual-writer.hash       # 记录 PKB 哈希
├── qa-reviewer.hash         # 记录 manual.md 哈希
├── webapp-testing.hash      # 记录 screenshots.yaml 哈希
└── document-renderer.hash   # 记录 Markdown 哈希
```

**强制刷新:** 用户传 `--no-cache` 时忽略所有缓存,全量重新执行。

**网站探索缓存:** `runtime-explorer:bootstrap` 不读取或写入本地输入哈希，每次显式调度都执行，因为本地文件无法证明线上站点未变化。bootstrap 必须确定性排序并仅在规范化内容变化时改写 PKB。`runtime/_meta.yaml` 的 `explored_at` 不得进入 manual-writer、diagram-generator、qa-reviewer 或 screenshot-planner 的稳定缓存键。

`qa-reviewer` 的缓存键必须同时覆盖 `manual.md`、页面/工作流 PKB；其输出验证必须包含 `visual-coverage-report.json` 且 `missing_count = 0`。视觉覆盖未通过时不得调度 screenshot-planner。

**缓存算法迁移说明:** 缓存哈希使用 SHA-256。旧 `.cache/*.hash` 文件需删除后重建,首次升级后执行一次 `--no-cache` 即可。

缓存辅助算法与稳定字段白名单见 [references/orchestration-details.md](references/orchestration-details.md)。缓存检查必须只读，Skill 成功且 outputs 验证通过后才能保存 SHA-256 哈希。

### Step 3: 拓扑排序

按 `depends_on` 对要执行的 Skill 排序:

```
1. 从待执行 Skill 列表中找出 depends_on 为空或已完成的
2. 执行它们
3. 标记为已完成
4. 回到步骤 1,直到全部执行完
```

**并行优化:** 同一阶段内无依赖关系的 Skill 可以并行执行:
- diagram-generator 完成后,manual-writer / database-spec-writer / api-doc-writer 可并行
- 但在 Skill 体系中,LLM 逐个调用更安全,并行通过 Task 工具实现

### Step 4: 逐阶段执行

按拓扑顺序逐个调用 Skill。每个 Skill 执行前:
1. 检查缓存(除非 --no-cache)
2. 检查 depends_on 是否已完成
3. 调用 Skill
4. 验证 outputs 是否生成
5. 保存缓存

**执行日志格式:**
```
[explorer] project-explorer: 执行中... 完成 ✅ (产出 7 个 YAML)
[runtime]  runtime-explorer: 跳过(未传 --deep) ⏭
[diagram]  diagram-generator: 缓存命中,跳过 ⏭
[writer]   manual-writer: 执行中... 完成 ✅ (产出 manual.md)
[writer]   database-spec-writer: 执行中... 完成 ✅
[review]   qa-reviewer: 执行中... 完成 ✅ (修正 3 处)
[screenshot] screenshot-planner: 执行中... 完成 ✅
[screenshot] webapp-testing: 执行中... 完成 ✅ (20/22 张成功)
[screenshot] screenshot-reviewer: 执行中... 完成 ✅ (2 张需补拍)
[render]   document-renderer: 执行中... 完成 ✅ (产出 用户使用手册.docx)
```

website 模式日志必须把入口写为 `[explorer] runtime-explorer:bootstrap`，并在汇总中报告已覆盖角色、未覆盖角色、探索页数和 `complete/partial/auth_failed` 状态。

### Step 5: 汇总报告

执行完成后输出总结:

```markdown
# 文档生成报告

## 执行概况
- 输入来源: --source code
- 文档类型: --type all
- 执行模式: 完整流程
- 缓存跳过: 2 个 Skill
- 实际执行: 8 个 Skill
- 总耗时: ~{时间}

## 各阶段结果

| 阶段 | Skill | 状态 | 缓存 | 说明 |
|------|-------|------|------|------|
| explorer | project-explorer | ✅ | — | 产出 7 个 YAML |
| runtime | runtime-explorer | ⏭ | — | 未启用 --deep |
| diagram | diagram-generator | ⏭ | 命中 | PKB 未变更 |
| writer | manual-writer | ✅ | — | 产出 manual.md |
| writer | database-spec-writer | ✅ | — | 产出 database-spec.md |
| writer | api-doc-writer | ✅ | — | 产出 api-doc.md |
| review | qa-reviewer | ✅ | — | 修正 3 处术语 |
| screenshot | screenshot-planner | ✅ | — | 规划 22 张截图 |
| screenshot | webapp-testing | ✅ | — | 采集 20/22 张 |
| screenshot | screenshot-reviewer | ✅ | — | 2 张需补拍 |
| render | document-renderer | ✅ | — | 产出 3 份 DOCX |

## 产出文件
- output/用户使用手册.docx
- output/数据库设计说明书.docx
- output/API接口文档.docx

## 缓存状态
已保存到 .cache/,下次执行时增量跳过。
```

## 使用方式

### 完整流程(默认)
```
invoke_command:/doc-gen --type all
```

### 仅凭网站和账号生成用户手册
```
invoke_command:/doc-gen --source website --type manual
```

### 网站冷启动 + 深度只读探索
```
invoke_command:/doc-gen --source website --type manual --deep
```

### 只从网站建立 PKB
```
invoke_command:/doc-gen --source website --type manual --stage explorer
```

### 只扫描源码(不生成文档)
```
invoke_command:/doc-gen --stage explorer
```

### 只生成 Markdown(不截图不渲染)
```
invoke_command:/doc-gen --type manual --stage writer
```

### 只截图(前提:手册已生成)
```
invoke_command:/doc-gen --stage screenshot
```

### 只渲染 DOCX(前提:Markdown 已生成)
```
invoke_command:/doc-gen --type all --stage render
```

### 深度模式 + 完整流程
```
invoke_command:/doc-gen --type all --deep
```

### 强制全量重新生成(忽略缓存)
```
invoke_command:/doc-gen --type all --no-cache
```

## 可选参数汇总

| 参数 | 可选值 | 默认值 | 说明 |
|------|--------|--------|------|
| `--source` | code / website | code | 输入来源；website 第一版仅支持 manual |
| `--type` | manual / database / api / all | manual | 文档类型 |
| `--stage` | all / explorer / runtime / diagram / writer / review / screenshot / render | all | 执行阶段 |
| `--deep` | — | 不启用 | 启用运行时探索 |
| `--format` | docx / pdf / html | docx | 输出格式 |
| `--lang` | zh / en | zh | 文档语言 |
| `--no-cache` | — | 不启用 | 忽略缓存,全量重新生成 |
| `--dry-run` | — | 不启用 | 输出执行计划(哪些 Skill 会跑、哪些被缓存跳过)而不实际执行 |

## 错误处理

- 任何阶段失败 → 记录错误,询问用户是否继续后续阶段
- website 与 database/api/all 组合 → 参数校验失败，不生成推断文档
- website 全部账号认证失败 → 标记 auth_failed 并终止，不创建虚假 PKB
- PKB 为空 → 终止,提示按当前 source 执行 `--stage explorer`
- 缓存文件损坏 → 自动删除,重新执行
- depends_on 未满足 → 自动补充执行依赖的 Skill

## 输出物清单

### --type manual
1. `knowledge/*.yaml` —— PKB
2. `output/diagrams/*.png` —— UML 图表
3. `output/manual.md` —— Markdown 手册
4. `output/screenshots/*.png` —— 界面截图
5. `output/用户使用手册.docx` —— 最终 DOCX
6. `.cache/*.hash` —— 缓存文件

当 `--source website` 时，以上 PKB 来自可访问网站和测试账号的已观察范围；不包含数据库、完整 API、后端架构或不可见权限。

### --type database
1. `knowledge/database/`
2. `output/diagrams/er-diagram.png`
3. `output/database-spec.md`
4. `output/数据库设计说明书.docx`

### --type api
1. `knowledge/apis/`
2. `output/api-doc.md`
3. `output/API接口文档.docx`

### --type all
以上全部,共 3 份 DOCX 文档。
