# Tasks

- [x] Task 1: 修复 generate_screenshots.py 数据正确性（P1，3 项）
  - [x] SubTask 1.1: 多角色重复截图去重——通用截图（无 roles）只截一次，results 按 id 去重
  - [x] SubTask 1.2: 实现 retake-list.yaml 读取——增加 --retake 参数，格式为 {retakes: [{id,...}]}，读取后过滤 plan
  - [x] SubTask 1.3: 修复 --role 预过滤排除通用截图（改为包含无 roles 字段的截图）
  - [x] SubTask 1.4: config["screenshot"] 改 .get() 防 KeyError

- [x] Task 2: 修复 webapp-testing retake 格式不匹配（P1）
  - [x] SubTask 2.1: 伪代码 retake_ids 读取改为 `[r["id"] for r in yaml.safe_load(f)["retakes"]]`

- [x] Task 3: 修正 doc-gen 执行顺序（P1）
  - [x] SubTask 3.1: Step 3 内调换 qa-reviewer 和 screenshot-planner 顺序（先 qa 后 planner）
  - [x] SubTask 3.2: 完整执行链路补充 qa-reviewer 和 screenshot-planner
  - [x] SubTask 3.3: 统一架构图阶段编号与 Step 编号（添加 =Step N 标注）

- [x] Task 4: 修复文件名/字段不匹配（P1）
  - [x] SubTask 4.1: manual-writer 图表嵌入改为从 manifest.yaml 读 file 字段，不硬编码文件名
  - [x] SubTask 4.2: database-spec-outline.md 4.1 表删除 {via_field} 列（已确认 table-level relations 的 via_field 在另一处是正确的）
  - [x] SubTask 4.3: project-explorer 阶段 3 增加 workflow_chains 推导步骤 + 自检项

- [x] Task 5: 修复大纲模板列表语法（P1）
  - [x] SubTask 5.1: manual-outline.md 所有 `- ` 无序列表改为 `（N）` 或顿号段落（9 处已替换）

- [x] Task 6: 补全输出清单与 PDF 方案（P2）
  - [x] SubTask 6.1: doc-gen --type api 输出清单增加时序图和 manifest.yaml
  - [x] SubTask 6.2: document-renderer 增加 PDF 方案（方案 D xelatex + 方案 E LibreOffice + HTML 降级）

- [x] Task 7: 增强 qa-reviewer 和 screenshot-config（P2）
  - [x] SubTask 7.1: qa-reviewer 增加图表引用完整性检查项（检查 8）
  - [x] SubTask 7.2: screenshot-config.yaml 未消费字段标注"当前不支持"
  - [x] SubTask 7.3: pkb-schema.yaml screenshots 增加 routes 字段

# Task Dependencies
- Task 1、2、5、6、7 相互独立，可并行
- Task 3 独立
- Task 4 独立（4.2 依赖读取 pkb-schema 确认）
