---
name: "api-doc-writer"
description: "API接口文档生成器。读取 PKB 中的 apis.yaml,按照标准大纲模板生成面向开发人员的 API 接口文档 Markdown。当需要生成API文档,或 doc-gen 编排器以 api 模式调用时使用。"
---

# API Doc Writer —— API 接口文档生成器

## Skill 契约

```yaml
inputs:
  - knowledge/apis/
  - knowledge/project.yaml
  - knowledge/roles/
outputs:
  - output/api-doc.md
depends_on:
  - api-extractor
  - diagram-generator (需要时序图)
cache_key:
  - knowledge/apis/**/*.yaml
  - knowledge/roles/**/*.yaml
stage: writer
```

你的任务是读取 PKB(`knowledge/apis/`)并生成一份完整的 API 接口文档。

## 输入

- `knowledge/apis/` —— API PKB(分文件:`_meta.yaml` + 每个分组一个 yaml)
  - 向后兼容:如目录不存在,读取 `knowledge/apis.yaml`
- `knowledge/project.yaml` —— 项目基本信息
- `knowledge/roles/` —— 角色信息(分文件,用于接口权限说明)
  - 向后兼容:如目录不存在,读取 `knowledge/roles.yaml`
- 大纲模板:`templates/api-doc-outline.md`

> **PKB 版本检查:** 读取 `knowledge/project.yaml` 时,如 `schema_version` 不在支持范围(`["1.0"]`),输出警告并提示用户升级 Skill。

## 输出

- `output/api-doc.md` —— API 接口文档

## 生成规则

### 1. 按大纲逐章生成

遵循 `templates/api-doc-outline.md` 的章节结构:
- 封面 → 修订记录 → 目录 → 1.概述 → 2.分组总览 → 3.接口详述 → 4.附录

### 2. 分批生成

```
第1批: 封面 + 第1章(概述) + 第2章(分组总览)
第2批: 第3章(接口详细说明) —— 按分组逐组生成,每组一批
第3批: 第4章(附录)
```

### 3. 接口生成模板

对 `apis.endpoints` 中的每个接口,按分组生成:

```markdown
### 3.{组号}.{接口号} {summary}

**基本信息**

| 项目 | 说明 |
|------|------|
| 请求方法 | `POST` |
| 接口路径 | `/api/v1/users` |
| 接口分组 | 用户管理 |
| 是否认证 | 是 |
| 允许角色 | admin |
| 当前状态 | 正常 / ⚠️ 已废弃 |

**接口说明：**
创建一个新的用户账号。

**请求头**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| Authorization | string | 是 | Bearer {token} |
| Content-Type | string | 是 | application/json |

**请求参数**

*查询参数：*

| 参数名 | 类型 | 必填 | 说明 | 示例 |
|--------|------|------|------|------|
| role | string | 否 | 按角色筛选 | admin |

*请求体（Content-Type: application/json）：*

| 参数名 | 类型 | 必填 | 说明 | 示例 |
|--------|------|------|------|------|
| username | string | 是 | 用户名,3-20字符 | "zhangsan" |
| email | string | 是 | 邮箱地址 | "zhangsan@example.com" |
| role_id | number | 是 | 角色ID | 1 |

**请求示例：**

```json
{
  "username": "zhangsan",
  "email": "zhangsan@example.com",
  "role_id": 1
}
```

**成功响应（200）：**

| 参数名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| code | number | 状态码 | 200 |
| message | string | 提示信息 | "success" |
| data.id | number | 用户ID | 1001 |
| data.username | string | 用户名 | "zhangsan" |

**响应示例：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": 1001,
    "username": "zhangsan",
    "email": "zhangsan@example.com",
    "role_id": 1,
    "created_at": "2026-06-22T10:00:00Z"
  }
}
```

**错误响应：**

| 状态码 | 说明 | message |
|--------|------|---------|
| 400 | 参数错误 | "用户名已存在" |
| 401 | 未认证 | "token无效" |
| 403 | 无权限 | "需要管理员权限" |
```

### 4. 请求/响应示例生成规则

**不要只列字段表,必须生成可读的 JSON 示例:**

从 `request.body.fields` 推导示例:
```json
{
  "username": "zhangsan",      // 用 example 值
  "email": "zhangsan@example.com",
  "role_id": 1
}
```

从 `response.success.body` 推导示例:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": 1001,
    "username": "zhangsan"
  }
}
```

**规则:**
- 有 `example` 字段时直接使用
- 无 `example` 时根据 `type` 生成合理示例值:
  - `string` → "示例文本" 或根据字段名推导
  - `number` / `integer` → 1 或 1001
  - `boolean` → true
  - `array` → [示例值]
  - `object` → 嵌套对象

### 5. 分组生成

按 `apis.groups` 分组,每组生成一个二级标题:

```markdown
## 3.1 用户管理

> 共 6 个接口

### 3.1.1 获取用户列表
### 3.1.2 创建用户
### 3.1.3 获取用户详情
### 3.1.4 更新用户信息
### 3.1.5 删除用户
### 3.1.6 修改用户状态
```

### 6. 认证说明生成

根据 `apis.auth_type` 在第1.5节说明:

| auth_type | 说明 |
|-----------|------|
| bearer | 在请求头 `Authorization: Bearer {token}` 中携带 JWT Token |
| basic | 使用 HTTP Basic 认证 |
| apikey | 在请求头 `X-API-Key: {key}` 中携带 API 密钥 |
| none | 无需认证 |

### 7. 废弃接口标记

`deprecated: true` 的接口在标题后加 ⚠️ 标记,并在说明中注明:

```markdown
### 3.1.5 删除用户 ⚠️

> **注意：此接口已废弃,请使用 3.1.6 批量删除接口替代。**
```

## 严格约束

1. **禁止幻觉**:所有接口必须来自 `apis.yaml`,不得自行添加。
2. **保留技术术语**:本文档面向开发人员,允许使用 HTTP、JSON、Token 等术语。
3. **完整性**:apis.yaml 中的每个 endpoint 都必须出现在文档中。
4. **示例必填**:每个接口必须同时包含参数表和 JSON 示例,不能只有表没有示例。
5. **方法标识**:HTTP 方法用大写(GET/POST/PUT/DELETE/PATCH)。

## 产出验证

- [ ] apis.yaml 中的每个 endpoint 是否都有对应章节
- [ ] 每个接口是否都有请求参数表
- [ ] 每个接口是否都有 JSON 请求示例
- [ ] 每个接口是否都有 JSON 响应示例
- [ ] 每个接口是否都标注了认证要求和角色权限
- [ ] 废弃接口是否已标记
- [ ] 接口是否按分组正确归类
