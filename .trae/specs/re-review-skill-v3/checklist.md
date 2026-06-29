# Checklist

## Task 1: 脚本数据正确性
- [x] generate_screenshots.py 通用截图（无 roles）不因多角色循环重复（universal_plan 分离 + 按 id 去重）
- [x] generate_screenshots.py 支持 --retake 参数读取 retake-list.yaml（line 360, 383-388）
- [x] generate_screenshots.py --role 预过滤包含通用截图（line 378）
- [x] generate_screenshots.py config 读取用 .get() 防 KeyError（line 371-372）
- [x] 脚本通过 py_compile 语法校验

## Task 2: retake 格式
- [x] webapp-testing 伪代码 retake_ids 读取格式为 [r["id"] for r in ...get("retakes", [])]

## Task 3: 执行顺序
- [x] doc-gen Step 3 中 qa-reviewer 在 screenshot-planner 之前（line 120）
- [x] 完整执行链路包含 qa-reviewer 和 screenshot-planner（line 188）
- [x] 架构图阶段编号标注 =Step N 交叉引用（line 25-71）

## Task 4: 文件名/字段
- [x] manual-writer 图表嵌入从 manifest.yaml 读 file 字段（line 138-140）
- [x] database-spec-outline.md 4.1 ER 表无 {via_field}（table-level relations 的 via_field 是正确的，保留）
- [x] project-explorer 阶段 3 包含 workflow_chains 推导 + 自检（line 428）

## Task 5: 大纲语法
- [x] manual-outline.md 无 `- ` 无序列表语法（9 处已替换为（N）格式）

## Task 6: 输出清单与 PDF
- [x] doc-gen --type api 输出清单含时序图和 manifest.yaml（line 212-213）
- [x] document-renderer 有 PDF 方案（方案 D xelatex + 方案 E LibreOffice + HTML 降级）

## Task 7: 增强检查
- [x] qa-reviewer 有图表引用完整性检查项（检查 8, line 151）
- [x] screenshot-config.yaml 未消费字段有标注（default_mode/page_timeout/action_delay/expected_redirect）
- [x] pkb-schema.yaml screenshots 含 routes 字段（line 188）

## 整体一致性
- [x] 修改仅限 `.trae/skills/**` 与 `templates/**`，未触碰任何业务源码（git status 确认）
