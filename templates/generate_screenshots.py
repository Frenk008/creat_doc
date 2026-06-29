#!/usr/bin/env python3
"""
Playwright 批量截图脚本
根据 screenshots.yaml 和 screenshot-config.yaml 自动采集界面截图。

用法:
  python generate_screenshots.py --config knowledge/screenshot-config.yaml --plan knowledge/screenshots.yaml --output output/screenshots
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import yaml

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
    print(f"  正在登录: {base_url + login_url}")

    page.goto(base_url + login_url, wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(1000)

    username = account.get("username", "")
    password = account.get("password", "")

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
        raise RuntimeError("无法找到用户名输入框")

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
        raise RuntimeError(f"登录后仍在登录页: {current_url}")

    print(f"  登录成功,当前页面: {current_url}")


# ============================================================
# 操作执行器
# ============================================================

def execute_action(page, action_desc: str):
    """
    解析截图计划中的操作描述并执行。
    使用关键词匹配,覆盖常见 UI 操作。
    """
    desc = action_desc or ""

    # 点击新增
    if any(kw in desc for kw in ["新增", "添加", "创建"]):
        _try_click(page, [
            "button:has-text('新增')", "button:has-text('添加')",
            "button:has-text('新建')", "button:has-text('创建')",
            "[data-action='create']", ".add-btn", "#addBtn",
            ".el-button--primary:has-text('新增')",
        ])

    # 点击编辑
    elif any(kw in desc for kw in ["编辑", "修改"]):
        _try_click(page, [
            "button:has-text('编辑')", "button:has-text('修改')",
            ".edit-btn", "[data-action='edit']",
            "a:has-text('编辑')",
        ])

    # 点击删除
    elif "删除" in desc:
        _try_click(page, [
            "button:has-text('删除')", ".delete-btn",
            "[data-action='delete']",
        ])

    # 点击搜索/查询
    elif any(kw in desc for kw in ["搜索", "查询", "检索"]):
        _try_click(page, [
            "button:has-text('搜索')", "button:has-text('查询')",
            "button:has-text('搜索')", ".search-btn",
        ])

    # 点击导出
    elif "导出" in desc:
        _try_click(page, [
            "button:has-text('导出')", ".export-btn",
        ])

    # 点击保存/确定
    elif any(kw in desc for kw in ["保存", "确定", "提交"]):
        _try_click(page, [
            "button:has-text('保存')", "button:has-text('确定')",
            "button:has-text('提交')", "button[type='submit']",
            ".el-button--primary:has-text('确定')",
        ])

    # 点击取消/关闭
    elif any(kw in desc for kw in ["取消", "关闭"]):
        _try_click(page, [
            "button:has-text('取消')", "button:has-text('关闭')",
        ])

    else:
        print(f"    ⚠️ 未识别的操作,跳过: {desc}")


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
    print(f"    ⚠️ 所有选择器均未找到可点击元素")
    return False


# ============================================================
# 高亮元素
# ============================================================

def highlight_element(page, highlight_desc: str):
    """在截图中高亮指定元素(添加红色边框)"""
    if not highlight_desc:
        return

    # 注入 CSS 高亮样式
    page.evaluate("""
        (desc) => {
            // 移除之前的高亮
            document.querySelectorAll('.screenshot-highlight').forEach(el => {
                el.classList.remove('screenshot-highlight');
                el.style.outline = '';
            });
        }
    """)

    # 尝试匹配常见元素
    keywords = highlight_desc.split("、")
    for kw in keywords:
        kw = kw.strip()
        selectors = [
            f"button:has-text('{kw}')",
            f"input[placeholder*='{kw}']",
            f"label:has-text('{kw}')",
            f"[title='{kw}']",
            f".el-form-item:has-text('{kw}')",
        ]
        for sel in selectors:
            try:
                el = page.query_selector(sel)
                if el:
                    page.evaluate(
                        "(el) => { el.classList.add('screenshot-highlight'); el.style.outline = '3px solid red'; }",
                        el,
                    )
            except Exception:
                continue


# ============================================================
# 截图
# ============================================================

def capture_screenshot(page, shot: dict, output_dir: str, config: dict = None) -> dict:
    """
    对单个截图计划执行截图。
    根据 shot 中的 app 字段选择对应的 base_url 和 route(多前端/多主题支持)。
    返回更新后的 shot 字典(含 status 和可能的 error)。
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

    print(f"  截图 {shot_id}: [{app or 'default'}] {full_url} ({action})")

    try:
        # 导航到页面
        page.goto(full_url, wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(500)

        # 执行前置操作
        if action:
            execute_action(page, action)
            page.wait_for_timeout(wait_after_action)

        # 滚动
        if need_scroll:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(300)

        # 高亮元素
        if highlight:
            highlight_element(page, highlight)

        # 截图
        output_path = os.path.join(output_dir, f"{shot_id}.png")
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=output_path, full_page=full_page)

        shot["status"] = "captured"
        shot["error"] = ""
        print(f"    ✅ 已保存: {output_path}")

    except Exception as e:
        shot["status"] = "failed"
        shot["error"] = str(e)
        print(f"    ❌ 失败: {e}")

        # 兜底:即使操作失败也截当前页面
        try:
            output_path = os.path.join(output_dir, f"{shot_id}.png")
            page.screenshot(path=output_path)
            shot["status"] = "partial"
            print(f"    ⚠️ 已保存兜底截图(状态: partial)")
        except Exception:
            pass

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
    args = parser.parse_args()

    # 加载配置
    config = load_config(args.config)
    plan = load_plan(args.plan)

    if not plan:
        print("错误: 截图计划为空", file=sys.stderr)
        sys.exit(1)

    base_url = config.get("base_url", "")  # 全局 base_url(单前端)
    screenshot_config = config.get("screenshot", {})
    viewport = screenshot_config.get("viewport", {"width": 1920, "height": 1080})
    test_accounts = config.get("test_accounts", {})

    # 过滤角色
    if args.role:
        plan = [s for s in plan if not s.get("roles") or args.role in s.get("roles", [])]
        if not plan:
            print(f"错误: 角色 {args.role} 没有对应的截图计划", file=sys.stderr)
            sys.exit(1)

    # 补拍模式:仅重新采集 retake-list.yaml 中列出的截图
    if args.retake and os.path.exists(args.retake):
        with open(args.retake, encoding="utf-8") as f:
            retake_data = yaml.safe_load(f) or {}
        retake_ids = [r["id"] for r in retake_data.get("retakes", [])]
        plan = [s for s in plan if s.get("id") in retake_ids]
        print(f"补拍模式: 仅采集 {len(plan)} 张截图")

    # 导入 Playwright
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("错误: Playwright 未安装。请运行:\n  pip install playwright\n  playwright install chromium", file=sys.stderr)
        sys.exit(1)

    Path(args.output).mkdir(parents=True, exist_ok=True)
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # 如果有测试账号,分角色截图;否则只截无需登录的部分
        if test_accounts:
            # 通用截图(无 roles 字段):使用第一个账号采集一次,避免每个角色重复采集
            universal_plan = [s for s in plan if not s.get("roles")]

            if universal_plan:
                first_role_name = next(iter(test_accounts))
                first_account = test_accounts[first_role_name]
                account_app = first_account.get("app", "")
                login_base_url = get_base_url(config, account_app) or base_url

                print(f"\n{'='*50}")
                print(f"通用截图 [{account_app or 'default'}] → {login_base_url}")
                print(f"{'='*50}")

                context = browser.new_context(viewport=viewport)
                page = context.new_page()
                login_url = first_account.get("login_url", "/login")
                try:
                    login(page, login_base_url, login_url, first_account)
                    # 逐页截图(capture_screenshot 会根据每个 shot 的 app 字段自动选 base_url)
                    for shot in universal_plan:
                        result = capture_screenshot(page, shot, args.output, config)
                        results.append(result)
                except Exception as e:
                    print(f"  ❌ 登录失败: {e}")
                    print(f"  跳过通用截图")
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

                print(f"\n{'='*50}")
                print(f"角色: {role_name} [{account_app or 'default'}] → {login_base_url}")
                print(f"{'='*50}")

                context = browser.new_context(viewport=viewport)
                page = context.new_page()

                # 登录
                login_url = account.get("login_url", "/login")
                try:
                    login(page, login_base_url, login_url, account)
                except Exception as e:
                    print(f"  ❌ 登录失败: {e}")
                    print(f"  跳过角色 {role_name} 的截图")
                    for shot in role_plan:
                        shot["status"] = "failed"
                        shot["error"] = f"登录失败: {e}"
                        results.append(shot)
                    context.close()
                    continue

                # 逐页截图(capture_screenshot 会根据每个 shot 的 app 字段自动选 base_url)
                for shot in role_plan:
                    result = capture_screenshot(page, shot, args.output, config)
                    results.append(result)

                context.close()
        else:
            # 无需登录的场景
            context = browser.new_context(viewport=viewport)
            page = context.new_page()
            for shot in plan:
                result = capture_screenshot(page, shot, args.output, config)
                results.append(result)
            context.close()

        browser.close()

    # 按 shot id 去重(保留最后一条结果),避免通用截图被重复写入
    seen = {}
    for r in results:
        seen[r["id"]] = r
    results = list(seen.values())

    # 更新截图计划文件
    with open(args.plan, "w", encoding="utf-8") as f:
        yaml.dump({"screenshots": results}, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    # 生成报告
    total = len(results)
    captured = sum(1 for r in results if r["status"] == "captured")
    partial = sum(1 for r in results if r["status"] == "partial")
    failed = sum(1 for r in results if r["status"] == "failed")

    print(f"\n{'='*50}")
    print(f"采集完成")
    print(f"{'='*50}")
    print(f"总计: {total} 张")
    print(f"成功: {captured} 张")
    print(f"部分: {partial} 张")
    print(f"失败: {failed} 张")
    print(f"成功率: {(captured + partial) / total * 100:.1f}%" if total > 0 else "无截图")

    # 保存 JSON 报告(供 screenshot-reviewer 使用)
    report_path = os.path.join(os.path.dirname(args.output), "capture-result.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "total": total,
            "captured": captured,
            "partial": partial,
            "failed": failed,
            "results": results,
        }, f, ensure_ascii=False, indent=2)

    print(f"报告已保存: {report_path}")


if __name__ == "__main__":
    main()
