---
name: "screenshot-reviewer"
description: "截图质量审核器(V2 功能,V1 为占位状态)。检查 webapp-testing 采集的截图是否符合计划要求,发现不合格截图后触发重新采集。当前 V1 版本仅记录占位,不实际执行。当 webapp-testing 完成截图后调用。"
---

# Screenshot Reviewer —— 截图质量审核器

> **版本状态: V1 为占位模式,不实际执行。此文档为 V2 完整实现的设计规范。**

## V1 行为(当前)

当被调用时:
1. 不执行任何审核操作
2. 返回:"截图审核在 V1 中为占位状态。截图计划见 screenshots.yaml,待 V2 实现实际截图后启用审核。"

---

## V2 完整设计(未来实现)

### 职责

对采集的截图进行质量检查,确保:
1. 截图内容与计划一致(页面正确、状态正确)
2. 高亮元素可见
3. 截图清晰(分辨率、无遮挡)
4. 无敏感信息泄露(密码、真实用户数据)

### 检查项

| 检查项 | 规则 | 处理 |
|--------|------|------|
| 页面匹配 | 截图中的页面 URL 与计划 route 一致 | 不一致 → 重新采集 |
| 状态匹配 | 截图时的系统状态与 data_state 一致 | 不一致 → 重新采集 |
| 高亮可见 | highlight 指定的元素在截图中可见 | 不可见 → 重新采集 |
| 分辨率 | 宽度 >= 1280px | 过小 → 重新采集 |
| 遮挡检查 | 无弹窗/Loading 遮挡关键区域 | 有遮挡 → 等待后重新采集 |
| 敏感信息 | 截图中无密码明文、真实用户数据 | 有泄露 → 脱敏处理 |

### 执行流程

```
output/screenshots/*.png
        │
        ▼
   逐张检查(使用视觉分析)
        │
        ├── 通过 → status = "reviewed"
        │
        └── 不通过 → 记录问题
                │
                ▼
           生成补拍清单
                │
                ▼
           回传给 webapp-testing 重新采集
```

### 产出

更新 `screenshots.yaml`:

```yaml
- id: "shot-5-1-1"
  status: "reviewed"       # reviewed / need_retake / failed
  review_notes: ""         # 审核备注
  retake_reason: ""        # 如需补拍,记录原因
```

审核报告 `output/screenshot-review-report.md`。
