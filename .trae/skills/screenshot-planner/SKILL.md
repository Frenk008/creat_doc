---
name: "screenshot-planner"
description: "截图计划生成器。读取生成的用户手册和 PKB,为每个需要截图的操作步骤生成详细的截图计划(页面、操作、数据状态、高亮元素)。当 manual-writer 完成手册生成后,或 doc-gen 编排器调用时使用。"
---

# Screenshot Planner —— 截图计划生成器

你的任务是读取用户手册和 PKB,为手册中每个图片占位生成可执行的截图计划。

## 输入

- `output/manual.md` —— 已生成的用户手册(含图片占位标记)
- `knowledge/pages.yaml` —— 页面信息
- `knowledge/workflows.yaml` —— 操作流程信息
- `knowledge/roles.yaml` —— 角色信息

## 输出

- `knowledge/screenshots.yaml` —— 截图计划清单

## 执行步骤

### Step 1: 提取图片占位

扫描 `manual.md`,提取所有图片占位标记:

```
【图片：用户管理-步骤1】（截图占位，后续补充）
【图片：创建用户-步骤3】（截图占位，后续补充）
```

每个占位记录:
- `manual_ref`: 手册中的位置(章节号 + 功能名 + 步骤号)
- `feature_name`: 功能名称
- `step_number`: 步骤号

### Step 2: 为每个占位匹配页面

从 `pages.yaml` 中找到对应页面:

```
"用户管理-步骤1" → pages.yaml 中 title="用户管理" 的 page
```

记录:
- `page_id`: 页面 ID
- `route`: 页面路由(供 webapp-testing 导航使用)
- `menu_path`: 菜单路径

### Step 3: 推导截图上下文

从 `workflows.yaml` 中找到该步骤对应的操作,推导截图时需要的状态:

```yaml
- id: "shot-5-2-3"
  manual_ref: "5.2 创建用户 - 步骤3"
  page_id: "user-create"
  route: "/users/create"
  action: "填写创建用户表单"
  need_scroll: false
  highlight: "姓名输入框、角色选择框"     # 需要高亮/标注的区域
  data_state: "已点击新增按钮,对话框已弹出" # 截图时系统应处于的状态
  prerequisite_shots: ["shot-5-2-1", "shot-5-2-2"] # 此截图依赖的前置截图
  status: "planned"
```

### Step 4: 规划截图顺序

按业务流程排列截图,确保:
1. 同一页面的连续步骤紧挨排列
2. 前置步骤的截图排在前面
3. 登录页截图始终排在第一位
4. 按角色分组(先管理员视角,再普通用户视角)

### Step 5: 识别特殊截图需求

| 场景 | 特殊处理 |
|------|----------|
| 弹窗/对话框 | 标注 `need_dialog: true`,截图前需触发弹窗 |
| 长列表/表格 | 标注 `need_scroll: true`,需滚动截全 |
| 下拉选择 | 标注 `need_expand: true`,需展开下拉框 |
| 确认操作 | 标注 `need_confirm: true`,需触发确认提示 |
| 错误提示 | 标注 `need_error_state: true`,需制造错误输入 |

## 输出格式

```yaml
screenshots:
  - id: "shot-4-1-1"
    manual_ref: "4.1 登录系统 - 步骤1"
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
3. **数据状态描述必须具体可执行**,如"列表已有3条记录"而非"有一些数据"。
4. **V1 不执行实际截图**,只输出计划。`status` 统一为 `planned`。
