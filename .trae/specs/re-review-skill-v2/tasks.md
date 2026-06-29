# Tasks

> 本轮修复针对二轮审查发现的 28 项问题，按 Skill 分组。仅修改 `.trae/skills/**` 与 `templates/**`。

- [ ] Task 1: 消除 Docker 逻辑矛盾（P0，跨 3 个 Skill）
  - [ ] SubTask 1.1: doc-gen 行 260 `--deep` 参数说明删除"Docker 启动"，改为"chrome-devtools-mcp，需用户先自行启动项目"
  - [ ] SubTask 1.2: webapp-testing 移除 Step 6 Docker 清理（行 179-186）、采集报告 Docker 状态字段（行 195）、错误处理 Docker 条目（行 216-218）、约束中的 Docker 引用（行 231）
  - [ ] SubTask 1.3: runtime-explorer 行 12 前置条件改为"目标项目已由用户自行启动"，删除"webapp-testing Step 2 已执行"引用

- [ ] Task 2: 修复 prerequisite_action 回归残留（P0）
  - [ ] SubTask 2.1: webapp-testing 行 99 `prerequisite_action` → `action`
  - [ ] SubTask 2.2: webapp-testing 行 101 `shot["prerequisite_action"]` → `shot["action"]`

- [ ] Task 3: 建立 runtime.yaml 消费契约（P1）
  - [ ] SubTask 3.1: manual-writer 输入章节增加 runtime.yaml（可选）
  - [ ] SubTask 3.2: manual-writer 生成规则增加：当 runtime.yaml 存在时，补充校验提示和操作反馈信息

- [ ] Task 4: 建立 retake-list.yaml 下游契约（P1）
  - [ ] SubTask 4.1: webapp-testing 输入章节增加 output/retake-list.yaml（可选）
  - [ ] SubTask 4.2: webapp-testing 执行流程增加补拍分支逻辑

- [ ] Task 5: writers 声明并使用 manifest.yaml（P1）
  - [ ] SubTask 5.1: manual-writer 输入增加 manifest.yaml，生成规则增加图表嵌入
  - [ ] SubTask 5.2: api-doc-writer 输入增加 manifest.yaml，生成规则增加时序图嵌入
  - [ ] SubTask 5.3: 统一 manifest.yaml 图片路径前缀（diagram-generator 的 file 字段与 writer 嵌入路径一致）
  - [ ] SubTask 5.4: manifest.yaml 每个图表条目增加 status 字段（rendered/failed）

- [ ] Task 6: 统一字段名与枚举值（P1/P2）
  - [ ] SubTask 6.1: runtime-explorer Step 3.3 `submit_button_text`/`cancel_button_text` → `submit_button`/`cancel_button`
  - [ ] SubTask 6.2: pkb-schema.yaml runtime status 增加 `timeout` 合法值
  - [ ] SubTask 6.3: runtime-explorer Step 5 注释列出全部合法 status 值

- [ ] Task 7: screenshot-planner 输出示例补全字段（P2）
  - [ ] SubTask 7.1: 输出示例增加 full_page / wait_after_action / roles 字段及说明

- [ ] Task 8: generate_screenshots.py 角色过滤（P2）
  - [ ] SubTask 8.1: 角色循环内增加按 roles 字段过滤

- [ ] Task 9: document-renderer 描述泛化（P2）
  - [ ] SubTask 9.1: 描述改为通用"将 Markdown 文档渲染为 DOCX/PDF/HTML"
  - [ ] SubTask 9.2: 输入章节说明接受任意 output/*.md

- [ ] Task 10: 文档编号与模板语法修复（P2）
  - [ ] SubTask 10.1: doc-gen database 输出物清单编号修复（第二个"3"→"4"）
  - [ ] SubTask 10.2: manual-outline.md 操作步骤改为 `步骤N：` 格式

- [ ] Task 11: 清理 webapp-testing 未定义变量与 dead code（P2）
  - [ ] SubTask 11.1: webapp-testing `dashboard_route` → `account["expected_redirect"]`
  - [ ] SubTask 11.2: generate_screenshots.py 删除 execute_action 无效 highlight 参数（行 135、282）
  - [ ] SubTask 11.3: generate_screenshots.py 删除 capture_screenshot 无效三元表达式（行 275-276）

- [ ] Task 12: 清理版本标签与步骤编号（P2）
  - [ ] SubTask 12.1: screenshot-planner 约束 #4 去掉"V1"标签
  - [ ] SubTask 12.2: doc-gen 删除空壳 Step 3.5

# Task Dependencies
- Task 1、2、3、4、5 相互独立，可并行
- Task 6、7、8、9、10、11、12 相互独立，可并行
- Task 5.3 依赖 Task 5.4（先加 status 字段再统一路径）
