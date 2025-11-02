import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from organized.finops.allocation import (
    AllocationBreakdown,
    AllocationEngine,
    CostRecord,
    PolicyValidationError,
    export_breakdowns,
    load_policy,
)


def sample_policy():
    return {
        "version": "test",
        "allocation_weights": {
            "direct": {"material": 1.0, "labor": 1.0},
            "shared": {
                "energy": {
                    "metric": "energy_cost",
                    "driver": "runtime_minutes",
                    "weight": 1.0,
                }
            },
        },
        "variance_thresholds": {"unit_cost": 0.05},
    }


def test_allocate_breakdown_with_shared_and_capital() -> None:
    policy = sample_policy()
    engine = AllocationEngine(policy)
    records = [
        CostRecord(
            identifier="cell-a",
            units_produced=10,
            direct_costs={"material": 100, "labor": 50},
            drivers={"runtime_minutes": 60},
            target_unit_cost=20,
        ),
        CostRecord(
            identifier="cell-b",
            units_produced=5,
            direct_costs={"material": 60, "labor": 30},
            drivers={"runtime_minutes": 40},
            target_unit_cost=18,
        ),
    ]
    shared_metrics = {"energy_cost": 100}
    capital_projects = [{"amortized_monthly_cost": 200}]

    breakdowns = engine.allocate(records, shared_metrics, capital_projects)

    assert len(breakdowns) == 2

    first = breakdowns[0]
    assert pytest.approx(first.direct_total) == 150.0
    assert pytest.approx(first.shared_total) == 60.0  # 60% of energy cost
    assert pytest.approx(first.capital_total) == 120.0  # 60% of capital
    assert pytest.approx(first.unit_cost, rel=1e-4) == (150 + 60 + 120) / 10
    assert first.variance is not None

    second = breakdowns[1]
    assert pytest.approx(second.direct_total) == 90.0
    assert pytest.approx(second.shared_total) == 40.0
    assert pytest.approx(second.capital_total) == 80.0


def test_export_breakdowns_round_trip() -> None:
    payload = export_breakdowns(
        [
            AllocationBreakdown(
                identifier="cell-a",
                direct_total=1,
                shared_total=2,
                capital_total=3,
                unit_cost=0.6,
                variance=0.1,
            )
        ]
    )
    data = json.loads(payload)
    assert data[0]["identifier"] == "cell-a"
    assert data[0]["variance"] == 0.1


def test_load_policy_validates(tmp_path: Path) -> None:
    path = tmp_path / "policy.yaml"
    path.write_text("allocation_weights: {}", encoding="utf-8")
    with pytest.raises(PolicyValidationError):
        load_policy(path)
