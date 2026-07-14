#!/usr/bin/env python3
"""Resolve manual screenshot placeholders to captured images before rendering."""

import argparse
import os
import re
from pathlib import Path

import yaml


PLACEHOLDER_RE = re.compile(r"【图片：(?P<key>[^】]+)】（截图占位，后续补充）")


def normalize_key(value: str) -> str:
    value = re.sub(r"^\s*\d+(?:\.\d+)*\s*", "", value or "")
    return re.sub(r"[\s—–-]+", "", value).lower()


def build_image_map(plan_path: Path, screenshots_dir: Path, markdown_dir: Path) -> dict:
    data = yaml.safe_load(plan_path.read_text(encoding="utf-8")) or {}
    mapping = {}
    for shot in data.get("screenshots", []):
        if shot.get("status") not in {"captured", "partial", "reviewed"}:
            continue
        image_path = screenshots_dir / f"{shot.get('id', '')}.png"
        if not image_path.is_file():
            continue
        relative_path = Path(os.path.relpath(image_path, markdown_dir)).as_posix()
        keys = [shot.get("placeholder", ""), shot.get("manual_ref", "")]
        for key in keys:
            if key:
                mapping[normalize_key(key)] = (relative_path, key)
    return mapping


def replace_placeholders(markdown: str, mapping: dict) -> tuple[str, int, list]:
    replaced = 0
    missing = []

    def replace(match):
        nonlocal replaced
        key = match.group("key").strip()
        item = mapping.get(normalize_key(key))
        if not item:
            missing.append(key)
            return match.group(0)
        image_path, _ = item
        replaced += 1
        return f"![{key}]({image_path})"

    return PLACEHOLDER_RE.sub(replace, markdown), replaced, missing


def atomic_write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(content, encoding="utf-8", newline="\n")
    os.replace(tmp_path, path)


def main():
    parser = argparse.ArgumentParser(description="将手册截图占位符替换为已采集图片")
    parser.add_argument("--input", default="output/manual.md")
    parser.add_argument("--plan", default="knowledge/screenshots.yaml")
    parser.add_argument("--screenshots", default="output/screenshots")
    parser.add_argument("--output", default="output/manual.render.md")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    mapping = build_image_map(Path(args.plan), Path(args.screenshots), output_path.parent)
    content = input_path.read_text(encoding="utf-8-sig")
    resolved, replaced, missing = replace_placeholders(content, mapping)
    atomic_write(output_path, resolved)
    print(f"resolved={replaced} missing={len(missing)} output={output_path}")
    for key in missing:
        print(f"warning: missing screenshot for {key}")


if __name__ == "__main__":
    main()
