# 安全/性能/最佳实践专项审查 Spec

## Why
前几轮审查聚焦"功能正确性",本轮专项聚焦**安全、性能、最佳实践**。经系统性扫描 14 个 Skill + 5 个模板,发现 16 项问题:其中 3 项 P0(凭据明文/路径遍历/截图泄密)、6 项 P1、7 项 P2。多数问题在 Skill 体系下不会被自动触发,但一旦面向真实项目(尤其是含真实用户数据的项目)就会成为实际风险。

## What Changes
- **P0 安全**:screenshot-config.yaml 明文密码改为环境变量引用;page_id/table_name 路径遍历校验;截图敏感数据脱敏
- **P1 安全**:.gitignore 模板补充敏感路径;PlantUML 外发数据警告
- **P1 性能**:project-explorer 增加分批扫描策略;Writer 增加按需读取
- **P1 最佳实践**:MD5 → SHA-256;PKB schema 版本字段;文件写入原子化
- **P2 改进**:日志规范、契约段落位置统一、generate_screenshots.py 异常分类、--dry-run 模式

## Impact
- 受影响文件:
  - `templates/screenshot-config.yaml`(凭据引用方式)
  - `templates/generate_screenshots.py`(脱敏 + SHA-256 + 异常分类 + 原子写)
  - `templates/pkb-schema.yaml`(version 字段)
  - `.trae/skills/doc-gen/SKILL.md`(缓存算法 + dry-run + .gitignore 模板)
  - `.trae/skills/project-explorer/SKILL.md`(分批扫描)
  - `.trae/skills/database-extractor/SKILL.md`(路径校验)
  - `.trae/skills/api-extractor/SKILL.md`(路径校验)
  - `.trae/skills/webapp-testing/SKILL.md`(脱敏策略)
  - `.trae/skills/diagram-generator/SKILL.md`(外发警告 + 本地模式)
  - `.trae/skills/document-renderer/SKILL.md`(原子写入)
  - 新增 `templates/.gitignore.template`
- 不涉及业务源码
- **BREAKING**:screenshot-config.yaml 的 password 字段语义变更(支持 `${ENV_VAR}` 语法),旧文件需迁移

## ADDED Requirements

### Requirement: 凭据安全存储
screenshot-config.yaml SHALL 支持通过 `${ENV_VAR}` 语法从环境变量读取密码,明文 password 字段 SHALL 标注"不推荐提交到 git"。

#### Scenario: 环境变量引用
- **WHEN** screenshot-config.yaml 中 password 值为 `${APP_ADMIN_PASS}`
- **THEN** generate_screenshots.py 在运行时从 os.environ 读取实际密码

#### Scenario: 环境变量缺失
- **WHEN** 引用的环境变量不存在
- **THEN** 脚本报错并提示具体变量名,不使用空字符串静默继续

### Requirement: PKB 实体 ID 路径遍历防护
所有将 entity_id(page_id / table_name / module_id / role_id / workflow_id)用作文件路径的 Skill 和脚本,SHALL 在写入前校验该 ID 仅包含 `[a-z0-9-]` 字符。

#### Scenario: 恶意 ID
- **WHEN** project-explorer 推导出 page_id 为 `../etc/passwd`
- **THEN** 校验失败,该实体跳过并记录警告

### Requirement: 截图敏感数据脱敏
webapp-testing SHALL 在截图前注入 CSS 遮罩规则,隐藏/模糊常见敏感字段(密码框、手机号、邮箱、身份证、银行卡)。

#### Scenario: 密码字段不出现在截图中
- **WHEN** 截图页面含 `<input type="password">`
- **THEN** 截图中该字段表现为黑点或被遮罩

### Requirement: PlantUML 数据外发警告
diagram-generator SHALL 在使用公网 PlantUML 服务器前,警告用户"图表内容(含表名/API 路径)将发送至 plantuml.com",并支持本地 PlantUML 服务器配置。

#### Scenario: 首次使用公网服务器
- **WHEN** 用户未配置本地 PlantUML server
- **THEN** 输出一次警告,提示可通过 `--server http://localhost:8080` 使用本地实例

### Requirement: PKB Schema 版本字段
pkb-schema.yaml SHALL 在文件首行声明 `schema_version: "1.0"`,所有读取 PKB 的 Skill SHALL 检查版本兼容性。

#### Scenario: 版本不兼容
- **WHEN** PKB schema_version 为 "2.0" 但 Skill 只支持 "1.x"
- **THEN** 输出警告并提示升级

### Requirement: 文件写入原子化
所有写入 PKB/输出文件的脚本和 Skill 指令 SHALL 采用"写临时文件 → rename"模式,避免中途失败导致文件损坏。

#### Scenario: 写入失败不破坏原文件
- **WHEN** yaml.dump 过程中磁盘满
- **THEN** 原文件保持完整,临时文件被清理

### Requirement: project-explorer 分批扫描
project-explorer SHALL 在源码文件数超过阈值(默认 500)时,自动切换为分批扫描策略:按目录分批读取 + 增量合并。

#### Scenario: 大项目不爆 token
- **WHEN** 项目源码文件 > 500
- **THEN** project-explorer 按目录分批扫描,每批不超过 50 个文件

### Requirement: 缓存哈希算法升级为 SHA-256
doc-gen 中的 `check_cache` 和 `save_cache` 函数 SHALL 使用 `hashlib.sha256` 替代 `hashlib.md5`。

### Requirement: .gitignore 模板
项目 SHALL 提供 `templates/.gitignore.template`,包含 `knowledge/screenshot-config.yaml`、`.cache/`、`output/screenshots/` 等敏感路径。

### Requirement: --dry-run 模式
doc-gen SHALL 支持 `--dry-run` 参数,输出执行计划(哪些 Skill 会跑、哪些被缓存跳过)而不实际执行。

#### Scenario: dry-run 输出
- **WHEN** 用户传 `--dry-run`
- **THEN** 输出执行计划表格,不调用任何 Skill

### Requirement: generate_screenshots.py 异常分类
脚本 SHALL 区分可重试异常(超时、元素未找到)和致命异常(配置错误、依赖缺失),不再用宽泛的 `except Exception` 吞掉所有错误。

### Requirement: 日志规范统一
所有脚本 SHALL 使用 `logging` 模块替代 `print`,Windows 下使用 UTF-8 编码输出避免中文乱码。

## MODIFIED Requirements
无。

## REMOVED Requirements
无。
