---
name: "project-explorer"
description: "核心源码分析器(轻量版)。自动探测项目技术栈,扫描源码结构并提取功能模块、页面、路由、角色、业务流程等核心信息。数据库和API分析由独立的 Extractor 负责。当需要分析项目源码或 doc-gen 编排器调用时使用。"
---

# Project Explorer —— 核心源码分析器

## Skill 契约

```yaml
inputs:
  - 项目源码目录(自动扫描)
outputs:
  - knowledge/project.yaml
  - knowledge/modules/
  - knowledge/pages/
  - knowledge/roles/
  - knowledge/workflows/
  - knowledge/workflow-chains.yaml
depends_on: []
cache_key:
  - 源码文件哈希(src/**/*.java, src/**/*.go, src/**/*.vue 等)
stage: explorer
```

你的任务是扫描项目源码,提取**核心功能信息**(不含数据库和 API 细节),输出为技术栈无关的 PKB YAML 文件。

**职责边界:**
- ✅ 负责:项目信息、技术栈探测、模块、页面、路由、角色、业务流程
- ❌ 不负责:数据库表结构 → 由 `database-extractor` 负责
- ❌ 不负责:API 接口定义 → 由 `api-extractor` 负责

## 执行阶段

### 阶段 0: 扫描规模评估

在深入扫描前,先评估项目规模,避免一次性读取过多文件导致 token 溢出:

1. 统计源码文件数(排除 node_modules/target/dist/.git/vendor)
2. 如文件数 ≤ 500(默认阈值),正常全量扫描
3. 如文件数 > 500,切换为**分批扫描模式**

**分批扫描模式:**
- 按目录分组(如 src/controller/、src/service/、src/views/user/ 等)
- 每批不超过 50 个文件
- 每批读取后立即提取关键信息,合并到中间结果
- 优先扫描配置文件、路由文件、入口文件(信息密度最高)
- 跳过测试文件(*Test.java、*_test.go、*.spec.js)和自动生成文件

**阈值可通过 project.yaml 配置:**
```yaml
scan:
  batch_threshold: 500      # 超过此文件数启用分批模式
  batch_size: 50            # 每批最大文件数
```

**输出提示:** 如启用分批扫描,在日志中标注"⚠️ 大项目分批扫描模式已启用,共 N 批"。

### 阶段 1: 技术栈探测

读取以下文件判断技术栈(存在即读):

| 文件 | 判断内容 |
|------|----------|
| `pom.xml` / `build.gradle` | Java + Spring Boot / Maven / Gradle |
| `go.mod` | Go + 框架(gin/echo/kratos/fiber) |
| `package.json` | 前端框架(vue/react/angular) + UI 库 + 构建工具 |
| `requirements.txt` / `pyproject.toml` | Python + Django/FastAPI/Flask |
| `composer.json` | PHP + Laravel |
| `Cargo.toml` | Rust |

**探测规则:**
1. 先读构建配置文件,确定后端和前端的存在性
2. 再抽样读 3-5 个前端文件,确认前端框架(检查 `vite.config` / `next.config` / `nuxt.config` / `angular.json`)
3. 检查路由配置文件确认路由方式
4. 检查是否有数据库相关配置(`application.yml` / `config.yaml` / `.env`),**只记录数据库类型,不深入扫描表结构**(表结构由 database-extractor 负责)
5. **多套前端识别**:扫描是否存在多个独立的前端应用。判断依据:
   - 存在多个 `package.json`(如根目录 + `admin/` 子目录 + `client/` 子目录)
   - 存在多个 `vite.config` / `next.config` / `nuxt.config` / `vue.config`
   - 项目根目录下有明显的分端目录(如 `admin/` + `client/`,或 `web/` + `mobile/`)
   - 有多个独立的 `router/index.js` 或路由配置文件(不同目录下)

**多套前端的 app 标识规则:**
- 每识别出一套独立前端,分配一个 `app` 标识
- 标识名从目录名推导(如 `admin/` → app="admin",`client/` → app="client")
- 如果只有单套前端,统一用 `app: "default"`
- 所有该前端下的页面,pages.yaml 中的 `app` 字段填写对应标识

**示例(两套前端):**
```
项目根/
├── admin/              → app="admin"
│   ├── package.json
│   ├── src/router/     → 这些页面的 app="admin"
│   └── ...
├── client/             → app="client"
│   ├── package.json
│   ├── src/router/     → 这些页面的 app="client"
│   └── ...
└── server/             → 后端(不分配 app)
```

产出 `knowledge/project.yaml` 中增加 `apps` 字段:
```yaml
tech_stack:
  frontend_apps:          # 多套前端列表(单前端则只有 default)
    - id: "admin"
      name: "管理端"
      framework: "vue3"
      base_path: "admin/"
    - id: "client"
      name: "用户端"
      framework: "react"
      base_path: "client/"
```

**主题/多路由映射识别:**

某些项目支持多主题(如 default / classic),同一页面在不同主题下路由路径不同。识别依据:
- 代码中存在路由映射表/重定向配置(如 `redirect` / `alias` / `pathMap`)
- 配置文件中有主题切换 + 对应的路由前缀差异
- 前端代码中有 `if theme === 'classic'` 类的路由分支

发现路由映射时,在 pages.yaml 中填充 `routes` 字段:
```yaml
pages:
  - id: "topup"
    app: "default"
    route: "/console/topup"          # 默认路由
    routes:                           # 多主题路由映射
      default: "/console/topup"
      classic: "/wallet"
    title: "充值"
```

如未发现路由映射,`routes` 留空,只用 `route` 字段(所有主题共享同一路由)。

### 阶段 2: 按技术栈选策略扫描

根据 `project.yaml` 的 tech_stack 字段,选择对应的扫描策略。

**注意:本阶段只扫描页面、路由、菜单、角色、权限。不扫描数据库表结构和 API 接口细节(那些由独立 Extractor 负责)。**

---

#### 策略 A: Java Spring Boot 后端(核心信息)

**扫描目标(仅核心信息):**
- `@Controller` 中的页面路由(WebMvc 跳转,非 REST API) → pages
- `@PreAuthorize` / `@Secured` / `@RolesAllowed` → 角色权限 → roles.yaml
- 枚举类或常量类中的角色定义 → roles.yaml
- Swagger `@Api(tags=)` → 辅助推导 modules

**不扫描(交给 api-extractor):**
- ~~`@RestController` / `@RequestMapping` → API 端点~~
- ~~`@RequestBody` / DTO 解析~~
- ~~请求/响应结构~~

**不扫描(交给 database-extractor):**
- ~~`@Entity` / `@Table` → 数据库表~~
- ~~字段映射~~

---

#### 策略 B: Go 后端 (Gin / Echo / Kratos) (核心信息)

**扫描目标(仅核心信息):**
- 路由注册中的页面路由(非 API):`router.GET("/users", renderTemplate)` → pages
- 中间件:认证/权限中间件 → roles.yaml
- Handler 函数名和注释 → 功能描述(辅助)

**不扫描(交给 api-extractor):**
- ~~API 路由注册~~
- ~~请求/响应结构~~

**不扫描(交给 database-extractor):**
- ~~ORM 模型结构体~~
- ~~SQL 文件~~

---

#### 策略 C: Vue 前端 (Vue2 / Vue3)

**扫描目标:**
- 路由配置:`router/index.js` / `router.ts` → pages.yaml 的 route 和 menu_path
- 菜单配置:布局组件中的 `<el-menu>` / `<a-menu>` 或独立菜单配置 → menu_path
- 页面组件:`views/` 或 `pages/` 目录下的 `.vue` 文件 → pages.yaml
- 按钮和操作:模板中的 `@click` / `<el-button>` / `<a-button>` → actions
- 表单字段:`<el-form-item>` / `<a-form-item>` 的 label → fields
- 路由守卫:`router.beforeEach` 中的角色判断 → roles.yaml
- 权限指令:`v-permission` / `v-role` → 角色权限

**关键转换规则:**
```
{ path: '/users', meta: { title: '用户管理', roles: ['admin'] } }
  → page.id = "user-management"
    page.route = "/users"
    page.title = "用户管理"
    page.roles = ["admin"]
    page.menu_path = 从父路由 title 推导

<el-button @click="handleAdd">新增</el-button>
  → action = "create"

<el-form-item label="用户名"><el-input v-model="form.username" />
  → field = "username" (中文名"用户名")
```

---

#### 策略 D: React 前端

**扫描目标:**
- 路由:`react-router` 的 `<Route path=...>` / `createBrowserRouter` → pages.yaml
- 菜单:`<Menu>` / `<Sider>` 组件中的 items → menu_path
- 页面组件:`pages/` 或 `src/pages/` 下的组件 → pages.yaml
- 按钮和操作:`onClick` / `<Button>` → actions
- 表单:`<Form.Item label=...>` / `name=...` → fields
- 权限:Auth 组件 / `useAuth` hook / `hasPermission` → roles.yaml

---

#### 策略 E: 通用兜底 (generic)

当无法确定具体框架时:
1. 扫描所有目录结构,识别页面级文件(包含 `view` / `page` / `screen` 关键字的文件)
2. 搜索 UI 文本:全局搜索中文文案字符串(引号内的中文)作为功能线索
3. 搜索路由关键字:`path` / `route` / `url` 字样
4. 搜索权限关键字:`role` / `permission` / `auth` 字样
5. **必须标注每个发现的置信度**(high / medium / low)

---

### 阶段 3: 语义整合

将扫描结果整合为最终的 PKB,按模块分文件输出:

1. **推导 modules**:按业务领域聚类 pages(如所有 user 相关 page 归入"用户管理"模块)
2. **推导 workflows**:按页面 actions 推导常见操作流程(create → fill → save)
3. **生成 roles**:综合前端权限 + 后端注解,产出角色定义
4. **生成 project.yaml**:填写项目信息

### 阶段 3.5: ID 合法性校验(路径遍历防护)

在写入文件前,对所有用作文件名的 entity_id 进行校验:

**校验规则:** `^[a-z0-9][a-z0-9-]{0,63}$`
- 仅允许小写字母、数字、连字符
- 必须以字母或数字开头
- 长度 1-64 字符

**需校验的字段:**
- modules 的 id
- pages 的 id
- roles 的 id
- workflows 的 id

**校验失败时:** 跳过该实体,记录 warning日志,不写入文件,不终止整个流程。

**实现示例(Python 辅助):**
```python
import re
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

def validate_id(entity_id: str, entity_type: str) -> bool:
    if not ID_PATTERN.match(entity_id or ""):
        print(f"⚠️ 跳过 {entity_type}: ID '{entity_id}' 不合法(仅允许 [a-z0-9-],长度1-64)")
        return False
    return True
```

### 阶段 4: 输出 PKB(按模块分文件)

将所有结果写入 `knowledge/` 目录,**每个知识实体一个文件**(支持增量更新):

```
knowledge/
├── project.yaml                  # 项目基本信息(单文件)
├── modules/                      # 每个模块一个文件
│   ├── user.yaml                 # 用户管理模块
│   │   # 内容: id, name, description, pages[], workflows[], roles[]
│   ├── order.yaml
│   └── ...
├── pages/                        # 每个页面一个文件
│   ├── login.yaml                # 登录页
│   │   # 内容: id, app, route, routes, title, menu_path, module_id, roles, actions, fields, description
│   ├── user-list.yaml
│   ├── user-edit.yaml
│   └── ...
├── roles/                        # 每个角色一个文件
│   ├── admin.yaml
│   │   # 内容: id, name, description, permissions{can_access[], cannot_access[]}, typical_scenarios[]
│   ├── user.yaml
│   └── ...
├── workflows/                    # 每个业务流程一个文件
│   ├── create-user.yaml
│   │   # 内容: id, name, module_id, roles[], steps[], preconditions[], postconditions[]
│   ├── delete-user.yaml
│   └── ...
└── workflow-chains.yaml          # 业务流程链(全局,单文件)
    # 内容: workflow_chains[]
```

**project.yaml 必须包含 `schema_version: "1.0"` 字段**(与 pkb-schema.yaml 保持一致)。

**文件命名规则:**
- 模块文件:`modules/{module_id}.yaml`(如 `modules/user-management.yaml`)
- 页面文件:`pages/{page_id}.yaml`(如 `pages/user-list.yaml`)
- 角色文件:`roles/{role_id}.yaml`(如 `roles/admin.yaml`)
- 流程文件:`workflows/{workflow_id}.yaml`(如 `workflows/create-user.yaml`)
- 文件名全部小写,用 `-` 连接,不含特殊字符

**向后兼容:**
- 如 `knowledge/modules/` 目录不存在但 `knowledge/modules.yaml` 存在,按旧格式读取
- 优先使用分文件结构,单文件格式仅供向后兼容

**注意:此 Skill 不产出 database/ 和 apis/ 目录。** 它们分别由 `database-extractor` 和 `api-extractor` 独立产出。

## 严格约束

1. **禁止幻觉**:所有功能必须从源码中找到证据。无法确认的功能标注 `confidence: low`,不得自行推测。
2. **技术栈无关输出**:YAML 中不得出现 `@RestController` / `v-model` / `useState` 等技术术语。只保留业务语义(route, title, actions, fields)。页面操作如能从模板稳定识别，应同时记录 `selector`、`ui_effect` 和 `capture`，供截图计划重放；优先使用 `data-testid` / `data-action`，其次使用带业务文本限定的角色选择器。
3. **中文优先**:所有面向用户的字段(title, description, menu_path)使用中文。从代码中的中文文案、Swagger 注解、i18n 文件提取。
4. **不读不必要文件**:跳过 `node_modules/` / `target/` / `dist/` / `.git/` / `vendor/` / `*.lock`。
5. **职责边界**:不扫描数据库表结构、不扫描 API 请求响应细节。只记录页面、路由、角色、权限。

## 产出验证

完成后自检:
- [ ] project.yaml 的 tech_stack 是否完整填写
- [ ] modules/ 是否至少包含 1 个模块文件
- [ ] pages/ 是否至少包含 1 个页面文件
- [ ] roles/ 是否包含角色文件(如代码中存在权限控制)
- [ ] 所有 YAML 格式是否正确(无语法错误)
