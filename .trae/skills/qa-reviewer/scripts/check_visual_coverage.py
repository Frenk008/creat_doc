#!/usr/bin/env python3
"""Audit whether state-changing manual steps have screenshot placeholders."""

import argparse
import json
import os
import re
from pathlib import Path


HEADING_RE = re.compile(r"^#{2,4}\s+(.+?)\s*$")
STEP_RE = re.compile(r"^步骤(?P<number>\d+)[：:]\s*(?P<text>.+?)\s*$")
PLACEHOLDER_RE = re.compile(r"【图片：(?P<key>[^】]+)】（截图占位，后续补充）")
PLACEHOLDER_STEP_RE = re.compile(r"步骤(?P<number>\d+)(?:-(?P<state>.+))?")
DIRECT_STATE_CHANGE_RE = re.compile(
    r"进入|跳转|打开|点击|弹出|展开|切换|提交|保存|确认|搜索|查询|重置|"
    r"发送|重试|取消|终止|上架|下架|删除|登录|回复"
)
INPUT_RE = re.compile(r"输入|填写|选择|勾选|上传|修改|设置")


def is_visual_checkpoint(step_text: str) -> bool:
    return bool(DIRECT_STATE_CHANGE_RE.search(step_text or ""))


def mark_checkpoints(steps: list) -> None:
    """标记直接状态变化，以及连续输入动作组的最后一步。"""
    for index, step in enumerate(steps):
        text = step.get("text", "")
        direct = is_visual_checkpoint(text)
        is_input = bool(INPUT_RE.search(text))
        next_is_input = (
            index + 1 < len(steps) and
            bool(INPUT_RE.search(steps[index + 1].get("text", ""))) and
            not is_visual_checkpoint(steps[index + 1].get("text", ""))
        )
        step["checkpoint"] = direct or (is_input and not next_is_input)
        if direct:
            step["checkpoint_reason"] = "visible_state_change"
        elif is_input and not next_is_input:
            step["checkpoint_reason"] = "input_group_complete"
        else:
            step["checkpoint_reason"] = ""


def audit_markdown(content: str) -> dict:
    sections = []
    current = {"title": "未命名章节", "steps": [], "placeholders": []}

    def flush():
        if current["steps"]:
            mark_checkpoints(current["steps"])
            checkpoints = [s for s in current["steps"] if s["checkpoint"]]
            missing = []
            for index, step in enumerate(current["steps"]):
                if not step["checkpoint"]:
                    continue
                next_line = (
                    current["steps"][index + 1]["line"]
                    if index + 1 < len(current["steps"])
                    else float("inf")
                )
                valid = [
                    p for p in current["placeholders"]
                    if p["number"] == step["number"] and p["state"] and
                    step["line"] < p["line"] < next_line
                ]
                if not valid:
                    missing.append(step)
            invalid = [p for p in current["placeholders"] if not p["state"]]
            sections.append({
                "title": current["title"],
                "step_count": len(current["steps"]),
                "checkpoint_count": len(checkpoints),
                "placeholder_count": len(current["placeholders"]),
                "missing": missing,
                "invalid_placeholders": invalid,
            })

    for line_number, line in enumerate(content.splitlines(), 1):
        heading = HEADING_RE.match(line.strip())
        if heading:
            flush()
            current = {"title": heading.group(1), "steps": [], "placeholders": []}
            continue
        step = STEP_RE.match(line.strip())
        if step:
            current["steps"].append({
                "number": int(step.group("number")),
                "text": step.group("text"),
                "line": line_number,
            })
        for placeholder in PLACEHOLDER_RE.finditer(line):
            number = PLACEHOLDER_STEP_RE.search(placeholder.group("key"))
            if number:
                current["placeholders"].append({
                    "number": int(number.group("number")),
                    "state": (number.group("state") or "").strip(),
                    "key": placeholder.group("key"),
                    "line": line_number,
                })
    flush()

    missing = [
        {"section": section["title"], **step}
        for section in sections for step in section["missing"]
    ]
    invalid_placeholders = [
        {"section": section["title"], **placeholder}
        for section in sections for placeholder in section["invalid_placeholders"]
    ]
    return {
        "section_count": len(sections),
        "step_count": sum(s["step_count"] for s in sections),
        "checkpoint_count": sum(s["checkpoint_count"] for s in sections),
        "placeholder_count": sum(s["placeholder_count"] for s in sections),
        "missing_count": len(missing) + len(invalid_placeholders),
        "missing": missing,
        "invalid_placeholder_count": len(invalid_placeholders),
        "invalid_placeholders": invalid_placeholders,
        "sections": sections,
    }


def atomic_write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(content, encoding="utf-8", newline="\n")
    os.replace(tmp_path, path)


def main():
    parser = argparse.ArgumentParser(description="检查用户手册关键 UI 状态截图覆盖率")
    parser.add_argument("--manual", default="output/manual.md")
    parser.add_argument("--output", default="output/visual-coverage-report.json")
    args = parser.parse_args()

    content = Path(args.manual).read_text(encoding="utf-8-sig")
    report = audit_markdown(content)
    atomic_write(Path(args.output), json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        f"steps={report['step_count']} checkpoints={report['checkpoint_count']} "
        f"placeholders={report['placeholder_count']} missing={report['missing_count']}"
    )
    for item in report["missing"]:
        print(f"missing: {item['section']} 步骤{item['number']} {item['text']}")
    for item in report["invalid_placeholders"]:
        print(f"invalid placeholder: {item['section']} {item['key']} (缺少界面状态名)")
    raise SystemExit(1 if report["missing_count"] else 0)


if __name__ == "__main__":
    main()
