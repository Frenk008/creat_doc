---
name: "doc-gen"
description: "自动化软件文档生成编排器。读取各 Skill 的契约(inputs/outputs/depends_on/cache_key/stage),动态决定执行顺序、缓存跳过、分段执行。支持用户手册、数据库说明书、API文档。当用户需要根据项目源码自动生成各类文档时调用。"
---

# Doc Gen —— 契约驱动编排器

你是文档生成系统的核心调度器。你通过读取各 Skill 的契约声明,动态决定执行顺序、缓存跳过、分段执行。

## 编排原理

```
1. 收集所有 Skill 的契约(从各 SKILL.md 的 "## Skill 契约" 段落)
2. 根据 --type 和 --stage 过滤要执行的 Skill
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

### runtime 阶段(仅 --deep)
```yaml
runtime-explorer:
  inputs: [knowledge/screenshot-config.yaml, knowledge/pages/, knowledge/modules/]
  outputs: [knowledge/runtime/]
  depends_on: [project-explorer]
  cache_key: [knowledge/pages/**/*.yaml, knowledge/modules/**/*.yaml]
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

## 执行流程

### Step 0: 解析参数

```
--type   manual(默认) / database / api / all
--stage  all(默认) / explorer / runtime / diagram / writer / review / screenshot / render
--deep   启用运行时探索(默认不启用)
--format docx(默认) / pdf / html
--lang   zh(默认) / en
```

1. 初始化 .gitignore: 如项目根目录无 `.gitignore`,从 `templates/.gitignore.template` 复制;如已存在,提示用户手动补充 `knowledge/screenshot-config.yaml` 和 `.cache/` 等敏感路径

### Step 1: 构建执行计划

根据 `--type` 和 `--stage` 决定要执行哪些 Skill:

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
| all(默认) | 全部 |
| explorer | 执行 project-explorer，并按 --type 执行对应 Extractor |
| runtime | 只执行 runtime-explorer(需 --deep) |
| diagram | 只执行 diagram-generator |
| writer | 只执行对应 Writer |
| review | 只执行 qa-reviewer |
| screenshot | 执行 screenshot-planner + webapp-testing + screenshot-reviewer |
| render | 只执行 document-renderer |

**--stage 的使用场景:**
- `--stage explorer`: 只扫描源码,生成 PKB,不生成文档
- `--stage writer`: 只生成 Markdown(前提 PKB 已存在)
- `--stage render`: 只渲染 DOCX(前提 Markdown 已存在)
- `--stage screenshot`: 只截图(前提手册已生成)

### Step 1.5: dry-run 输出(仅 --dry-run 模式)

如用户传入 `--dry-run` 参数,输出执行计划表格后**直接退出,不调用任何 Skill**:


执行计划(--dry-run,不实际执行):

| Skill | 阶段 | 会执行? | 缓存命中? | depends_on |
|-------|------|---------|-----------|------------|
| project-explorer | explorer | ✅ | ❌ | — |
| database-extractor | explorer | ✅ | ❌ | project-explorer |
| api-extractor | explorer | ✅ | ❌ | project-explorer |
| diagram-generator | diagram | ✅ | ❌ | project-explorer |
| manual-writer | writer | ✅ | ❌ | project-explorer, diagram-generator |
| database-spec-writer | writer | ✅ | ❌ | project-explorer, diagram-generator |
| api-doc-writer | writer | ✅ | ❌ | project-explorer, diagram-generator |
| qa-reviewer | review | ✅ | ❌ | manual-writer |
| screenshot-planner | screenshot | ✅ | ❌ | manual-writer |
| webapp-testing | screenshot | ✅ | ❌ | screenshot-planner |
| screenshot-reviewer | screenshot | ✅ | ❌ | webapp-testing |
| document-renderer | render | ✅ | ❌ | qa-reviewer, screenshot-reviewer |

如需实际执行,请去掉 --dry-run 参数。


缓存命中状态需要实际检查 cache_key 文件哈希后才能确定。在 dry-run 中,如 `.cache/` 目录为空则全部显示"❌(无缓存)",否则显示"?(需检查)"。

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

`qa-reviewer` 的缓存键必须同时覆盖 `manual.md`、页面/工作流 PKB；其输出验证必须包含 `visual-coverage-report.json` 且 `missing_count = 0`。视觉覆盖未通过时不得调度 screenshot-planner。

**缓存算法迁移说明:** 缓存哈希使用 SHA-256。旧 `.cache/*.hash` 文件需删除后重建,首次升级后执行一次 `--no-cache` 即可。

**缓存检查脚本(Python 辅助):**

```python
import hashlib
import json
from pathlib import Path

def check_cache(skill_name: str, cache_key_files: list, cache_dir: str = ".cache") -> bool:
    """
    检查 Skill 的缓存是否命中。
    返回 True 表示缓存命中(可跳过),False 表示需要重新执行。
    """
    cache_file = Path(cache_dir) / f"{skill_name}.hash"

    # 计算当前文件哈希
    current_hash = {}
    for pattern in cache_key_files:
        for f in Path(".").glob(pattern):
            if f.is_file():
                current_hash[str(f)] = hashlib.sha256(f.read_bytes()).hexdigest()

    current_hash_str = json.dumps(current_hash, sort_keys=True)

    # 对比缓存
    if cache_file.exists():
        saved_hash = cache_file.read_text(encoding="utf-8")
        if saved_hash == current_hash_str:
            return True  # 缓存命中

    # 检查阶段只读，不能提前写入；Skill 成功且 outputs 验证通过后再调用 save_cache。
    return False


def save_cache(skill_name: str, cache_key_files: list, cache_dir: str = ".cache"):
    """Skill 执行完成后保存缓存"""
    cache_file = Path(cache_dir) / f"{skill_name}.hash"
    current_hash = {}
    for pattern in cache_key_files:
        for f in Path(".").glob(pattern):
            if f.is_file():
                current_hash[str(f)] = hashlib.sha256(f.read_bytes()).hexdigest()
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(current_hash, sort_keys=True), encoding="utf-8")
```

`webapp-testing` 会更新 `knowledge/screenshots.yaml` 的状态，因此其缓存键必须只取稳定的计划字段
(`id/route/state_name/state_type/action/highlight/full_page/roles`)与截图配置；不得直接对执行后会变化的整个 YAML 求哈希。

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

### Step 5: 汇总报告

执行完成后输出总结:

```markdown
# 文档生成报告

## 执行概况
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
| `--type` | manual / database / api / all | manual | 文档类型 |
| `--stage` | all / explorer / runtime / diagram / writer / review / screenshot / render | all | 执行阶段 |
| `--deep` | — | 不启用 | 启用运行时探索 |
| `--format` | docx / pdf / html | docx | 输出格式 |
| `--lang` | zh / en | zh | 文档语言 |
| `--no-cache` | — | 不启用 | 忽略缓存,全量重新生成 |
| `--dry-run` | — | 不启用 | 输出执行计划(哪些 Skill 会跑、哪些被缓存跳过)而不实际执行 |

## 错误处理

- 任何阶段失败 → 记录错误,询问用户是否继续后续阶段
- PKB 为空 → 终止,提示先执行 `--stage explorer`
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
