# Doc Gen Skill 完整使用指南

本文说明如何使用本仓库的 `doc-gen` Skill，从环境准备、首次执行、截图配置、分阶段重跑，到质量验收和故障排查。

> `doc-gen` 是 Trae 对话中的 Skill 编排指令，不是 PowerShell 命令。文中的 `/doc-gen ...` 应输入到 Trae 对话框；只有 `python ...`、`pandoc ...` 等代码块需要在终端执行。

## 目录

- [1. 能生成什么](#1-能生成什么)
- [2. 工作流程](#2-工作流程)
- [3. 使用前准备](#3-使用前准备)
- [4. 第一次使用：推荐全过程](#4-第一次使用推荐全过程)
- [5. 一键执行与常用命令](#5-一键执行与常用命令)
- [6. 截图配置](#6-截图配置)
- [7. 参数速查](#7-参数速查)
- [8. 缓存与增量更新](#8-缓存与增量更新)
- [9. 独立调试截图采集](#9-独立调试截图采集)
- [10. 常见问题](#10-常见问题)
- [11. 推荐使用策略](#11-推荐使用策略)

## 1. 能生成什么

`doc-gen` 会分析目标项目源码，生成项目知识库（PKB），再按需要生成以下文档：

| 类型 | 参数 | 主要产物 |
|---|---|---|
| 用户手册 | `--type manual` | `output/用户使用手册.docx` |
| 数据库说明书 | `--type database` | `output/数据库设计说明书.docx` |
| API 文档 | `--type api` | `output/API接口文档.docx` |
| 全部文档 | `--type all` | 上述三份文档 |

用户手册流程还可以启动目标系统，自动规划、采集、标注和审核界面截图。数据库说明书与 API 文档不要求目标系统运行。

## 2. 工作流程

完整流程如下：

```text
源码分析（explorer）
  → 可选运行时探索（runtime，需 --deep）
  → 图表生成（diagram）
  → Markdown 编写（writer）
  → 用户手册质量审核（review）
  → 用户手册截图规划、采集与审核（screenshot）
  → DOCX / PDF / HTML 渲染（render）
```

`doc-gen` 会读取 `.trae/skills/` 下各子 Skill 的输入、输出与依赖契约，按依赖顺序执行；输入没有变化时，通过 `.cache/` 跳过已完成阶段。

## 3. 使用前准备

### 3.1 确认目录结构

在待生成文档的项目根目录中，至少应有：

```text
目标项目/
├── .trae/skills/           # doc-gen 及全部子 Skill
├── templates/              # 大纲、PKB、截图配置等模板
├── requirements.txt
└── 项目源码...
```

不要只复制 `.trae/skills/doc-gen/`。编排器还依赖 `project-explorer`、各类 Writer、Reviewer、截图和渲染 Skill，以及根目录下的模板与脚本。

### 3.2 安装 Python 依赖

在项目根目录打开 PowerShell：

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
```

依赖用途：

- Playwright：自动登录、操作页面和采集截图。
- PyYAML：读写 PKB 与截图计划。
- Pillow：截图标注、浏览器头合成。
- python-docx：未安装 Pandoc 时的 DOCX 兜底渲染。

验证基础环境：

```powershell
python -m unittest discover -s tests -v
python -m py_compile templates/generate_screenshots.py measure_addr_rect.py
```

### 3.3 可选外部工具

| 工具 | 用途 | 缺失时的行为 |
|---|---|---|
| Pandoc | 首选 DOCX、HTML 渲染 | 回退到 python-docx |
| XeLaTeX | 直接生成 PDF | 尝试 LibreOffice |
| LibreOffice | 把 DOCX 转为 PDF | 回退为 HTML |
| PlantUML Server | 把 UML 渲染为 PNG | 图表阶段无法完成或需要替代方案 |

敏感项目不要把表名、API 路径、业务流程发送到公共 PlantUML 服务。应使用本地 PlantUML Server，并在执行图表脚本时指定 `--server http://localhost:8080`。

### 3.4 保护凭据和运行时数据

确认项目 `.gitignore` 至少包含：

```gitignore
knowledge/screenshot-config.yaml
.cache/
knowledge/runtime/
output/screenshots/
output/playwright/
output/*.render.md
```

完整建议见 `templates/.gitignore.template`。账号密码应使用环境变量引用，不要把明文密码写入仓库。

## 4. 第一次使用：推荐全过程

以下过程便于逐阶段检查问题。若项目较小且配置已经完整，可直接看第 5 节的一键执行。

### 第 1 步：预览执行计划

在 Trae 对话框输入：

```text
/doc-gen --type all --dry-run
```

Skill 只展示将运行的阶段、依赖与缓存情况，不修改文件。先确认文档类型与执行范围是否符合预期。

### 第 2 步：扫描源码并生成 PKB

```text
/doc-gen --type all --stage explorer
```

检查以下核心产物：

```text
knowledge/
├── project.yaml
├── modules/
├── pages/
├── roles/
├── workflows/
├── database/       # database/all 模式
└── apis/           # api/all 模式
```

重点抽查模块、页面、角色、路由、数据库表和 API 是否与实际项目一致。PKB 是后续所有文档的事实来源；此处错误会传播到最终文档。

### 第 3 步：可选的运行时探索

仅当需要发现弹窗、表单校验、动态加载内容或稳定截图选择器时使用。

1. 先启动目标系统，并在浏览器确认可访问。
2. 按第 6 节创建 `knowledge/screenshot-config.yaml`。
3. 在 Trae 输入：

```text
/doc-gen --stage runtime --deep
```

运行时结果写入 `knowledge/runtime/`，并补充页面与工作流 PKB。该阶段以只读探索为主，不应执行真实增删改业务数据。

### 第 4 步：生成图表

```text
/doc-gen --type all --stage diagram
```

检查 `output/diagrams/manifest.yaml` 与 `output/diagrams/*.png`。图表缺失会影响相关 Writer 的配图。

### 第 5 步：生成 Markdown

```text
/doc-gen --type all --stage writer
```

根据类型生成：

```text
output/manual.md
output/database-spec.md
output/api-doc.md
```

此时适合做内容审阅，因为 Markdown 比最终 DOCX 更容易定位和修改。

### 第 6 步：审核用户手册

`review` 阶段只适用于用户手册：

```text
/doc-gen --type manual --stage review
```

检查：

- `output/qa-report.md`：内容完整性、术语、章节、链接等问题。
- `output/visual-coverage-report.json`：界面状态是否都有图片占位。

截图规划前必须满足 `missing_count = 0`。可在终端独立复查：

```powershell
python .trae/skills/qa-reviewer/scripts/check_visual_coverage.py `
  --manual output/manual.md `
  --output output/visual-coverage-report.json
```

### 第 7 步：启动目标系统并配置截图

用户手册需要真实截图时：

1. 自行启动后端和所有前端应用。
2. 在浏览器中确认登录页和主要页面正常访问。
3. 创建并填写 `knowledge/screenshot-config.yaml`，详见第 6 节。
4. 在当前 PowerShell 会话设置密码环境变量，例如：

```powershell
$env:APP_ADMIN_PASS = "实际管理员密码"
$env:APP_USER_PASS = "实际用户密码"
```

### 第 8 步：规划、采集并审核截图

在 Trae 输入：

```text
/doc-gen --type manual --stage screenshot
```

该阶段依次执行：

1. `screenshot-planner` 生成 `knowledge/screenshots.yaml`。
2. `webapp-testing` 自动登录、执行计划动作并生成截图。
3. `screenshot-reviewer` 检查空白页、错误页、状态不符、敏感信息和标注完整性。

首次采集时，Skill 可能询问浏览器模式：

- 无头：速度快，适合批量执行。
- 有头：显示浏览器窗口，适合观察操作。
- 有头 + 慢动作：适合调试登录或选择器问题。

主要产物：

```text
knowledge/screenshots.yaml
output/screenshots/*.png
output/screenshots/original/*.png
output/capture-result.json
output/screenshot-capture-report.md
output/screenshot-review-report.md
output/retake-list.yaml          # 有不合格截图时生成
```

如果存在 `output/retake-list.yaml`，再次运行截图阶段会按补拍清单处理，无需全量重拍。

### 第 9 步：渲染最终文档

```text
/doc-gen --type all --stage render --format docx
```

渲染用户手册时，Skill 会先把已审核截图嵌入 `output/manual.render.md`，不会覆盖审核后的 `output/manual.md`，再生成最终文档。

### 第 10 步：交付前验收

至少完成以下检查：

- PKB 抽查结果与源码一致。
- `qa-report.md` 中没有未处理的严重问题。
- `visual-coverage-report.json` 的 `missing_count` 为 `0`。
- `capture-result.json` 无 `failed`，`retake-list.yaml` 为空或已全部补拍。
- 截图不含密码、身份证号、银行卡号、手机号等敏感信息。
- DOCX/PDF 的目录、章节编号、表格、图表和截图显示正常。
- 用 Word 打开 DOCX 后，如目录未刷新，选择目录并执行“更新整个目录”。

## 5. 一键执行与常用命令

以下内容均输入到 Trae 对话框。

### 生成完整用户手册

```text
/doc-gen --type manual
```

若包含截图，目标系统必须已经启动，且截图配置可用。

### 一次生成全部文档

```text
/doc-gen --type all
```

### 深度探索后生成全部文档

```text
/doc-gen --type all --deep
```

### 仅生成数据库说明书

```text
/doc-gen --type database
```

### 仅生成 API 文档

```text
/doc-gen --type api
```

### 强制全量重建

```text
/doc-gen --type all --no-cache
```

首次从旧版缓存算法升级后，应执行一次 `--no-cache`。

### 生成 PDF 或 HTML

```text
/doc-gen --type manual --format pdf
/doc-gen --type manual --format html
```

若 PDF 引擎不可用，Skill 会按 DOCX 转换、HTML 的顺序降级，并报告实际产物。

### 生成英文文档

```text
/doc-gen --type all --lang en
```

## 6. 截图配置

从模板复制：

```powershell
New-Item -ItemType Directory -Force knowledge | Out-Null
Copy-Item templates/screenshot-config.yaml knowledge/screenshot-config.yaml
```

### 6.1 单前端项目

```yaml
screenshot:
  viewport:
    width: 1920
    height: 1080
  headless: true
  slow_mo: 0
  interactive: false
  auto_annotate: true
  keep_original: true
  add_browser_chrome: false

base_url: "http://localhost:8080"

test_accounts:
  admin:
    username: "admin"
    password: "${APP_ADMIN_PASS}"
    login_url: "/login"
```

### 6.2 多前端项目

```yaml
apps:
  admin:
    base_url: "http://localhost:8080"
  client:
    base_url: "http://localhost:3000"

test_accounts:
  admin:
    username: "admin"
    password: "${APP_ADMIN_PASS}"
    login_url: "/login"
    app: "admin"
  user:
    username: "testuser"
    password: "${APP_USER_PASS}"
    login_url: "/login"
    app: "client"
```

多前端项目中，`knowledge/pages/*.yaml` 与截图计划的 `app` 字段必须和 `apps` 键匹配。

### 6.3 浏览器头与自动标注

- `auto_annotate: true`：按截图计划的 `highlight` 字段绘制编号、箭头和标签。
- `keep_original: true`：保留未标注原图，方便复核或重新处理。
- `add_browser_chrome: true`：在截图顶部合成浏览器头，需要有效的 `browser_chrome_header_path`。

模板中的 `default_mode`、`page_timeout`、`action_delay` 当前仅作说明；实际行为分别由每张截图的 `full_page`、脚本超时和 `wait_after_action` 控制。

## 7. 参数速查

| 参数 | 可选值 | 默认值 | 说明 |
|---|---|---|---|
| `--type` | `manual/database/api/all` | `manual` | 选择文档类型 |
| `--stage` | `all/explorer/runtime/diagram/writer/review/screenshot/render` | `all` | 只运行指定阶段 |
| `--deep` | 无值开关 | 关闭 | 启用运行时探索 |
| `--format` | `docx/pdf/html` | `docx` | 最终输出格式 |
| `--lang` | `zh/en` | `zh` | 文档语言 |
| `--no-cache` | 无值开关 | 关闭 | 忽略缓存，强制重建 |
| `--dry-run` | 无值开关 | 关闭 | 只显示执行计划 |

阶段执行的前置条件：

| 阶段 | 主要前置产物 |
|---|---|
| `explorer` | 项目源码 |
| `runtime` | PKB、截图配置、已启动的目标系统、`--deep` |
| `diagram` | 对应类型的 PKB |
| `writer` | PKB、图表 manifest |
| `review` | `output/manual.md` |
| `screenshot` | 审核后的手册、视觉覆盖报告、截图配置、已启动的目标系统 |
| `render` | 对应的 Markdown；手册截图可选但建议先通过审核 |

若依赖缺失，编排器会尝试补充执行依赖；若 PKB 为空，应先运行 `--stage explorer`。

## 8. 缓存与增量更新

每个 Skill 成功且输出验证通过后，缓存哈希写入 `.cache/{skill-name}.hash`。再次执行时：

- 输入未变：该 Skill 显示“缓存命中，跳过”。
- 相关源码或 PKB 变化：只重跑受影响阶段。
- 缓存损坏：删除对应 `.hash` 后重跑。
- 希望全部重建：使用 `--no-cache`。

不要在一个阶段刚开始时手工写缓存；失败任务不得留下代表成功的缓存。

## 9. 独立调试截图采集

通常应让 `doc-gen` 调用截图 Skill。只有定位截图问题时，才在终端直接运行脚本。

无头采集：

```powershell
python templates/generate_screenshots.py `
  --config knowledge/screenshot-config.yaml `
  --plan knowledge/screenshots.yaml `
  --output output/screenshots `
  --headless
```

有头慢动作调试：

```powershell
python templates/generate_screenshots.py `
  --config knowledge/screenshot-config.yaml `
  --plan knowledge/screenshots.yaml `
  --output output/screenshots `
  --headed `
  --slow-mo 500
```

只补拍审核清单：

```powershell
python templates/generate_screenshots.py `
  --config knowledge/screenshot-config.yaml `
  --plan knowledge/screenshots.yaml `
  --output output/screenshots `
  --retake output/retake-list.yaml
```

还可使用 `--role admin` 只采集指定角色，使用 `--annotate/--no-annotate` 和 `--add-chrome/--no-add-chrome` 临时覆盖配置。

## 10. 常见问题

### `/doc-gen` 被 PowerShell 识别为无效命令

原因：它是 Trae Skill 指令。请把 `/doc-gen ...` 输入到 Trae 对话框，不要在终端执行。

### 找不到某个子 Skill

确认复制了完整 `.trae/skills/`，而不是只有 `doc-gen` 目录；再检查目标项目是否以该目录为工作区根目录打开。

### PKB 为空或文档缺功能

先运行 `--stage explorer --no-cache`，抽查 `knowledge/modules/`、`pages/`、`roles/` 和 `workflows/`。大项目会分批扫描，应确认没有把业务源码目录误当成构建产物排除。

### 视觉覆盖检查不通过

查看 `output/visual-coverage-report.json` 的缺失状态，让 `qa-reviewer` 补齐 `manual.md` 中的标准图片占位后再运行截图阶段。不要绕过 `missing_count = 0` 的门禁。

### 无法访问页面

检查目标系统是否已启动、`base_url`/端口是否正确、是否需要 VPN 或代理。多前端项目要确认 `apps` 中的所有应用都已启动。

### 环境变量缺失

脚本会指出缺失变量名。用 `$env:变量名 = "值"` 在当前 PowerShell 会话设置后重试；不要把明文密码直接提交到 YAML。

### 登录后仍停留在登录页

先用 `--headed --slow-mo 500` 独立调试；检查账号、登录 URL、登录表单选择器、验证码和单点登录流程。验证码或 MFA 通常需要测试环境绕过方案或预置登录态。

### 截图是空白页、Loading 或状态不符

检查 `output/capture-result.json`、`screenshot-capture-report.md` 和 `screenshot-review-report.md`。常见原因是前置动作选择器失效、接口数据未准备、等待时间不足或账号无权限。修正 PKB/截图计划后按补拍清单重试。

### 截图标注没有出现

确认已安装 Pillow、`auto_annotate: true`，并检查计划中的 `highlight` 选择器及结果中的 `annotation_warnings`。标注未命中不一定使采集失败，但如果影响操作理解，应补拍。

### DOCX 中仍有图片占位

说明对应截图状态不可用、文件不存在，或占位键与 `knowledge/screenshots.yaml` 不匹配。补拍后重新运行 `--stage render`。

### Pandoc 找不到 `templates/reference.docx`

可生成默认参考模板：

```powershell
pandoc -o templates/reference.docx --print-default-data-file reference.docx
```

生成失败时可不传 `--reference-doc` 使用 Pandoc 默认样式；没有 Pandoc 时会回退到 python-docx。

### PDF 没有生成

安装 XeLaTeX，或安装 LibreOffice 以便从 DOCX 转换。两者均不可用时，检查 Skill 报告的 HTML 降级产物。

### 图表渲染失败

检查 PlantUML Server 网络连通性和 PlantUML 语法。敏感项目应启动本地服务，避免为了修复网络问题而改用公共服务上传项目结构。

## 11. 推荐使用策略

- 首次使用先 `--dry-run`，再分阶段生成并抽查 PKB。
- 日常源码小改直接重跑原命令，利用缓存增量更新。
- PKB 结构或缓存算法升级后使用一次 `--no-cache`。
- 只修改文档样式时运行 `--stage render`，无需重新扫描和截图。
- 只修改手册内容时依次运行 `review → screenshot → render`。
- 只修复截图时运行 `screenshot → render`；存在补拍清单时优先补拍。
- 数据库/API 文档不需要启动 Web 应用；用户手册真实截图需要。
