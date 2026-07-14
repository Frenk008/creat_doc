#!/usr/bin/env python3
"""
Playwright 批量截图脚本
根据 screenshots.yaml 和 screenshot-config.yaml 自动采集界面截图。

用法:
  python generate_screenshots.py --config knowledge/screenshot-config.yaml --plan knowledge/screenshots.yaml --output output/screenshots

浏览器模式:
  --headless          强制无头(默认)
  --headed            使用有头浏览器(可视化,覆盖 config 中 headless)
  --slow-mo N         慢动作调试毫秒数(配合 --headed)
  若命令行未指定,则读取 screenshot-config.yaml 中 screenshot.headless / screenshot.slow_mo

截图后处理:
  --add-chrome        在每张截图顶部拼接伪造的浏览器头(含真实 URL)
  若命令行未指定,则读取 screenshot-config.yaml 中 screenshot.add_browser_chrome
"""

import argparse
import json
import logging
import math
import os
import re
import shutil
import sys
import time
from pathlib import Path

import yaml

# Pillow 用于合成伪造浏览器头(可选依赖,仅 --add-chrome 时需要)
try:
    from PIL import Image, ImageDraw
    _PILLOW_AVAILABLE = True
except ImportError:
    _PILLOW_AVAILABLE = False

_ENV_VAR_PATTERN = re.compile(r"^\$\{(\w+)\}$")


def _resolve_env_var(value):
    """
    若 value 形如 ${VAR_NAME},从环境变量读取实际值。
    若环境变量不存在,报错退出(code=2),不静默使用空值。
    """
    if not isinstance(value, str):
        return value
    m = _ENV_VAR_PATTERN.match(value)
    if not m:
        return value
    var_name = m.group(1)
    resolved = os.environ.get(var_name)
    if resolved is None:
        logging.error(f"错误: 环境变量 {var_name} 未设置(在 screenshot-config.yaml 中被引用)")
        sys.exit(2)
    return resolved


# ============================================================
# 脱敏 CSS(截图前注入,遮盖密码/敏感字段)
# ============================================================
MASK_CSS = """
input[type="password"],
.sensitive,
[data-mask],
[aria-label*="密码"],
[aria-label*="验证码"] {
    color: transparent !important;
    background: #ccc !important;
    border: 1px solid #999 !important;
}
.masked-text {
    filter: blur(3px);
}
"""

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(message)s",
)
# Windows 中文输出兼容
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:
    pass  # 非 Python 3.7+ 或非 Windows


# ============================================================
# 异常分类
# ============================================================

class RetryableError(Exception):
    """可重试异常:超时、元素未找到、网络问题等。标记 failed 但不退出。"""
    pass


class FatalError(Exception):
    """致命异常:配置错误、依赖缺失、认证失败等。标记 failed 并退出。"""
    pass


# ============================================================
# 配置加载
# ============================================================

def load_config(config_path: str) -> dict:
    """加载截图配置"""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_base_url(config: dict, app: str = None) -> str:
    """
    根据 app 标识获取对应的 base_url。
    优先级:apps[app].base_url > base_url(全局)
    支持单前端(只有 base_url)和多前端(apps 字典)。
    """
    apps = config.get("apps")
    if apps and app and app in apps:
        return apps[app].get("base_url", "")
    return config.get("base_url", "")


def load_plan(plan_path: str) -> list:
    """加载截图计划"""
    with open(plan_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("screenshots", []) if data else []


# ============================================================
# 登录
# ============================================================

def login(page, base_url: str, login_url: str, account: dict):
    """
    执行登录操作。
    尝试多种常见选择器以提高通用性。
    """
    logging.info(f"  正在登录: {base_url + login_url}")

    page.goto(base_url + login_url, wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(1000)

    username = _resolve_env_var(account.get("username", ""))
    password = _resolve_env_var(account.get("password", ""))

    # 填写用户名(尝试多种选择器)
    username_selectors = [
        "input[name='username']",
        "input#username",
        "input[placeholder*='用户名']",
        "input[placeholder*='账号']",
        "input[type='text']:first-of-type",
    ]
    filled = False
    for sel in username_selectors:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.fill(username)
                filled = True
                break
        except Exception:
            continue
    if not filled:
        raise FatalError("无法找到用户名输入框(配置错误)")

    # 填写密码
    password_selectors = [
        "input[name='password']",
        "input#password",
        "input[type='password']",
        "input[placeholder*='密码']",
    ]
    filled = False
    for sel in password_selectors:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.fill(password)
                filled = True
                break
        except Exception:
            continue
    if not filled:
        raise RuntimeError("无法找到密码输入框")

    # 点击登录按钮
    login_selectors = [
        "button[type='submit']",
        "button:has-text('登录')",
        "button:has-text('Login')",
        "button:has-text('登 录')",
        "input[type='submit']",
        ".login-btn",
        "#loginBtn",
    ]
    clicked = False
    for sel in login_selectors:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click()
                clicked = True
                break
        except Exception:
            continue
    if not clicked:
        raise RuntimeError("无法找到登录按钮")

    # 等待跳转(离开登录页即视为成功)
    page.wait_for_timeout(2000)
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass

    current_url = page.url
    if "login" in current_url.lower():
        raise FatalError(f"认证失败,仍在登录页: {current_url}")

    logging.info(f"  登录成功,当前页面: {current_url}")


# ============================================================
# 操作执行器
# ============================================================

def _action_result(success: bool, message: str = "") -> dict:
    return {"success": success, "message": message}


def execute_action(page, action_desc):
    """
    解析截图计划中的操作描述并执行。
    使用关键词匹配,覆盖常见 UI 操作。
    """
    if isinstance(action_desc, list):
        for item in action_desc:
            result = execute_action(page, item)
            if not result["success"]:
                return result
        return _action_result(True)

    if isinstance(action_desc, dict):
        action_type = str(action_desc.get("type", "")).lower()
        selector = action_desc.get("selector")
        value = action_desc.get("value", "")
        try:
            if action_type in ("noop", "wait"):
                if action_type == "wait":
                    page.wait_for_timeout(int(action_desc.get("milliseconds", 500)))
                return _action_result(True)
            if not selector:
                return _action_result(False, f"结构化动作缺少 selector：{action_type or 'unknown'}")
            if action_type == "wait_for":
                page.wait_for_selector(
                    selector,
                    state=str(action_desc.get("state", "visible")),
                    timeout=int(action_desc.get("timeout", 5000)),
                )
                return _action_result(True)
            element = page.query_selector(selector)
            if not element or not element.is_visible():
                return _action_result(False, f"动作元素不可见：{selector}")
            if action_type == "click":
                element.click(timeout=int(action_desc.get("timeout", 2000)))
            elif action_type == "fill":
                element.fill(str(value))
            elif action_type == "select":
                element.select_option(str(value))
            elif action_type == "check":
                element.check()
            elif action_type == "press":
                element.press(str(value))
            elif action_type == "upload":
                element.set_input_files(value)
            else:
                return _action_result(False, f"不支持的动作类型：{action_type}")
            page.wait_for_timeout(int(action_desc.get("wait_after", 300)))
            return _action_result(True)
        except Exception as e:
            return _action_result(False, f"动作执行失败：{e}")

    desc = str(action_desc or "").strip()
    if not desc or any(kw in desc for kw in ["展示页面", "初始页面", "无需操作"]):
        return _action_result(True)

    # 点击新增
    if any(kw in desc for kw in ["新增", "添加", "创建"]):
        success = _try_click(page, [
            "button:has-text('新增')", "button:has-text('添加')",
            "button:has-text('新建')", "button:has-text('创建')",
            "[data-action='create']", ".add-btn", "#addBtn",
            ".el-button--primary:has-text('新增')",
        ])

    # 点击编辑
    elif any(kw in desc for kw in ["编辑", "修改"]):
        success = _try_click(page, [
            "button:has-text('编辑')", "button:has-text('修改')",
            ".edit-btn", "[data-action='edit']",
            "a:has-text('编辑')",
        ])

    # 点击删除
    elif "删除" in desc:
        success = _try_click(page, [
            "button:has-text('删除')", ".delete-btn",
            "[data-action='delete']",
        ])

    # 点击搜索/查询
    elif any(kw in desc for kw in ["搜索", "查询", "检索"]):
        success = _try_click(page, [
            "button:has-text('搜索')", "button:has-text('查询')",
            "button:has-text('搜索')", ".search-btn",
        ])

    # 点击导出
    elif "导出" in desc:
        success = _try_click(page, [
            "button:has-text('导出')", ".export-btn",
        ])

    # 点击保存/确定
    elif any(kw in desc for kw in ["保存", "确定", "提交"]):
        success = _try_click(page, [
            "button:has-text('保存')", "button:has-text('确定')",
            "button:has-text('提交')", "button[type='submit']",
            ".el-button--primary:has-text('确定')",
        ])

    # 点击取消/关闭
    elif any(kw in desc for kw in ["取消", "关闭"]):
        success = _try_click(page, [
            "button:has-text('取消')", "button:has-text('关闭')",
        ])

    else:
        message = f"未识别或缺少执行数据的操作：{desc}"
        logging.warning(f"    ⚠️ {message}")
        return _action_result(False, message)

    if success:
        return _action_result(True)
    return _action_result(False, f"未找到操作目标：{desc}")


def _try_click(page, selectors: list, timeout: int = 2000):
    """尝试多个选择器,第一个成功的即返回"""
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click(timeout=timeout)
                page.wait_for_timeout(500)
                return True
        except Exception:
            continue
    logging.warning(f"    ⚠️ 所有选择器均未找到可点击元素")
    return False


# ============================================================
# 高亮元素
# ============================================================

def split_highlight_targets(highlight_desc: str) -> list:
    """将截图计划中的高亮描述拆成有序、去重的标签。"""
    if not highlight_desc:
        return []
    targets = []
    for value in re.split(r"[、，,]", str(highlight_desc)):
        value = value.strip()
        if value and value not in targets:
            targets.append(value)
    return targets


def locate_annotation_targets(page, highlight_desc: str, full_page: bool = False) -> dict:
    """按描述顺序定位可见 DOM 元素，返回适合截图坐标系的结构化结果。"""
    labels = split_highlight_targets(highlight_desc)
    matched = []
    missing = []

    for requested_index, label in enumerate(labels, 1):
        try:
            result = page.evaluate(
                """
                ({label, fullPage}) => {
                    const visible = (el) => {
                        if (!el) return false;
                        const style = getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        return style.display !== 'none' && style.visibility !== 'hidden' &&
                               Number(style.opacity || 1) > 0 && rect.width > 0 && rect.height > 0;
                    };
                    const norm = (value) => (value || '').replace(/\\s+/g, ' ').trim();
                    const contains = (value) => norm(value).includes(label);
                    const candidates = Array.from(document.querySelectorAll(
                        'button,input,textarea,select,label,table,[title],[aria-label],[data-testid],[data-action],' +
                        '.el-form-item,.ant-form-item,.el-table,.ant-table,[role="button"],[role="grid"],[role="table"],[role="listbox"]'
                    )).filter(visible);
                    const matchers = [
                        el => el.tagName === 'BUTTON' && contains(el.innerText || el.textContent),
                        el => ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName) && contains(el.placeholder),
                        el => el.tagName === 'LABEL' && contains(el.innerText || el.textContent),
                        el => contains(el.title),
                        el => contains(el.getAttribute('aria-label')),
                        el => el.matches('.el-form-item,.ant-form-item') && contains(el.innerText || el.textContent),
                        el => contains(el.innerText || el.textContent),
                    ];
                    let element = null;
                    for (const matcher of matchers) {
                        element = candidates.find(matcher);
                        if (element) break;
                    }
                    if (!element) return null;
                    if (element.tagName === 'LABEL') {
                        const control = (element.htmlFor && document.getElementById(element.htmlFor)) ||
                                        element.querySelector('input,textarea,select,button');
                        if (visible(control)) element = control;
                    }
                    const rect = element.getBoundingClientRect();
                    return {
                        x: rect.left + (fullPage ? window.scrollX : 0),
                        y: rect.top + (fullPage ? window.scrollY : 0),
                        width: rect.width,
                        height: rect.height,
                    };
                }
                """,
                {"label": label, "fullPage": full_page},
            )
        except Exception:
            result = None

        if result:
            matched.append({"index": requested_index, "label": label, **result})
        else:
            missing.append(label)

    return {
        "requested": len(labels),
        "matched": len(matched),
        "missing": missing,
        "targets": matched,
    }


# ============================================================
# 截图
# ============================================================

# 系统字体候选(用于在地址栏绘制 URL 文字,优先支持中文)
_FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyh.ttc",        # 微软雅黑(Windows)
    "C:/Windows/Fonts/simhei.ttf",      # 黑体(Windows)
    "C:/Windows/Fonts/arial.ttf",       # Arial(Windows 兜底)
    "/System/Library/Fonts/PingFang.ttc",  # 苹方(macOS)
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux 兜底
]


def _load_font(size: int):
    """加载支持中文的系统字体,失败则返回 PIL 默认字体。"""
    try:
        from PIL import ImageFont
        for fp in _FONT_CANDIDATES:
            if os.path.exists(fp):
                try:
                    return ImageFont.truetype(fp, size)
                except Exception:
                    continue
        return ImageFont.load_default()
    except Exception:
        return None


def _fit_text(text: str, font, max_width: int):
    """按像素宽度截断 URL,超出部分显示 ...。"""
    if not text or not font:
        return text or ""
    try:
        from PIL import ImageFont
        if hasattr(font, "getlength"):
            if font.getlength(text) <= max_width:
                return text
            # 逐步截断
            for i in range(len(text), 0, -1):
                t = text[:i] + "..."
                if font.getlength(t) <= max_width:
                    return t
            return "..."
    except Exception:
        pass
    return text


def _parse_color(value, default="#E53935"):
    """将 #RRGGBB 配置转换为 Pillow 颜色，非法值使用默认色。"""
    value = value if isinstance(value, str) else default
    if re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))
    return _parse_color(default, "#E53935") if value != default else (229, 57, 53)


def _boxes_overlap(a, b, margin=8):
    return not (a[2] + margin <= b[0] or b[2] + margin <= a[0] or
                a[3] + margin <= b[1] or b[3] + margin <= a[1])


def _clamp_box(x, y, width, height, canvas_w, canvas_h, margin=8):
    x = max(margin, min(int(x), max(margin, canvas_w - width - margin)))
    y = max(margin, min(int(y), max(margin, canvas_h - height - margin)))
    return (x, y, x + width, y + height)


def _label_box(target, width, height, canvas_w, canvas_h, occupied):
    """在目标四周选择第一个不越界且不与既有标签明显冲突的位置。"""
    x, y = target["x"], target["y"]
    w, h = target["width"], target["height"]
    gap = 22
    candidates = [
        (x + w + gap, y + h / 2 - height / 2),
        (x - width - gap, y + h / 2 - height / 2),
        (x + w / 2 - width / 2, y - height - gap),
        (x + w / 2 - width / 2, y + h + gap),
    ]
    clamped = [_clamp_box(cx, cy, width, height, canvas_w, canvas_h) for cx, cy in candidates]
    for box in clamped:
        if not any(_boxes_overlap(box, other) for other in occupied):
            return box
    # 密集区域兜底：沿垂直方向错位，仍确保标签在画布内。
    base = clamped[0]
    for offset in range(16, canvas_h, 16):
        for direction in (1, -1):
            box = _clamp_box(base[0], base[1] + direction * offset,
                             width, height, canvas_w, canvas_h)
            if not any(_boxes_overlap(box, other) for other in occupied):
                return box
    return base


def _draw_arrow(draw, start, end, color, width=4):
    draw.line([start, end], fill=color, width=width)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    head = 12
    spread = math.pi / 7
    points = [
        end,
        (end[0] - head * math.cos(angle - spread), end[1] - head * math.sin(angle - spread)),
        (end[0] - head * math.cos(angle + spread), end[1] - head * math.sin(angle + spread)),
    ]
    draw.polygon(points, fill=color)


def annotate_screenshot(source_path: str, output_path: str, annotation: dict,
                        color_value="#E53935", style="numbered_arrow") -> bool:
    """在原始截图上绘制编号、标签、箭头和目标框。"""
    if not _PILLOW_AVAILABLE or style != "numbered_arrow":
        return False
    try:
        image = Image.open(source_path).convert("RGB")
        draw = ImageDraw.Draw(image)
        color = _parse_color(color_value)
        font = _load_font(max(16, min(24, image.width // 80)))
        number_font = _load_font(max(16, min(22, image.width // 90)))
        occupied = []

        for target in annotation.get("targets", []):
            x1 = max(0, int(round(target["x"])))
            y1 = max(0, int(round(target["y"])))
            x2 = min(image.width - 1, int(round(target["x"] + target["width"])))
            y2 = min(image.height - 1, int(round(target["y"] + target["height"])))
            if x2 <= x1 or y2 <= y1:
                continue
            draw.rounded_rectangle((x1 - 3, y1 - 3, x2 + 3, y2 + 3), radius=6,
                                   outline=color, width=4)

            label = _fit_text(target["label"], font, min(360, max(120, image.width // 3)))
            try:
                text_box = draw.textbbox((0, 0), label, font=font)
                text_w, text_h = text_box[2] - text_box[0], text_box[3] - text_box[1]
            except Exception:
                text_w, text_h = len(label) * 18, 22
            bubble = max(28, text_h + 12)
            box_w = min(image.width - 16, bubble + text_w + 24)
            box_h = max(40, text_h + 16)
            box = _label_box(target, box_w, box_h, image.width, image.height, occupied)
            occupied.append(box)
            bx1, by1, bx2, by2 = box

            draw.rounded_rectangle(box, radius=box_h // 2, fill=(255, 255, 255),
                                   outline=color, width=3)
            circle_cx = bx1 + bubble // 2 + 4
            circle_cy = (by1 + by2) // 2
            radius = bubble // 2 - 3
            draw.ellipse((circle_cx - radius, circle_cy - radius,
                          circle_cx + radius, circle_cy + radius), fill=color)
            number = str(target["index"])
            try:
                nb = draw.textbbox((0, 0), number, font=number_font)
                nw, nh = nb[2] - nb[0], nb[3] - nb[1]
            except Exception:
                nw, nh = 10, 18
            draw.text((circle_cx - nw / 2, circle_cy - nh / 2 - 1), number,
                      fill=(255, 255, 255), font=number_font)
            draw.text((bx1 + bubble + 8, by1 + (box_h - text_h) / 2 - 1), label,
                      fill=(35, 35, 35), font=font)

            target_center = ((x1 + x2) / 2, (y1 + y2) / 2)
            label_center = ((bx1 + bx2) / 2, (by1 + by2) / 2)
            start = (bx1 if target_center[0] < label_center[0] else bx2, label_center[1])
            _draw_arrow(draw, start, target_center, color)

        tmp_path = output_path + ".tmp"
        image.save(tmp_path, "PNG")
        os.replace(tmp_path, output_path)
        return True
    except Exception as e:
        logging.warning(f"  ⚠️ 自动标注失败({source_path}):{e}")
        return False


def _atomic_write_text(path: str, content: str):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    os.replace(tmp_path, path)


def build_capture_markdown(results: list, total: int, captured: int,
                           partial: int, failed: int) -> str:
    lines = [
        "# 截图采集报告", "",
        "## 概况", "",
        f"- 总计：{total}", f"- 成功：{captured}",
        f"- 部分成功：{partial}", f"- 失败：{failed}", "",
        "## 结果", "",
        "| 截图 ID | 状态 | 标注 | 警告/错误 |",
        "|---|---|---:|---|",
    ]
    for result in results:
        annotation = result.get("annotation", {})
        annotation_text = f"{annotation.get('matched', 0)}/{annotation.get('requested', 0)}"
        warnings = (result.get("action_warnings", []) +
                    result.get("annotation_warnings", []))
        detail = "；".join(warnings) or result.get("error", "") or "-"
        detail = str(detail).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {result.get('id', '')} | {result.get('status', '')} | {annotation_text} | {detail} |")
    return "\n".join(lines) + "\n"


def add_browser_chrome(png_path: str, url: str, title: str = "",
                       header_path: str = None, addr_rect=None) -> bool:
    """
    后处理:在截图顶部拼接【真实浏览器头部图片】,并在地址栏区域绘制真实 URL。
    就地覆盖原 PNG 文件。

    Args:
        png_path:    截图文件路径
        url:         显示在地址栏的 URL(通常是 page.url())
        title:       标签栏标题(通常不绘制,头部图片自带标签;保留兼容)
        header_path: 用户提供的浏览器头部模板图片路径(必需)。
                     建议截取浏览器顶部区域(标签栏 + 地址栏 + 工具栏),
                     宽度尽量与截图视口一致(如 1920)以减少缩放失真。
        addr_rect:   地址栏区域 [x1, y1, x2, y2],取值为相对于头部图片
                     宽高的比例(0~1)。如 [0.28, 0.5, 0.92, 0.72]。
                     传入 None 则不绘制 URL 文字(仅拼接头部图片)。

    Returns:
        True 表示成功合成,False 表示跳过(依赖/文件缺失或图像异常)
    """
    if not _PILLOW_AVAILABLE:
        logging.warning("  ⚠️ 跳过浏览器头合成:Pillow 未安装 (pip install pillow)")
        return False

    if not header_path or not os.path.exists(header_path):
        logging.warning(f"  ⚠️ 跳过浏览器头合成:未找到头部模板图片 ({header_path})")
        return False

    try:
        page_img = Image.open(png_path).convert("RGB")
        header_img = Image.open(header_path).convert("RGB")

        # 将头部图片水平缩放至与截图同宽(保持宽高比)
        target_w = page_img.width
        scale = target_w / header_img.width
        target_h = int(round(header_img.height * scale))
        if scale != 1.0:
            try:
                header_img = header_img.resize((target_w, target_h), Image.LANCZOS)
            except Exception:
                header_img = header_img.resize((target_w, target_h))  # 老版本 Pillow 兜底

        # 在地址栏区域绘制 URL 文字
        if addr_rect and url:
            try:
                x1 = int(addr_rect[0] * target_w)
                y1 = int(addr_rect[1] * target_h)
                x2 = int(addr_rect[2] * target_w)
                y2 = int(addr_rect[3] * target_h)
                draw = ImageDraw.Draw(header_img)
                font_size = max(10, int((y2 - y1) * 0.55))
                font = _load_font(font_size)
                # 截断 URL 适应地址栏宽度
                max_w = max(20, (x2 - x1) - 24)
                disp_url = _fit_text(url, font, max_w)
                # 垂直居中
                try:
                    ascent = font.getbbox(disp_url)[3]
                except Exception:
                    ascent = font_size
                ty = y1 + max(0, ((y2 - y1) - ascent) // 2)
                draw.text((x1 + 16, ty), disp_url, fill=(32, 33, 36), font=font)
            except Exception as e:
                logging.warning(f"    ⚙️ 地址栏 URL 绘制失败({e}),仅拼接头部图片")

        # 拼接:头部在上,原页面截图在下
        canvas = Image.new("RGB", (target_w, target_h + page_img.height), (255, 255, 255))
        canvas.paste(header_img, (0, 0))
        canvas.paste(page_img, (0, target_h))

        # 原子写入(先写 tmp 再替换)
        tmp_path = png_path + ".tmp"
        canvas.save(tmp_path, "PNG")
        os.replace(tmp_path, png_path)
        return True

    except Exception as e:
        logging.warning(f"  ⚠️ 浏览器头合成失败({png_path}):{e}")
        return False

def capture_screenshot(page, shot: dict, output_dir: str, config: dict = None,
                       add_chrome: bool = False, auto_annotate: bool = True) -> dict:
    """
    对单个截图计划执行截图。
    根据 shot 中的 app 字段选择对应的 base_url 和 route(多前端/多主题支持)。
    返回更新后的 shot 字典(含 status 和可能的 error)。
    auto_annotate=True 且 shot.highlight 非空时生成标注图；add_chrome 在标注后执行。
    """
    shot_id = shot["id"]
    app = shot.get("app", "")
    action = shot.get("action", "")
    need_scroll = shot.get("need_scroll", False)
    highlight = shot.get("highlight", "")
    full_page = shot.get("full_page", False)
    wait_after_action = shot.get("wait_after_action", 500)

    # 根据 app 选择 route:优先 routes[app],其次 route
    routes = shot.get("routes") or {}
    route = routes.get(app) or shot.get("route", "/")

    # 根据 app 选择 base_url
    if config:
        base_url = get_base_url(config, app)
    else:
        base_url = ""

    # 构建完整 URL
    if route.startswith("http"):
        full_url = route
    elif base_url:
        full_url = base_url + route
    else:
        full_url = route

    logging.info(f"  截图 {shot_id}: [{app or 'default'}] {full_url} ({action})")

    try:
        # 导航到页面
        page.goto(full_url, wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(500)

        # 脱敏注入:遮盖密码/敏感字段
        try:
            page.add_style_tag(content=MASK_CSS)
        except Exception:
            pass  # 某些页面可能不支持 add_style_tag,不阻塞截图

        # 执行前置操作；失败时仍保留截图，但状态必须是 partial，避免错误页面被当作成功。
        action_result = _action_result(True)
        shot["action_warnings"] = []
        if shot.get("selector_status") == "unresolved":
            action_result = _action_result(False, "截图计划包含未解析的 selector")
            shot["action_warnings"].append(action_result["message"])
        if action:
            executed = execute_action(page, action)
            if not executed["success"]:
                action_result = executed
                shot["action_warnings"].append(executed["message"])
            page.wait_for_timeout(wait_after_action)

        # 滚动
        if need_scroll:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(300)

        sc = (config or {}).get("screenshot", {})
        annotation = locate_annotation_targets(page, highlight, full_page) if highlight else {
            "requested": 0, "matched": 0, "missing": [], "targets": []
        }
        shot["annotation"] = {key: annotation[key] for key in ("requested", "matched", "missing")}
        shot["annotation_warnings"] = [
            f"未找到标注目标：{label}" for label in annotation["missing"]
        ]

        # 先保留纯页面原图，再由原图生成下游继续引用的主文件。
        output_path = os.path.join(output_dir, f"{shot_id}.png")
        original_dir = os.path.join(output_dir, "original")
        original_path = os.path.join(original_dir, f"{shot_id}.png")
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        Path(original_dir).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=original_path, full_page=full_page)
        shutil.copyfile(original_path, output_path)

        if auto_annotate and annotation["targets"]:
            if annotate_screenshot(
                original_path,
                output_path,
                annotation,
                color_value=sc.get("annotation_color", "#E53935"),
                style=sc.get("annotation_style", "numbered_arrow"),
            ):
                logging.info(f"    ✨ 已自动标注 {annotation['matched']}/{annotation['requested']} 个目标")
            else:
                shot["annotation_warnings"].append("自动标注未生成，已保留未标注截图")
        elif highlight and not auto_annotate:
            shot["annotation_warnings"].append("自动标注已禁用")

        if not sc.get("keep_original", True):
            try:
                os.remove(original_path)
            except OSError:
                pass

        shot["status"] = "captured" if action_result["success"] else "partial"
        shot["error"] = "" if action_result["success"] else action_result["message"]
        logging.info(f"    ✅ 已保存: {output_path}")

        # 后处理:合成浏览器头(仅 captured 状态,不含 partial 兜底)
        if add_chrome:
            try:
                cur_url = page.url or full_url
                # 从 config 读取头部模板图片路径和地址栏区域
                header_path = sc.get("browser_chrome_header_path")
                addr_rect = sc.get("browser_chrome_addr_rect")
                if add_browser_chrome(output_path, cur_url, "",
                                      header_path=header_path, addr_rect=addr_rect):
                    logging.info(f"    ✨ 已添加浏览器头: {output_path}")
            except Exception as e:
                logging.warning(f"    ⚠️ 浏览器头合成跳过: {e}")

    except RetryableError as e:
        shot["status"] = "failed"
        shot["error"] = f"可重试: {e}"
        logging.error(f"    ❌ 失败(可重试): {e}")

        # 兜底:即使操作失败也截当前页面
        try:
            output_path = os.path.join(output_dir, f"{shot_id}.png")
            original_dir = os.path.join(output_dir, "original")
            original_path = os.path.join(original_dir, f"{shot_id}.png")
            Path(original_dir).mkdir(parents=True, exist_ok=True)
            page.screenshot(path=original_path)
            shutil.copyfile(original_path, output_path)
            shot.setdefault("annotation", {"requested": 0, "matched": 0, "missing": []})
            shot.setdefault("annotation_warnings", [])
            shot.setdefault("action_warnings", [str(e)])
            if not ((config or {}).get("screenshot", {})).get("keep_original", True):
                os.remove(original_path)
            shot["status"] = "partial"
            logging.warning(f"    ⚠️ 已保存兜底截图(状态: partial)")
        except Exception:
            pass

    except FatalError as e:
        shot["status"] = "failed"
        shot["error"] = f"致命错误: {e}"
        logging.error(f"    ❌ 致命错误: {e}")
        raise  # 致命错误向上抛出,由 main 决定是否继续

    except Exception as e:
        shot["status"] = "failed"
        shot["error"] = f"未知错误: {e}"
        logging.error(f"    ❌ 未知错误: {e}")

    return shot


# ============================================================
# 主流程
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Playwright 批量截图采集器")
    parser.add_argument("--config", default="knowledge/screenshot-config.yaml", help="截图配置文件路径")
    parser.add_argument("--plan", default="knowledge/screenshots.yaml", help="截图计划文件路径")
    parser.add_argument("--output", default="output/screenshots", help="截图输出目录")
    parser.add_argument("--role", default=None, help="只截取指定角色的截图(默认全部)")
    parser.add_argument("--retake", dest="retake", default=None, help="Path to retake-list.yaml for selective recapture")
    # 浏览器模式:--headless 与 --headed 互斥,二选一覆盖配置;都不传则读 config
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--headed", dest="headed", action="store_true", help="使用有头浏览器(可视化),覆盖 config 中的 headless 设置")
    mode_group.add_argument("--headless", dest="headless_flag", action="store_true", help="强制使用无头模式(默认),覆盖 config 中的 headless 设置")
    parser.add_argument("--slow-mo", dest="slow_mo", type=int, default=None, help="慢动作调试(毫秒,如 500)。配合 --headed 使用")
    chrome_group = parser.add_mutually_exclusive_group()
    chrome_group.add_argument("--add-chrome", dest="add_chrome", action="store_true", help="启用浏览器头合成，覆盖配置")
    chrome_group.add_argument("--no-add-chrome", dest="add_chrome", action="store_false", help="禁用浏览器头合成，覆盖配置")
    annotation_group = parser.add_mutually_exclusive_group()
    annotation_group.add_argument("--annotate", dest="annotate", action="store_true", help="启用截图自动标注，覆盖配置")
    annotation_group.add_argument("--no-annotate", dest="annotate", action="store_false", help="禁用截图自动标注，覆盖配置")
    parser.set_defaults(annotate=None, add_chrome=None)
    args = parser.parse_args()

    # 加载配置
    config = load_config(args.config)
    plan = load_plan(args.plan)

    if not plan:
        logging.error("错误: 截图计划为空")
        sys.exit(1)

    base_url = config.get("base_url", "")  # 全局 base_url(单前端)
    screenshot_config = config.get("screenshot", {})
    viewport = screenshot_config.get("viewport", {"width": 1920, "height": 1080})
    test_accounts = config.get("test_accounts", {})

    # 决定浏览器运行模式:命令行(--headed/--headless 互斥)> 配置文件 > 默认无头
    if args.headed:
        headless = False
    elif args.headless_flag:
        headless = True
    else:
        # 配置文件中 headless 缺省为 true(无头)
        headless = screenshot_config.get("headless", True)
    # slow_mo:命令行 > 配置文件 > 默认 0
    slow_mo = args.slow_mo if args.slow_mo is not None else screenshot_config.get("slow_mo", 0)

    # 浏览器头合成:命令行 > 配置文件 > 默认关闭
    add_chrome = (args.add_chrome if args.add_chrome is not None
                  else screenshot_config.get("add_browser_chrome", False))
    # 自动标注:命令行 > 配置文件 > 默认开启
    auto_annotate = (args.annotate if args.annotate is not None
                     else screenshot_config.get("auto_annotate", True))

    mode_desc = "有头" if not headless else "无头"
    logging.info(f"浏览器模式: {mode_desc}" + (f",慢动作 {slow_mo}ms" if slow_mo else ""))
    if add_chrome:
        logging.info("已启用:截图后将合成伪造浏览器头(顶部 URL 标签)")
        if not _PILLOW_AVAILABLE:
            logging.warning("  ⚠️ 启用了 --add-chrome 但 Pillow 未安装,合成将被跳过。请运行: pip install pillow")
    if auto_annotate:
        logging.info("已启用:截图后自动绘制编号、箭头和标签")
        if not _PILLOW_AVAILABLE:
            logging.warning("  ⚠️ 自动标注需要 Pillow，当前将保留未标注截图。请运行: pip install pillow")

    # 过滤角色
    if args.role:
        plan = [s for s in plan if not s.get("roles") or args.role in s.get("roles", [])]
        if not plan:
            logging.error(f"错误: 角色 {args.role} 没有对应的截图计划")
            sys.exit(1)

    # 补拍模式:仅重新采集 retake-list.yaml 中列出的截图
    if args.retake and os.path.exists(args.retake):
        with open(args.retake, encoding="utf-8") as f:
            retake_data = yaml.safe_load(f) or {}
        retake_ids = [r["id"] for r in retake_data.get("retakes", [])]
        plan = [s for s in plan if s.get("id") in retake_ids]
        logging.info(f"补拍模式: 仅采集 {len(plan)} 张截图")

    # 导入 Playwright
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logging.error("错误: Playwright 未安装。请运行:\n  pip install playwright\n  playwright install chromium")
        sys.exit(1)

    Path(args.output).mkdir(parents=True, exist_ok=True)
    results = []

    with sync_playwright() as p:
        # 有头模式失败时的自动回退(SSH / 无 display 环境)
        launch_kwargs = {"headless": headless}
        if slow_mo:
            launch_kwargs["slow_mo"] = slow_mo
        try:
            browser = p.chromium.launch(**launch_kwargs)
        except Exception as e:
            if not headless:
                logging.warning(f"  ⚠️ 有头模式启动失败({e}),自动回退到无头模式")
                launch_kwargs["headless"] = True
                launch_kwargs.pop("slow_mo", None)
                browser = p.chromium.launch(**launch_kwargs)
            else:
                raise

        # 如果有测试账号,分角色截图;否则只截无需登录的部分
        if test_accounts:
            # 通用截图(无 roles 字段):使用第一个账号采集一次,避免每个角色重复采集
            universal_plan = [s for s in plan if not s.get("roles")]

            if universal_plan:
                first_role_name = next(iter(test_accounts))
                first_account = test_accounts[first_role_name]
                account_app = first_account.get("app", "")
                login_base_url = get_base_url(config, account_app) or base_url

                logging.info(f"\n{'='*50}")
                logging.info(f"通用截图 [{account_app or 'default'}] → {login_base_url}")
                logging.info(f"{'='*50}")

                context = browser.new_context(viewport=viewport)
                page = context.new_page()
                login_url = first_account.get("login_url", "/login")
                try:
                    login(page, login_base_url, login_url, first_account)
                    # 逐页截图(capture_screenshot 会根据每个 shot 的 app 字段自动选 base_url)
                    for shot in universal_plan:
                        result = capture_screenshot(page, shot, args.output, config,
                                                    add_chrome=add_chrome, auto_annotate=auto_annotate)
                        results.append(result)
                except Exception as e:
                    logging.error(f"  ❌ 登录失败: {e}")
                    logging.info(f"  跳过通用截图")
                    for shot in universal_plan:
                        shot["status"] = "failed"
                        shot["error"] = f"登录失败: {e}"
                        results.append(shot)
                context.close()

            # 角色专属截图:为每个账号采集其角色对应的截图(自动排除通用截图)
            for role_name, account in test_accounts.items():
                if args.role and args.role != role_name:
                    continue

                # 角色过滤:仅显式包含当前角色的截图(通用截图已在上方采集一次)
                role_plan = [s for s in plan if role_name in s.get("roles", [])]
                if not role_plan:
                    continue

                # 根据 account 的 app 字段选择登录用的 base_url
                account_app = account.get("app", "")
                login_base_url = get_base_url(config, account_app) or base_url

                logging.info(f"\n{'='*50}")
                logging.info(f"角色: {role_name} [{account_app or 'default'}] → {login_base_url}")
                logging.info(f"{'='*50}")

                context = browser.new_context(viewport=viewport)
                page = context.new_page()

                # 登录
                login_url = account.get("login_url", "/login")
                try:
                    login(page, login_base_url, login_url, account)
                except Exception as e:
                    logging.error(f"  ❌ 登录失败: {e}")
                    logging.info(f"  跳过角色 {role_name} 的截图")
                    for shot in role_plan:
                        shot["status"] = "failed"
                        shot["error"] = f"登录失败: {e}"
                        results.append(shot)
                    context.close()
                    continue

                # 逐页截图(capture_screenshot 会根据每个 shot 的 app 字段自动选 base_url)
                for shot in role_plan:
                    result = capture_screenshot(page, shot, args.output, config,
                                                add_chrome=add_chrome, auto_annotate=auto_annotate)
                    results.append(result)

                context.close()
        else:
            # 无需登录的场景
            context = browser.new_context(viewport=viewport)
            page = context.new_page()
            for shot in plan:
                result = capture_screenshot(page, shot, args.output, config,
                                            add_chrome=add_chrome, auto_annotate=auto_annotate)
                results.append(result)
            context.close()

        browser.close()

    # 按 shot id 去重(保留最后一条结果),避免通用截图被重复写入
    seen = {}
    for r in results:
        seen[r["id"]] = r
    results = list(seen.values())

    # 更新截图计划文件
    # 原子写入:先写临时文件,再 rename,避免中途失败损坏原文件
    tmp_path = args.plan + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        yaml.dump({"screenshots": results}, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    os.replace(tmp_path, args.plan)

    # 生成报告
    total = len(results)
    captured = sum(1 for r in results if r["status"] == "captured")
    partial = sum(1 for r in results if r["status"] == "partial")
    failed = sum(1 for r in results if r["status"] == "failed")

    logging.info(f"\n{'='*50}")
    logging.info(f"采集完成")
    logging.info(f"{'='*50}")
    logging.info(f"总计: {total} 张")
    logging.info(f"成功: {captured} 张")
    logging.info(f"部分: {partial} 张")
    logging.info(f"失败: {failed} 张")
    logging.info(f"成功率: {(captured + partial) / total * 100:.1f}%" if total > 0 else "无截图")

    # 保存 JSON 报告(供 screenshot-reviewer 使用)
    report_path = os.path.join(os.path.dirname(args.output), "capture-result.json")
    report_data = {
        "total": total,
        "captured": captured,
        "partial": partial,
        "failed": failed,
        "results": results,
    }
    _atomic_write_text(report_path, json.dumps(report_data, ensure_ascii=False, indent=2) + "\n")

    markdown_report_path = os.path.join(os.path.dirname(args.output), "screenshot-capture-report.md")
    _atomic_write_text(
        markdown_report_path,
        build_capture_markdown(results, total, captured, partial, failed),
    )

    logging.info(f"报告已保存: {report_path}")
    logging.info(f"人类可读报告已保存: {markdown_report_path}")


if __name__ == "__main__":
    main()
