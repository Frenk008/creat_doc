---
name: "database-spec-writer"
description: "数据库设计说明书生成器。读取 PKB 中的 database.yaml,按照标准大纲模板生成面向开发人员的数据库设计说明书 Markdown。当需要生成数据库说明书,或 doc-gen 编排器以 database 模式调用时使用。"
---

# Database Spec Writer —— 数据库设计说明书生成器

你的任务是读取 PKB(`knowledge/database.yaml`)并生成一份完整的数据库设计说明书。

## 输入

- `knowledge/database.yaml` —— 数据库表结构、字段、索引、关系
- `knowledge/project.yaml` —— 项目基本信息
- `output/diagrams/manifest.yaml` —— 图表清单(含 ER 图路径)
- 大纲模板:`templates/database-spec-outline.md`

## 输出

- `output/database-spec.md` —— 数据库设计说明书

## 图表嵌入

如果 `output/diagrams/manifest.yaml` 存在且包含 ER 图,在第4章"表关系说明"中嵌入:

```markdown
## 4.1 ER 关系总览

![ER实体关系图](diagrams/er-diagram.png)

> 图：{项目名} 数据库实体关系图
```

如果 manifest.yaml 不存在或渲染失败,则用文字描述关系链路替代(见大纲模板 4.2 节)。

## 生成规则

### 1. 按大纲逐章生成

遵循 `templates/database-spec-outline.md` 的章节结构:
- 封面 → 修订记录 → 目录 → 1.概述 → 2.表清单 → 3.表结构详设 → 4.表关系 → 5.数据字典 → 6.附录

### 2. 分批生成(避免 token 溢出)

```
第1批: 封面 + 第1章(概述) + 第2章(表清单)
第2批: 第3章(表结构详细设计) —— 按表逐张生成,每批3-5张表
第3批: 第4章(表关系) + 第5章(数据字典) + 第6章(附录)
```

### 3. 表结构生成模板

对 `database.tables` 中的每张表,在"第3章"生成一节:

```markdown
## 3.{序号} {business_name}（{name}）

### 基本信息
- 表名：`{name}`
- 中文名：{business_name}
- 所属模块：{module_id}
- 说明：{description}

### 字段定义

| 序号 | 字段名 | 中文名 | 数据类型 | 允许空 | 默认值 | 主键 | 唯一 | 说明 |
|------|--------|--------|----------|--------|--------|------|------|------|
| 1 | `id` | 主键 | BIGINT | 否 | - | 是 | - | 自增主键 |
| 2 | `username` | 用户名 | VARCHAR(50) | 否 | - | - | 是 | 登录账号 |
```

**字段生成规则:**
- 允许空:nullable 为 true 显示"是",false 显示"否"
- 主键/唯一:对应字段为 true 时显示"是",否则显示"-"
- 默认值为空则显示"-"
- 中文名从 `business_name` 取,无则显示字段名

### 4. 索引与约束生成

```markdown
### 约束与索引

**主键：** `id`

**唯一约束：**

| 约束名 | 字段 |
|--------|------|
| uk_username | username |

**索引：**

| 索引名 | 字段 | 类型 | 说明 |
|--------|------|------|------|
| idx_created_at | created_at | normal | 创建时间索引 |
```

### 5. 表关系生成

对 `relations` 和 `er_relations` 生成关系说明:

```markdown
### 外键关系

| 字段 | 引用表.字段 | 关系类型 | 说明 |
|------|-------------|----------|------|
| role_id | sys_role.id | N:1 | 关联角色表 |
```

在第4章汇总全局 ER 关系,并**用文字描述关系链路**(供后续绘制 ER 图参考):

```markdown
## 4.2 关系图说明

核心关系链路：
- sys_user → sys_role (N:1)：用户归属角色
- sys_user → sys_department (N:1)：用户归属部门
- sys_order → sys_user (N:1)：订单归属用户
- sys_order_item → sys_order (N:1)：订单项归属订单
```

### 6. 数据字典生成

扫描所有字段的 `enum_values`,对含枚举值的字段生成说明:

```markdown
## 5.1 用户表 - status

| 枚举值 | 含义 |
|--------|------|
| 0 | 禁用 |
| 1 | 启用 |
| 2 | 待审核 |
```

### 7. 命名规范推断

从表名和字段名推断命名规范,在第1.3节说明:

| 推断依据 | 规范 |
|----------|------|
| 表名格式 | 如 sys_user → "系统表统一使用 sys_ 前缀" |
| 字段格式 | 如 create_time → "全小写+下划线" |
| 主键命名 | 如 id → "统一使用 id 作为主键名" |
| 外键命名 | 如 role_id → "外键以 _id 结尾" |

## 严格约束

1. **禁止幻觉**:所有表和字段必须来自 `database.yaml`,不得自行添加。
2. **保留技术术语**:本文档面向开发人员,允许使用 SQL、索引、外键等技术术语。
3. **完整性**:database.yaml 中的每张表都必须在文档中出现,不得遗漏。
4. **数据类型完整**:显示完整数据类型(如 `VARCHAR(50)` 而非仅 `VARCHAR`)。

## 产出验证

- [ ] database.yaml 中的每张表是否都有对应章节
- [ ] 每张表的字段是否完整列出
- [ ] 主键、外键、索引是否正确标识
- [ ] 表间关系是否在第4章汇总
- [ ] 含枚举值的字段是否在数据字典中说明
