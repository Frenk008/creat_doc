---
name: "api-extractor"
description: "API接口提取器。专门扫描接口定义(Spring注解、Go路由、Swagger/OpenAPI文件),提取端点、请求/响应结构、认证要求,输出 apis.yaml。当 doc-gen 需要 --type api/all 时,或 project-explorer 完成后调用。"
---

# API Extractor —— API 接口提取器

## Skill 契约

```yaml
inputs:
  - 项目源码目录(扫描接口相关文件)
  - knowledge/project.yaml (读取后端框架)
  - knowledge/roles/ (读取角色定义,辅助接口权限映射)
outputs:
  - knowledge/apis/ (目录:_meta.yaml + 每个分组一个文件)
depends_on:
  - project-explorer
cache_key:
  - 源码中的接口相关文件(**/*Controller.java, **/*handler.go, **/swagger.json)
stage: explorer
```

你的任务是专门扫描接口定义,产出完整的 `apis.yaml`。

**职责边界:**
- ✅ 负责:API 端点、HTTP 方法、路径、请求/响应结构、认证要求、错误码
- ❌ 不负责:页面、路由、角色 → 由 `project-explorer` 负责
- ❌ 不负责:数据库表结构 → 由 `database-extractor` 负责

## 执行流程

### Step 1: 确定扫描策略

读取 `knowledge/project.yaml` 确定后端框架:
- Java Spring Boot → 来源 1
- Go (Gin/Echo/Kratos) → 来源 2
- 已有 Swagger 文件 → 来源 3(优先,直接转换)
- 无法确定 → 来源 4(通用兜底)

### Step 2: 按来源扫描

#### 来源 1: Spring Boot 注解(Java)

```
@RestController
@RequestMapping("/api/v1/users")
@Api(tags = "用户管理")
public class UserController {

    @PostMapping("/create")
    @ApiOperation("创建用户")
    @PreAuthorize("hasRole('ADMIN')")
    public Result<UserVO> create(@RequestBody @Valid CreateUserDTO dto) {
        ...
    }
}
```

提取规则:
- 类级 `@RequestMapping` → apis.base_url + group
- `@Api(tags=)` → group.name
- 方法级 `@PostMapping` / `@GetMapping` → endpoint.method, endpoint.path
- `@ApiOperation` → endpoint.summary
- `@PreAuthorize` → endpoint.roles
- `@RequestBody` 参数 DTO → 解析其字段为 request.body.fields
- `@PathVariable` → request.params (in: path)
- `@RequestParam` → request.params (in: query)
- 返回类型 → response.success.body
- `@Valid` 注解 → 推导校验规则作为字段 description

**DTO/VO 解析:**
扫描请求和响应的数据传输对象:

```java
public class CreateUserDTO {
    @NotBlank(message = "用户名不能为空")
    @Size(min = 3, max = 20)
    private String username;

    @Email(message = "邮箱格式不正确")
    private String email;
}
```
→ request.body.fields 包含 username(required, description="用户名不能为空,3-20字符"), email(required)

#### 来源 2: Go 框架路由(Gin / Echo / Kratos)

```go
// Gin
r := gin.Default()
api := r.Group("/api/v1")
userGroup := api.Group("/users")
{
    userGroup.GET("", listUsers)
    userGroup.POST("/create", createUser)
}
```
→ endpoints: GET /api/v1/users, POST /api/v1/users/create

Kratos proto 文件:
```proto
service UserService {
  rpc CreateUser (CreateUserRequest) returns (CreateUserReply) {
    option (google.api.http) = {
      post: "/api/v1/users"
      body: "*"
    };
  }
}
```
→ endpoint: POST /api/v1/users, 请求/响应从 message 定义提取

#### 来源 3: Swagger / OpenAPI 文件(最优来源)

读取 `swagger.json` / `openapi.yaml`,直接映射到 apis.yaml(这是最完整的来源):

```
paths:
  /api/v1/users:
    post:
      summary: 创建用户
      tags: [用户管理]
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CreateUserRequest'
      responses:
        '200':
          description: 成功
```

**如项目已有 Swagger 文件,直接转换,无需扫描代码。** 这是最省时且最准确的来源。

#### 来源 4: 通用兜底

- 搜索所有包含 HTTP 方法关键字的代码:`GET` / `POST` / `PUT` / `DELETE` + 路径字符串
- 搜索装饰器/注解:`@GetMapping` / `router.GET` / `@GET`
- 标注置信度

### Step 3: 权限映射

从 `knowledge/roles/*.yaml` 和 API 的角色注解,推导每个接口的 `roles` 和 `auth_required`；目录不存在时才回退旧版 `knowledge/roles.yaml`。

### Step 3.5: ID 合法性校验(路径遍历防护)

在写入文件前,校验 group_id 匹配 `^[a-z0-9][a-z0-9-]{0,63}$`。校验失败的分组跳过并记录 warning,不终止流程。

### Step 4: 输出(按分组分文件)

将结果写入 `knowledge/apis/` 目录,**每个接口分组一个文件**:

```
knowledge/apis/
├── _meta.yaml              # API 元信息
│   # 内容: base_url, auth_type, groups[]
├── user-api.yaml           # 用户管理接口组
│   # 内容: group_id, endpoints[]
├── order-api.yaml          # 订单管理接口组
└── ...
```

**_meta.yaml 格式:**
```yaml
base_url: "/api/v1"
auth_type: "bearer"
groups:
  - id: "user-management"
    name: "用户管理"
  - id: "order-management"
    name: "订单管理"
```

**每个分组的文件格式(如 user-api.yaml):**
```yaml
group_id: "user-management"
endpoints:
  - id: "create-user"
    method: "POST"
    path: "/api/v1/users"
    summary: "创建用户"
    # ... 完整的 request/response 结构
```

**向后兼容:** 如 `knowledge/apis/` 目录不存在但 `knowledge/apis.yaml` 存在,按旧格式读取。

## 严格约束

1. **禁止幻觉**:所有接口必须从源码或 Swagger 文件中找到证据。
2. **完整性**:发现的所有端点都必须记录,不得遗漏。
3. **请求/响应结构**:每个接口尽量提取完整的字段列表和示例。无法从代码提取的字段标注 `（待确认）`。
4. **HTTP 方法大写**:GET / POST / PUT / DELETE / PATCH。
5. **废弃接口标记**:`@Deprecated` 或 OpenAPI `deprecated: true` 的接口标记 `deprecated: true`。
6. **不扫描页面/数据库**:只关注接口定义。

## 产出验证

- [ ] apis.yaml 格式正确
- [ ] 每个接口都有 method + path + summary
- [ ] 请求参数(headers/params/body)已提取
- [ ] 响应结构(success/errors)已提取
- [ ] 认证要求和角色权限已标注
- [ ] 接口已按 group 正确分组
