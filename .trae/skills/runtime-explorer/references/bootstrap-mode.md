# Bootstrap 模式

## 目录

- [目标与边界](#目标与边界)
- [输入校验](#输入校验)
- [探索流程](#探索流程)
- [PKB 构建规则](#pkb-构建规则)
- [覆盖与失败处理](#覆盖与失败处理)
- [完成条件](#完成条件)

## 目标与边界

在没有源码和现有 PKB 时，仅凭已部署网站与测试账号，建立用户手册所需的可观察事实。只生成 manual 类型 PKB；不得生成或推断数据库、完整 API、服务架构和不可见权限。

严格执行只读探索：

- 允许同源导航、展开菜单、切换页签、搜索、筛选、查看详情、打开并取消弹窗、聚焦和失焦字段。
- 禁止保存、删除、确认业务操作、上传文件、提交任何表单、导出、访问外部链接。
- 不确定控件是否会修改数据时，视为禁止操作。

## 输入校验

读取 `knowledge/screenshot-config.yaml` 并验证：

1. 顶层 `base_url` 非空，或 `apps.*.base_url` 至少一个可访问。
2. `test_accounts` 至少包含一个角色，并提供 username、password、login_url。
3. `${ENV_VAR}` 密码引用可以解析；不得把解析后的密码写入文件或日志。
4. 每个 base URL 使用 HTTPS，或明确属于 localhost/受控测试环境。
5. 网站不可达时终止，不创建虚假 PKB。

## 探索流程

### 1. 按角色登录

按 `test_accounts` 键排序，逐个账号建立独立会话。账号键作为 role ID，显示名优先取配置中的 `display_name`，否则使用页面可见角色名，仍无结果时使用账号键。

登录后如仍位于登录页、出现 CAPTCHA/MFA 或权限错误：

- 将该角色加入 `uncovered_roles`。
- 在 `failures` 中记录不含凭据的原因。
- 继续下一个角色；全部角色失败时设置 `auth_failed` 并终止。

### 2. 收集导航入口

只从以下区域收集候选入口：

- 主导航、侧边栏、抽屉式导航。
- 面包屑和页面内一级页签。
- 具有同源 href 的可见菜单项。

忽略页脚、广告、内容正文链接、分页链接、下载链接、外部域名和 logout。将 URL 规范化为 `app + pathname + 稳定查询参数`；去除 fragment、跟踪参数和会话参数。

### 3. 有界遍历

- 每个角色最多探索 50 个唯一页面。
- 按菜单顺序广度优先；达到上限时记录剩余入口到 `skipped_pages`，状态设为 `partial`。
- 同一 `app + route` 跨角色只创建一个 page，合并并排序 roles。
- 页面导航超时只跳过当前页，不中断其他角色。

### 4. 提取页面事实

对每个页面记录：

- 标题、route、app、菜单层级和所属一级菜单。
- 可见表格列、表单字段、搜索与筛选字段。
- 可见按钮及稳定 selector；优先 data-testid/data-action，其次 role + 可见文本。
- 弹窗、抽屉、详情页和客户端可见校验提示。

可以打开新增或编辑弹窗查看字段，但不得触发保存。禁止点击删除、保存、确定、提交、上传和导出控件。

### 5. 生成只读工作流

只为实际完成的只读动作生成 workflow，例如进入页面、搜索、筛选、切换页签、查看详情、打开并取消弹窗。写操作只可记录为页面存在的 action，不得生成已执行步骤、成功反馈或 postcondition。

## PKB 构建规则

### project.yaml

- 保持 `schema_version: "1.0"`。
- 设置 `project.source_type: website`。
- 项目名称取站点标题或登录后产品标题；无法识别时取 base URL 主机名。
- 不可观察的 version、tech_stack 和 database 留空，不得推断。

### modules/

- 每个一级菜单生成一个模块。
- 无一级菜单的网站生成 `general` 模块。
- 合并各角色观察结果，并维护 pages、workflows、roles 反向引用。

### pages/

- 每个规范化 `app + route` 生成一个页面文件。
- ID 使用 app、route 和标题生成，并清洗为 `[a-z0-9-]`；冲突时追加稳定短后缀。
- roles 是所有可访问该页面的已验证账号角色。
- actions 和 fields 只包含 DOM 中实际观察到的信息。

### roles/

- 每个测试账号键生成一个角色文件。
- `can_access` 来自实际遍历结果；`cannot_access` 只记录明确返回 403/无权限的页面，不用“未看见”推断无权限。

### workflows/ 与 workflow-chains.yaml

- workflow 步骤必须可从已记录 page 和 action 重放。
- 只读工作流允许生成 postcondition；未执行的写操作不得生成结果。
- workflow chain 仅连接已观察到的只读流程。

所有实体按 ID 排序，列表去重后排序。使用临时文件加原子 rename，仅在规范化内容变化时替换现有 PKB。

## 覆盖与失败处理

在 `knowledge/runtime/_meta.yaml` 记录：

```yaml
runtime:
  mode: bootstrap
  status: complete
  account_roles: [admin, user]
  uncovered_roles: []
  explored_pages: [dashboard, user-list]
  skipped_pages: []
  total_pages: 2
  explored_count: 2
  failures: []
  explored_at: "ISO-8601 时间"
```

状态规则：

- `complete`：所有可登录角色均完成有界遍历，未达到页面上限。
- `partial`：至少一个角色成功，但存在登录失败、超时或页面上限截断。
- `auth_failed`：所有角色均无法登录。
- `failed`：配置、连接或输出验证失败，无法形成最小 PKB。

## 完成条件

bootstrap 只有同时满足以下条件才算成功：

1. `project.yaml` 存在且 source_type 为 website。
2. modules/pages/roles 至少各有一个合法实体。
3. workflows 与 workflow-chains 文件存在；没有可安全执行的流程时允许为空，但必须说明原因。
4. 所有 page.module_id 和 workflow.page_id 引用都能解析。
5. runtime 元数据包含覆盖范围和失败记录。
6. 输出中不存在密码、Cookie、Token 或其他会话凭据。
