#!/usr/bin/env python3
"""Runbook URL Validator for Alertmanager configurations.

This module validates that all runbook_url annotations in Prometheus alert rules
are reachable and properly formatted. Implements ADR-005 follow-up requirements
for observability automation.

Usage:
    python runbook_validator.py --input alerts_main.jsonnet
    python runbook_validator.py --input alerts_main.jsonnet --fail-on-404
    python runbook_validator.py --input alerts_main.jsonnet --dry-run
"""

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import requests
import yaml


# Constants
DEFAULT_TIMEOUT: int = 10
DEFAULT_RETRIES: int = 3
RETRY_DELAY: float = 2.0
CACHE_TTL: int = 300  # 5 minutes
URL_PATTERN = re.compile(
    r'^https?://'  # http:// or https://
    r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
    r'localhost|'  # localhost
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # or IP
    r'(?::\d+)?'  # optional port
    r'(?:/?|[/?]\S+)$', re.IGNORECASE
)


@dataclass
class ValidationResult:
    """Result of URL validation check."""

    url: str
    status_code: Optional[int]
    is_reachable: bool
    error_message: Optional[str]
    alert_name: str
    is_placeholder: bool = False


class RunbookValidator:
    """Validates runbook URLs in Prometheus alert rules."""

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
        fail_on_404: bool = False,
        dry_run: bool = False
    ) -> None:
        """Initialize the validator.

        Args:
            timeout: HTTP request timeout in seconds
            retries: Number of retry attempts for failed requests
            fail_on_404: Whether to fail on 404 responses
            dry_run: Skip actual HTTP requests (testing mode)
        """
        self.timeout = timeout
        self.retries = retries
        self.fail_on_404 = fail_on_404
        self.dry_run = dry_run
        self.cache: dict[str, tuple[ValidationResult, float]] = {}
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'eFab-Runbook-Validator/1.0'
        })

    def extract_runbook_urls(self, jsonnet_file: Path) -> list[dict[str, Any]]:
        """Extract runbook URLs from Jsonnet alert rules.

        Args:
            jsonnet_file: Path to Jsonnet alert configuration file

        Returns:
            List of dictionaries containing alert metadata and runbook URLs

        Raises:
            subprocess.CalledProcessError: If Jsonnet compilation fails
            FileNotFoundError: If jsonnet_file does not exist
        """
        if not jsonnet_file.exists():
            raise FileNotFoundError(f"Jsonnet file not found: {jsonnet_file}")

        # Compile Jsonnet to JSON (using sample parameters)
        try:
            result = subprocess.run(
                [
                    'jsonnet',
                    str(jsonnet_file),
                    '--tla-str', 'site=factory-01',
                    '--tla-str', 'cell=cell-a',
                    '--tla-str', 'environment=prod',
                    '--tla-str', 'slack_channel=#alerts'
                ],
                capture_output=True,
                text=True,
                check=True
            )
            alert_config = json.loads(result.stdout)
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to compile Jsonnet: {e.stderr}", file=sys.stderr)
            raise

        # Extract runbook URLs from alerts
        runbook_entries = []
        for group in alert_config.get('groups', []):
            for rule in group.get('rules', []):
                if 'alert' not in rule:
                    continue

                alert_name = rule['alert']
                annotations = rule.get('annotations', {})
                runbook_url = annotations.get('runbook_url')

                if runbook_url:
                    runbook_entries.append({
                        'alert_name': alert_name,
                        'runbook_url': runbook_url,
                        'group': group.get('name', 'unknown'),
                        'severity': rule.get('labels', {}).get('severity', 'unknown')
                    })

        return runbook_entries

    def is_placeholder_url(self, url: str) -> bool:
        """Check if URL is a placeholder/TODO.

        Args:
            url: URL string to check

        Returns:
            True if URL is a placeholder, False otherwise
        """
        placeholders = [
            'TODO',
            'FIXME',
            'example.com',
            'localhost',
            'placeholder',
            'changeme'
        ]
        url_lower = url.lower()
        return any(placeholder.lower() in url_lower for placeholder in placeholders)

    def validate_url_format(self, url: str) -> tuple[bool, Optional[str]]:
        """Validate URL format and structure.

        Args:
            url: URL string to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not url:
            return False, "Empty URL"

        if not URL_PATTERN.match(url):
            return False, "Invalid URL format"

        parsed = urlparse(url)

        if parsed.scheme not in ['http', 'https']:
            return False, f"Invalid scheme: {parsed.scheme} (must be http or https)"

        if not parsed.netloc:
            return False, "Missing domain/host"

        # Enforce HTTPS for production runbooks (with exceptions for local testing)
        if not self.dry_run and parsed.scheme == 'http' and parsed.netloc != 'localhost':
            return False, "Runbook URLs must use HTTPS (not HTTP)"

        return True, None

    def check_url_reachability(
        self,
        url: str,
        alert_name: str
    ) -> ValidationResult:
        """Check if URL is reachable with retry logic.

        Args:
            url: URL to check
            alert_name: Name of the alert for logging

        Returns:
            ValidationResult containing check results
        """
        # Check cache first
        if url in self.cache:
            cached_result, cache_time = self.cache[url]
            if time.time() - cache_time < CACHE_TTL:
                return cached_result

        # Check if placeholder
        is_placeholder = self.is_placeholder_url(url)

        # Validate format
        is_valid_format, format_error = self.validate_url_format(url)
        if not is_valid_format:
            result = ValidationResult(
                url=url,
                status_code=None,
                is_reachable=False,
                error_message=format_error,
                alert_name=alert_name,
                is_placeholder=is_placeholder
            )
            self.cache[url] = (result, time.time())
            return result

        # Skip HTTP check in dry-run mode or for placeholders
        if self.dry_run or is_placeholder:
            result = ValidationResult(
                url=url,
                status_code=None,
                is_reachable=is_placeholder,  # Treat placeholders as "reachable" in dry-run
                error_message="Dry-run mode" if self.dry_run else "Placeholder URL",
                alert_name=alert_name,
                is_placeholder=is_placeholder
            )
            self.cache[url] = (result, time.time())
            return result

        # Attempt HTTP request with retries
        last_error = None
        for attempt in range(self.retries):
            try:
                response = self.session.head(
                    url,
                    timeout=self.timeout,
                    allow_redirects=True
                )
                result = ValidationResult(
                    url=url,
                    status_code=response.status_code,
                    is_reachable=response.status_code < 400,
                    error_message=None if response.status_code < 400 else f"HTTP {response.status_code}",
                    alert_name=alert_name,
                    is_placeholder=False
                )
                self.cache[url] = (result, time.time())
                return result

            except requests.exceptions.RequestException as e:
                last_error = str(e)
                if attempt < self.retries - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))  # Exponential backoff

        # All retries failed
        result = ValidationResult(
            url=url,
            status_code=None,
            is_reachable=False,
            error_message=f"Request failed: {last_error}",
            alert_name=alert_name,
            is_placeholder=False
        )
        self.cache[url] = (result, time.time())
        return result

    def validate_file(self, jsonnet_file: Path) -> list[ValidationResult]:
        """Validate all runbook URLs in a Jsonnet file.

        Args:
            jsonnet_file: Path to Jsonnet alert configuration

        Returns:
            List of validation results for all runbook URLs
        """
        print(f"Extracting runbook URLs from: {jsonnet_file}")
        runbook_entries = self.extract_runbook_urls(jsonnet_file)

        if not runbook_entries:
            print("WARNING: No runbook_url annotations found in alerts")
            return []

        print(f"Found {len(runbook_entries)} runbook URL(s) to validate\n")

        results = []
        for entry in runbook_entries:
            alert_name = entry['alert_name']
            url = entry['runbook_url']

            print(f"Validating: {alert_name}")
            print(f"  URL: {url}")

            result = self.check_url_reachability(url, alert_name)
            results.append(result)

            # Print result
            if result.is_placeholder:
                print(f"  Status: PLACEHOLDER (skipped)")
            elif result.is_reachable:
                print(f"  Status: OK ({result.status_code})")
            else:
                print(f"  Status: FAILED - {result.error_message}")
            print()

        return results

    def print_summary(self, results: list[ValidationResult]) -> None:
        """Print validation summary.

        Args:
            results: List of validation results
        """
        if not results:
            print("No runbook URLs to validate")
            return

        total = len(results)
        reachable = sum(1 for r in results if r.is_reachable and not r.is_placeholder)
        placeholders = sum(1 for r in results if r.is_placeholder)
        failed = sum(1 for r in results if not r.is_reachable and not r.is_placeholder)

        print("=" * 70)
        print("VALIDATION SUMMARY")
        print("=" * 70)
        print(f"Total URLs:        {total}")
        print(f"Reachable:         {reachable}")
        print(f"Placeholders:      {placeholders}")
        print(f"Failed:            {failed}")
        print()

        if failed > 0:
            print("FAILED URLs:")
            for result in results:
                if not result.is_reachable and not result.is_placeholder:
                    print(f"  - {result.alert_name}: {result.url}")
                    print(f"    Error: {result.error_message}")
            print()

        if placeholders > 0:
            print("PLACEHOLDER URLs (need attention):")
            for result in results:
                if result.is_placeholder:
                    print(f"  - {result.alert_name}: {result.url}")
            print()

    def should_fail(self, results: list[ValidationResult]) -> bool:
        """Determine if validation should fail based on results.

        Args:
            results: List of validation results

        Returns:
            True if validation should fail, False otherwise
        """
        for result in results:
            # Always fail on format errors or unreachable non-placeholders
            if not result.is_reachable and not result.is_placeholder:
                if self.fail_on_404 or result.status_code is None:
                    return True
                if result.status_code and result.status_code >= 500:
                    # Fail on server errors regardless of fail_on_404
                    return True

        return False


def main() -> int:
    """Main entry point for runbook validator.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(
        description='Validate runbook URLs in Prometheus alert rules'
    )
    parser.add_argument(
        '--input',
        type=Path,
        required=True,
        help='Path to Jsonnet alert configuration file'
    )
    parser.add_argument(
        '--fail-on-404',
        action='store_true',
        help='Fail validation on HTTP 404 responses (strict mode)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Skip actual HTTP requests (testing mode)'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f'HTTP request timeout in seconds (default: {DEFAULT_TIMEOUT})'
    )
    parser.add_argument(
        '--retries',
        type=int,
        default=DEFAULT_RETRIES,
        help=f'Number of retry attempts (default: {DEFAULT_RETRIES})'
    )

    args = parser.parse_args()

    # Initialize validator
    validator = RunbookValidator(
        timeout=args.timeout,
        retries=args.retries,
        fail_on_404=args.fail_on_404,
        dry_run=args.dry_run
    )

    try:
        # Validate file
        results = validator.validate_file(args.input)

        # Print summary
        validator.print_summary(results)

        # Determine exit code
        if validator.should_fail(results):
            print("VALIDATION FAILED")
            return 1
        else:
            print("VALIDATION PASSED")
            return 0

    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError:
        print("ERROR: Failed to compile Jsonnet file", file=sys.stderr)
        print("Ensure jsonnet is installed and the file is valid", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
