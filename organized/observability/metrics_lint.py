#!/usr/bin/env python3
"""Metrics Schema Linter for Prometheus metric naming conventions.

This module enforces Prometheus best practices for metric naming, labeling,
and consistency across observability configurations. Implements ADR-005
follow-up requirements.

Enforced conventions:
- Metric naming: {namespace}_{subsystem}_{name}_{unit}
- Label consistency across related metrics
- Proper unit suffixes (_seconds, _bytes, _total, etc.)
- No deprecated metric patterns

Usage:
    python metrics_lint.py
    python metrics_lint.py --strict
    python metrics_lint.py --config metrics_config.yaml
"""

import argparse
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml


# Constants
VALID_UNIT_SUFFIXES = [
    '_total',      # Counters
    '_count',      # Counters
    '_sum',        # Summaries
    '_bucket',     # Histograms
    '_seconds',    # Time duration
    '_milliseconds',  # Time duration
    '_bytes',      # Data size
    '_percent',    # Percentage (0-100)
    '_ratio',      # Ratio (0-1)
    '_celsius',    # Temperature
    '_fahrenheit', # Temperature
    '_info',       # Info metrics
]

DEPRECATED_PATTERNS = [
    r'.*_ms$',          # Use _milliseconds or _seconds instead
    r'.*_time$',        # Use _seconds instead
    r'.*_duration$',    # Use _seconds instead
    r'.*_size$',        # Use _bytes instead
    r'.*_pct$',         # Use _percent instead
]

NAMESPACE_PATTERN = re.compile(r'^[a-z][a-z0-9_]*$')
METRIC_NAME_PATTERN = re.compile(r'^[a-z][a-z0-9_]*[a-z0-9]$')
LABEL_NAME_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')


@dataclass
class MetricDefinition:
    """Represents a Prometheus metric definition."""

    name: str
    metric_type: str  # counter, gauge, histogram, summary
    labels: list[str] = field(default_factory=list)
    source_file: str = ''
    line_number: int = 0

    def namespace(self) -> str:
        """Extract namespace from metric name."""
        parts = self.name.split('_')
        return parts[0] if parts else ''

    def has_valid_unit_suffix(self) -> bool:
        """Check if metric has a valid unit suffix."""
        return any(self.name.endswith(suffix) for suffix in VALID_UNIT_SUFFIXES)

    def is_deprecated_pattern(self) -> bool:
        """Check if metric uses deprecated naming pattern."""
        return any(re.match(pattern, self.name) for pattern in DEPRECATED_PATTERNS)


@dataclass
class LintError:
    """Represents a linting error."""

    severity: str  # ERROR, WARNING, INFO
    rule: str
    message: str
    metric_name: str
    source_file: str = ''
    line_number: int = 0


class MetricsLinter:
    """Lints Prometheus metrics for naming and consistency issues."""

    def __init__(self, strict: bool = False) -> None:
        """Initialize the linter.

        Args:
            strict: If True, warnings are treated as errors
        """
        self.strict = strict
        self.errors: list[LintError] = []
        self.metrics: dict[str, MetricDefinition] = {}

    def extract_metrics_from_jsonnet(self, jsonnet_file: Path) -> list[MetricDefinition]:
        """Extract metric names from Jsonnet files.

        Args:
            jsonnet_file: Path to Jsonnet file

        Returns:
            List of metric definitions found in the file
        """
        metrics = []

        # Read Jsonnet source and extract metric references
        with open(jsonnet_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Pattern to match metric names in PromQL expressions
        metric_pattern = re.compile(r'\b([a-z][a-z0-9_]*(?:_[a-z0-9]+)*)\b')

        for line_num, line in enumerate(lines, start=1):
            # Look for metric references in expr fields
            if 'expr' in line or 'target' in line:
                matches = metric_pattern.findall(line)
                for match in matches:
                    # Filter out common PromQL keywords and functions
                    if match not in ['expr', 'sum', 'rate', 'increase', 'avg', 'max',
                                   'min', 'by', 'le', 'job', 'instance', 'env']:
                        # Determine metric type based on naming convention
                        metric_type = 'counter' if '_total' in match else 'gauge'
                        if '_bucket' in match:
                            metric_type = 'histogram'

                        metric = MetricDefinition(
                            name=match,
                            metric_type=metric_type,
                            source_file=str(jsonnet_file),
                            line_number=line_num
                        )
                        metrics.append(metric)

        return metrics

    def check_naming_convention(self, metric: MetricDefinition) -> None:
        """Validate metric naming follows Prometheus conventions.

        Args:
            metric: Metric definition to check
        """
        # Check overall format
        if not METRIC_NAME_PATTERN.match(metric.name):
            self.errors.append(LintError(
                severity='ERROR',
                rule='NAMING_FORMAT',
                message=f"Metric name '{metric.name}' must match pattern: [a-z][a-z0-9_]*[a-z0-9]",
                metric_name=metric.name,
                source_file=metric.source_file,
                line_number=metric.line_number
            ))

        # Check namespace
        namespace = metric.namespace()
        if not namespace or not NAMESPACE_PATTERN.match(namespace):
            self.errors.append(LintError(
                severity='ERROR',
                rule='NAMESPACE_FORMAT',
                message=f"Metric namespace '{namespace}' must be lowercase alphanumeric with underscores",
                metric_name=metric.name,
                source_file=metric.source_file,
                line_number=metric.line_number
            ))

        # Check for unit suffix
        if not metric.has_valid_unit_suffix():
            # Special case: info and up metrics don't need units
            if not metric.name.endswith('_info') and not metric.name.endswith('_up'):
                self.errors.append(LintError(
                    severity='WARNING',
                    rule='MISSING_UNIT',
                    message=f"Metric '{metric.name}' should have a unit suffix: {', '.join(VALID_UNIT_SUFFIXES)}",
                    metric_name=metric.name,
                    source_file=metric.source_file,
                    line_number=metric.line_number
                ))

        # Check for deprecated patterns
        if metric.is_deprecated_pattern():
            self.errors.append(LintError(
                severity='ERROR',
                rule='DEPRECATED_PATTERN',
                message=f"Metric '{metric.name}' uses deprecated naming pattern",
                metric_name=metric.name,
                source_file=metric.source_file,
                line_number=metric.line_number
            ))

    def check_metric_type_consistency(self, metric: MetricDefinition) -> None:
        """Check metric type is consistent with naming.

        Args:
            metric: Metric definition to check
        """
        # Counters should end with _total or _count
        if metric.metric_type == 'counter':
            if not (metric.name.endswith('_total') or metric.name.endswith('_count')):
                self.errors.append(LintError(
                    severity='WARNING',
                    rule='COUNTER_SUFFIX',
                    message=f"Counter metric '{metric.name}' should end with _total or _count",
                    metric_name=metric.name,
                    source_file=metric.source_file,
                    line_number=metric.line_number
                ))

        # Histograms should have _bucket suffix (in base name)
        if metric.metric_type == 'histogram':
            base_name = metric.name.replace('_bucket', '').replace('_sum', '').replace('_count', '')
            if metric.name.endswith('_bucket'):
                # This is the bucket series, which is correct
                pass
            elif not any(metric.name.endswith(suffix) for suffix in ['_sum', '_count']):
                self.errors.append(LintError(
                    severity='INFO',
                    rule='HISTOGRAM_SUFFIX',
                    message=f"Histogram metric '{metric.name}' should reference _bucket, _sum, or _count",
                    metric_name=metric.name,
                    source_file=metric.source_file,
                    line_number=metric.line_number
                ))

    def check_label_consistency(self) -> None:
        """Check label consistency across metrics in the same namespace."""
        # Group metrics by namespace
        namespace_metrics: dict[str, list[MetricDefinition]] = defaultdict(list)
        for metric in self.metrics.values():
            namespace_metrics[metric.namespace()].append(metric)

        # Check for common labels within namespaces
        for namespace, metrics in namespace_metrics.items():
            if len(metrics) < 2:
                continue

            # Find common base labels (exclude metric-specific labels)
            common_labels = set(metrics[0].labels)
            for metric in metrics[1:]:
                common_labels.intersection_update(metric.labels)

            # Warn if metrics in same namespace have inconsistent labels
            for metric in metrics:
                missing_labels = common_labels - set(metric.labels)
                if missing_labels and len(common_labels) > 0:
                    self.errors.append(LintError(
                        severity='WARNING',
                        rule='LABEL_CONSISTENCY',
                        message=f"Metric '{metric.name}' missing common namespace labels: {', '.join(missing_labels)}",
                        metric_name=metric.name,
                        source_file=metric.source_file,
                        line_number=metric.line_number
                    ))

    def lint_file(self, file_path: Path) -> None:
        """Lint a single Jsonnet file.

        Args:
            file_path: Path to file to lint
        """
        print(f"Linting: {file_path}")

        metrics = self.extract_metrics_from_jsonnet(file_path)

        for metric in metrics:
            # Store metric for cross-file analysis
            if metric.name not in self.metrics:
                self.metrics[metric.name] = metric

            # Run checks
            self.check_naming_convention(metric)
            self.check_metric_type_consistency(metric)

    def lint_directory(self, directory: Path) -> None:
        """Lint all Jsonnet files in a directory.

        Args:
            directory: Directory to scan for Jsonnet files
        """
        jsonnet_files = list(directory.glob('*.jsonnet'))

        if not jsonnet_files:
            print(f"WARNING: No .jsonnet files found in {directory}")
            return

        print(f"Found {len(jsonnet_files)} Jsonnet file(s) to lint\n")

        for file_path in jsonnet_files:
            self.lint_file(file_path)

        # Run cross-file checks
        self.check_label_consistency()

    def print_report(self) -> None:
        """Print linting report."""
        if not self.errors:
            print("\n" + "=" * 70)
            print("All metrics passed validation!")
            print("=" * 70)
            return

        # Group errors by severity
        errors_by_severity = defaultdict(list)
        for error in self.errors:
            errors_by_severity[error.severity].append(error)

        print("\n" + "=" * 70)
        print("METRICS LINTING REPORT")
        print("=" * 70)

        for severity in ['ERROR', 'WARNING', 'INFO']:
            errors = errors_by_severity.get(severity, [])
            if not errors:
                continue

            print(f"\n{severity}S ({len(errors)}):")
            print("-" * 70)

            for error in errors:
                location = f"{error.source_file}:{error.line_number}" if error.source_file else "unknown"
                print(f"  [{error.rule}] {error.message}")
                print(f"  Location: {location}")
                print()

        # Print summary
        total_errors = len(errors_by_severity.get('ERROR', []))
        total_warnings = len(errors_by_severity.get('WARNING', []))
        total_info = len(errors_by_severity.get('INFO', []))

        print("=" * 70)
        print(f"Total Errors:   {total_errors}")
        print(f"Total Warnings: {total_warnings}")
        print(f"Total Info:     {total_info}")
        print("=" * 70)

    def should_fail(self) -> bool:
        """Determine if linting should fail.

        Returns:
            True if there are errors (or warnings in strict mode)
        """
        if any(error.severity == 'ERROR' for error in self.errors):
            return True

        if self.strict and any(error.severity == 'WARNING' for error in self.errors):
            return True

        return False


def main() -> int:
    """Main entry point for metrics linter.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(
        description='Lint Prometheus metrics for naming and consistency'
    )
    parser.add_argument(
        '--directory',
        type=Path,
        default=Path('.'),
        help='Directory containing Jsonnet files (default: current directory)'
    )
    parser.add_argument(
        '--strict',
        action='store_true',
        help='Treat warnings as errors'
    )
    parser.add_argument(
        '--config',
        type=Path,
        help='Path to custom configuration file (YAML)'
    )

    args = parser.parse_args()

    # Initialize linter
    linter = MetricsLinter(strict=args.strict)

    try:
        # Lint directory
        linter.lint_directory(args.directory)

        # Print report
        linter.print_report()

        # Determine exit code
        if linter.should_fail():
            print("\nMETRICS LINTING FAILED")
            return 1
        else:
            print("\nMETRICS LINTING PASSED")
            return 0

    except Exception as e:
        print(f"ERROR: Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
