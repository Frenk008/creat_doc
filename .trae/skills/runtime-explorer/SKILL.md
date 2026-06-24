---
name: "runtime-explorer"
description: "运行时探索器(V2 功能,V1 为占位状态)。通过启动项目并使用浏览器自动化,发现静态分析无法获取的动态行为(弹窗内容、表单校验、动态加载等)并更新 PKB。当前 V1 版本仅记录占位,不实际执行。当 doc-gen 以 --deep 模式调用时触发。"
---

# Runtime Explorer —— 运行时探索器

> **版本状态: V1 为占位模式,不实际执行。此文档为 V2 完整实现的设计规范。**

## V1 行为(当前)

当被调用时:
1. 不启动项目,不执行浏览器操作
2. 在 `knowledge/runtime.yaml` 中写入:

```yaml
runtime:
  status: "not_explored"
  note: "V1 版本跳过运行时探索。动态行为(弹窗内容、表单校验规则等)需人工补充或升级到 V2。"
  discovered_dialogs: []
  dynamic_fields: []
  validation_rules: []
```

3. 返回提示:"运行时探索在 V1 中为占位状态,PKB 仅包含静态分析结果。"

---

## V2 完整设计(未来实现)

### 职责

补充静态分析无法发现的动态行为:
- 点击按钮后弹出的对话框/表单
- 表单字段的动态校验规则
- 异步加载的下拉选项
- 操作成功/失败后的提示信息
- 条件显示的 UI 元素

### 执行流程

```
1. 启动目标项目(或连接到已运行实例)
2. 使用 Playwright/Puppeteer 打开浏览器
3. 按 pages.yaml 逐页访问
4. 对每个页面执行交互探索:
   a. 点击所有可点击元素
   b. 记录弹出的对话框及其表单字段
   c. 提交空表单记录校验提示
   d. 记录操作后的反馈信息
5. 将发现写入 knowledge/runtime.yaml
6. 更新 PKB 中相关 pages/workflows
```

### 产出

`knowledge/runtime.yaml`:

```yaml
runtime:
  status: "complete"
  explored_pages: ["login", "user-list", "user-create"]
  dialogs:
    - trigger_page: "user-list"
      trigger_action: "click_create"
      dialog_title: "新增用户"
      fields:
        - name: "username"
          label: "用户名"
          type: "input"
          required: true
          validation: "必填项,3-20个字符"
        - name: "email"
          label: "邮箱"
          type: "input"
          required: true
          validation: "必填项,需符合邮箱格式"
      submit_button: "确定"
      cancel_button: "取消"
  validation_rules:
    - page: "user-create"
      field: "username"
      rules:
        - "必填"
        - "长度3-20"
        - "不能包含特殊字符"
  feedback_messages:
    - trigger: "create_user_success"
      message: "用户创建成功"
      type: "success"
```
