# Checklist

## Task 1: Docker 逻辑矛盾
- [x] doc-gen `--deep` 参数说明不再出现"Docker 启动"
- [x] webapp-testing 不再出现 Docker 清理/Docker 错误处理/Docker 约束（grep 确认无残留）
- [x] runtime-explorer 前置条件不再引用"webapp-testing Step 2"
- [x] 三个 Skill 对项目启动方式表述一致（用户自行启动）

## Task 2: prerequisite_action 回归
- [x] grep webapp-testing SKILL.md `prerequisite_action` 无匹配（全局 grep 确认）

## Task 3: runtime.yaml 消费
- [x] manual-writer 输入章节列出 runtime.yaml（可选）
- [x] manual-writer 生成规则提及读取校验提示/反馈信息

## Task 4: retake-list.yaml 契约
- [x] webapp-testing 输入章节列出 retake-list.yaml（可选）
- [x] webapp-testing 执行流程包含补拍模式分支（含 Python 代码）

## Task 5: manifest.yaml 嵌入
- [x] manual-writer 输入列出 manifest.yaml 并有嵌入规则
- [x] api-doc-writer 输入列出 manifest.yaml 并有时序图嵌入规则
- [x] manifest.yaml file 字段路径统一为 diagrams/（相对 output/）
- [x] manifest.yaml 每个图表条目含 status 字段

## Task 6: 字段名与枚举
- [x] runtime-explorer Step 3.3 使用 submit_button/cancel_button（无 _text 后缀）
- [x] pkb-schema.yaml runtime status 含 timeout
- [x] runtime-explorer Step 5 注释列出全部合法 status

## Task 7: planner 示例
- [x] screenshot-planner 输出示例含 full_page / wait_after_action / roles

## Task 8: 脚本角色过滤
- [x] generate_screenshots.py 角色循环按 roles 字段过滤（line 377）

## Task 9: renderer 泛化
- [x] document-renderer 描述为通用渲染，不限于用户手册
- [x] 输入章节接受任意 output/*.md

## Task 10: 编号与模板
- [x] doc-gen database 输出物编号连续（4 条无重复）
- [x] manual-outline.md 操作步骤使用"步骤N："格式

## Task 11: 变量与 dead code
- [x] webapp-testing 无未定义的 dashboard_route（改为 account['expected_redirect']）
- [x] generate_screenshots.py execute_action 无无效 highlight 参数（签名和调用处均已清理）
- [x] generate_screenshots.py 无无效三元表达式

## Task 12: 版本标签与步骤
- [x] screenshot-planner 约束无"V1"标签
- [x] doc-gen 无空壳 Step 3.5

## 整体一致性
- [x] 修改仅限 `.trae/skills/**` 与 `templates/**`，未触碰任何业务源码（git status 确认）
