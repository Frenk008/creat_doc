---
name: "webapp-testing"
description: "Web应用自动化截图采集器(V2)。连接用户已启动的项目,使用Playwright按照截图计划批量采集界面截图。当screenshot-planner完成截图规划后,或doc-gen编排器调用时使用。"
---

# WebApp Testing —— Web 应用自动化截图采集器

你的任务是连接到用户已启动的目标项目,使用 Playwright 按照 `screenshots.yaml` 截图计划批量采集实际界面截图。

## 前置条件

1. **用户已自行启动项目**并通过浏览器确认可以正常访问(不负责启动项目)
2. 系统已安装 Playwright(`pip install playwright && playwright install chromium`)
3. 用户提供截图配置文件 `knowledge/screenshot-config.yaml`(含访问 URL + 测试账号)

## 输入

- `knowledge/screenshots.yaml` —— 截图计划(由 screenshot-planner 生成)
- `knowledge/screenshot-config.yaml` —— 截图配置(URL、账号等)
- `knowledge/pages.yaml` —— 页面路由信息(辅助登录)
- `output/retake-list.yaml` —— 补拍清单(可选,由 screenshot-reviewer 产出。若存在则仅补拍其中列出的截图 ID)

## 输出

- `output/screenshots/*.png` —— 采集的截图文件
- 更新 `knowledge/screenshots.yaml` 中每条记录的 `status`
- `output/capture-result.json` —— 结构化采集结果(**供 screenshot-reviewer 读取**),字段:`total` / `captured` / `partial` / `failed` / `results[]`,其中每个 result 含 `id` / `status`(captured / partial / failed) / `error`
- `output/screenshot-capture-report.md` —— 人类可读的采集报告

## 执行流程

### Step 1: 读取并校验配置

读取 `knowledge/screenshot-config.yaml`,如不存在则引导用户创建(模板见 `templates/screenshot-config.yaml`)。

**校验项:**
- screenshot.base_url 非空
- test_accounts 至少有一个角色
- screenshots.yaml 中有 `status: planned` 的记录

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
1. 启动 Chromium(headless 模式)
2. 设置视口大小(默认 1920x1080)
3. 按 test_accounts 中第一个角色登录系统
4. 遍历 screenshots.yaml 中的计划:
   a. 导航到 page route
   b. 执行 prerequisite 操作(如点击按钮触发弹窗)
   c. 等待页面加载完成
   d. 高亮指定元素(可选)
   e. 截图保存到 output/screenshots/{id}.png
   f. 记录成功/失败状态
5. 关闭浏览器
```

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

```python
for shot in screenshots:
    try:
        # 导航
        page.goto(base_url + shot["route"])
        page.wait_for_load_state("networkidle", timeout=15000)
        
        # 前置操作(如需点击触发弹窗)
        if shot.get("action"):
            # 根据 screenshot-planner 的 action 描述执行
            execute_action(page, shot["action"])
            page.wait_for_timeout(500)  # 等待动画
        
        # 需要滚动的场景
        if shot.get("need_scroll"):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(300)
        
        # 截图
        page.screenshot(path=f"output/screenshots/{shot['id']}.png", full_page=shot.get("full_page", False))
        shot["status"] = "captured"
    except Exception as e:
        shot["status"] = "failed"
        shot["error"] = str(e)
```

**操作执行器(将截图计划的 action 描述转为实际操作):**

```python
def execute_action(page, action_desc):
    """
    解析 screenshot-planner 生成的 action 描述并执行。
    action_desc 是自然语言,如"点击新增按钮""填写表单"。
    这里用简单关键词匹配,复杂场景需 AI 辅助。
    """
    desc = action_desc.lower()
    
    # 点击类操作
    if "点击" in action_desc or "新增" in action_desc:
        # 尝试多种选择器
        for selector in ["button:has-text('新增')", "button:has-text('添加')", 
                         "[data-action='create']", ".add-btn", "#addBtn"]:
            try:
                page.click(selector, timeout=2000)
                return
            except:
                continue
    
    # 保存类操作
    elif "保存" in action_desc:
        for selector in ["button:has-text('保存')", "button:has-text('确定')",
                         "[type='submit']"]:
            try:
                page.click(selector, timeout=2000)
                return
            except:
                continue
    
    # 其他操作记录日志,不强制执行
    print(f"  ⚠️ 无法自动执行操作: {action_desc}")
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

## 文件编码规范

生成的脚本文件和报告使用 **UTF-8 无 BOM** 编码(同 document-renderer 的编码规范)。

## 严格约束

1. **不修改项目源码**:只通过浏览器操作进行截图采集(不负责启动/停止项目),不修改项目任何文件。
2. **截图计划为准**:只截取 screenshots.yaml 中列出的页面,不自行增加。
3. **失败不阻塞**:单张截图失败不影响其他截图,继续执行后续计划。
4. **清理资源**:采集完成后必须关闭浏览器。
