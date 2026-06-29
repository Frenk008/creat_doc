---
name: "manual-writer"
description: "用户手册生成器。读取 PKB YAML 知识库,按照标准大纲模板生成面向普通用户的 Markdown 用户手册。当 project-explorer 完成源码分析后,或 doc-gen 编排器调用时使用。"
---

# Manual Writer —— 用户手册生成器

你的任务是读取 PKB(`knowledge/` 目录)并生成一份完整的、面向普通用户的 Markdown 用户手册。

## 输入

- PKB 目录:`knowledge/`(包含 project.yaml, modules.yaml, pages.yaml, roles.yaml, workflows.yaml 等)
- 大纲模板:`templates/manual-outline.md`
- `knowledge/runtime.yaml` —— 运行时探索结果(可选。若存在,读取 discovered_validation_rules 和 discovered_feedback_messages,在功能说明中补充表单校验提示和操作反馈信息)
- `output/diagrams/manifest.yaml` —— 图表清单(可选。若存在,在对应功能章节嵌入流程图和功能总览图引用)

## 输出

- `output/manual.md` —— 完整的 Markdown 用户手册

## 生成规则

### 1. 严格遵循大纲

按照 `templates/manual-outline.md` 的章节结构逐章生成:
- 封面 → 修订记录 → 目录 → 1.软件简介 → 2.功能概览 → 3.角色说明 → 4.快速开始 → 5.功能使用说明 → 6.常见业务流程 → 7.FAQ → 8.注意事项

### 2. 分模块生成(避免 token 溢出)

**不要一次性生成全文。按以下顺序逐步生成并拼接:**

```
第1批: 封面 + 修订记录 + 第1章(软件简介) + 第2章(功能概览)
第2批: 第3章(角色说明) + 第4章(快速开始)
第3批: 第5章(功能使用说明) —— 按模块逐个生成
第4批: 第6章(业务流程) + 第7章(FAQ) + 第8章(注意事项)
```

### 3. 功能说明生成模板

对于 `modules.yaml` 中的每个模块,在"第5章 功能使用说明"中生成一节。
对于模块关联的每个页面,生成一个功能小节:

```markdown
### 5.{模块序号}.{页面序号} {页面中文标题}

**功能介绍：**
{从 pages.yaml 的 description 提取,转为用户语言}

**使用条件：**
（1）{角色要求,从 roles.yaml 提取}
（2）{前置条件,从 workflows.yaml 的 preconditions 提取}

**操作步骤：**
步骤1：{从 workflows.yaml 的 steps 逐条转换}
步骤2：{将 "action" 字段转为"点击""选择""输入"等用户操作语言}
步骤3：{每步末尾附操作结果}

【图片：{功能名}-步骤{N}】（截图占位，后续补充）

**操作结果：**
{从 workflows.yaml 的 postconditions 提取}

**注意事项：**
（1）{从 steps 的 notes 提取,或根据 actions 推导合理注意事项}
（2）{...}
```

### 4. 语言转换规则

**必须将技术表达转为用户语言:**

| PKB 中的字段 | 手册中的表达 |
|-------------|-------------|
| `action: create` | "点击「新增」按钮" |
| `action: edit` | "点击对应记录的「编辑」按钮" |
| `action: delete` | "点击对应记录的「删除」按钮" |
| `action: export` | "点击「导出」按钮" |
| `action: search` | "在搜索框中输入关键词" |
| `action: save` | "点击「保存」按钮" |
| `fields: [username, email]` | "填写用户名、邮箱等信息" |
| `roles: [admin]` | "该功能仅管理员可用" |
| `route: /users` | 不出现路由路径,改为"进入用户管理页面" |

### 5. 角色说明生成

根据 `roles.yaml`,在第3章为每个角色生成一节:

```markdown
## 3.{序号} {角色中文名}

### 权限范围
**可使用的功能：**
- {列出 can_access 中的模块/页面中文名}

**不可使用的功能：**
- {列出 cannot_access 中的模块/页面中文名}

### 典型使用场景
{列出 typical_scenarios}
```

### 6. 业务流程生成

根据 `workflows.yaml` 中的 `workflow_chains`,在第6章生成完整流程:

```markdown
## 6.{序号} {流程名称}

{流程描述}

完整操作流程：
1. {workflow 1 中文名} → 2. {workflow 2 中文名} → ...

详细步骤：
### 步骤1：{workflow 1}
{展开 workflow 1 的 steps}
...
```

### 7. FAQ 生成

**仅根据 PKB 中的实际功能生成**,不编造不存在场景:

```markdown
## Q: 无法登录怎么办？
A: 请检查以下几点：
1. 确认用户名和密码输入正确
2. 确认账户未被锁定
3. {如 PKB 中有验证码相关功能则补充}

（仅当 PKB 中确实存在登录功能时才生成此条）
```

### 8. 图表嵌入

**图表嵌入:** 若 manifest.yaml 存在,遍历其中 status: rendered 的图表条目,在对应章节嵌入:
- type: component → 嵌入到"2 系统功能概览",引用路径为 manifest 中的 `file` 字段值
- type: flow → 嵌入到"6 常见业务流程"对应流程处,引用路径为 manifest 中的 `file` 字段值
- 嵌入格式:`![{title}]({file})`,其中 {title} 和 {file} 均从 manifest.yaml 读取,不硬编码文件名
- status: failed 的图表用文字描述替代,不嵌入断裂链接

## 严格约束

1. **禁止开发术语**:不出现作为实现细节的技术术语(如源码、函数、类、接口、组件、框架、编译)。但**面向用户的功能名称保留**(如"API 密钥""数据库连接"这类产品本身就需要用户理解的概念允许出现)。
2. **代码片段白名单**:仅允许以下场景出现代码块,且必须配文字说明:
   - 用户需要输入或复制的内容(如 API Key、配置示例、命令行指令)
   - 产品提供给用户的示例(如请求示例、脚本模板)
   - **禁止**:出现源码级实现(如 `function createUser()` / `@RestController` / `router.push()`)。
   - **判断标准**:这段代码是"用户要用的"还是"开发者写的"?前者保留,后者删除。
3. **禁止部署说明**:不涉及面向运维的安装、环境配置、服务启动等内容。但**面向最终用户的初始设置**(如"在设置页填写 API Key")属于操作指南,应当保留。
4. **图片占位完整**:每个操作步骤必须附图片占位。
5. **禁止幻觉**:手册中的每个功能必须能在 PKB 中找到对应记录。无法确认的内容标注 `（待确认）`,不自行补充。
6. **禁止 Markdown 列表语法(关键)**:
   - **禁止使用** `1. ` `2. ` `3. ` 等 Markdown 有序列表语法 —— 它会被渲染器转为 Word 自动编号,导致不同模块之间编号连续递增、不重置。
   - **禁止使用** `- ` 或 `* ` 等 Markdown 无序列表语法 —— 它会被渲染器转为 Word 项目符号(小圆点)。
   - **替代写法**:所有列表内容一律使用**普通段落 + 手写编号**,具体规则:
     - 操作步骤:每条单独一行,以 `步骤1：` `步骤2：` `步骤3：` 开头(编号在每个功能小节内从1重新开始)
     - 条件/注意事项/要点:每条单独一行,以 `（1）` `（2）` `（3）` 开头(编号在每个段落内从1重新开始)
     - 简短并列项:用顿号连接在一句话内,如"支持增、删、改、查四种操作"
7. **文件编码(关键)**:分批生成后合并 Markdown 时,必须遵守以下规则防止乱码:
   - 所有分片文件和最终文件统一使用 **UTF-8 无 BOM** 编码
   - **禁止使用** PowerShell 的 `Out-File -Encoding utf8` 或 `Set-Content -Encoding UTF8`(Windows PowerShell 5.x 会带 BOM)
   - **正确写法**:用 `[System.IO.File]::WriteAllText(path, content, [System.Text.UTF8Encoding]::new($false))`,或用 Python `pathlib.Path(path).write_text(text, encoding="utf-8")`
   - 合并分片时:每个文件读取后用 `utf-8-sig` 或 `.strip("\ufeff")` 去除残留 BOM,段与段之间用两个换行 `\n\n` 连接

## 产出验证

生成完成后自检:
- [ ] 是否覆盖 modules.yaml 中的所有模块
- [ ] 是否覆盖 pages.yaml 中的所有页面
- [ ] 是否覆盖 roles.yaml 中的所有角色
- [ ] 每个功能是否都有图片占位
- [ ] 是否存在任何开发术语(全局搜索检查)
- [ ] FAQ 是否仅基于实际功能生成
- [ ] **合并后的文件无 BOM 标记**(检查开头和中间是否有 `\ufeff` 字符)
