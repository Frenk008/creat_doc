---
name: "webapp-testing"
description: "Web应用自动化截图采集器(V2)。连接用户已启动的项目,使用Playwright按照截图计划批量采集界面截图。当screenshot-planner完成截图规划后,或doc-gen编排器调用时使用。"
---

# WebApp Testing —— Web 应用自动化截图采集器

## Skill 契约

```yaml
inputs:
  - knowledge/screenshots.yaml
  - knowledge/screenshot-config.yaml
outputs:
  - output/screenshots/*.png
  - output/screenshots/original/*.png
  - knowledge/screenshots.yaml (更新 status)
  - output/capture-result.json
depends_on:
  - screenshot-planner
cache_key:
  - knowledge/screenshots.yaml (仅稳定计划字段)
  - knowledge/screenshot-config.yaml
stage: screenshot
```

你的任务是连接到用户已启动的目标项目,使用 Playwright 按照 `screenshots.yaml` 截图计划批量采集实际界面截图。

## 前置条件

1. **用户已自行启动项目**并通过浏览器确认可以正常访问(不负责启动项目)
2. 系统已安装 Playwright(`pip install playwright && playwright install chromium`)
3. 用户提供截图配置文件 `knowledge/screenshot-config.yaml`(含访问 URL + 测试账号)
4. 密码字段支持 `${ENV_VAR}` 环境变量引用,避免明文提交到 git

## 输入

- `knowledge/screenshots.yaml` —— 截图计划(由 screenshot-planner 生成)
- `knowledge/screenshot-config.yaml` —— 截图配置(URL、账号等)
- `output/retake-list.yaml` —— 补拍清单(可选,由 screenshot-reviewer 产出。若存在则仅补拍其中列出的截图 ID)

## 输出

- `output/screenshots/*.png` —— 采集的截图文件
- `output/screenshots/original/*.png` —— 未添加标注和浏览器头的纯页面原图（`keep_original: true` 时）
- 更新 `knowledge/screenshots.yaml` 中每条记录的 `status`
- `output/capture-result.json` —— 结构化采集结果(**供 screenshot-reviewer 读取**),字段:`total` / `captured` / `partial` / `failed` / `results[]`,其中每个 result 含 `id` / `status`(captured / partial / failed) / `error`
- `output/screenshot-capture-report.md` —— 人类可读的采集报告

## 执行流程

### Step 1: 读取并校验配置

读取 `knowledge/screenshot-config.yaml`,如不存在则引导用户创建(模板见 `templates/screenshot-config.yaml`)。

**校验项:**
- 顶层 `base_url` 非空，或 `apps.*.base_url` 至少配置一个
- test_accounts 至少有一个角色
- screenshots.yaml 中有 `status: planned` 的记录

### Step 1.5: 询问用户截图模式(交互)

在连接项目之前,询问用户选择浏览器运行模式。这是本 Skill 唯一需要用户交互的步骤。

**询问策略(满足任一条件则跳过询问):**

1. **命令行已显式指定**(`--headed` 或 `--headless`):不询问,直接使用
2. **配置文件显式禁用询问**(`screenshot.interactive: false`):不询问,直接使用配置中的 `headless` 值
3. **补拍模式**(`output/retake-list.yaml` 存在):默认沿用上次设置,不询问(补拍通常是已知问题,不需要再看过程)

**询问内容(使用 AskUserQuestion 工具):**

```
问题: 截图使用哪种浏览器模式?
选项:
  1. 无头模式(推荐)    —— 快速采集,无窗口干扰,适合批量截图
  2. 有头模式          —— 可见浏览器窗口,便于观察截图过程
  3. 有头 + 慢动作调试  —— 每步操作放慢 500ms,用于排查选择器/登录失败
```

**处理用户选择:**

| 用户选择 | 写入/传递 | 命令行参数 |
|---|---|---|
| 无头模式(推荐) | `headless: true` | `--headless`(或默认) |
| 有头模式 | `headless: false` | `--headed` |
| 有头 + 慢动作调试 | `headless: false, slow_mo: 500` | `--headed --slow-mo 500` |

**回写配置(记忆选择):**

用户选择后,将其写回 `knowledge/screenshot-config.yaml` 的 `screenshot.headless` 和 `screenshot.slow_mo` 字段。这样:
- 下次执行本 Skill 时,可作为默认值
- screenshot-reviewer 触发的补拍可直接复用,无需再次询问

> **凭据安全警告(必须遵守):** 回写时只能**局部更新** `screenshot.headless` 和 `screenshot.slow_mo` 两个字段,**严禁整文件重写**。该文件含 `${ENV_VAR}` 密码引用、`apps`、`test_accounts` 等结构,整文件覆写可能破坏密码占位符或丢失字段。推荐用 YAML 解析后只改这两个键再 dump,或用文本替换精确修改这两行。

**环境兼容性兜底:**

若用户选择有头模式但当前环境无法启动 GUI(如 SSH / 无 display 的 Linux 服务器),脚本会自动回退到无头模式并输出警告。脚本内部已实现该回退逻辑(generate_screenshots.py 中 `launch` 失败时 try/except 回退)。

### Step 2: 连接性检测

检查 `base_url` 是否可访问(用户应已自行启动项目):

```bash
# 尝试访问 base_url,最多重试 3 次
curl -sf {base_url} --connect-timeout 5
```

**如果 base_url 不可达:**
- 提示用户:"项目尚未启动或地址不正确,请先启动项目并确认浏览器能正常访问 {base_url}"
- 提示用户检查:screenshot-config.yaml 中的 base_url 和端口是否正确
- 等待用户确认后重试,**不自行启动项目**

**如果 base_url 可达:** 继续下一步。

**多套前端处理:**
如果 `screenshot-config.yaml` 中配置了 `apps`(多套前端),脚本会根据每张截图的 `app` 字段自动选择对应的 base_url。无需手动区分,用户只需确保所有前端应用都已启动。

### Step 3: 生成 Playwright 截图脚本

根据 `screenshots.yaml` 和 `screenshot-config.yaml`,生成 Python 脚本并执行。

脚本逻辑见 `templates/generate_screenshots.py`。核心流程:

```python
# 伪代码
1. 启动 Chromium(按 Step 1.5 用户选择的模式:无头 / 有头 / 有头+慢动作)
2. 设置视口大小(默认 1920x1080)
3. 按 test_accounts 中第一个角色登录系统
4. 遍历 screenshots.yaml 中的计划:
   a. 导航到 page route
   b. 执行 prerequisite 操作(如点击按钮触发弹窗)
   c. 等待页面加载完成
   d. 高亮指定元素(可选)
   e. 原图保存到 output/screenshots/original/{id}.png，并按 highlight 自动生成编号、箭头和标签到 output/screenshots/{id}.png
   f. 记录成功/失败状态
5. 关闭浏览器
```

**自动标注配置：** 默认启用 `screenshot.auto_annotate: true`，样式为 `numbered_arrow`，颜色由 `annotation_color` 控制。命令行 `--annotate` / `--no-annotate` 的优先级高于配置。没有 `highlight` 时不绘制。目标未命中不会使截图失败，而是在结果中写入 `annotation.missing` 和 `annotation_warnings`。

浏览器头使用 `--add-chrome` / `--no-add-chrome` 覆盖配置，两个方向都必须支持。

每条采集结果包含：

```yaml
annotation:
  requested: 3
  matched: 2
  missing: ["用户列表表格"]
annotation_warnings:
  - "未找到标注目标：用户列表表格"
```

**截图前脱敏注入(必须执行):**

在截图前,通过 `page.add_style_tag` 注入 CSS,遮盖敏感字段:

```python
MASK_CSS = """
input[type="password"],
.sensitive,
[data-mask],
[aria-label*="密码"],
[aria-label*="验证码"] {
    color: transparent !important;
    background: #ccc !important;
    border: 1px solid #999 !important;
}
/* 遮盖常见敏感数据样式 */
.masked-text {
    filter: blur(3px);
}
"""

# 在每个页面截图前注入
page.add_style_tag(content=MASK_CSS)
```

**脱敏规则:**
- `input[type="password"]`:密码框统一灰底
- `.sensitive` / `[data-mask]`:业务代码可主动标注的敏感字段
- 含"密码""验证码"的 aria-label:兜底匹配
- 模糊滤镜用于文字内容(可选)

**关键实现细节:**

**登录逻辑:**
```python
# 从 pages.yaml 找到登录页路由,或使用 config 中的 login_url
page.goto(base_url + login_url)
page.fill("input[name='username'], input#username", account["username"])
page.fill("input[name='password'], input#password", account["password"])
page.click("button[type='submit'], button:has-text('登录'), button:has-text('Login')")
# 等待跳转离开登录页
page.wait_for_url(f"**{account['expected_redirect']}", timeout=10000)
```

**页面导航 + 截图:**

**补拍模式:** 若 `output/retake-list.yaml` 存在,仅采集其中列出的截图 ID,覆盖原文件。读取方式:
```python
if os.path.exists("output/retake-list.yaml"):
    with open("output/retake-list.yaml", encoding="utf-8") as f:
        retake_data = yaml.safe_load(f) or {}
    # screenshot-reviewer 产出格式: {retakes: [{id: "...", ...}, ...]}
    retake_ids = [r["id"] for r in retake_data.get("retakes", [])]
    screenshots = [s for s in screenshots if s["id"] in retake_ids]
```

实际采集必须调用 `templates/generate_screenshots.py`，不要在 Skill 中复制另一套截图循环。该脚本统一负责原图保留、动作失败状态、自动标注、浏览器头、报告和原子写入。

**操作执行器:** 优先执行截图计划中的完整可重放动作列表；自然语言仅兼容简单按钮点击。每张图先重新进入 route，再从第一条 action 执行到目标状态。任一动作失败或 `selector_status: unresolved` 时写入 `action_warnings`，保留截图并将状态设为 `partial`，不得继续标记为 `captured`。

```yaml
action:
  - type: click
    selector: "button:has-text('新增')"
  - type: fill
    selector: "input[name='username']"
    value: "测试用户"
  - type: select
    selector: "select[name='role']"
    value: "user"
  - type: wait_for
    selector: "[role='dialog']"
    state: "visible"
```

### Step 4: 多角色截图(如需)

如果 screenshots.yaml 中有不同角色的截图需求,且 config 中配置了多个 test_accounts:

```python
for role_name, account in test_accounts.items():
    # 每个角色新建 context(独立会话)
    context = browser.new_context()
    page = context.new_page()
    
    # 用该角色登录
    login(page, account)
    
    # 只截该角色相关的截图(按 screenshots 中的 roles 字段过滤)
    role_shots = [s for s in screenshots if role_name in s.get("roles", [])]
    capture_screenshots(page, role_shots)
    
    context.close()
```

### Step 4.5: 询问是否添加浏览器头部(交互,可选)

在所有截图采集完成、进入结果汇总之前,询问用户是否需要给已采集的截图拼接【真实浏览器头部图片】(在地址栏区域绘制真实 URL)。

**前置条件:**
- Pillow 已安装(`pip install pillow`)。若未安装,跳过询问并提示用户。
- 用户提供浏览器头部模板图片(默认路径 `templates/browser_chrome_header.png`,可在 `screenshot-config.yaml` 的 `screenshot.browser_chrome_header_path` 配置)。若文件不存在,提示用户截取后放入指定路径,跳过询问。
- 建议同时配置 `screenshot.browser_chrome_addr_rect`(地址栏区域比例),用于精确定位 URL 文字绘制位置。

**询问策略(满足任一条件则跳过询问):**

1. **本次截图 0 张成功**(无图可合成,直接跳过)
2. **命令行已显式指定** `--add-chrome`:不询问,直接按命令行执行
3. **配置已显式声明** `add_browser_chrome: true`(或 `false`):不询问,直接使用配置值
4. **补拍模式**(`output/retake-list.yaml` 存在):默认沿用上次设置,不询问

**询问内容(使用 AskUserQuestion 工具):**

```
问题: 已采集 N 张截图,是否给每张截图拼接浏览器头部(含真实 URL)?
选项:
  1. 不添加(推荐)   —— 纯页面截图,适合大多数技术手册
  2. 添加浏览器头    —— 顶部拼接真实浏览器头部图片(地址栏显示真实 URL),适合产品演示
```

**用户选择"添加浏览器头"时的处理:**

由于脚本中 `--add-chrome` 是在截图**之前**传入的(每张截图成功后立即合成),而此询问在所有截图**之后**进行,因此:

- 若用户选择"添加",但截图阶段未传 `--add-chrome`:需要**对已保存的 PNG 执行纯后处理合成**。Agent 直接遍历 `output/screenshots/` 下的 PNG 文件,调用 `templates/generate_screenshots.py` 中的 `add_browser_chrome(png_path, url, "", header_path=..., addr_rect=...)` 函数(URL 可从 `screenshots.yaml` 的 `route` 字段取,header_path 和 addr_rect 从 config 取)。
- 若用户选择"不添加",但截图阶段已传 `--add-chrome`:无需回退(保持已合成的图,或提示用户是否重拍覆盖)

> **推荐做法:** 在 Step 3 执行脚本前,默认**不**传 `--add-chrome`;用户在此处选择"添加"后,Agent 对 output/screenshots/ 下的 PNG 执行批量后处理合成。这样避免一次性决定导致不可逆。

**回写配置:** 用户选择后,写回 `knowledge/screenshot-config.yaml` 的 `screenshot.add_browser_chrome` 字段(仅局部更新,严禁整文件重写,同 Step 1.5 的凭据安全要求)。

**合成内容说明:**
- 头部图片:用户自行截取的真实浏览器顶部(标签栏 + 地址栏 + 工具栏),脚本按截图宽度等比缩放后拼接在顶部。
- URL 文字:在 `browser_chrome_addr_rect` 指定的地址栏区域内绘制真实 URL(来自 `page.url()`),自动截断以适应宽度。
- 不绘制额外的 logo 或商标(头部图片本身由用户提供,用户自负商标合规责任)。

### Step 5: 收集结果并更新状态

执行完成后:
1. 更新 `knowledge/screenshots.yaml` 中每条记录的 `status`(`captured` / `failed`)
2. 生成采集报告 `output/screenshot-capture-report.md`

### Step 6: 清理

如用户通过 Docker 启动项目,提示用户自行清理容器(本 Skill 不负责停止项目)。

## 采集报告格式

```markdown
# 截图采集报告

## 采集概况
- 采集时间：{时间}
- 计划截图数：{总数}
- 成功采集：{成功数}
- 采集失败：{失败数}
- 成功率：{百分比}

## 详细结果

| 截图ID | 手册位置 | 页面 | 状态 | 说明 |
|--------|----------|------|------|------|
| shot-4-1-1 | 4.1 登录-步骤1 | /login | ✅ 已采集 | |
| shot-5-1-1 | 5.1 用户管理-步骤1 | /users | ✅ 已采集 | |
| shot-5-1-2 | 5.1 用户管理-步骤2 | /users | ❌ 失败 | 元素未找到:新增按钮 |

## 失败分析
{列出失败截图的原因和建议处理方式}
```

## 错误处理

| 错误场景 | 处理方式 |
|---------|---------|
| Playwright 未安装 | 提示 `pip install playwright && playwright install chromium` |
| 登录失败 | 尝试备用选择器,仍失败则跳过需登录的截图 |
| 页面导航超时 | 记录 timeout,该页截图标记 failed |
| 元素未找到 | 截当前页面作为兜底,标记为 partial |
| 环境变量缺失 | 报错并提示具体变量名,不静默继续 |

## 日志规范

生成的脚本 SHALL 统一使用 Python `logging` 模块替代 `print`:
- `logging.info()` —— 正常流程信息
- `logging.warning()` —— 可恢复的异常或需要注意的情况
- `logging.error()` —— 错误信息(输出到 stderr)
- Windows 下 SHALL 配置 `sys.stdout.reconfigure(encoding="utf-8")` 避免中文乱码

## 文件编码规范

生成的脚本文件和报告使用 **UTF-8 无 BOM** 编码(同 document-renderer 的编码规范)。

## 严格约束

1. **不修改项目源码**:只通过浏览器操作进行截图采集(不负责启动/停止项目),不修改项目任何文件。
2. **截图计划为准**:只截取 screenshots.yaml 中列出的页面,不自行增加。
3. **失败不阻塞**:单张截图失败不影响其他截图,继续执行后续计划。
4. **清理资源**:采集完成后必须关闭浏览器。
6. **截图前必须注入脱敏 CSS**:每个页面截图前必须执行 `page.add_style_tag(content=MASK_CSS)`,遮盖密码框和敏感字段,避免真实用户数据泄露到文档中。
7. **浏览器头图片来源合规**:拼接用的浏览器头部图片由用户自行提供(默认 `templates/browser_chrome_header.png`),商标合规责任由用户自负。脚本仅在地址栏区域绘制纯 URL 文字,不额外添加任何浏览器 logo 或商标。
