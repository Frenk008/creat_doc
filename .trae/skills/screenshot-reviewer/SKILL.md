---
name: "screenshot-reviewer"
description: "截图质量审核器(V2)。检查webapp-testing采集的截图是否符合计划要求,发现不合格截图后触发重新采集。使用chrome-devtools-mcp打开图片或页面进行检查。当webapp-testing完成截图后调用。"
---

# Screenshot Reviewer —— 截图质量审核器(V2)

## Skill 契约

```yaml
inputs:
  - output/capture-result.json
  - knowledge/screenshots.yaml
  - output/screenshots/
outputs:
  - output/screenshot-review-report.md
  - output/retake-list.yaml (如有不合格)
  - knowledge/screenshots.yaml (更新 status)
depends_on:
  - webapp-testing
cache_key:
  - output/capture-result.json
stage: screenshot
```

你的任务是检查 webapp-testing 采集的截图质量,发现不合格截图后生成补拍清单,触发重新采集。

## 前置条件

- `output/screenshots/*.png` —— webapp-testing 采集的截图
- `output/capture-result.json` —— 采集结果(含每张图的状态和错误信息)
- `knowledge/screenshots.yaml` —— 截图计划(原始)

## 输入

- `output/capture-result.json` —— 采集结果
- `knowledge/screenshots.yaml` —— 截图计划
- `output/screenshots/` —— 截图文件目录

## 输出

- `output/screenshot-review-report.md` —— 审核报告
- `output/retake-list.yaml` —— 补拍清单(如有不合格截图)
- 更新 `knowledge/screenshots.yaml` 中每条记录的 `status` 和 `review_notes`

## 审核流程

### Step 1: 分析采集结果

读取 `capture-result.json`,统计采集状态:

```
captured  → 需要进一步审核内容质量
partial   → 需要审核(兜底截图可能内容不对)
failed    → 直接进入补拍清单
```

### Step 2: 逐张审核 captured 和 partial 的截图

**审核方法:** 使用 chrome-devtools-mcp 的 `take_screenshot` 或直接用 `evaluate_script` 检查截图文件。

**审核检查项:**

| 检查项 | 规则 | 不合格处理 |
|--------|------|-----------|
| 文件存在 | PNG 文件实际存在于 output/screenshots/ | 加入补拍清单 |
| 文件大小 | > 5KB(过小可能是空白页) | 加入补拍清单 |
| 页面匹配 | 截图的页面 URL 与计划 route 一致 | 加入补拍清单 |
| 内容非空 | 不是全白/全灰/Loading 页 | 加入补拍清单 |
| 无遮挡 | 关键区域无弹窗/Loading 遮挡 | 标记 warning |
| 高亮可见 | highlight 元素在截图中可见 | 标记 warning |
| 自动标注完整性 | `annotation.matched` 等于 `annotation.requested` | 读取 `annotation_warnings` 并标记 warning，必要时建议补拍 |
| 前置动作完整性 | `action_warnings` 为空 | 动作失败的截图不得审核为通过，加入补拍清单 |
| 状态匹配 | 截图呈现 `state_type/state_name` 描述的页面、弹窗、确认框或结果状态 | 状态不符加入补拍清单 |
| 选择器可执行 | `selector_status` 不为 unresolved | unresolved 直接进入补拍/人工确认 |
| 无错误页 | 不是 404/500/空白错误页 | 加入补拍清单 |
| 敏感信息检查 | 截图中不含明文密码/身份证号/银行卡号/手机号 | 加入补拍清单(脱敏后重拍) |

自动标注目标未命中本身不改变 `captured` 状态。审核报告必须列出对应警告；仅当缺少标注会导致操作指引不可理解时，才加入补拍清单。

**程序化检查(Python 脚本辅助):**

```python
from pathlib import Path
from PIL import Image
import json

with open("output/capture-result.json", encoding="utf-8") as f:
    results = json.load(f)

issues = []
for r in results["results"]:
    shot_id = r["id"]
    png_path = Path(f"output/screenshots/{shot_id}.png")

    # 检查 1: 文件存在
    if not png_path.exists():
        issues.append({"id": shot_id, "issue": "文件不存在", "action": "retake"})
        continue

    # 检查 2: 文件大小
    size = png_path.stat().st_size
    if size < 5000:
        issues.append({"id": shot_id, "issue": f"文件过小({size}B),可能是空白页", "action": "retake"})
        continue

    # 检查 3: 图像内容(用 PIL 检查是否全白/全灰)
    img = Image.open(png_path)
    extrema = img.convert("L").getextrema()
    if extrema[0] > 240 and extrema[1] > 250:
        issues.append({"id": shot_id, "issue": "图像可能是空白页(全白)", "action": "retake"})
        continue

    # 检查 4: 图像尺寸(不应过小)
    width, height = img.size
    if width < 800 or height < 400:
        issues.append({"id": shot_id, "issue": f"图像尺寸过小({width}x{height})", "action": "retake"})
        continue

    # 通过所有检查
    r["review_status"] = "passed"
```

### Step 3: AI 视觉检查(使用 chrome-devtools-mcp)

对于通过程序化检查的截图,使用 chrome-devtools-mcp 进行视觉验证:

```bash
# 用 chrome-devtools-mcp 打开截图检查
# 或者:重新打开页面,对比截图和实际页面
```

**使用 MCP 工具检查(可选,用于关键截图):**

1. 用 `navigate_page` 打开对应页面
2. 用 `take_screenshot` 截取一张参考图
3. 对比 webapp-testing 的截图和参考图是否一致

**注意:** 这一步是可选的增强,只对关键页面(如登录、首页)执行,不对所有截图执行(避免 token 浪费)。

### Step 4: 生成审核报告

```markdown
# 截图审核报告

## 审核概况
- 审核时间：{时间}
- 审核截图数：{总数}
- 通过：{通过数}
- 需补拍：{补拍数}
- 警告：{警告数}

## 审核结果

| 截图ID | 手册位置 | 采集状态 | 审核结果 | 说明 |
|--------|----------|---------|---------|------|
| shot-4-1-1 | 4.1 登录-步骤1 | captured | ✅ 通过 | |
| shot-5-1-1 | 5.1 用户管理-步骤1 | captured | ✅ 通过 | |
| shot-5-1-2 | 5.1 用户管理-步骤2 | partial | ⚠️ 警告 | 高亮元素不可见 |
| shot-5-2-1 | 5.2 创建用户-步骤1 | failed | ❌ 需补拍 | 元素未找到 |
| shot-5-2-2 | 5.2 创建用户-步骤2 | captured | ❌ 需补拍 | 空白页 |

## 补拍清单
共 {N} 张需要补拍,见 output/retake-list.yaml
```

### Step 5: 生成补拍清单

将不合格截图写入 `output/retake-list.yaml`:

```yaml
retakes:
  - id: "shot-5-2-1"
    original_error: "元素未找到:新增按钮"
    review_issue: "截图失败,需重新采集"
    suggested_action: "检查页面是否需要先点击某个标签页才能显示新增按钮"
    page_id: "user-list"
    route: "/users"
    action: "点击新增"
    priority: "high"  # high / medium / low

  - id: "shot-5-2-2"
    original_error: ""
    review_issue: "空白页,可能页面未加载完成"
    suggested_action: "增加等待时间后重新截图"
    page_id: "user-create"
    route: "/users/create"
    action: ""
    priority: "high"
```

### Step 6: 触发补拍(如有不合格截图)

如果 `retake-list.yaml` 非空,将补拍清单传回 webapp-testing 重新采集:

```
webapp-testing 读取 retake-list.yaml → 只补拍不合格的截图 → 覆盖原文件
```

**补拍规则:**
- 最多补拍 2 轮(避免死循环)
- 每轮只补拍上一轮失败的截图
- 补拍后重新进入审核流程
- 2 轮后仍失败的截图,在手册中保留占位标记
- **浏览器模式沿用**:补拍默认复用 `screenshot-config.yaml` 中已存储的 `headless`/`slow_mo`,**不再询问用户**(参见 webapp-testing Step 1.5 条件3)。如需切换模式,用户可在 config 中手动修改,或 Agent 按需在命令行追加 `--headed`。

### Step 7: 更新截图状态

审核完成后,更新 `knowledge/screenshots.yaml`:

```yaml
- id: "shot-5-1-1"
  status: "reviewed"        # reviewed / need_retake / failed
  review_notes: ""           # 审核通过,无备注
  retake_count: 0            # 补拍次数

- id: "shot-5-2-1"
  status: "failed"           # 补拍2轮仍失败
  review_notes: "新增按钮选择器未匹配,建议手动截图"
  retake_count: 2
```

## 最终处理

审核全部完成后:

1. **status = reviewed 的截图**:通知 document-renderer 将手册中的图片占位替换为实际图片引用
2. **status = failed 的截图**:手册中保留占位标记 `【图片：功能名-步骤X】（截图占位，后续补充）`
3. **status = need_retake 的截图**:继续补拍流程(Step 6)

## 文件编码规范

报告和补拍清单使用 UTF-8 无 BOM 编码。

## 严格约束

1. **不改截图文件**:审核只检查和标记,不修改已采集的截图文件。
2. **补拍上限**:最多 2 轮补拍,避免无限循环。
3. **失败不阻塞**:个别截图审核失败不影响整体文档生成,只是该图保留占位。
4. **状态独立性**:补拍单张截图时仍必须从 route 起点完整重放成功；不得依赖上一张截图遗留的弹窗或表单状态。
4. **资源清理**:使用 MCP 工具检查时,完成后关闭页面。
