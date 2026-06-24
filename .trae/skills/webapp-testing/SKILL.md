---
name: "webapp-testing"
description: "Web应用自动化测试与截图采集器(V2 功能,V1 为占位状态)。使用 Playwright 自动操作 Web 应用,按照截图计划采集实际界面截图。当前 V1 版本仅记录占位,不实际执行。当 doc-gen 需要实际截图时调用。"
---

# WebApp Testing —— Web 应用自动化截图采集器

> **版本状态: V1 为占位模式,不实际执行。此文档为 V2 完整实现的设计规范。**

## V1 行为(当前)

当被调用时:
1. 不启动浏览器,不执行截图
2. 在 `output/` 目录创建截图占位说明文件:

```markdown
# 截图采集状态(V1 占位)

V1 版本未执行实际截图采集。

截图计划已生成于: knowledge/screenshots.yaml
共规划截图: {N} 张

如需采集实际截图,请:
1. 确保目标项目已启动并可访问
2. 升级到 V2 版本(集成 Playwright)
3. 或手动按截图计划逐一截图,放入 output/screenshots/ 目录
```

3. 手册中的图片统一保留占位标记

---

## V2 完整设计(未来实现)

### 职责

按照 `screenshots.yaml` 中的计划,自动:
1. 启动浏览器(Playwright)
2. 登录系统(使用测试账号)
3. 导航到目标页面
4. 执行前置操作(如点击按钮、填写表单)
5. 截图
6. 验证截图质量

### 执行流程

```
screenshots.yaml (截图计划)
        │
        ▼
   Playwright 启动
        │
        ▼
   登录系统 (使用 roles.yaml 中的测试账号)
        │
        ▼
   按 screenshots 顺序执行:
   ┌─────────────────────────────┐
   │ for each screenshot:        │
   │   1. 导航到 page.route      │
   │   2. 执行 prerequisite 操作  │
   │   3. 设置 data_state         │
   │   4. 高亮 highlight 元素     │
   │   5. 截图并保存              │
   │   6. 更新 status             │
   └─────────────────────────────┘
        │
        ▼
   截图保存至 output/screenshots/
```

### 配置需求

```yaml
# knowledge/screenshot-config.yaml
test_accounts:
  admin:
    username: "admin"
    password: "***"
    login_url: "/login"
  user:
    username: "testuser"
    password: "***"
base_url: "http://localhost:8080"
browser: "chromium"  # chromium / firefox / webkit
viewport:
  width: 1920
  height: 1080
```

### 产出

```
output/screenshots/
├── shot-4-1-1.png     # 登录页面
├── shot-5-1-1.png     # 用户列表
├── shot-5-1-2.png     # 点击新增后
└── ...
```

并更新 `screenshots.yaml` 中的 status 为 `captured`。
