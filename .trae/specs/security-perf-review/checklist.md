# Checklist

## Task 1: 凭据安全
- [x] screenshot-config.yaml 注释中明确"推荐 ${ENV_VAR},勿提交明文"
- [x] screenshot-config.yaml 示例 password 改为 `${APP_ADMIN_PASS}` / `${APP_USER_PASS}`
- [x] generate_screenshots.py 实现 `_resolve_env_var` 函数
- [x] `_resolve_env_var` 在环境变量缺失时报错退出(code=2),不静默继续
- [x] generate_screenshots.py login 链路对 username/password 调用 `_resolve_env_var`
- [x] webapp-testing SKILL.md 前置条件/错误处理中提及环境变量支持

## Task 2: 路径遍历防护
- [x] project-explorer SKILL.md 含"ID 合法性校验"步骤
- [x] database-extractor SKILL.md 含 table_name 校验
- [x] api-extractor SKILL.md 含 group_id 校验
- [x] pkb-schema.yaml 含 ID 命名规范段(`^[a-z0-9][a-z0-9-]{0,63}$`)

## Task 3: 截图脱敏
- [x] webapp-testing SKILL.md 含"脱敏注入"步骤和 CSS 示例
- [x] generate_screenshots.py 在 capture_screenshot 开头注入 MASK_CSS
- [x] MASK_CSS 至少覆盖 `input[type=password]`、`.sensitive`、`[data-mask]`
- [x] webapp-testing 严格约束含第 6 条"脱敏必须注入"
- [x] screenshot-reviewer 审核检查项含"敏感信息检查"

## Task 4: .gitignore 模板
- [x] templates/.gitignore.template 文件存在
- [x] 模板包含 knowledge/screenshot-config.yaml、.cache/、output/screenshots/、output/*.docx、output/*.pdf、knowledge/runtime/
- [x] doc-gen SKILL.md Step 0 含 .gitignore 初始化子步骤

## Task 5: PlantUML 外发警告
- [x] diagram-generator SKILL.md 含"安全提示"段落
- [x] generate.py 在使用公网服务器时输出一次 stderr 警告
- [x] diagram-generator SKILL.md 错误处理中提及本地 server 支持

## Task 6: SHA-256 缓存
- [x] doc-gen SKILL.md 中 check_cache 使用 hashlib.sha256
- [x] doc-gen SKILL.md 中 save_cache 使用 hashlib.sha256
- [x] 含迁移说明(旧 .cache/*.hash 需 --no-cache 重建)

## Task 7: PKB Schema 版本
- [x] pkb-schema.yaml 首行含 `schema_version: "1.0"`
- [x] project-explorer 要求 project.yaml 含 schema_version
- [x] manual-writer / database-spec-writer / api-doc-writer 输入段含版本检查说明

## Task 8: 原子写入
- [x] document-renderer SKILL.md 含"原子写入"子段和 Python 示例
- [x] generate_screenshots.py 的 yaml.dump 改为 tmp + os.replace

## Task 9: 分批扫描
- [x] project-explorer SKILL.md 含"阶段 0: 扫描规模评估"
- [x] 阈值默认 500 可配置
- [x] 每个策略段落含"分批读取"说明(每批 ≤50 文件)

## Task 10: --dry-run
- [x] doc-gen 参数表含 --dry-run 行
- [x] doc-gen Step 1.5 存在
- [x] dry-run 输出表格(Skill/阶段/缓存/depends_on)且不调用 Skill

## Task 11: 异常分类
- [x] generate_screenshots.py 含 RetryableError / FatalError 类定义
- [x] capture_screenshot 不再使用宽泛 except Exception
- [x] login 异常区分认证失败 vs 选择器超时

## Task 12: 日志规范
- [x] generate_screenshots.py 使用 logging 替代 print
- [x] generate.py 使用 logging 替代 print
- [x] Windows UTF-8 stdout 配置存在
- [x] webapp-testing / diagram-generator SKILL.md 含"日志规范"段

## Task 13: 契约段落位置
- [x] 11 个 Skill 的 `## Skill 契约` 均位于一级标题之后、其他二级标题之前

## 整体一致性
- [x] 所有修改仅限 `.trae/skills/**`、`templates/**`、新增模板文件
- [x] 未触碰任何业务源码
- [x] 所有新增 YAML 字段有注释说明
