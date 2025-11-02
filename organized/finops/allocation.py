from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

import yaml


class PolicyValidationError(ValueError):
    """Raised when the allocation policy is malformed."""


@dataclasses.dataclass
class CostRecord:
    """Cost object representing a production cell, order, or SKU."""

    identifier: str
    units_produced: float
    direct_costs: Mapping[str, float]
    drivers: Mapping[str, float]
    target_unit_cost: Optional[float] = None


@dataclasses.dataclass
class AllocationBreakdown:
    identifier: str
    direct_total: float
    shared_total: float
    capital_total: float
    unit_cost: float
    variance: Optional[float]


def load_policy(path: Path) -> Dict[str, Any]:
    """Load the allocation policy template."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    validate_policy(data)
    return data


def validate_policy(policy: Mapping[str, Any]) -> None:
    if "allocation_weights" not in policy:
        raise PolicyValidationError("missing allocation_weights key")
    if "direct" not in policy["allocation_weights"]:
        raise PolicyValidationError("allocation_weights.direct required")
    if "shared" not in policy["allocation_weights"]:
        raise PolicyValidationError("allocation_weights.shared required")
    if not isinstance(policy["allocation_weights"]["shared"], Mapping):
        raise PolicyValidationError("allocation_weights.shared must be mapping")
    for name, rule in policy["allocation_weights"]["shared"].items():
        if not isinstance(rule, Mapping):
            raise PolicyValidationError(f"shared rule `{name}` must be mapping")
        for field in ("metric", "driver", "weight"):
            if field not in rule:
                raise PolicyValidationError(f"shared rule `{name}` missing `{field}`")


class AllocationEngine:
    """Compute FinOps allocations based on policy weights."""

    def __init__(self, policy: Mapping[str, Any]):
        validate_policy(policy)
        self.policy = policy

    def allocate(
        self,
        records: Iterable[CostRecord],
        shared_metrics: Mapping[str, float],
        capital_projects: Optional[Iterable[Mapping[str, Any]]] = None,
    ) -> List[AllocationBreakdown]:
        records = list(records)
        driver_totals = self._aggregate_drivers(records)
        shared_config = self.policy["allocation_weights"]["shared"]

        capital_total = self._sum_capital(capital_projects)

        breakdowns: List[AllocationBreakdown] = []
        for record in records:
            direct_total = self._direct_cost(record)
            shared_total = self._shared_cost(record, driver_totals, shared_metrics, shared_config)
            capital_share = self._capital_share(record, driver_totals, capital_total, shared_config)
            units = max(record.units_produced, 1e-6)
            unit_cost = (direct_total + shared_total + capital_share) / units

            variance = None
            if record.target_unit_cost:
                target = record.target_unit_cost
                variance = (unit_cost - target) / target if target else None

            breakdowns.append(
                AllocationBreakdown(
                    identifier=record.identifier,
                    direct_total=direct_total,
                    shared_total=shared_total,
                    capital_total=capital_share,
                    unit_cost=unit_cost,
                    variance=variance,
                )
            )
        return breakdowns

    def _direct_cost(self, record: CostRecord) -> float:
        direct_policy = self.policy["allocation_weights"]["direct"]
        total = 0.0
        for category, weight in direct_policy.items():
            cost = float(record.direct_costs.get(category, 0.0))
            total += cost * float(weight)
        return total

    def _shared_cost(
        self,
        record: CostRecord,
        driver_totals: Mapping[str, float],
        shared_metrics: Mapping[str, float],
        shared_config: Mapping[str, Mapping[str, Any]],
    ) -> float:
        total = 0.0
        for _, rule in shared_config.items():
            driver = rule["driver"]
            driver_total = float(driver_totals.get(driver, 0.0))
            if driver_total <= 0:
                continue
            driver_value = float(record.drivers.get(driver, 0.0))
            metric_value = float(shared_metrics.get(rule["metric"], 0.0))
            weight = float(rule["weight"])
            total += metric_value * weight * (driver_value / driver_total)
        return total

    def _aggregate_drivers(self, records: Iterable[CostRecord]) -> Dict[str, float]:
        totals: Dict[str, float] = {}
        for record in records:
            for driver, value in record.drivers.items():
                totals[driver] = totals.get(driver, 0.0) + float(value)
        return totals

    def _sum_capital(
        self,
        capital_projects: Optional[Iterable[Mapping[str, Any]]],
    ) -> float:
        if not capital_projects:
            return 0.0
        total = 0.0
        for project in capital_projects:
            total += float(project.get("amortized_monthly_cost", 0.0))
        return total

    def _capital_share(
        self,
        record: CostRecord,
        driver_totals: Mapping[str, float],
        capital_total: float,
        shared_config: Mapping[str, Mapping[str, Any]],
    ) -> float:
        if capital_total <= 0:
            return 0.0

        # Reuse the first shared driver as the apportionment baseline.
        first_rule = next(iter(shared_config.values()), None)
        if not first_rule:
            return 0.0
        driver = first_rule["driver"]
        driver_total = float(driver_totals.get(driver, 0.0))
        if driver_total <= 0:
            return 0.0
        driver_value = float(record.drivers.get(driver, 0.0))
        return capital_total * (driver_value / driver_total)


def export_breakdowns(breakdowns: Iterable[AllocationBreakdown]) -> str:
    """Return JSON payload for persistence or API response."""
    return json.dumps(
        [dataclasses.asdict(item) for item in breakdowns],
        indent=2,
        sort_keys=True,
    )
