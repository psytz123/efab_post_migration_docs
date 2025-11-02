"""Tests for runbook_validator module.

Comprehensive test suite for validating runbook URL validation logic,
error handling, and edge cases.
"""

import json
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture
    from _pytest.fixtures import FixtureRequest
    from _pytest.logging import LogCaptureFixture
    from _pytest.monkeypatch import MonkeyPatch
    from pytest_mock.plugin import MockerFixture

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from runbook_validator import (
    RunbookValidator,
    ValidationResult,
    URL_PATTERN,
)


class TestURLPatternMatching:
    """Test URL pattern regex validation."""

    def test_valid_https_url(self) -> None:
        """Test that valid HTTPS URLs match the pattern."""
        assert URL_PATTERN.match('https://wiki.example.com/runbooks/alert-1')

    def test_valid_http_url(self) -> None:
        """Test that valid HTTP URLs match the pattern."""
        assert URL_PATTERN.match('http://localhost:8080/runbooks')

    def test_url_with_port(self) -> None:
        """Test URLs with explicit port numbers."""
        assert URL_PATTERN.match('https://wiki.example.com:8443/runbooks')

    def test_url_with_query_params(self) -> None:
        """Test URLs with query parameters."""
        assert URL_PATTERN.match('https://wiki.example.com/runbooks?page=1')

    def test_invalid_url_no_scheme(self) -> None:
        """Test that URLs without scheme don't match."""
        assert not URL_PATTERN.match('wiki.example.com/runbooks')

    def test_invalid_url_ftp_scheme(self) -> None:
        """Test that non-HTTP schemes don't match."""
        assert not URL_PATTERN.match('ftp://wiki.example.com/runbooks')


class TestRunbookValidator:
    """Test RunbookValidator class functionality."""

    @pytest.fixture
    def validator(self) -> RunbookValidator:
        """Create a RunbookValidator instance for testing.

        Returns:
            Configured RunbookValidator instance
        """
        return RunbookValidator(timeout=5, retries=1, dry_run=True)

    @pytest.fixture
    def sample_jsonnet(self, tmp_path: Path) -> Path:
        """Create a sample Jsonnet file for testing.

        Args:
            tmp_path: Pytest temporary directory fixture

        Returns:
            Path to created Jsonnet file
        """
        jsonnet_content = """
        {
          groups: [
            {
              name: 'test-group',
              rules: [
                {
                  alert: 'TestAlert1',
                  expr: 'up == 0',
                  annotations: {
                    runbook_url: 'https://wiki.example.com/runbook-1',
                    summary: 'Test alert 1'
                  }
                },
                {
                  alert: 'TestAlert2',
                  expr: 'up == 0',
                  annotations: {
                    runbook_url: 'https://wiki.example.com/runbook-2',
                    summary: 'Test alert 2'
                  }
                }
              ]
            }
          ]
        }
        """
        jsonnet_file = tmp_path / "test_alerts.jsonnet"
        jsonnet_file.write_text(jsonnet_content)
        return jsonnet_file

    def test_is_placeholder_url(self, validator: RunbookValidator) -> None:
        """Test placeholder URL detection.

        Args:
            validator: RunbookValidator fixture
        """
        assert validator.is_placeholder_url('https://TODO.com/runbook')
        assert validator.is_placeholder_url('https://example.com/TODO')
        assert validator.is_placeholder_url('https://placeholder.com/runbook')
        assert not validator.is_placeholder_url('https://wiki.efab.com/runbook')

    def test_validate_url_format_valid(self, validator: RunbookValidator) -> None:
        """Test URL format validation for valid URLs.

        Args:
            validator: RunbookValidator fixture
        """
        is_valid, error = validator.validate_url_format('https://wiki.example.com/runbook')
        assert is_valid
        assert error is None

    def test_validate_url_format_empty(self, validator: RunbookValidator) -> None:
        """Test URL format validation for empty URLs.

        Args:
            validator: RunbookValidator fixture
        """
        is_valid, error = validator.validate_url_format('')
        assert not is_valid
        assert error == "Empty URL"

    def test_validate_url_format_invalid_scheme(self, validator: RunbookValidator) -> None:
        """Test URL format validation for invalid schemes.

        Args:
            validator: RunbookValidator fixture
        """
        is_valid, error = validator.validate_url_format('ftp://wiki.example.com/runbook')
        assert not is_valid
        assert 'scheme' in error.lower()

    def test_validate_url_format_no_domain(self, validator: RunbookValidator) -> None:
        """Test URL format validation for URLs without domain.

        Args:
            validator: RunbookValidator fixture
        """
        is_valid, error = validator.validate_url_format('https://')
        assert not is_valid
        assert 'domain' in error.lower() or 'host' in error.lower()

    def test_check_url_reachability_placeholder(self, validator: RunbookValidator) -> None:
        """Test URL reachability check for placeholder URLs.

        Args:
            validator: RunbookValidator fixture
        """
        result = validator.check_url_reachability(
            'https://TODO.com/runbook',
            'TestAlert'
        )
        assert result.is_placeholder
        assert result.alert_name == 'TestAlert'

    def test_check_url_reachability_dry_run(self, validator: RunbookValidator) -> None:
        """Test URL reachability in dry-run mode.

        Args:
            validator: RunbookValidator fixture
        """
        result = validator.check_url_reachability(
            'https://wiki.example.com/runbook',
            'TestAlert'
        )
        assert result.error_message == 'Dry-run mode'
        assert not result.is_reachable  # Dry run doesn't actually check

    def test_check_url_reachability_caching(self, validator: RunbookValidator) -> None:
        """Test that URL checks are cached.

        Args:
            validator: RunbookValidator fixture
        """
        url = 'https://wiki.example.com/runbook'
        alert_name = 'TestAlert'

        # First call
        result1 = validator.check_url_reachability(url, alert_name)

        # Second call should return cached result
        result2 = validator.check_url_reachability(url, alert_name)

        assert result1.url == result2.url
        assert url in validator.cache

    @patch('subprocess.run')
    def test_extract_runbook_urls(
        self,
        mock_run: Mock,
        validator: RunbookValidator,
        tmp_path: Path
    ) -> None:
        """Test extraction of runbook URLs from Jsonnet.

        Args:
            mock_run: Mock for subprocess.run
            validator: RunbookValidator fixture
            tmp_path: Pytest temporary directory fixture
        """
        # Mock jsonnet compilation output
        mock_run.return_value = Mock(
            stdout=json.dumps({
                'groups': [{
                    'name': 'test-group',
                    'rules': [{
                        'alert': 'TestAlert',
                        'expr': 'up == 0',
                        'annotations': {
                            'runbook_url': 'https://wiki.example.com/runbook',
                            'summary': 'Test'
                        },
                        'labels': {
                            'severity': 'critical'
                        }
                    }]
                }]
            }),
            stderr='',
            returncode=0
        )

        jsonnet_file = tmp_path / "test.jsonnet"
        jsonnet_file.write_text('{}')

        urls = validator.extract_runbook_urls(jsonnet_file)

        assert len(urls) == 1
        assert urls[0]['alert_name'] == 'TestAlert'
        assert urls[0]['runbook_url'] == 'https://wiki.example.com/runbook'
        assert urls[0]['severity'] == 'critical'

    def test_extract_runbook_urls_file_not_found(self, validator: RunbookValidator) -> None:
        """Test extraction with non-existent file.

        Args:
            validator: RunbookValidator fixture
        """
        with pytest.raises(FileNotFoundError):
            validator.extract_runbook_urls(Path('/nonexistent/file.jsonnet'))

    def test_should_fail_on_unreachable(self) -> None:
        """Test failure determination for unreachable URLs."""
        validator = RunbookValidator(fail_on_404=True, dry_run=True)

        results = [
            ValidationResult(
                url='https://example.com',
                status_code=None,
                is_reachable=False,
                error_message='Connection failed',
                alert_name='Test',
                is_placeholder=False
            )
        ]

        assert validator.should_fail(results)

    def test_should_not_fail_on_placeholders(self) -> None:
        """Test that placeholders don't cause failures."""
        validator = RunbookValidator(fail_on_404=True, dry_run=True)

        results = [
            ValidationResult(
                url='https://TODO.com',
                status_code=None,
                is_reachable=False,
                error_message='Placeholder',
                alert_name='Test',
                is_placeholder=True
            )
        ]

        assert not validator.should_fail(results)

    def test_should_fail_on_server_error(self) -> None:
        """Test failure determination for server errors (5xx)."""
        validator = RunbookValidator(fail_on_404=False, dry_run=True)

        results = [
            ValidationResult(
                url='https://example.com',
                status_code=500,
                is_reachable=False,
                error_message='HTTP 500',
                alert_name='Test',
                is_placeholder=False
            )
        ]

        assert validator.should_fail(results)

    def test_should_not_fail_on_404_without_flag(self) -> None:
        """Test that 404s don't fail without --fail-on-404.

        Args:
            None
        """
        validator = RunbookValidator(fail_on_404=False, dry_run=True)

        results = [
            ValidationResult(
                url='https://example.com',
                status_code=404,
                is_reachable=False,
                error_message='HTTP 404',
                alert_name='Test',
                is_placeholder=False
            )
        ]

        assert not validator.should_fail(results)


class TestRunbookValidatorHTTP:
    """Test HTTP request functionality (mocked)."""

    @patch('requests.Session.head')
    def test_check_url_reachability_success(self, mock_head: Mock) -> None:
        """Test successful URL reachability check.

        Args:
            mock_head: Mock for requests.Session.head
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_head.return_value = mock_response

        validator = RunbookValidator(dry_run=False, retries=1)
        result = validator.check_url_reachability(
            'https://wiki.example.com/runbook',
            'TestAlert'
        )

        assert result.is_reachable
        assert result.status_code == 200

    @patch('requests.Session.head')
    def test_check_url_reachability_404(self, mock_head: Mock) -> None:
        """Test URL reachability check with 404 response.

        Args:
            mock_head: Mock for requests.Session.head
        """
        mock_response = Mock()
        mock_response.status_code = 404
        mock_head.return_value = mock_response

        validator = RunbookValidator(dry_run=False, retries=1)
        result = validator.check_url_reachability(
            'https://wiki.example.com/runbook',
            'TestAlert'
        )

        assert not result.is_reachable
        assert result.status_code == 404

    @patch('requests.Session.head')
    def test_check_url_reachability_retry(self, mock_head: Mock) -> None:
        """Test retry logic for failed requests.

        Args:
            mock_head: Mock for requests.Session.head
        """
        mock_head.side_effect = [
            requests.exceptions.ConnectionError('Connection failed'),
            Mock(status_code=200)
        ]

        validator = RunbookValidator(dry_run=False, retries=2)
        result = validator.check_url_reachability(
            'https://wiki.example.com/runbook',
            'TestAlert'
        )

        # Should succeed on second attempt
        assert result.is_reachable
        assert mock_head.call_count == 2

    @patch('requests.Session.head')
    def test_check_url_reachability_all_retries_fail(self, mock_head: Mock) -> None:
        """Test behavior when all retry attempts fail.

        Args:
            mock_head: Mock for requests.Session.head
        """
        mock_head.side_effect = requests.exceptions.ConnectionError('Connection failed')

        validator = RunbookValidator(dry_run=False, retries=3)
        result = validator.check_url_reachability(
            'https://wiki.example.com/runbook',
            'TestAlert'
        )

        assert not result.is_reachable
        assert 'failed' in result.error_message.lower()
        assert mock_head.call_count == 3


class TestValidationResult:
    """Test ValidationResult dataclass."""

    def test_validation_result_creation(self) -> None:
        """Test ValidationResult creation and attributes."""
        result = ValidationResult(
            url='https://example.com',
            status_code=200,
            is_reachable=True,
            error_message=None,
            alert_name='TestAlert',
            is_placeholder=False
        )

        assert result.url == 'https://example.com'
        assert result.status_code == 200
        assert result.is_reachable
        assert result.error_message is None
        assert result.alert_name == 'TestAlert'
        assert not result.is_placeholder

    def test_validation_result_default_placeholder(self) -> None:
        """Test ValidationResult default placeholder value."""
        result = ValidationResult(
            url='https://example.com',
            status_code=200,
            is_reachable=True,
            error_message=None,
            alert_name='TestAlert'
        )

        assert not result.is_placeholder  # Default is False


class TestIntegration:
    """Integration tests for full validation workflow."""

    @patch('subprocess.run')
    @patch('requests.Session.head')
    def test_full_validation_workflow(
        self,
        mock_head: Mock,
        mock_run: Mock,
        tmp_path: Path
    ) -> None:
        """Test complete validation workflow.

        Args:
            mock_head: Mock for requests.Session.head
            mock_run: Mock for subprocess.run
            tmp_path: Pytest temporary directory fixture
        """
        # Setup mocks
        mock_run.return_value = Mock(
            stdout=json.dumps({
                'groups': [{
                    'name': 'test-group',
                    'rules': [
                        {
                            'alert': 'GoodAlert',
                            'annotations': {
                                'runbook_url': 'https://wiki.example.com/good',
                            }
                        },
                        {
                            'alert': 'PlaceholderAlert',
                            'annotations': {
                                'runbook_url': 'https://TODO.com/placeholder',
                            }
                        }
                    ]
                }]
            }),
            stderr='',
            returncode=0
        )

        mock_head.return_value = Mock(status_code=200)

        # Create test file
        jsonnet_file = tmp_path / "test.jsonnet"
        jsonnet_file.write_text('{}')

        # Run validation
        validator = RunbookValidator(dry_run=False)
        results = validator.validate_file(jsonnet_file)

        assert len(results) == 2
        assert any(r.alert_name == 'GoodAlert' for r in results)
        assert any(r.alert_name == 'PlaceholderAlert' for r in results)
        assert any(r.is_placeholder for r in results)
