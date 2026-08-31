---
name: "runtime-explorer"
description: "运行时探索器。通过chrome-devtools-mcp连接已部署网站：bootstrap模式可在没有源码和PKB时从网站、测试账号冷启动生成用户手册所需PKB；enrich模式补充已有PKB中的弹窗、表单校验、动态加载和稳定选择器。当doc-gen使用--source website或--deep时调用。"
---

# Runtime Explorer —— 运行时探索器

## Skill 契约

```yaml
modes:
  bootstrap:
    inputs: [knowledge/screenshot-config.yaml]
    outputs: [knowledge/project.yaml, knowledge/modules/, knowledge/pages/, knowledge/roles/, knowledge/workflows/, knowledge/workflow-chains.yaml, knowledge/runtime/]
    depends_on: []
    cache_key: []  # 线上状态无法由本地文件哈希判断，每次显式调用都执行
  enrich:
    inputs: [knowledge/screenshot-config.yaml, knowledge/pages/, knowledge/modules/, knowledge/workflows/]
    outputs: [knowledge/runtime/, knowledge/pages/, knowledge/workflows/]
    depends_on: [project-explorer 或 runtime-explorer:bootstrap]
    cache_key: [knowledge/pages/**/*.yaml, knowledge/modules/**/*.yaml, knowledge/workflows/**/*.yaml]
stage: runtime
```

通过 chrome-devtools-mcp 连接已运行的目标项目，并按调用参数选择模式：

- `bootstrap`：在没有源码和 PKB 时，从已部署网站生成用户手册所需的最小完整 PKB。
- `enrich`：读取已有 PKB，补充静态分析无法发现的动态行为。

执行 `bootstrap` 前必须完整读取 [references/bootstrap-mode.md](references/bootstrap-mode.md)，并严格遵守其中的遍历上限、合并规则和只读边界。

## 前置条件

1. 目标项目已部署或由用户自行启动(用户已确认浏览器可以访问 base_url)
2. 项目可通过浏览器访问(有 base_url)
3. chrome-devtools-mcp 已集成(本环境已内置)

## 输入

- 所有模式：`knowledge/screenshot-config.yaml`，包含 base_url/apps 和 test_accounts
- `bootstrap`：不要求任何现有 PKB
- `enrich`：要求 `knowledge/pages/`、`knowledge/modules/` 和 `knowledge/workflows/`

## 输出

- `bootstrap`：创建 `project.yaml`、分文件 modules/pages/roles/workflows、`workflow-chains.yaml` 和 `runtime/`
- `enrich`：更新对应页面与工作流，并写入 `runtime/` 发现记录
- 所有 YAML 使用 UTF-8 无 BOM；实体 ID 只允许 `[a-z0-9-]`

## 为什么用 chrome-devtools-mcp 而不是 Playwright

runtime-explorer 的核心是**探索**,不是按计划执行:
- 打开页面后,需要 **AI 实时判断**"这个弹窗 PKB 里有没有记录过"
- 看到一个表单,需要 **AI 判断**"哪些字段和只读校验信息值得记录"
- 发现新的 UI 元素,需要 **AI 决定**"要不要点击看看会弹出什么"

这种"走走停停、实时判断"的工作模式,天然适合 MCP 工具逐步调用,而不适合预先编写脚本。

## 探索策略

### 核心原则

```
不追求全覆盖,只补高价值发现。
每发现一个静态分析遗漏的信息,就更新 PKB。
```

发现弹窗、抽屉、下拉框、确认框和结果提示时，必须记录触发动作的稳定 selector、目标状态 selector、`ui_effect` 与建议 `capture`。Screenshot Planner 将用这些信息构建从 route 起点可独立重放的动作序列。

### 探索深度控制

为避免无限探索,设置明确的边界:

| 探索内容 | 深度 | 说明 |
|---------|------|------|
| 页面级 | pages/ 中的所有页面文件 | 每页都打开看一眼 |
| 弹窗级 | 点击主操作按钮(新增/编辑) | 只探索主要弹窗,不探索每个下拉 |
| 表单级 | 弹窗中的所有输入框 | 记录字段和校验规则 |
| 交互级 | 不深入(不执行实际增删改) | 只看不动数据 |

## 模式选择

1. 调用方显式传入 `mode=bootstrap|enrich` 时，以显式值为准。
2. `doc-gen --source website --stage explorer` 必须调用 bootstrap。
3. `doc-gen --source website --stage runtime` 必须调用 enrich；PKB 不存在时终止并提示先执行 explorer。
4. `doc-gen --source code --deep` 必须调用 enrich。
5. 不得仅因 PKB 缺失就静默切换模式。

## Enrich 执行流程

### Step 1: 读取 PKB 和配置

读取 `pages/*.yaml` 获取页面列表,读取 `screenshot-config.yaml` 获取 base_url 和测试账号。

### Step 2: 登录系统

使用 chrome-devtools-mcp 工具登录:

```
1. navigate_page → 打开 {base_url}/login
2. take_snapshot → 获取登录页结构
3. fill → 填写用户名(username 选择器)
4. fill → 填写密码(password 选择器)
5. click → 点击登录按钮
6. wait_for → 等待页面跳转
```

**MCP 工具调用示例:**

```
navigate_page(url="{base_url}/login")
take_snapshot()  → 分析登录表单结构
fill(selector="input[name='username']", value="admin")
fill(selector="input[name='password']", value="admin123")
click(selector="button[type='submit']")
wait_for(text="首页", timeout=10000)  # 等待首页加载
```

### Step 3: 逐页探索

对 `pages/*.yaml` 中的每个页面:

#### 3.1 打开页面

```
navigate_page(url="{base_url}{page.route}")
take_snapshot()  → 获取页面 DOM 结构
```

#### 3.2 对比静态分析结果

分析 snapshot,与 PKB 中的 `pages.actions` 和 `pages.fields` 对比:

**发现新内容时更新 PKB:**

```yaml
# 静态分析知道页面有"新增"按钮,但不知道点击后弹出什么
# 运行时发现:
page_id: "user-list"
discovered_actions:
  - action: "create"
    trigger: "点击新增按钮"
    result: "弹出对话框"
    dialog_title: "新增用户"
    discovered_fields:       # ← 静态分析不知道的表单字段
      - name: "username"
        label: "用户名"
        type: "input"
        required: true
      - name: "email"
        label: "邮箱"
        type: "input"
        required: true
      - name: "role"
        label: "角色"
        type: "select"
        options: ["管理员", "普通用户"]  # ← 下拉选项
```

#### 3.3 点击主要操作按钮

对页面上的主要操作按钮(新增、编辑),点击并记录弹出的内容:

```
click(selector="button:has-text('新增')")
take_snapshot()  → 获取弹窗 DOM
```

**记录弹窗信息:**

```yaml
discovered_dialogs:
  - trigger_page: "user-list"
    trigger_action: "click_create_button"
    dialog_type: "modal"        # modal / drawer / page
    dialog_title: "新增用户"
    fields:
      - name: "username"
        label: "用户名"
        type: "input"
        required: true
        placeholder: "请输入用户名"
      - name: "role"
        label: "角色"
        type: "select"
        options: ["管理员", "普通用户", "审核员"]
    submit_button: "确定"
    cancel_button: "取消"
```

#### 3.4 探索表单校验

只通过 DOM 属性、可访问性信息和聚焦后失焦观察校验，不点击任何保存、确定或提交控件：

```
take_snapshot()  → 读取 required / pattern / min / max / aria-describedby
focus(selector="input[name='username']")
press_key(key="Tab")  → 仅触发客户端失焦校验
take_snapshot()  → 获取可见校验信息
```

**记录校验规则:**

```yaml
discovered_validation_rules:
  - page: "user-create"
    field: "username"
    rules:
      - type: "required"
        message: "请输入用户名"
      - type: "length"
        message: "长度在 3 到 20 个字符"
    # 如果能触发更多校验则记录
```

#### 3.5 探索动态加载

检查页面是否有动态加载的内容(异步下拉、级联选择等):

```
# 通过 snapshot 检查是否有 loading 状态、异步组件
# 如果发现动态加载行为,记录触发条件
```

### Step 4: 关闭弹窗,恢复页面

探索完一个弹窗后:

```
click(selector="button:has-text('取消')")  # 或 press_key(key="Escape")
```

确保页面恢复到初始状态,再继续探索下一个。

### Step 5: 生成 runtime/ 结果

将发现按类别写入 `knowledge/runtime/`，并用 `_meta.yaml` 记录探索状态:

```yaml
runtime:
  status: "complete"            # not_explored / partial / complete / timeout / auth_failed / failed
  mode: "enrich"                # bootstrap / enrich
  explored_at: "{时间}"
  account_roles: ["admin"]
  uncovered_roles: []
  explored_pages: ["login", "user-list", "user-create", "role-list"]
  skipped_pages: []
  failures: []
  total_pages: 15               # pages/ 中的页面总数
  explored_count: 4             # 实际探索的页面数

  discovered_dialogs:
    - trigger_page: "user-list"
      trigger_action: "click_create_button"
      dialog_title: "新增用户"
      dialog_type: "modal"
      fields: [...]
      submit_button: "确定"
      cancel_button: "取消"

    - trigger_page: "user-list"
      trigger_action: "click_edit_button"
      dialog_title: "编辑用户"
      dialog_type: "modal"
      fields: [...]

  discovered_validation_rules:
    - page: "user-create"
      field: "username"
      rules:
        - type: "required"
          message: "请输入用户名"
        - type: "length"
          message: "长度在 3 到 20 个字符"

    - page: "user-create"
      field: "email"
      rules:
        - type: "required"
          message: "请输入邮箱"
        - type: "email"
          message: "请输入正确的邮箱格式"

  discovered_dynamic_elements:
    - page: "order-create"
      element: "产品下拉框"
      trigger: "选择产品分类后动态加载"
      dependency: "category_id"

  discovered_feedback_messages:
    - trigger: "create_user_success"
      message: "新增成功"
      type: "success"
    - trigger: "create_user_duplicate"
      message: "用户名已存在"
      type: "error"
```

### Step 6: 更新 PKB

将运行时发现回写到 PKB 文件:

**更新对应 pages/{page_id}.yaml:**
- 将 `discovered_fields` 合并到 page.fields
- 将弹窗中的操作补充到 page.actions

**更新对应 workflows/{workflow_id}.yaml:**
- 将弹窗中的表单字段补充到 workflow steps
- 将校验规则补充到 steps 的 notes

## 探索优化(避免 token 爆炸)

### 分页探索

如果 pages/ 有很多页面(>10 个),分批探索:

```
第1批: 登录页 + 首页 + 前3个核心模块页面
第2批: 其余页面
```

### 跳过低价值页面

以下页面可以跳过运行时探索:
- 纯展示页面(无操作按钮)
- 静态分析已经覆盖了所有 fields 的页面
- 外部链接页面(跳转到其他系统)

### 控制弹窗探索深度

对每个页面:
- 只探索 1-2 个主要操作(新增/编辑)
- 不探索次要操作(导出、批量删除、排序)
- 不进入多级弹窗(弹窗中再弹窗)

## 错误处理

| 错误场景 | 处理 |
|---------|------|
| 页面导航超时 | 跳过该页,记录 status: "timeout" |
| 登录失败 | 尝试备用账号,仍失败则标记 status: "auth_failed" |
| 弹窗未弹出 | 记录但不算错误(可能是权限不足) |
| MCP 工具调用失败 | 重试一次,仍失败则跳过 |

## 文件编码规范

所有 YAML 输出使用 UTF-8 无 BOM 编码。

## 严格约束

1. **严格只读**：不得执行保存、删除、确认业务操作、上传、导出或任何表单提交。
2. **只开不落库**：可以打开新增/编辑弹窗查看结构，但只能通过取消、关闭或 Escape 恢复页面。
3. **不绕过认证**：遇到 CAPTCHA、MFA 或登录失败时，记录 `auth_failed`/`partial`，不得尝试绕过。
4. **只记录事实**：不得推断技术栈、数据库、完整 API 或当前账号不可见的功能。
5. **每次探索后恢复**：弹窗探索完毕后必须关闭，不残留界面状态。
6. **确定性输出**：实体按 `id` 排序；内容未变化时不得改写 PKB。时间戳只写入 `runtime/_meta.yaml`。
