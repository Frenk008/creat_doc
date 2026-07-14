import importlib.util
import tempfile
import unittest
from pathlib import Path

import yaml
from PIL import Image


ROOT = Path(__file__).parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCREENSHOTS = load_module("flow_screenshots", ROOT / "templates" / "generate_screenshots.py")
PREPARE = load_module(
    "prepare_markdown",
    ROOT / ".trae" / "skills" / "document-renderer" / "scripts" / "prepare_markdown.py",
)
VISUAL_COVERAGE = load_module(
    "check_visual_coverage",
    ROOT / ".trae" / "skills" / "qa-reviewer" / "scripts" / "check_visual_coverage.py",
)
MEASURE = load_module("measure_addr_rect", ROOT / "measure_addr_rect.py")


class FakeElement:
    def __init__(self, visible=True):
        self.visible = visible
        self.value = None

    def is_visible(self):
        return self.visible

    def fill(self, value):
        self.value = value


class ActionPage:
    def __init__(self, elements=None):
        self.elements = elements or {}

    def query_selector(self, selector):
        return self.elements.get(selector)

    def wait_for_timeout(self, _milliseconds):
        return None


class FlowIntegrityTests(unittest.TestCase):
    def test_visual_coverage_reports_missing_state_changing_steps(self):
        report = VISUAL_COVERAGE.audit_markdown(
            "## 5.1 联系管理\n"
            "步骤1：进入联系管理页面。\n"
            "【图片：联系管理-步骤1-咨询列表】（截图占位，后续补充）\n"
            "步骤2：点击「查看」按钮打开详情。\n"
            "步骤3：阅读联系信息。\n"
        )
        self.assertEqual(report["checkpoint_count"], 2)
        self.assertEqual(report["missing_count"], 1)
        self.assertEqual(report["missing"][0]["number"], 2)

    def test_visual_coverage_accepts_multiple_states_on_same_route(self):
        report = VISUAL_COVERAGE.audit_markdown(
            "## 5.1 联系管理\n"
            "步骤1：进入联系管理页面。\n"
            "【图片：联系管理-步骤1-咨询列表】（截图占位，后续补充）\n"
            "步骤2：点击「查看」按钮打开详情。\n"
            "【图片：联系管理-步骤2-联系详情弹窗】（截图占位，后续补充）\n"
        )
        self.assertEqual(report["missing_count"], 0)

    def test_visual_coverage_requires_placeholder_before_next_step(self):
        report = VISUAL_COVERAGE.audit_markdown(
            "## 5.1 联系管理\n"
            "步骤1：进入联系管理页面。\n"
            "步骤2：点击「查看」按钮打开详情。\n"
            "【图片：联系管理-步骤1-咨询列表】（截图占位，后续补充）\n"
            "【图片：联系管理-步骤2-联系详情弹窗】（截图占位，后续补充）\n"
        )
        self.assertEqual(report["missing_count"], 1)
        self.assertEqual(report["missing"][0]["number"], 1)

    def test_visual_coverage_requires_state_name(self):
        report = VISUAL_COVERAGE.audit_markdown(
            "## 5.1 联系管理\n"
            "步骤1：进入联系管理页面。\n"
            "【图片：联系管理-步骤1】（截图占位，后续补充）\n"
        )
        self.assertEqual(report["invalid_placeholder_count"], 1)
        self.assertEqual(report["missing_count"], 2)

    def test_visual_coverage_collapses_continuous_input_group(self):
        report = VISUAL_COVERAGE.audit_markdown(
            "## 5.2 创建用户\n"
            "步骤1：填写用户名。\n"
            "步骤2：输入手机号。\n"
            "步骤3：选择用户角色。\n"
            "【图片：创建用户-步骤3-表单填写完成】（截图占位，后续补充）\n"
            "步骤4：点击「保存」按钮。\n"
            "【图片：创建用户-步骤4-保存成功】（截图占位，后续补充）\n"
        )
        self.assertEqual(report["checkpoint_count"], 2)
        self.assertEqual(report["missing_count"], 0)

    def test_structured_action_reports_missing_target(self):
        result = SCREENSHOTS.execute_action(
            ActionPage(), {"type": "click", "selector": "#missing"}
        )
        self.assertFalse(result["success"])
        self.assertIn("不可见", result["message"])

    def test_structured_fill_action(self):
        element = FakeElement()
        result = SCREENSHOTS.execute_action(
            ActionPage({"#name": element}),
            {"type": "fill", "selector": "#name", "value": "测试用户"},
        )
        self.assertTrue(result["success"])
        self.assertEqual(element.value, "测试用户")

    def test_capture_markdown_contains_action_and_annotation_warnings(self):
        report = SCREENSHOTS.build_capture_markdown(
            [{
                "id": "shot-1", "status": "partial", "error": "",
                "annotation": {"requested": 2, "matched": 1},
                "action_warnings": ["未找到按钮"],
                "annotation_warnings": ["未找到标注目标：表格"],
            }],
            1, 0, 1, 0,
        )
        self.assertIn("1/2", report)
        self.assertIn("未找到按钮；未找到标注目标：表格", report)

    def test_measure_config_preserves_screenshot_nesting(self):
        original = "screenshot:\n  add_browser_chrome: true\n  browser_chrome_addr_rect: [0, 0, 1, 1]\n"
        updated = MEASURE.update_config_content(original, [0.1, 0.2, 0.8, 0.9])
        data = yaml.safe_load(updated)
        self.assertEqual(data["screenshot"]["browser_chrome_addr_rect"], [0.1, 0.2, 0.8, 0.9])
        self.assertNotIn("browser_chrome_addr_rect", {k: v for k, v in data.items() if k != "screenshot"})

    def test_renderer_replaces_only_available_screenshots(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            screenshots = root / "screenshots"
            screenshots.mkdir()
            Image.new("RGB", (20, 20), "white").save(screenshots / "shot-1.png")
            plan = root / "screenshots.yaml"
            plan.write_text(yaml.safe_dump({"screenshots": [{
                "id": "shot-1", "placeholder": "创建用户-步骤3", "status": "captured"
            }]}, allow_unicode=True), encoding="utf-8")
            mapping = PREPARE.build_image_map(plan, screenshots, root)
            result, replaced, missing = PREPARE.replace_placeholders(
                "【图片：创建用户-步骤3】（截图占位，后续补充）\n"
                "【图片：删除用户-步骤1】（截图占位，后续补充）",
                mapping,
            )
            self.assertEqual(replaced, 1)
            self.assertEqual(missing, ["删除用户-步骤1"])
            self.assertIn("![创建用户-步骤3](screenshots/shot-1.png)", result)
            self.assertIn("【图片：删除用户-步骤1】", result)


if __name__ == "__main__":
    unittest.main()
