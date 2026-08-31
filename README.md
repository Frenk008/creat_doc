# 文档生成平台

完整使用流程、参数、截图配置和排错说明见 [Doc Gen Skill 完整使用指南](DOC-GEN-SKILL-使用指南.md)。

支持 `--source code` 从源码生成多类文档，也支持 `--source website` 仅凭已部署网站和测试账号只读生成用户手册。

## Python 环境

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
```

自动截图依赖 Playwright、PyYAML 和 Pillow；DOCX 兜底渲染依赖 python-docx。

## 可选外部工具

- Pandoc：首选 DOCX/HTML 渲染器；未安装时使用 python-docx。
- LibreOffice 或 XeLaTeX：生成 PDF 时使用。
- PlantUML Server：图表渲染。敏感项目应使用本地服务并通过 `--server` 指定地址，避免向公网发送项目结构。

## 验证

```powershell
python -m unittest discover -s tests -v
python -m py_compile templates/generate_screenshots.py measure_addr_rect.py
```

生成手册后可单独检查关键 UI 状态是否缺图：

```powershell
python .trae/skills/qa-reviewer/scripts/check_visual_coverage.py `
  --manual output/manual.md `
  --output output/visual-coverage-report.json
```

`missing=0` 后才能进入截图规划阶段。
