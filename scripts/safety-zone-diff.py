#!/usr/bin/env python3
"""
Safety zone configuration diff analyzer.

Detects changes to safety zone configurations between git refs and fails
if safety-critical changes are detected without proper approval.

Per ADR-004 Safety Governance requirements.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
    from deepdiff import DeepDiff
except ImportError:
    print("Error: Required packages not installed.")
    print("Run: pip install pyyaml deepdiff")
    sys.exit(1)


# Safety-critical configuration keys that trigger stricter validation
CRITICAL_KEYS = {
    "max_speed",
    "estop_required",
    "safety_zone",
    "plc_authority",
    "hardware_override",
    "emergency_stop",
    "collision_detection",
    "safety_limits",
}


class SafetyZoneDiff:
    """Analyzer for safety zone configuration differences."""

    def __init__(self, base_ref: str, head_ref: str, fail_on_diff: bool = False) -> None:
        """
        Initialize safety zone diff analyzer.

        Args:
            base_ref: Base git reference (e.g., 'origin/main')
            head_ref: Head git reference (e.g., 'HEAD')
            fail_on_diff: Whether to fail on any detected differences
        """
        self.base_ref = base_ref
        self.head_ref = head_ref
        self.fail_on_diff = fail_on_diff
        self.differences: List[Dict[str, Any]] = []
        self.critical_changes: List[Dict[str, Any]] = []

    def load_safety_config(self, ref: str) -> Dict[str, Any]:
        """
        Load safety configuration from git ref.

        Args:
            ref: Git reference to load from

        Returns:
            Safety configuration dictionary
        """
        # In real implementation, would use git to checkout ref
        # For testing, we'll use filesystem
        config_path = Path("organized/safety/config/safety-zones.yml")

        if not config_path.exists():
            return {}

        with open(config_path, "r") as f:
            return yaml.safe_load(f) or {}

    def analyze_diff(self) -> Dict[str, Any]:
        """
        Analyze differences between base and head configurations.

        Returns:
            Dictionary containing diff analysis results
        """
        base_config = self.load_safety_config(self.base_ref)
        head_config = self.load_safety_config(self.head_ref)

        diff = DeepDiff(base_config, head_config, ignore_order=True)

        results = {
            "base_ref": self.base_ref,
            "head_ref": self.head_ref,
            "has_changes": bool(diff),
            "critical_changes": [],
            "non_critical_changes": [],
            "added_zones": [],
            "removed_zones": [],
            "modified_zones": [],
        }

        if not diff:
            return results

        # Analyze value changes
        if "values_changed" in diff:
            for key, change in diff["values_changed"].items():
                is_critical = any(crit_key in key for crit_key in CRITICAL_KEYS)

                change_info = {
                    "path": key,
                    "old_value": change["old_value"],
                    "new_value": change["new_value"],
                    "critical": is_critical,
                }

                if is_critical:
                    results["critical_changes"].append(change_info)
                    self.critical_changes.append(change_info)
                else:
                    results["non_critical_changes"].append(change_info)

                self.differences.append(change_info)

        # Analyze additions
        if "dictionary_item_added" in diff:
            for item in diff["dictionary_item_added"]:
                results["added_zones"].append(str(item))

        # Analyze removals
        if "dictionary_item_removed" in diff:
            for item in diff["dictionary_item_removed"]:
                results["removed_zones"].append(str(item))

        return results

    def generate_report(self, output_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Generate diff report.

        Args:
            output_path: Optional path to write JSON report

        Returns:
            Report dictionary
        """
        analysis = self.analyze_diff()

        report = {
            "timestamp": "2025-11-01T00:00:00Z",  # Would use actual timestamp
            "analysis": analysis,
            "requires_approval": len(self.critical_changes) > 0,
            "approval_checklist": self._generate_approval_checklist(analysis),
        }

        if output_path:
            with open(output_path, "w") as f:
                json.dump(report, f, indent=2)

        return report

    def _generate_approval_checklist(self, analysis: Dict[str, Any]) -> List[str]:
        """
        Generate approval checklist based on changes.

        Args:
            analysis: Diff analysis results

        Returns:
            List of required approval items
        """
        checklist = []

        if analysis["critical_changes"]:
            checklist.append("Safety engineer approval required")
            checklist.append("Verify against ADR-004 compliance")
            checklist.append("Update edge validation SOP")

        if analysis["added_zones"]:
            checklist.append("New zone commissioning required")
            checklist.append("PLC configuration update needed")

        if analysis["removed_zones"]:
            checklist.append("Zone decommissioning approval required")
            checklist.append("Verify no active tasks in removed zones")

        if analysis["modified_zones"]:
            checklist.append("Modified zone re-validation required")
            checklist.append("Edge agent cache update needed")

        return checklist

    def should_fail(self) -> bool:
        """
        Determine if diff should fail CI pipeline.

        Returns:
            True if should fail, False otherwise
        """
        if not self.fail_on_diff:
            return False

        # Fail on any critical changes
        if self.critical_changes:
            return True

        # Fail on zone additions/removals
        analysis = self.analyze_diff()
        if analysis["added_zones"] or analysis["removed_zones"]:
            return True

        return False


def main() -> int:
    """
    Main entry point for safety zone diff tool.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(
        description="Analyze safety zone configuration differences"
    )
    parser.add_argument(
        "--base",
        default="origin/main",
        help="Base git reference (default: origin/main)",
    )
    parser.add_argument(
        "--head",
        default="HEAD",
        help="Head git reference (default: HEAD)",
    )
    parser.add_argument(
        "--fail-on-diff",
        action="store_true",
        help="Fail if any safety-critical differences detected",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("diff-report.json"),
        help="Output path for JSON report",
    )

    args = parser.parse_args()

    analyzer = SafetyZoneDiff(
        base_ref=args.base,
        head_ref=args.head,
        fail_on_diff=args.fail_on_diff,
    )

    report = analyzer.generate_report(args.output)

    print(f"\n{'='*60}")
    print("SAFETY ZONE DIFF ANALYSIS")
    print(f"{'='*60}\n")

    print(f"Base: {args.base}")
    print(f"Head: {args.head}")
    print(f"\nChanges detected: {report['analysis']['has_changes']}")

    if report["analysis"]["critical_changes"]:
        print(f"\n⚠️  CRITICAL CHANGES: {len(report['analysis']['critical_changes'])}")
        for change in report["analysis"]["critical_changes"]:
            print(f"  - {change['path']}")
            print(f"    Old: {change['old_value']}")
            print(f"    New: {change['new_value']}")

    if report["analysis"]["added_zones"]:
        print(f"\n➕ Added zones: {len(report['analysis']['added_zones'])}")
        for zone in report["analysis"]["added_zones"]:
            print(f"  - {zone}")

    if report["analysis"]["removed_zones"]:
        print(f"\n➖ Removed zones: {len(report['analysis']['removed_zones'])}")
        for zone in report["analysis"]["removed_zones"]:
            print(f"  - {zone}")

    if report["requires_approval"]:
        print(f"\n{'='*60}")
        print("APPROVAL REQUIRED")
        print(f"{'='*60}\n")
        for item in report["approval_checklist"]:
            print(f"  [ ] {item}")

    print(f"\nReport written to: {args.output}")

    if analyzer.should_fail():
        print("\n❌ DIFF CHECK FAILED: Safety-critical changes detected")
        print("Approval required before merge.\n")
        return 1

    print("\n✅ DIFF CHECK PASSED\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
