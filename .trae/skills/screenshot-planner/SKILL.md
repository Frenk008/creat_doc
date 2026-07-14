---
name: "screenshot-planner"
description: "截图计划生成器。读取生成的用户手册和 PKB,为每个需要截图的操作步骤生成详细的截图计划(页面、操作、数据状态、高亮元素)。当 manual-writer 完成手册生成后,或 doc-gen 编排器调用时使用。"
---

# Screenshot Planner —— 截图计划生成器

## Skill 契约

```yaml
inputs:
  - output/manual.md
  - output/visual-coverage-report.json
  - knowledge/pages/
  - knowledge/workflows/
  - knowledge/roles/
  - knowledge/runtime/ (如已执行 deep 探索)
outputs:
  - knowledge/screenshots.yaml
depends_on:
  - qa-reviewer
cache_key:
  - output/manual.md
  - output/visual-coverage-report.json
  - knowledge/pages/**/*.yaml
  - knowledge/workflows/**/*.yaml
  - knowledge/runtime/**/*.yaml
stage: screenshot
```

你的任务是读取用户手册和 PKB,为手册中每个图片占位生成可执行的截图计划。

## 输入

- `output/manual.md` —— 已生成的用户手册(含图片占位标记)
- `output/visual-coverage-report.json` —— QA 生成的视觉状态覆盖报告；`missing_count` 必须为 0
- `knowledge/pages/` —— 页面信息目录
- `knowledge/workflows/` —— 操作流程目录
- `knowledge/roles/` —— 角色信息目录

## 输出

- `knowledge/screenshots.yaml` —— 截图计划清单

## 执行步骤

开始规划前检查 `visual-coverage-report.json`。若 `missing_count > 0`，终止规划并返回 qa-reviewer 补齐占位；不得在占位不足时继续生成一节一图的计划。

### Step 1: 提取图片占位

扫描 `manual.md`,提取所有图片占位标记:

```
【图片：用户管理-步骤1】（截图占位，后续补充）
【图片：创建用户-步骤3】（截图占位，后续补充）
```

每个占位记录:
- `manual_ref`: 手册中的位置(章节号 + 功能名 + 步骤号)
- `placeholder`: `【图片：...】` 中的原始键，必须原样保存
- `feature_name`: 功能名称
- `step_number`: 步骤号
- `state_name`: 占位符中的界面状态名

### Step 2: 为每个占位匹配页面

从 `pages/*.yaml` 中找到对应页面:

```
"用户管理-步骤1" → pages/ 中 title="用户管理" 的页面文件
```

记录:
- `page_id`: 页面 ID
- `app`: 所属前端应用(从 pages.app 复制,多套前端时用于选择 base_url)
- `route`: 页面默认路由(从 pages.route 复制)
- `routes`: 多主题路由映射(从 pages.routes 复制,如有)
- `menu_path`: 菜单路径

> **多套前端注意**:如果项目有两套前端(如 admin + client),pages/ 中每个页面文件会有 `app` 字段区分。截图计划中必须带上 `app` 字段,这样 webapp-testing 才知道用哪个 base_url 访问该页面。
>
> **多主题路由映射**:如果同一页面在不同主题下路由不同(如 default 的 `/console/topup` 对应 classic 的 `/wallet`),页面文件会有 `routes` 字典。截图计划也需复制 `routes`,这样脚本会根据 screenshot-config 中实际运行的 app/主题选择正确路由。

### Step 3: 推导截图上下文

从 `workflows/*.yaml` 中找到该步骤对应的操作,推导截图时需要的状态:

每张截图都从 `route` 重新进入页面，因此 `action` 必须是从路由初始状态到目标状态的**完整可重放动作序列**，不能只写最后一次点击，也不能依赖前一张截图已经执行过操作。`prerequisite_shots` 只用于排序和业务说明，不用于复用浏览器状态。

```yaml
- id: "shot-5-2-3"
  manual_ref: "5.2 创建用户 - 步骤3"
  placeholder: "创建用户-步骤3"
  state_name: "表单填写完成"
  state_type: "form_filled"
  replay_from: "route"
  page_id: "user-create"
  route: "/users/create"
  action:
    - type: "click"
      selector: "button:has-text('新增')"
    - type: "fill"
      selector: "input[name='name']"
      value: "测试用户"
    - type: "wait_for"
      selector: "form"
      state: "visible"
  need_scroll: false
  highlight: "姓名输入框、角色选择框"     # 自动标注目标，按书写顺序编号
  full_page: false                        # 是否整页截图(默认 false)
  wait_after_action: 500                  # 操作后等待毫秒(默认 500)
  data_state: "已点击新增按钮,对话框已弹出" # 截图时系统应处于的状态
  capture_reason: "填写完成后需要指导用户核对姓名和角色"
  prerequisite_shots: ["shot-5-2-1", "shot-5-2-2"] # 此截图依赖的前置截图
  roles: ["管理员"]                        # 适用角色(多角色截图时过滤;不填=所有角色通用)
  status: "planned"
```

### Step 4: 规划截图顺序

按业务流程排列截图,确保:
1. 同一页面的连续步骤紧挨排列
2. 前置步骤的截图排在前面
3. 登录页截图始终排在第一位
4. 按角色分组(先管理员视角,再普通用户视角)

### Step 4.1: 构建状态检查点与累积动作

对同一路由的连续操作按状态拆成多张截图：

```yaml
- id: "contact-list"
  placeholder: "联系管理-步骤1-咨询列表"
  route: "/enterprise/contacts"
  state_type: "page"
  action: []

- id: "contact-detail"
  placeholder: "联系管理-步骤2-联系详情弹窗"
  route: "/enterprise/contacts"
  state_type: "dialog"
  action:
    - type: "click"
      selector: "tr:has-text('11') button:has-text('查看')"
    - type: "wait_for"
      selector: "[role='dialog']"
      state: "visible"
```

对更深状态重复前面的动作。例如“回复表单填写完成”必须包含打开回复弹窗以及所有 fill 动作。补拍任意一张图时都应独立成功。

稳定 selector 优先级：Runtime Explorer 记录的 selector > `data-testid/data-action` > 角色/文本限定 selector > 通用文本 selector。列表行操作必须加入业务数据限定，不能直接选择页面上第一个“查看/编辑”按钮。

### Step 5: 识别特殊截图需求

| 场景 | 特殊处理 |
|------|----------|
| 弹窗/对话框 | `state_type: dialog`，点击后追加 `wait_for [role=dialog]` |
| 长列表/表格 | 标注 `need_scroll: true`,需滚动截全 |
| 下拉选择 | 标注 `need_expand: true`,需展开下拉框 |
| 确认操作 | 标注 `need_confirm: true`,需触发确认提示 |
| 错误提示 | 标注 `need_error_state: true`,需制造错误输入 |

> **字段生效说明(重要)**:截图脚本消费 `action` / `need_scroll` / `highlight` / `full_page` / `wait_after_action`。`action` 优先生成结构化动作列表，支持 `click`、`fill`、`select`、`check`、`press`、`upload`、`wait`、`wait_for`；每个交互动作必须给出稳定 selector，填写/选择/按键/上传动作还需给出 value。自然语言字符串仅用于兼容简单按钮点击。动作失败时截图保留但状态为 `partial`。其余特殊状态字段仍是规划信息。

## 输出格式

```yaml
screenshots:
  - id: "shot-4-1-1"
    manual_ref: "4.1 登录系统 - 步骤1"
    placeholder: "登录系统-步骤1-登录页面"
    state_name: "登录页面"
    state_type: "page"
    replay_from: "route"
    page_id: "login"
    route: "/login"
    action: "展示登录页面"
    need_scroll: false
    highlight: "用户名输入框、密码输入框、登录按钮"
    data_state: "未登录状态,登录页面初始展示"
    prerequisite_shots: []
    status: "planned"

  - id: "shot-5-1-1"
    manual_ref: "5.1 用户管理 - 步骤1"
    page_id: "user-list"
    route: "/users"
    action: "展示用户列表页面"
    need_scroll: false
    highlight: "新增按钮、搜索框、用户列表表格"
    data_state: "列表中已有至少3条用户记录"
    prerequisite_shots: ["shot-4-1-1"]
    status: "planned"

  # ... 更多截图计划
```

## 严格约束

1. **手册中每个图片占位必须有对应的截图计划**,不遗漏。
2. **截图计划必须基于 PKB 中的实际页面**,不得为不存在的页面规划截图。
3. **数据状态描述必须具体可执行**,如"列表已有3条记录"而非"有一些数据"。注意:`data_state` 当前仅作为**人工补拍/造数的参考说明**,截图脚本不会自动构造该数据状态;若某截图强依赖特定数据,应在审核阶段人工准备数据或手动补拍。
4. **本 Skill 仅输出截图计划**,不执行实际截图。`status` 统一为 `planned`。后续状态流转由下游推进:planned →(webapp-testing)captured/partial/failed →(screenshot-reviewer)reviewed/need_retake/failed。
5. `highlight` 使用 `、`、中文逗号或英文逗号分隔多个目标；名称应尽量对应页面可见文字、placeholder、title 或 aria-label。截图脚本会生成编号气泡、箭头和标签。
6. **每张截图必须可独立重放**：`action` 包含从 route 初始状态到目标状态的全部动作；禁止依赖 `prerequisite_shots` 保存页面状态。
7. **一占位一状态一截图**：同一路由出现列表、详情弹窗、编辑弹窗、确认框、结果状态时，分别生成不同 ID。
8. 无法从 PKB/Runtime Explorer 得到稳定 selector 时，写入 `selector_status: unresolved`，不得臆造选择器；截图审核阶段必须将其列为待补拍。
