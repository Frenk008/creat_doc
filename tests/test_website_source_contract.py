import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


class WebsiteSourceContractTests(unittest.TestCase):
    def test_doc_gen_declares_source_default_and_website_restriction(self):
        skill = read(".trae/skills/doc-gen/SKILL.md")
        self.assertRegex(skill, r"--source\s+code\(默认\) / website")
        self.assertIn("website 只允许 manual", skill)
        self.assertIn("--source website` 与 `--type database/api/all", skill)

    def test_website_flow_replaces_source_explorer_dependencies(self):
        skill = read(".trae/skills/doc-gen/SKILL.md")
        self.assertIn(
            "| website | manual | runtime-explorer:bootstrap | bootstrap；--deep 时改为 enrich | runtime-explorer:bootstrap, diagram-generator；--deep 时同时等待 enrich |",
            skill,
        )
        self.assertIn("runtime-explorer:bootstrap", skill)
        self.assertIn("runtime-explorer:enrich (仅 --deep)", skill)
        self.assertIn("diagram-generator 必须等待 enrich 完成", skill)

    def test_dry_run_exits_before_mutating_setup(self):
        skill = read(".trae/skills/doc-gen/SKILL.md")
        dry_run_exit = skill.index("`--dry-run` 必须在任何文件写入")
        cache_check = skill.index("### Step 2: 缓存检查")
        self.assertLess(dry_run_exit, cache_check)
        self.assertIn("非 dry-run 才初始化 `.gitignore`", skill)
        self.assertIn("凭据解析和目标网站访问前退出", skill)

    def test_user_guide_matches_website_contract(self):
        guide = read("DOC-GEN-SKILL-使用指南.md")
        self.assertIn(
            "/doc-gen --source website --type manual --stage runtime", guide
        )
        self.assertIn("### 6.4 网站冷启动探索", guide)
        self.assertIn("`runtime-explorer:bootstrap` 是例外", guide)
        self.assertIn("Skill 本身不会绕过认证", guide)
        self.assertNotIn("验证码或 MFA 通常需要测试环境绕过方案", guide)

    def test_runtime_bootstrap_has_no_project_explorer_dependency(self):
        skill = read(".trae/skills/runtime-explorer/SKILL.md")
        bootstrap_contract = skill.split("bootstrap:", 1)[1].split("enrich:", 1)[0]
        self.assertIn("depends_on: []", bootstrap_contract)
        self.assertIn("knowledge/screenshot-config.yaml", bootstrap_contract)

    def test_runtime_explorer_is_strictly_read_only(self):
        skill = read(".trae/skills/runtime-explorer/SKILL.md")
        bootstrap = read(".trae/skills/runtime-explorer/references/bootstrap-mode.md")
        self.assertNotIn("提交空表单", skill)
        self.assertIn("不得执行保存、删除、确认业务操作、上传、导出或任何表单提交", skill)
        self.assertIn("不确定控件是否会修改数据时，视为禁止操作", bootstrap)
        self.assertIn("禁止保存、删除、确认业务操作、上传文件、提交任何表单、导出", bootstrap)

    def test_schema_and_consumers_support_website_source(self):
        schema = read("templates/pkb-schema.yaml")
        writer = read(".trae/skills/manual-writer/SKILL.md")
        reviewer = read(".trae/skills/qa-reviewer/SKILL.md")
        self.assertIn('source_type: "code"', schema)
        self.assertIn('project.source_type: website', writer)
        self.assertIn("已观察范围", reviewer)

    def test_runtime_timestamp_is_excluded_from_stable_cache(self):
        planner = read(".trae/skills/screenshot-planner/SKILL.md")
        details = read(".trae/skills/doc-gen/references/orchestration-details.md")
        self.assertIn("排除 _meta.yaml.explored_at", planner)
        self.assertIn("website bootstrap 不使用缓存", details)

    def test_skill_entrypoints_stay_within_progressive_disclosure_limit(self):
        for relative_path in (
            ".trae/skills/runtime-explorer/SKILL.md",
            ".trae/skills/doc-gen/SKILL.md",
        ):
            with self.subTest(relative_path=relative_path):
                self.assertLessEqual(len(read(relative_path).splitlines()), 500)

    def test_fixture_contains_role_difference_and_mutation_traps(self):
        fixture = read("tests/fixtures/website-bootstrap.html")
        self.assertIn('data-role="admin-only"', fixture)
        self.assertIn('href="#/users"', fixture)
        self.assertGreaterEqual(len(re.findall(r'data-mutation-trap="true"', fixture)), 3)


if __name__ == "__main__":
    unittest.main()
