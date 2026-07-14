# Tasks

> 本任务列表按"P0 安全 → P1 → P2"顺序排列。修复仅针对 `.trae/skills/**`、`templates/**` 和新增模板文件,不触碰业务源码。

# Task Dependencies
- Task 1、2、3 为 P0,独立可并行
- Task 4-9 为 P1,Task 4/5/6 依赖 Task 1 的凭据迁移完成
- Task 10-13 为 P2,无依赖

---

- [x] Task 1: 凭据安全存储改造(P0)
  - [x] SubTask 1.1: 在 `templates/screenshot-config.yaml` 顶部增加注释:`password 字段推荐使用 ${ENV_VAR} 引用环境变量,不要提交明文到 git`
  - [x] SubTask 1.2: 在 `templates/screenshot-config.yaml` 的 admin/user 示例中将 password 改为 `${APP_ADMIN_PASS}` / `${APP_USER_PASS}` 形式
  - [x] SubTask 1.3: 在 `templates/generate_screenshots.py` 中增加 `_resolve_env_var(value)` 函数:若 value 匹配 `^\$\{(\w+)\}$`,从 os.environ 读取;变量缺失时报错并退出(code=2),不静默使用空值
  - [x] SubTask 1.4: 在 generate_screenshots.py 的 login 调用链中,对 username/password 调用 `_resolve_env_var`
  - [x] SubTask 1.5: 在 webapp-testing SKILL.md 的"前置条件"和"错误处理"中补充:密码支持环境变量引用;缺失时报具体变量名

- [x] Task 2: PKB 实体 ID 路径遍历防护(P0)
  - [x] SubTask 2.1: 在 project-explorer SKILL.md 的"阶段 4 输出 PKB"前增加"ID 合法性校验"步骤:所有 entity_id 必须匹配 `^[a-z0-9][a-z0-9-]{0,63}$`,否则跳过并记录 warning
  - [x] SubTask 2.2: 在 database-extractor SKILL.md 的"Step 4 输出"前增加同样的 ID 校验(table_name 走同一规则)
  - [x] SubTask 2.3: 在 api-extractor SKILL.md 的"Step 4 输出"前增加 group_id 校验
  - [x] SubTask 2.4: 在 pkb-schema.yaml 的开头注释中增加"ID 命名规范"段:仅允许 `[a-z0-9-]`,长度 1-64

- [x] Task 3: 截图敏感数据脱敏(P0)
  - [x] SubTask 3.1: 在 webapp-testing SKILL.md 的"Step 3 生成 Playwright 脚本"和"严格约束"中新增"脱敏注入"步骤:截图前执行 `page.add_style_tag(content=...)` 注入 CSS,将 `input[type=password]`、`.sensitive`、`[data-mask]` 设置为 `color: transparent; background: #ccc;`
  - [x] SubTask 3.2: 在 generate_screenshots.py 的 capture_screenshot 函数开头增加 `page.add_style_tag(content=MASK_CSS)`,其中 MASK_CSS 常量在文件顶部定义
  - [x] SubTask 3.3: 在 webapp-testing SKILL.md 的"严格约束"中新增第 6 条:"截图前必须注入脱敏 CSS"
  - [x] SubTask 3.4: 在 screenshot-reviewer SKILL.md 的审核检查项表格中新增"敏感信息检查"行:检查截图中是否出现明文密码/身份证/银行卡模式

- [x] Task 4: .gitignore 模板(P1)
  - [x] SubTask 4.1: 新建 `templates/.gitignore.template`,内容包含:`knowledge/screenshot-config.yaml`、`.cache/`、`output/screenshots/`、`output/*.docx`、`output/*.pdf`、`knowledge/runtime/`
  - [x] SubTask 4.2: 在 doc-gen SKILL.md 的"Step 0 初始化"中新增子步骤:如项目根目录无 `.gitignore`,复制 `templates/.gitignore.template` 到项目根目录;如已存在,提示用户手动补充

- [x] Task 5: PlantUML 数据外发警告(P1)
  - [x] SubTask 5.1: 在 diagram-generator SKILL.md 的"模式 A: PKB 驱动"开头新增"安全提示"段落:公网 PlantUML 服务器会接收完整图表内容(含表名、字段、API 路径),敏感项目应使用 `--server http://localhost:8080`
  - [x] SubTask 5.2: 在 generate.py 的 main() 函数中,当 servers 为默认公网列表时,首次执行输出一次 stderr 警告
  - [x] SubTask 5.3: 在 diagram-generator SKILL.md 的"错误处理"中补充:支持本地 PlantUML server(用户通过 `--server` 参数或 PKB 配置指定)

- [x] Task 6: 缓存哈希算法升级为 SHA-256(P1)
  - [x] SubTask 6.1: 在 doc-gen SKILL.md 的 `check_cache` 和 `save_cache` Python 代码中,将 `hashlib.md5` 全部替换为 `hashlib.sha256`
  - [x] SubTask 6.2: 在 doc-gen SKILL.md 中新增迁移说明:旧 `.cache/*.hash` 文件需删除后重建(`--no-cache` 一次即可)

- [x] Task 7: PKB Schema 版本字段(P1)
  - [x] SubTask 7.1: 在 `templates/pkb-schema.yaml` 的首行(目录结构注释之前)增加 `schema_version: "1.0"` 字段及注释
  - [x] SubTask 7.2: 在 project-explorer SKILL.md 的"阶段 4 输出"中,要求 project.yaml 必须包含 `schema_version: "1.0"`
  - [x] SubTask 7.3: 在 manual-writer / database-spec-writer / api-doc-writer 的"## 输入"段落中,新增版本检查说明:读取 PKB 时如 schema_version 不在支持范围(["1.0"]),输出警告

- [x] Task 8: 文件写入原子化(P1)
  - [x] SubTask 8.1: 在 document-renderer SKILL.md 的"文件编码与合并规范"段落中,新增"原子写入"子段:所有写入操作使用 `临时文件 + os.replace` 模式,给出 Python 示例代码
  - [x] SubTask 8.2: 在 generate_screenshots.py 的 yaml.dump 段落改为:先写入 `args.plan + ".tmp"`,再 `os.replace(tmp, args.plan)`

- [x] Task 9: project-explorer 分批扫描(P1)
  - [x] SubTask 9.1: 在 project-explorer SKILL.md 的"阶段 1 技术栈探测"之前新增"阶段 0: 扫描规模评估"步骤:统计源码文件数,如超过 500(可配置),切换为分批模式
  - [x] SubTask 9.2: 在"阶段 2 按技术栈选策略扫描"中,为每个策略增加"分批读取"说明:按目录分组,每批不超过 50 个文件,合并结果

- [x] Task 10: --dry-run 模式(P2)
  - [x] SubTask 10.1: 在 doc-gen SKILL.md 的参数表中新增 `--dry-run` 行
  - [x] SubTask 10.2: 在"Step 1 构建执行计划"后新增"Step 1.5: dry-run 输出":如传入 --dry-run,输出执行计划表格(Skill / 阶段 / 缓存命中 / depends_on)后直接退出,不调用任何 Skill

- [x] Task 11: generate_screenshots.py 异常分类(P2)
  - [x] SubTask 11.1: 在 generate_screenshots.py 顶部新增异常类:`RetryableError`(超时/元素未找到/网络)和 `FatalError`(配置错误/依赖缺失)
  - [x] SubTask 11.2: 在 capture_screenshot 中将宽泛 `except Exception` 改为 `except RetryableError`(标记 failed 可补拍)和 `except FatalError`(标记 failed + 退出)
  - [x] SubTask 11.3: login 函数中的异常区分:认证失败为 FatalError,选择器超时为 RetryableError

- [x] Task 12: 日志规范统一(P2)
  - [x] SubTask 12.1: 在 generate_screenshots.py 和 generate.py 中,将 `print(...)` 替换为 `logging.info/warning/error`,在 main() 开头配置 `logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")`,Windows 下增加 `sys.stdout.reconfigure(encoding="utf-8")` 防中文乱码
  - [x] SubTask 12.2: 在 webapp-testing / diagram-generator SKILL.md 中新增"日志规范"段:要求生成脚本统一使用 logging 模块

- [x] Task 13: 契约段落位置统一(P2)
  - [x] SubTask 13.1: 检查 11 个含契约的 Skill 文件,确保 `## Skill 契约` 段落位于一级标题(`# 标题`)之后、其他二级标题之前;如有偏差统一调整
