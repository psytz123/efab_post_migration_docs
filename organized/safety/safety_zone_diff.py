#!/usr/bin/env python3
"""Safety zone diff utility.

This script compares safety zone definitions from two configuration files
(Task API JSON vs Edge YAML) and reports mismatches.

Usage:
    python safety_zone_diff.py --task-api task_api.json --edge edge_config.yaml

The tool focuses on structures containing `safety_zone`, `safety_zones`, or
`safety.zones` keys. It falls back to a recursive diff for arbitrary data.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

try:
    import yaml  # type: ignore
except ImportError as exc:  # pragma: no cover - dependency check
    raise SystemExit("PyYAML is required: pip install pyyaml") from exc


def load_config(path: Path) -> Any:
    """Load JSON or YAML configuration."""
    data = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix in {".json"}:
        return json.loads(data)
    if suffix in {".yml", ".yaml"}:
        return yaml.safe_load(data)
    raise ValueError(f"Unsupported file type: {path}")


def extract_safety_zones(config: Any) -> Dict[str, Any]:
    """Extract safety zone definitions if present."""
    if isinstance(config, dict):
        if "safety_zones" in config and isinstance(config["safety_zones"], dict):
            return config["safety_zones"]
        if "safetyZone" in config and isinstance(config["safetyZone"], dict):
            return config["safetyZone"]
        if "safety" in config and isinstance(config["safety"], dict):
            safety = config["safety"]
            if isinstance(safety.get("zones"), dict):
                return safety["zones"]
    return {}


def diff_dict(left: Any, right: Any, prefix: str = "") -> Iterable[Tuple[str, Any, Any]]:
    """Yield differences between two nested dictionaries/lists."""
    if isinstance(left, dict) and isinstance(right, dict):
        keys = set(left) | set(right)
        for key in sorted(keys):
            sub_prefix = f"{prefix}.{key}" if prefix else str(key)
            if key not in left:
                yield (sub_prefix, None, right[key])
            elif key not in right:
                yield (sub_prefix, left[key], None)
            else:
                yield from diff_dict(left[key], right[key], sub_prefix)
    elif isinstance(left, list) and isinstance(right, list):
        max_len = max(len(left), len(right))
        for idx in range(max_len):
            sub_prefix = f"{prefix}[{idx}]"
            if idx >= len(left):
                yield (sub_prefix, None, right[idx])
            elif idx >= len(right):
                yield (sub_prefix, left[idx], None)
            else:
                yield from diff_dict(left[idx], right[idx], sub_prefix)
    else:
        if left != right:
            yield (prefix, left, right)


def _suggest_remediation(path: str, task_value: Any, edge_value: Any) -> str:
    """Provide a remediation hint for a mismatched path."""
    if task_value is None and edge_value is None:
        return f"Review `{path}` – both Task API and Edge values missing; confirm zone definitions."
    if task_value is None:
        return (
            f"Add `{path}` to the Task API configuration or decommission it from the Edge config "
            "if obsolete."
        )
    if edge_value is None:
        return (
            f"Push `{path}` changes to the Edge configuration before OTA rollout to align with the "
            "Task API."
        )
    return (
        f"Reconcile `{path}` values (`task={task_value}` vs `edge={edge_value}`) and update both "
        "sources to match."
    )


def generate_report(task_config: Any, edge_config: Any) -> Dict[str, Any]:
    """Generate comparison report between Task API and Edge configurations."""
    task_zones = extract_safety_zones(task_config)
    edge_zones = extract_safety_zones(edge_config)

    report: Dict[str, Any] = {
        "task_zones_found": bool(task_zones),
        "edge_zones_found": bool(edge_zones),
        "zone_diffs": [],
        "raw_diffs": [],
    }

    zone_diffs = [
        {"path": path, "task": left, "edge": right}
        for path, left, right in diff_dict(task_zones, edge_zones)
    ] if (task_zones or edge_zones) else []
    report["zone_diffs"] = zone_diffs

    report["raw_diffs"] = [
        {"path": path, "task": left, "edge": right}
        for path, left, right in diff_dict(task_config, edge_config)
    ]

    report["remediations"] = [
        {
            "path": diff["path"],
            "suggestion": _suggest_remediation(diff["path"], diff["task"], diff["edge"]),
        }
        for diff in zone_diffs
    ]

    report["summary"] = {
        "zone_diff_count": len(zone_diffs),
        "raw_diff_count": len(report["raw_diffs"]),
        "status": "ok" if not zone_diffs else "action_required",
    }

    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare Task API and Edge safety zones")
    parser.add_argument("--task-api", type=Path, required=True, help="Path to Task API config (JSON/YAML)")
    parser.add_argument("--edge", type=Path, required=True, help="Path to Edge config (JSON/YAML)")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print report")
    parser.add_argument(
        "--fail-on-diff",
        action="store_true",
        help="Exit with code 2 when safety zone mismatches are detected (for CI pipelines).",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print a human-readable summary alongside the JSON report.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    task_config = load_config(args.task_api)
    edge_config = load_config(args.edge)
    report = generate_report(task_config, edge_config)

    if args.pretty:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(json.dumps(report))

    if args.summary:
        summary = report["summary"]
        print(
            f"[SUMMARY] status={summary['status']} zone_diffs={summary['zone_diff_count']} "
            f"raw_diffs={summary['raw_diff_count']}"
        )

    if args.fail_on_diff and report["zone_diffs"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
