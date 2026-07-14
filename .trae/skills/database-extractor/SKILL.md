---
name: "database-extractor"
description: "数据库结构提取器。专门扫描数据库相关文件(SQL建表脚本、ORM实体类、配置),提取表结构、字段、索引、外键关系,输出 database.yaml。当 doc-gen 需要 --type database/all 时,或 project-explorer 完成后调用。"
---

# Database Extractor —— 数据库结构提取器

## Skill 契约

```yaml
inputs:
  - 项目源码目录(扫描数据库相关文件)
  - knowledge/project.yaml (读取数据库类型/技术栈)
outputs:
  - knowledge/database/ (目录:_meta.yaml + 每张表一个文件)
depends_on:
  - project-explorer
cache_key:
  - 源码中的数据库相关文件(**/*.sql, **/*.java(entity), **/*.go(model))
stage: explorer
```

你的任务是专门扫描数据库相关文件,产出完整的 `database.yaml`。

**职责边界:**
- ✅ 负责:数据库表结构、字段、索引、外键、ER关系
- ❌ 不负责:页面、路由、角色 → 由 `project-explorer` 负责
- ❌ 不负责:API 接口 → 由 `api-extractor` 负责

## 执行流程

### Step 1: 确定数据库类型

读取 `knowledge/project.yaml` 中的 `database` 字段。如 project.yaml 不存在,自行读取配置文件:
- `application.yml` / `application.properties`(Spring Boot)
- `config.yaml` / `.env`(Go / Node)
- `settings.py`(Django)

记录:
```yaml
database:
  engine: "mysql"           # mysql / postgresql / mongodb / sqlite
  version: "8.0"
  charset: "utf8mb4"
```

### Step 2: 按来源扫描表结构

#### 来源 1: SQL 建表脚本(最准确,优先)

搜索 `*.sql` 文件(通常在 `db/` / `sql/` / `migration/` / `resources/` / `flyway/` / `liquibase/` 目录):

```
CREATE TABLE sys_user (
  id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  username VARCHAR(50) NOT NULL COMMENT '用户名',
  password VARCHAR(100) NOT NULL COMMENT '密码',
  role_id BIGINT COMMENT '角色ID',
  status TINYINT DEFAULT 1 COMMENT '状态:0禁用 1启用',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_username (username),
  KEY idx_role_id (role_id),
  CONSTRAINT fk_user_role FOREIGN KEY (role_id) REFERENCES sys_role(id)
) ENGINE=InnoDB COMMENT='用户表';
```

提取规则:
- `CREATE TABLE` → table.name, table.engine
- `COMMENT='xxx'` → table.business_name / field.description
- 列定义 → field.name, field.type, field.nullable, field.default
- `AUTO_INCREMENT` → field.auto_increment
- `PRIMARY KEY` → field.primary_key
- `UNIQUE KEY` → field.unique, field.index_name
- `KEY` / `INDEX` → field.index
- `FOREIGN KEY ... REFERENCES` → field.foreign_key + relation
- `COMMENT 'xx:0禁用 1启用'` → 解析 enum_values

#### 来源 2: ORM 实体类(Java)

扫描 `@Entity` / `@Table` 注解的类:

```
@Table(name = "sys_user")
@Entity
public class User {
    @Id
    @GeneratedValue(strategy = IDENTITY)
    private Long id;

    @Column(name = "username", nullable = false, length = 50, unique = true)
    private String username;

    @ManyToOne
    @JoinColumn(name = "role_id")
    private Role role;
}
```

提取规则:
- `@Table(name=)` → table.name
- `@Column` → field.type(从 Java 类型+length 推导), nullable, unique
- `@Id` → field.primary_key
- `@GeneratedValue` → field.auto_increment
- `@JoinColumn` → field.foreign_key + relation(N:1)
- `@OneToMany` / `@ManyToMany` → relation(1:N / N:M)

#### 来源 3: ORM 模型(Go)

扫描 gorm / sqlx 模型结构体:

```go
type User struct {
    ID       int64  `gorm:"primaryKey;autoIncrement" json:"id"`
    Username string `gorm:"type:varchar(50);not null;uniqueIndex" json:"username"`
    RoleID   int64  `gorm:"index" json:"role_id"`
}
```

提取规则:
- `gorm:"primaryKey"` → field.primary_key
- `gorm:"autoIncrement"` → field.auto_increment
- `gorm:"type:varchar(50)"` → field.type
- `gorm:"not null"` → field.nullable = false
- `gorm:"uniqueIndex"` → field.unique
- `gorm:"index"` → field.index

#### 来源 4: Django 模型(Python)

```python
class User(models.Model):
    username = models.CharField(max_length=50, unique=True, verbose_name='用户名')
    email = models.EmailField(verbose_name='邮箱')
    role = models.ForeignKey('Role', on_delete=models.CASCADE)
```

提取规则:
- `CharField(max_length=50)` → field.type = "VARCHAR(50)"
- `unique=True` → field.unique
- `verbose_name` → field.business_name
- `ForeignKey` → relation(N:1) + field.foreign_key

### Step 3: 关系推导

- 从外键定义直接提取表关系
- 无显式外键时,按 `xxx_id` 字段名命名约定推导:N:1 关系
- 汇总到 `er_relations`

### Step 3.5: ID 合法性校验(路径遍历防护)

在写入文件前,校验 table_name 匹配 `^[a-z0-9][a-z0-9-]{0,63}$`(允许下划线作为兼容:`^[a-z0-9_][a-z0-9_-]{0,63}$`)。校验失败的表跳过并记录 warning,不终止流程。

### Step 4: 输出(按表分文件)

将结果写入 `knowledge/database/` 目录,**每张表一个文件**:

```
knowledge/database/
├── _meta.yaml              # 数据库元信息
│   # 内容: engine, version, charset, er_relations[]
├── sys_user.yaml           # 用户表
│   # 内容: name, business_name, description, module_id, engine, charset,
│   #       fields[], indexes[], relations[]
├── sys_role.yaml           # 角色表
└── ...
```

**_meta.yaml 格式:**
```yaml
engine: "mysql"
version: "8.0"
charset: "utf8mb4"
er_relations:
  - from_table: "sys_user"
    to_table: "sys_role"
    type: "N:1"
    description: "用户归属角色"
```

**每张表的文件格式(如 sys_user.yaml):**
```yaml
name: "sys_user"
business_name: "用户表"
description: "存储系统用户信息"
module_id: "user-management"
fields:
  - name: "id"
    business_name: "主键"
    type: "BIGINT"
    primary_key: true
    auto_increment: true
  # ...
indexes: [...]
relations: [...]
```

**向后兼容:** 如 `knowledge/database/` 目录不存在但 `knowledge/database.yaml` 存在,按旧格式读取。

## 严格约束

1. **禁止幻觉**:所有表和字段必须从源码或 SQL 文件中找到证据。
2. **完整性**:发现的所有表都必须记录,不得遗漏。
3. **数据类型完整**:显示完整数据类型(如 `VARCHAR(50)` 而非仅 `VARCHAR`)。
4. **中文优先**:表名和字段的中文名从 `COMMENT` / `verbose_name` / `@ApiModelProperty` 提取。
5. **不扫描页面/API**:只关注数据库结构。

## 产出验证

- [ ] database.yaml 格式正确
- [ ] 每张表至少包含主键
- [ ] 外键关系已提取到 relations 和 er_relations
- [ ] 字段类型完整(含长度)
- [ ] 含枚举值的字段已解析 enum_values
