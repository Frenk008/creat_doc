# 数据库说明书大纲模板

> 以下为 database-spec-writer 生成 Markdown 数据库说明书的标准章节结构。
> 面向开发人员和数据库设计人员,可包含技术细节。

---

# 封面

- 软件名称：{project.name}
- 文档类型：数据库设计说明书
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

## 1.1 数据库简介
- 数据库引擎：{database.engine}
- 版本：{database.version}
- 字符集：{database.charset}

## 1.2 设计原则
{数据库设计的基本原则,如命名规范、主键策略等}

## 1.3 命名规范
- 表名规范：{如 sys_ 前缀}
- 字段名规范：{如全小写下划线}
- 索引名规范：{如 idx_ 前缀}

---

# 2. 数据表清单

| 序号 | 表名 | 中文名 | 所属模块 | 说明 |
|------|------|--------|----------|------|
| 1 | {table.name} | {table.business_name} | {table.module_id} | {table.description} |

---

# 3. 表结构详细设计

> 对 database.tables 中的每张表,生成一节。

## 3.{N} {table.business_name}（{table.name}）

### 基本信息
- 表名：{table.name}
- 中文名：{table.business_name}
- 所属模块：{table.module_id}
- 说明：{table.description}

### 字段定义

| 序号 | 字段名 | 中文名 | 数据类型 | 允许空 | 默认值 | 主键 | 自增 | 唯一 | 说明 |
|------|--------|--------|----------|--------|--------|------|------|------|------|
| 1 | {field.name} | {field.business_name} | {field.type} | {是/否} | {field.default} | {是/否} | {是/否} | {是/否} | {field.description} |

### 约束与索引

**主键：** {primary_key 字段}

**唯一约束：**
| 约束名 | 字段 |
|--------|------|
| {index.name} | {index.fields} |

**外键关系：**
| 字段 | 引用表 | 引用字段 | 关系类型 |
|------|--------|----------|----------|
| {field.name} | {relation.target_table} | {relation.via_field} | {relation.type} |

**索引：**
| 索引名 | 字段 | 类型 | 说明 |
|--------|------|------|------|
| {index.name} | {index.fields} | {index.type} | {index.description} |

---

# 4. 表关系说明

## 4.1 ER 关系总览

> 基于 er_relations 生成表间关系说明

| 序号 | 主表 | 从表 | 关系类型 | 关联字段 | 说明 |
|------|------|------|----------|----------|------|
| 1 | {rel.from_table} | {rel.to_table} | {rel.type} | {via_field} | {rel.description} |

## 4.2 关系图说明

{用文字描述核心表之间的关系链路,供后续绘制 ER 图参考}

---

# 5. 数据字典

> 对含枚举值的字段,生成枚举值说明

## 5.{N} {table.business_name} - {field.name}

| 枚举值 | 含义 | 说明 |
|--------|------|------|
| {value} | {meaning} | {description} |

---

# 6. 附录

## 6.1 术语表
| 术语 | 说明 |
|------|------|

## 6.2 SQL 建表脚本
（可附完整 DDL 脚本,或标注"见项目源码 db/ 目录"）
