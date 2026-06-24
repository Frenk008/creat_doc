---
name: "webapp-testing"
description: "Web应用自动化截图采集器(V2)。通过Docker启动项目,使用Playwright按照截图计划批量采集界面截图。当screenshot-planner完成截图规划后,或doc-gen编排器调用时使用。"
---

# WebApp Testing —— Web 应用自动化截图采集器

你的任务是通过 Docker 启动目标项目,使用 Playwright 按照 `screenshots.yaml` 截图计划批量采集实际界面截图。

## 前置条件

1. 目标项目包含 `docker-compose.yml`(或 `docker-compose.yaml`)
2. 系统已安装 Docker 和 Docker Compose
3. 系统已安装 Playwright(`pip install playwright && playwright install chromium`)
4. 用户提供截图配置文件 `knowledge/screenshot-config.yaml`

## 输入

- `knowledge/screenshots.yaml` —— 截图计划(由 screenshot-planner 生成)
- `knowledge/screenshot-config.yaml` —— 截图配置(Docker、账号、URL 等)
- `knowledge/pages.yaml` —— 页面路由信息(辅助登录)

## 输出

- `output/screenshots/*.png` —— 采集的截图文件
- 更新 `knowledge/screenshots.yaml` 中每条记录的 `status`
- `output/screenshot-capture-report.md` —— 采集报告

## 执行流程

### Step 1: 读取并校验配置

读取 `knowledge/screenshot-config.yaml`,如不存在则引导用户创建(模板见 `templates/screenshot-config.yaml`)。

**校验项:**
- docker.compose_file 指向的文件存在
- screenshot.base_url 非空
- test_accounts 至少有一个角色
- screenshots.yaml 中有 `status: planned` 的记录

### Step 2: Docker 启动项目

```bash
# 进入项目目录
cd {project_root}

# 启动容器(后台模式)
docker compose -f {compose_file} up -d

# 等待服务就绪
```

**就绪检测策略(按优先级):**

1. 如果配置了 `healthcheck_url`:
```bash
# 轮询健康检查接口,最多等 120 秒
for i in $(seq 1 24); do
    curl -sf {healthcheck_url} && break
    sleep 5
done
```

2. 如果未配置 healthcheck,等待 `wait_seconds`(默认 15 秒),再尝试访问 base_url:
```bash
# 轮询 base_url,最多等 60 秒
for i in $(seq 1 12); do
    curl -sf {base_url} && break
    sleep 5
done
```

3. 如果 base_url 仍不可达,报告错误并询问用户是否继续。

**Docker 启动失败处理:**
- 检查 `docker compose logs` 输出
- 端口冲突 → 提示用户修改端口映射
- 镜像不存在 → 提示用户先 `docker compose build`
- 依赖服务未启动 → 等待重试

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
page.wait_for_url(f"**{dashboard_route}", timeout=10000)
```

**页面导航 + 截图:**
```python
for shot in screenshots:
    try:
        # 导航
        page.goto(base_url + shot["route"])
        page.wait_for_load_state("networkidle", timeout=15000)
        
        # 前置操作(如需点击触发弹窗)
        if shot.get("prerequisite_action"):
            # 根据 screenshot-planner 的 action 描述执行
            execute_action(page, shot["prerequisite_action"])
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

### Step 6: Docker 清理

```bash
# 停止并清理容器(保留数据卷)
docker compose -f {compose_file} down
```

**如果用户要求保留容器运行**(用于调试),跳过此步骤。

## 采集报告格式

```markdown
# 截图采集报告

## 采集概况
- 采集时间：{时间}
- Docker 容器：{状态}
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
| Docker 未安装 | 提示安装 Docker Desktop |
| docker compose 启动失败 | 输出 `docker compose logs`,询问用户 |
| Playwright 未安装 | 提示 `pip install playwright && playwright install chromium` |
| 登录失败 | 尝试备用选择器,仍失败则跳过需登录的截图 |
| 页面导航超时 | 记录 timeout,该页截图标记 failed |
| 元素未找到 | 截当前页面作为兜底,标记为 partial |
| 端口冲突 | 提示修改 compose 中的端口映射 |

## 文件编码规范

生成的脚本文件和报告使用 **UTF-8 无 BOM** 编码(同 document-renderer 的编码规范)。

## 严格约束

1. **不修改项目源码**:只通过 Docker 启动和浏览器操作,不修改项目任何文件。
2. **截图计划为准**:只截取 screenshots.yaml 中列出的页面,不自行增加。
3. **失败不阻塞**:单张截图失败不影响其他截图,继续执行后续计划。
4. **清理资源**:采集完成后必须关闭浏览器;Docker 容器默认关闭(除非用户要求保留)。
