import importlib.util
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageChops


MODULE_PATH = Path(__file__).parents[1] / "templates" / "generate_screenshots.py"
SPEC = importlib.util.spec_from_file_location("generate_screenshots", MODULE_PATH)
SCREENSHOTS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCREENSHOTS)


class FakePage:
    url = "http://example.test/users"

    def goto(self, *_args, **_kwargs):
        return None

    def wait_for_timeout(self, *_args, **_kwargs):
        return None

    def add_style_tag(self, **_kwargs):
        return None

    def evaluate(self, _script, payload=None):
        if isinstance(payload, dict) and "label" in payload:
            if payload["label"] == "缺失按钮":
                return None
            offset = 400 if payload.get("fullPage") else 0
            return {"x": 120, "y": 90 + offset, "width": 160, "height": 48}
        return None

    def screenshot(self, path, full_page=False):
        height = 900 if full_page else 600
        Image.new("RGB", (900, height), "white").save(path)


class AnnotationTests(unittest.TestCase):
    def test_split_targets_supports_all_delimiters_and_deduplicates(self):
        self.assertEqual(
            SCREENSHOTS.split_highlight_targets("新增按钮、搜索框，表格,新增按钮"),
            ["新增按钮", "搜索框", "表格"],
        )
        self.assertEqual(SCREENSHOTS.split_highlight_targets(""), [])

    def test_locate_targets_preserves_requested_numbering_and_missing(self):
        result = SCREENSHOTS.locate_annotation_targets(
            FakePage(), "新增按钮、缺失按钮、搜索框", full_page=True
        )
        self.assertEqual(result["requested"], 3)
        self.assertEqual(result["matched"], 2)
        self.assertEqual(result["missing"], ["缺失按钮"])
        self.assertEqual([t["index"] for t in result["targets"]], [1, 3])
        self.assertEqual(result["targets"][0]["y"], 490)

    def test_annotate_screenshot_draws_and_keeps_canvas_size(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source.png"
            output = Path(temp) / "output.png"
            Image.new("RGB", (640, 420), "white").save(source)
            annotation = {
                "targets": [
                    {"index": 1, "label": "左上", "x": 2, "y": 2, "width": 60, "height": 30},
                    {"index": 2, "label": "很长的标签文字用于测试自动截断和碰撞处理", "x": 560, "y": 370, "width": 70, "height": 35},
                ]
            }
            self.assertTrue(SCREENSHOTS.annotate_screenshot(str(source), str(output), annotation))
            original = Image.open(source)
            annotated = Image.open(output)
            self.assertEqual(annotated.size, original.size)
            self.assertIsNotNone(ImageChops.difference(original, annotated).getbbox())

    def test_capture_keeps_original_and_warns_for_missing_target(self):
        with tempfile.TemporaryDirectory() as temp:
            shot = {
                "id": "shot-1",
                "route": "/users",
                "highlight": "新增按钮、缺失按钮",
            }
            config = {
                "base_url": "http://example.test",
                "screenshot": {
                    "keep_original": True,
                    "auto_annotate": True,
                    "annotation_style": "numbered_arrow",
                    "annotation_color": "#E53935",
                },
            }
            result = SCREENSHOTS.capture_screenshot(
                FakePage(), shot, temp, config, auto_annotate=True
            )
            original_path = Path(temp) / "original" / "shot-1.png"
            final_path = Path(temp) / "shot-1.png"
            self.assertEqual(result["status"], "captured")
            self.assertEqual(result["annotation"], {
                "requested": 2, "matched": 1, "missing": ["缺失按钮"]
            })
            self.assertEqual(result["annotation_warnings"], ["未找到标注目标：缺失按钮"])
            self.assertTrue(original_path.exists())
            self.assertTrue(final_path.exists())
            self.assertIsNotNone(ImageChops.difference(
                Image.open(original_path), Image.open(final_path)
            ).getbbox())

    def test_real_browser_end_to_end_when_playwright_is_available(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest("Playwright Python package is not installed")

        fixture_url = (Path(__file__).parent / "fixtures" / "annotation.html").resolve().as_uri()
        with tempfile.TemporaryDirectory() as temp:
            try:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(headless=True)
                    context = browser.new_context(viewport={"width": 1000, "height": 700})
                    page = context.new_page()
                    result = SCREENSHOTS.capture_screenshot(
                        page,
                        {
                            "id": "browser-shot",
                            "route": fixture_url,
                            "highlight": "新增按钮、搜索框、导出数据、用户列表表格、缺失元素",
                        },
                        temp,
                        {"screenshot": {"keep_original": True, "annotation_color": "#E53935"}},
                        auto_annotate=True,
                    )
                    context.close()
                    browser.close()
            except Exception as exc:
                if "Executable doesn't exist" in str(exc):
                    self.skipTest("Playwright Chromium is not installed")
                raise

            self.assertEqual(result["status"], "captured")
            self.assertEqual(result["annotation"]["requested"], 5)
            self.assertEqual(result["annotation"]["matched"], 4)
            self.assertEqual(result["annotation"]["missing"], ["缺失元素"])
            original = Image.open(Path(temp) / "original" / "browser-shot.png")
            annotated = Image.open(Path(temp) / "browser-shot.png")
            self.assertIsNotNone(ImageChops.difference(original, annotated).getbbox())

    def test_same_route_can_capture_dialog_state_with_replay_actions(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest("Playwright Python package is not installed")

        fixture_url = (Path(__file__).parent / "fixtures" / "annotation.html").resolve().as_uri()
        with tempfile.TemporaryDirectory() as temp:
            try:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(headless=True)
                    page = browser.new_page(viewport={"width": 1000, "height": 700})
                    result = SCREENSHOTS.capture_screenshot(
                        page,
                        {
                            "id": "dialog-shot",
                            "route": fixture_url,
                            "placeholder": "联系管理-步骤2-联系详情弹窗",
                            "state_type": "dialog",
                            "selector_status": "resolved",
                            "action": [
                                {"type": "click", "selector": "#view-detail"},
                                {"type": "wait_for", "selector": "[role='dialog']", "state": "visible"},
                            ],
                            "highlight": "联系详情",
                        },
                        temp,
                        {"screenshot": {"keep_original": True}},
                        auto_annotate=True,
                    )
                    browser.close()
            except Exception as exc:
                if "Executable doesn't exist" in str(exc):
                    self.skipTest("Playwright Chromium is not installed")
                raise

            self.assertEqual(result["status"], "captured")
            self.assertEqual(result["action_warnings"], [])
            self.assertEqual(result["annotation"]["matched"], 1)


if __name__ == "__main__":
    unittest.main()
