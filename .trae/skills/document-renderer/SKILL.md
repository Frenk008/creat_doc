---
name: "document-renderer"
description: "文档渲染器。将审核后的 Markdown 文档渲染为 DOCX/PDF/HTML 格式的正式文档。支持自动生成目录、图片占位框、章节编号格式化。当 qa-reviewer 完成审核后,或 doc-gen 编排器调用时使用。"
---

# Document Renderer —— 文档渲染器

你的任务是将 Markdown 文档渲染为可直接交付的 DOCX(或 PDF/HTML)文档。

## 输入

- `output/manual.md` 或 `output/database-spec.md` 或 `output/api-doc.md` —— 待渲染的 Markdown 文档(根据文档类型,接受任意 output/*.md)
- `output/format` —— 目标格式(默认 docx)

## 输出

- `output/用户使用手册.docx` (或 .pdf / .html)

## 渲染方案

### 方案 A: Pandoc (首选)

检查系统是否安装 pandoc,如已安装则使用:

```bash
pandoc output/manual.md \
  -o output/用户使用手册.docx \
  --reference-doc=templates/reference.docx \
  --toc \
  --toc-depth=3 \
  --number-sections \
  -f markdown \
  -t docx
```

**参数说明:**
- `--reference-doc`: 使用参考样式文档(控制字体、间距、标题样式)
- `--toc`: 自动生成目录
- `--toc-depth=3`: 目录深度为3级
- `--number-sections`: 自动章节编号

**reference.docx 处理(关键,避免报错):**
`templates/reference.docx` 在新仓库中**默认不存在**。按以下优先级处理,缺失时不得直接报错:
1. 若 `templates/reference.docx` 存在 → 直接使用。
2. 若不存在但有 pandoc → 先用以下命令生成默认模板,再用其渲染:
   ```bash
   pandoc -o templates/reference.docx --print-default-data-file reference.docx
   ```
3. 若生成失败或无 pandoc → **去掉 `--reference-doc` 参数**继续渲染(使用 pandoc 默认样式),并在日志提示"reference.docx 未生成,使用默认样式"。
4. 若连 pandoc 都没有 → 转方案 B(python-docx),其样式由代码内联设置,不依赖 reference.docx。

**如无 reference.docx**,先用以下命令生成默认模板:
```bash
pandoc -o templates/reference.docx --print-default-data-file reference.docx
```

### 方案 B: python-docx (备选)

如系统无 pandoc 但有 Python,则使用 python-docx 手动构建:

```python
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

doc = Document()

# 设置默认字体
style = doc.styles['Normal']
font = style.font
font.name = 'SimSun'
font.size = Pt(12)

# 封面
# 标题页
# 目录(通过域代码)
# 正文(逐段解析 Markdown)
```

**Markdown → DOCX 映射规则:**

| Markdown | DOCX |
|----------|------|
| `# 标题` | Heading 1 样式 |
| `## 标题` | Heading 2 样式 |
| `### 标题` | Heading 3 样式 |
| `**粗体**` | 加粗文本 |
| `| 表格 |` | Word 表格 |
| `【图片：...】` | 图片占位框(灰底文本框 + 提示文字) |
| 普通段落 | Normal 样式段落 |
| 含"步骤N："的段落 | Normal 段落,手写编号保留(不用 Word 自动编号) |
| 含"（N）"的段落 | Normal 段落,手写编号保留(不用 Word 自动编号) |

**严禁的渲染行为(关键):**

1. **禁止 Word 自动编号**:不得使用 Word 的自动编号列表(Numbering Style)。所有编号必须是 Markdown 源文件中的手写编号文本,作为普通段落的一部分。原因:Word 自动编号会跨模块连续递增,无法在每个功能小节内重置。

2. **禁止 Word 项目符号**:不得使用 Word 的项目符号列表(Bullet Style)。Markdown 中的 `-` 和 `*` 列表标记,在渲染时应当作为普通段落处理,不带项目符号圆点。

**python-docx 实现要点:**
```python
# 错误写法 —— 会触发 Word 自动编号/项目符号
# doc.add_paragraph('步骤1：点击新增', style='List Number')
# doc.add_paragraph('条件A', style='List Bullet')

# 正确写法 —— 普通段落,编号是文本的一部分
p = doc.add_paragraph('步骤1：点击新增按钮')
p.style = doc.styles['Normal']
p.paragraph_format.left_indent = Pt(21)  # 首行缩进2字符

p = doc.add_paragraph('（1）需要管理员权限')
p.style = doc.styles['Normal']
```

**Pandoc 渲染要点:**
如果使用 pandoc,需要禁用列表自动识别。在 Markdown 源文件中,确保列表项不以 `数字.` 或 `-` 开头(由 manual-writer 保证)。如 Markdown 中不出现列表语法,pandoc 不会生成 Word 列表样式。

### 方案 C: HTML 中转 (兜底)

如以上方案均不可用,先转为 HTML 再用 Word 打开:

```bash
pandoc output/manual.md -o output/manual.html --standalone --toc
```

然后提示用户用 Word 打开 HTML 并另存为 DOCX。

### PDF 输出方案 (当 --format pdf 时)

- **方案 D: Pandoc + LaTeX**
  ```bash
  pandoc output/manual.md -o output/用户使用手册.pdf \
    --pdf-engine=xelatex \
    -V CJKmainfont="Microsoft YaHei" \
    --toc --toc-depth=3 --number-sections
  ```
  需要 TeX 发行版(如 TeX Live 或 MiKTeX)。
- **方案 E: 先生成 DOCX 再转换(Pandoc 不可用时的降级)**
  先用方案 A/B 生成 DOCX,再用 LibreOffice 转换:
  ```bash
  libreoffice --headless --convert-to pdf output/用户使用手册.docx
  ```
  需要 LibreOffice。
- **若 LaTeX 和 LibreOffice 均不可用**: 回退为 HTML 输出,提示用户"PDF 引擎不可用,已输出 HTML"

## 图片占位渲染

手册中的图片占位标记需要特殊渲染:

```
【图片：创建用户-步骤3】（截图占位，后续补充）
```

渲染为 DOCX 中的**灰底占位框**:

```
┌──────────────────────────────────────────┐
│                                          │
│        [图片位置]                        │
│        创建用户 - 步骤3                   │
│        （截图占位，后续补充）              │
│                                          │
└──────────────────────────────────────────┘
```

使用 python-docx 实现:
```python
from docx.shared import RGBColor, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
# 设置灰色背景和边框
# 添加占位文字
```

## 目录生成

**DOCX 目录通过域代码实现(可更新):**

```python
# python-docx 插入 TOC 域代码
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

paragraph = doc.add_paragraph()
run = paragraph.add_run()
fldChar = OxmlElement('w:fldChar')
fldChar.set(qn('w:fldCharType'), 'begin')
run._r.append(fldChar)

instrText = OxmlElement('w:instrText')
instrText.set(qn('xml:space'), 'preserve')
instrText.text = ' TOC \\o "1-3" \\h \\z \\u '
run2 = paragraph.add_run()
run2._r.append(instrText)
# ... 结束域代码
```

用户打开 DOCX 后按 `Ctrl+A` → `F9` 即可更新目录。

## 文档样式规范

| 元素 | 样式 |
|------|------|
| 正文字体 | 宋体(SimSun),12pt |
| 标题字体 | 黑体(SimHei) |
| 一级标题 | 18pt,加粗 |
| 二级标题 | 16pt,加粗 |
| 三级标题 | 14pt,加粗 |
| 行距 | 1.5 倍 |
| 页边距 | 上下2.54cm,左右3.18cm |
| 页眉 | 文档名称 |
| 页脚 | 页码 |

## 文件编码与合并规范(关键)

> Windows + PowerShell 环境下,文件编码问题是最常见的 bug 来源。以下规范**必须严格遵守**。

### 核心原则

**所有 Markdown 和 YAML 文件统一使用 UTF-8 无 BOM 编码。**

### 错误写法(会导致乱码)

```powershell
# ❌ Out-File 默认带 UTF-8 BOM
$content | Out-File -Encoding utf8 output/manual.md

# ❌ Set-FileContent 默认带 BOM(Windows PowerShell 5.x)
Set-Content output/manual.md -Encoding UTF8 $content

# ❌ 多文件拼接 —— BOM 会嵌在中间
Get-Content part1.md, part2.md | Out-File merged.md -Encoding utf8
# 结果:merged.md 中间出现 ﻿﻿ 字符(BOM),pandoc 渲染时变成乱码
```

### 正确写法(PowerShell)

```powershell
# ✅ 写单个文件:UTF-8 无 BOM
[System.IO.File]::WriteAllText(
    "output/manual.md",
    $content,
    [System.Text.UTF8Encoding]::new($false)  # $false = 无 BOM
)

# ✅ 合并多个 Markdown 文件(自动去除每个文件的 BOM)
$parts = @("output/part1.md", "output/part2.md", "output/part3.md")
$merged = $parts | ForEach-Object {
    [System.IO.File]::ReadAllText($_, [System.Text.UTF8Encoding]::new($false))
}
[System.IO.File]::WriteAllText(
    "output/manual.md",
    ($merged -join "`n`n"),
    [System.Text.UTF8Encoding]::new($false)
)
```

### 正确写法(Python,推荐跨平台方案)

```python
import pathlib

# ✅ 写文件:明确指定 encoding="utf-8"(Python 默认无 BOM)
pathlib.Path("output/manual.md").write_text(
    content, encoding="utf-8", newline="\n"
)

# ✅ 合并多个 Markdown 文件
parts = ["output/part1.md", "output/part2.md", "output/part3.md"]
merged = []
for p in parts:
    text = pathlib.Path(p).read_text(encoding="utf-8-sig")  # utf-8-sig 自动吃掉 BOM
    merged.append(text.strip("\ufeff"))  # 双保险:去除残留 BOM

result = "\n\n".join(merged)
pathlib.Path("output/manual.md").write_text(
    result, encoding="utf-8", newline="\n"
)
```

### 合并规则

当 manual-writer 或其他 Writer 分批生成 Markdown 后,需要合并为最终文件:

| 规则 | 说明 |
|------|------|
| 分隔符 | 段与段之间用 **两个换行符** `\n\n` 连接(Markdown 段落规范) |
| 去 BOM | 每个分片文件读取后,用 `utf-8-sig` 或 `strip("\ufeff")` 去除可能存在的 BOM |
| 去尾部空行 | 每个分片 `rstrip()` 后再拼接,避免多余空行 |
| 行尾符 | 统一使用 `\n`(LF),不用 `\r\n`(CRLF) |
| 最终校验 | 合并后检查文件开头无 `\ufeff`,文件中间无 `\ufeff` |

### 快速校验脚本

合并完成后,运行校验确保无 BOM:

```python
import pathlib

content = pathlib.Path("output/manual.md").read_bytes()
bom_count = content.count(b"\xef\xbb\xbf")
if bom_count > 0:
    print(f"⚠️ 发现 {bom_count} 个 BOM 标记,需要修复")
    # 自动修复:读取后重新写入
    text = content.decode("utf-8-sig")
    pathlib.Path("output/manual.md").write_text(text, encoding="utf-8", newline="\n")
    print("已自动修复")
else:
    print("✅ 编码正常,无 BOM")
```

### PowerShell 版本注意事项

| PowerShell 版本 | `-Encoding utf8` 行为 | 推荐方案 |
|----------------|----------------------|---------|
| Windows PowerShell 5.x | **带 BOM** | 用 `[System.IO.File]::WriteAllText` |
| PowerShell Core 7.x | **无 BOM** | 可直接用 `-Encoding utf8NoBOM` |

**不要假设 `-Encoding utf8` 等于无 BOM**,必须显式指定。

## 环境检查

执行前先检查可用的渲染工具:

```bash
pandoc --version        # 检查 pandoc
python -c "import docx" # 检查 python-docx
```

按优先级选择:pandoc > python-docx > HTML中转

## 产出验证

- [ ] DOCX 文件已生成且可正常打开
- [ ] 目录占位存在(用户可更新)
- [ ] 图片占位框显示正常
- [ ] 中文字体显示正确
- [ ] 章节编号连续
- [ ] 表格渲染正确
- [ ] **Markdown 文件无 BOM 标记**(运行校验脚本确认)
