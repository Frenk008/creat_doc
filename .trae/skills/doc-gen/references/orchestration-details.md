# 编排细节

## Dry-run 输出

`--dry-run` 使用下列表格结构，并在输出后直接退出：

| Skill | 阶段 | 会执行? | 缓存命中? | depends_on |
|-------|------|---------|-----------|------------|
| project-explorer | explorer | ✅ | ❌ | — |
| diagram-generator | diagram | ✅ | ❌ | project-explorer |
| manual-writer | writer | ✅ | ❌ | project-explorer, diagram-generator |
| qa-reviewer | review | ✅ | ❌ | manual-writer |
| screenshot-planner | screenshot | ✅ | ❌ | qa-reviewer |
| webapp-testing | screenshot | ✅ | ❌ | screenshot-planner |
| screenshot-reviewer | screenshot | ✅ | ❌ | webapp-testing |
| document-renderer | render | ✅ | ❌ | screenshot-reviewer |

按 source/type/stage 过滤行。缓存目录为空时显示“❌（无缓存）”，否则显示“?（需检查）”。website bootstrap 固定显示“—（线上状态，每次执行）”。

## 缓存辅助算法

```python
import hashlib
import json
from pathlib import Path

def collect_hash(patterns: list[str]) -> str:
    current = {}
    for pattern in patterns:
        for path in Path(".").glob(pattern):
            if path.is_file():
                current[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return json.dumps(current, sort_keys=True)

def check_cache(skill_name: str, patterns: list[str], cache_dir: str = ".cache") -> bool:
    cache_file = Path(cache_dir) / f"{skill_name}.hash"
    return cache_file.exists() and cache_file.read_text(encoding="utf-8") == collect_hash(patterns)

def save_cache(skill_name: str, patterns: list[str], cache_dir: str = ".cache") -> None:
    cache_file = Path(cache_dir) / f"{skill_name}.hash"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(collect_hash(patterns), encoding="utf-8")
```

检查阶段不得写缓存。只有 Skill 执行成功且 outputs 验证通过后才能调用 `save_cache`。

## 稳定字段

- `webapp-testing` 缓存只取截图计划的 `id/route/state_name/state_type/action/highlight/full_page/roles` 与截图配置，不对执行后状态字段求哈希。
- runtime 稳定缓存排除 `_meta.yaml.explored_at`，保留 mode/status/account_roles/uncovered_roles/explored_pages/skipped_pages/failures 与结构化发现。
- website bootstrap 不使用缓存；线上状态无法由本地文件哈希证明未变化。
