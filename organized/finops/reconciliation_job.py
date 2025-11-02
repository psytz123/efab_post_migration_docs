#!/usr/bin/env python3
"""FinOps reconciliation job prototype.

The job loads allocation policy weights, applies them to cost records, and
emits a JSON summary suitable for S3/Slack handoff.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
from pathlib import Path
from typing import Any, Dict, List

from organized.finops.allocation import AllocationBreakdown, AllocationEngine, CostRecord, load_policy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run FinOps cost allocation reconciliation.")
    parser.add_argument("--policy", type=Path, required=True, help="Path to allocation_policy.yaml")
    parser.add_argument("--actuals", type=Path, required=True, help="Path to actuals JSON payload")
    parser.add_argument("--output", type=Path, help="Optional path to write reconciliation report JSON")
    return parser.parse_args()


def load_actuals(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def to_cost_records(records: List[Dict[str, Any]]) -> List[CostRecord]:
    return [
        CostRecord(
            identifier=record["identifier"],
            units_produced=float(record["units_produced"]),
            direct_costs=record.get("direct_costs", {}),
            drivers=record.get("drivers", {}),
            target_unit_cost=record.get("target_unit_cost"),
        )
        for record in records
    ]


def summarise_variance(
    breakdowns: List[AllocationBreakdown],
    variance_threshold: float,
) -> Dict[str, Any]:
    breaches = [
        {
            "identifier": item.identifier,
            "variance": item.variance,
            "unit_cost": item.unit_cost,
        }
        for item in breakdowns
        if item.variance is not None and abs(item.variance) > variance_threshold
    ]
    return {
        "breaches": breaches,
        "breach_count": len(breaches),
        "status": "ok" if not breaches else "attention_required",
    }


def main() -> None:
    args = parse_args()
    policy = load_policy(args.policy)
    actuals = load_actuals(args.actuals)

    engine = AllocationEngine(policy)
    breakdowns = engine.allocate(
        records=to_cost_records(actuals.get("records", [])),
        shared_metrics=actuals.get("shared_metrics", {}),
        capital_projects=actuals.get("capital_projects"),
    )

    variance_threshold = float(policy.get("variance_thresholds", {}).get("unit_cost", 0.05))
    summary = summarise_variance(breakdowns, variance_threshold)

    report = {
        "policy_version": policy.get("version"),
        "variance_summary": summary,
        "breakdowns": [dataclasses.asdict(item) for item in breakdowns],
    }

    payload = json.dumps(report, indent=2, sort_keys=True)

    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload)


if __name__ == "__main__":
    main()
