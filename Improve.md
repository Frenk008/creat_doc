# Documentation Generation Platform - Architecture Refactor Specification

## Background

当前系统已经实现了自动生成用户手册的基础流程：

```
Source Code
    │
    ▼
Project Explorer
    │
    ▼
Project Knowledge Base
    │
    ▼
Manual Writer
    │
    ▼
Screenshot
    │
    ▼
Renderer
```

但是，该架构仍存在以下问题：

* Explorer 职责过重
* PKB 不支持增量更新
* Workflow 为串行执行
* 无缓存机制
* 不支持多文档并行生成
* 后续扩展数据库说明书、设计说明书时耦合度较高

本次重构目标是将系统升级为可扩展的 Documentation Generation Platform。

---

# 一、整体架构调整

新的整体架构如下：

```
                Source Code
                     │
         ┌───────────┴────────────┐
         ▼                        ▼
 Universal Explorer      Runtime Explorer
 （静态分析）             （运行时探索）
         └───────────┬────────────┘
                     ▼
        Project Knowledge Base（PKB）
                     │
        ┌────────────┼─────────────┐
        ▼            ▼             ▼
 Manual Writer   Database Writer   Design Writer
        │            │             │
        └────────────┼─────────────┘
                     ▼
             Document Reviewer
                     │
                     ▼
         Screenshot Planner
                     │
                     ▼
            WebApp Testing
                     │
                     ▼
          Screenshot Reviewer
                     │
                     ▼
            Document Renderer
         HTML / PDF / DOCX
```

说明：

* PKB 为整个系统唯一事实来源（Single Source of Truth）
* 所有 Writer 不再读取源码，仅消费 PKB
* 新增文档类型时，仅增加新的 Writer

---

# 二、Project Explorer 重构

当前：

Project Explorer 负责全部分析。

调整为：

## Core Explorer

负责：

* 项目基本信息
* 模块
* 页面
* 用户角色
* Workflow

输出：

```
knowledge/

project.yaml

modules/

pages/

roles/

workflow/
```

不要解析数据库。

不要解析 API。

不要解析架构。

---

新增：

Database Extractor

输出：

```
knowledge/database/
```

---

新增：

API Extractor

输出：

```
knowledge/apis/
```

---

新增：

Architecture Extractor

输出：

```
knowledge/architecture/
```

Explorer 只负责调度这些 Extractor。

---

# 三、PKB 重构

不要生成一个巨大的 YAML。

改为：

```
knowledge/

project.yaml

modules/

    user.yaml

    order.yaml

pages/

    login.yaml

    user-list.yaml

workflow/

    create-user.yaml

roles/

database/

apis/

runtime/

screenshots/
```

要求：

每个知识实体一个文件。

支持增量更新。

---

# 四、Workflow Engine

不要写死：

```
Explorer

↓

Writer

↓

Screenshot

↓

Renderer
```

改为：

Task DAG。

每个 Skill 必须声明：

```yaml
name:

inputs:

outputs:

depends_on:

cache_key:
```

由 Workflow 自动调度。

---

# 五、Cache

新增：

```
.cache/

explorer/

writer/

runtime/

screenshot/

renderer/
```

每个 Skill 必须支持缓存。

例如：

Explorer：

```
project.hash
```

Writer：

```
manual.hash
```

Screenshot：

```
image.hash
```

Renderer：

```
render.hash
```

---

# 六、Incremental Build

不要重新生成整个 PKB。

要求：

模块级更新。

例如：

修改：

```
src/order/*
```

只更新：

```
knowledge/modules/order.yaml

knowledge/pages/order*

knowledge/workflow/order*
```

不要影响其它模块。

Writer：

也支持：

章节级更新。

Screenshot：

支持：

图片级更新。

---

# 七、Parallel Execution

PKB 完成后：

多个 Writer 必须支持并行。

例如：

```
PKB

├── Manual Writer

├── Database Writer

├── API Writer

├── Design Writer
```

互不依赖。

截图：

不同模块允许多个 Browser Agent 并行执行。

---

# 八、Stage Execution

支持：

```
--stage explorer

--stage writer

--stage screenshot

--stage render
```

开发阶段无需执行完整流程。

---

# 九、Runtime Explorer

Runtime Explorer 负责：

* 自动注册
* 自动登录
* 自动创建测试数据
* 补充运行时信息

输出：

```
knowledge/runtime/
```

更新：

PKB。

不要直接修改用户手册。

---

# 十、Screenshot Planner

新增独立 Skill。

职责：

根据 Markdown：

生成：

```
Image ID

Page

Need Data

Need Action

Need Scroll

Highlight
```

Browser Agent：

只执行。

不要自己推理。

---

# 十一、Document Reviewer

新增统一 Reviewer。

负责：

* 语言一致性
* 章节完整性
* 图片编号
* 链接
* FAQ
* 格式检查

不要修改 PKB。

仅修改 Markdown。

---

# 十二、Renderer

Renderer 只负责：

Markdown

↓

HTML

↓

DOCX

↓

PDF

不要参与内容生成。

---

# 十三、长期目标

整个平台应支持：

* 用户手册
* 管理员手册
* 软件设计说明书
* 数据库说明书
* API 文档
* 测试文档
* 培训文档
* 运维文档

所有文档均基于同一份 PKB 生成。

不得重复分析源码。

---

# 十四、设计原则

必须遵循：

1. Single Source of Truth（PKB）
2. Skill 单一职责
3. DAG Workflow
4. Cache First
5. Incremental First
6. Parallel First
7. Markdown 作为统一 Document IR
8. Renderer 与内容生成解耦
9. Runtime 负责补充 PKB，而不是生成文档
10. 所有新增文档仅新增 Writer，不修改核心 Workflow
