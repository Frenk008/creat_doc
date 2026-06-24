# API 接口文档大纲模板

> 以下为 api-doc-writer 生成 Markdown API 接口文档的标准章节结构。
> 面向前后端开发人员和第三方集成方。

---

# 封面

- 软件名称：{project.name}
- 文档类型：API 接口文档
- 版本号：{project.version}
- 编制日期：{生成日期}

---

# 文档修订记录

| 版本 | 日期 | 修订内容 | 编制人 |
|------|------|----------|--------|
| v1.0 | {日期} | 初始版本 | 自动生成 |

---

# 目录

（由渲染器自动生成）

---

# 1. 概述

## 1.1 接口简介
{API 总体说明}

## 1.2 基础信息
- Base URL：{apis.base_url}
- 认证方式：{apis.auth_type}
- 请求格式：application/json
- 响应格式：application/json

## 1.3 通用响应结构

```json
{
  "code": 200,
  "message": "success",
  "data": {}
}
```

## 1.4 状态码说明

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | 未认证 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

## 1.5 认证说明
{根据 auth_type 说明如何传递 Token/Key}

---

# 2. 接口分组总览

| 序号 | 分组 | 接口数量 | 说明 |
|------|------|----------|------|
| 1 | {group.name} | {N} | {group.description} |

---

# 3. 接口详细说明

> 按 apis.groups 顺序,逐组逐接口说明。

## 3.{分组序号} {group.name}

### 3.{分组序号}.{接口序号} {endpoint.summary}

**基本信息**
- 接口名称：{endpoint.summary}
- 请求方法：{endpoint.method}
- 接口路径：{endpoint.path}
- 是否需要认证：{是/否}
- 允许角色：{endpoint.roles}
- 状态：{endpoint.deprecated ? "已废弃" : "正常"}

**接口说明：**
{endpoint.description}

**请求参数**

*请求头：*

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| {header.name} | {header.type} | {是/否} | {header.description} |

*路径/查询参数：*

| 参数名 | 位置 | 类型 | 必填 | 说明 | 示例 |
|--------|------|------|------|------|------|
| {param.name} | {param.in} | {param.type} | {是/否} | {param.description} | {param.example} |

*请求体：*

Content-Type: {body.content_type}

| 参数名 | 类型 | 必填 | 说明 | 示例 |
|--------|------|------|------|------|------|
| {field.name} | {field.type} | {是/否} | {field.description} | {field.example} |

请求示例：
```json
{根据 fields 生成请求示例 JSON}
```

**响应结果**

*成功响应（{code}）：*

| 参数名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| {field.name} | {field.type} | {field.description} | {field.example} |

响应示例：
```json
{根据 fields 生成响应示例 JSON}
```

*错误响应：*

| 状态码 | 说明 | message |
|--------|------|---------|
| {error.code} | {error.description} | {error.message} |

---

# 4. 附录

## 4.1 数据模型
{引用 database.yaml 中的相关表结构}

## 4.2 变更记录
| 版本 | 变更接口 | 变更说明 |
|------|----------|----------|
