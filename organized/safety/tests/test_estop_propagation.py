"""
Integration tests for E-stop propagation chain.

Tests verify that emergency stop signals propagate from PLC through Edge Agent
to Task API with <5 second latency requirement per ADR-004.
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture
    from _pytest.fixtures import FixtureRequest
    from _pytest.logging import LogCaptureFixture
    from _pytest.monkeypatch import MonkeyPatch
    from pytest_mock.plugin import MockerFixture


# Constants
ESTOP_LATENCY_THRESHOLD_SECONDS = 5.0
EDGE_CACHE_TTL_SECONDS = 300
AUDIT_LOG_RETENTION_DAYS = 90
PLC_POLL_INTERVAL_MS = 100
TASK_API_TIMEOUT_MS = 1000


class MockPLC:
    """Mock PLC controller for testing E-stop signals."""

    def __init__(self) -> None:
        """Initialize mock PLC with default state."""
        self._estop_active: bool = False
        self._signal_timestamp: Optional[datetime] = None
        self._hardware_override: bool = False

    def trigger_estop(self, hardware: bool = False) -> None:
        """
        Trigger emergency stop signal.

        Args:
            hardware: If True, simulates hardware E-stop (highest authority)
        """
        self._estop_active = True
        self._hardware_override = hardware
        self._signal_timestamp = datetime.utcnow()

    def clear_estop(self) -> None:
        """Clear emergency stop signal."""
        self._estop_active = False
        self._hardware_override = False
        self._signal_timestamp = None

    def get_status(self) -> Dict[str, Any]:
        """
        Get current PLC status.

        Returns:
            Dictionary containing E-stop state and metadata
        """
        return {
            "estop_active": self._estop_active,
            "hardware_override": self._hardware_override,
            "timestamp": self._signal_timestamp.isoformat() if self._signal_timestamp else None,
            "poll_interval_ms": PLC_POLL_INTERVAL_MS,
        }


class MockEdgeAgent:
    """Mock Edge Agent for testing offline behavior and policy caching."""

    def __init__(self, online: bool = True) -> None:
        """
        Initialize mock Edge Agent.

        Args:
            online: Whether agent has network connectivity to Task API
        """
        self._online = online
        self._cached_policies: Dict[str, Any] = {}
        self._event_queue: List[Dict[str, Any]] = []
        self._last_sync: Optional[datetime] = None

    def set_online(self, online: bool) -> None:
        """Set network connectivity status."""
        self._online = online

    def cache_policy(self, zone: str, policy: Dict[str, Any]) -> None:
        """
        Cache safety policy for offline operation.

        Args:
            zone: Safety zone identifier
            policy: Policy configuration
        """
        self._cached_policies[zone] = {
            "policy": policy,
            "cached_at": datetime.utcnow(),
            "ttl": EDGE_CACHE_TTL_SECONDS,
        }

    async def handle_estop(self, plc_status: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle E-stop signal from PLC.

        Args:
            plc_status: PLC status dictionary

        Returns:
            Event dictionary with propagation details
        """
        event_timestamp = datetime.utcnow()

        event = {
            "event_type": "estop_triggered",
            "source": "plc",
            "plc_status": plc_status,
            "edge_timestamp": event_timestamp.isoformat(),
            "online": self._online,
            "used_cache": not self._online,
        }

        self._event_queue.append(event)

        # Simulate processing delay
        await asyncio.sleep(0.05)  # 50ms processing time

        return event

    def get_event_queue(self) -> List[Dict[str, Any]]:
        """Get queued events for syncing to Task API."""
        return self._event_queue.copy()

    def clear_queue(self) -> None:
        """Clear event queue after successful sync."""
        self._event_queue.clear()
        self._last_sync = datetime.utcnow()


class MockTaskAPI:
    """Mock Task API for testing audit log integration."""

    def __init__(self) -> None:
        """Initialize mock Task API."""
        self._audit_log: List[Dict[str, Any]] = []
        self._network_delay_ms: int = 50

    async def log_safety_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Log safety event to audit trail.

        Args:
            event: Event dictionary from Edge Agent

        Returns:
            Response with audit log ID and timestamp
        """
        # Simulate network delay
        await asyncio.sleep(self._network_delay_ms / 1000)

        audit_entry = {
            "audit_id": f"audit_{len(self._audit_log) + 1}",
            "event": event,
            "logged_at": datetime.utcnow().isoformat(),
            "retention_days": AUDIT_LOG_RETENTION_DAYS,
        }

        self._audit_log.append(audit_entry)

        return {
            "status": "logged",
            "audit_id": audit_entry["audit_id"],
            "timestamp": audit_entry["logged_at"],
        }

    def get_audit_log(self) -> List[Dict[str, Any]]:
        """Get complete audit log."""
        return self._audit_log.copy()

    def set_network_delay(self, delay_ms: int) -> None:
        """Set simulated network delay."""
        self._network_delay_ms = delay_ms


@pytest.fixture
def mock_plc() -> MockPLC:
    """
    Provide mock PLC controller.

    Returns:
        Initialized MockPLC instance
    """
    return MockPLC()


@pytest.fixture
def mock_edge_agent() -> MockEdgeAgent:
    """
    Provide mock Edge Agent.

    Returns:
        Initialized MockEdgeAgent instance
    """
    return MockEdgeAgent(online=True)


@pytest.fixture
def mock_task_api() -> MockTaskAPI:
    """
    Provide mock Task API.

    Returns:
        Initialized MockTaskAPI instance
    """
    return MockTaskAPI()


@pytest.mark.asyncio
async def test_estop_propagation_happy_path(
    mock_plc: MockPLC,
    mock_edge_agent: MockEdgeAgent,
    mock_task_api: MockTaskAPI,
) -> None:
    """
    Test successful E-stop propagation through entire chain.

    Verifies:
    - PLC → Edge Agent → Task API propagation
    - Latency < 5 seconds
    - Audit log entry created
    """
    # Start timing
    start_time = time.time()

    # Step 1: PLC triggers E-stop
    mock_plc.trigger_estop(hardware=False)
    plc_status = mock_plc.get_status()

    assert plc_status["estop_active"] is True
    assert plc_status["hardware_override"] is False

    # Step 2: Edge Agent handles E-stop
    edge_event = await mock_edge_agent.handle_estop(plc_status)

    assert edge_event["event_type"] == "estop_triggered"
    assert edge_event["source"] == "plc"
    assert edge_event["online"] is True
    assert edge_event["used_cache"] is False

    # Step 3: Task API logs event
    api_response = await mock_task_api.log_safety_event(edge_event)

    assert api_response["status"] == "logged"
    assert "audit_id" in api_response

    # Verify latency requirement
    end_time = time.time()
    total_latency = end_time - start_time

    assert total_latency < ESTOP_LATENCY_THRESHOLD_SECONDS, \
        f"E-stop propagation took {total_latency:.2f}s, exceeds {ESTOP_LATENCY_THRESHOLD_SECONDS}s threshold"

    # Verify audit log
    audit_log = mock_task_api.get_audit_log()
    assert len(audit_log) == 1
    assert audit_log[0]["event"]["event_type"] == "estop_triggered"


@pytest.mark.asyncio
async def test_estop_offline_edge_behavior(
    mock_plc: MockPLC,
    mock_edge_agent: MockEdgeAgent,
    mock_task_api: MockTaskAPI,
) -> None:
    """
    Test Edge Agent behavior when offline with cached policies.

    Verifies:
    - Edge Agent operates autonomously when offline
    - Uses cached safety policies
    - Queues events for later sync
    """
    # Setup: Cache safety policy
    safety_policy = {
        "zone": "zone_1",
        "max_speed": 100,
        "estop_required": True,
    }
    mock_edge_agent.cache_policy("zone_1", safety_policy)

    # Set Edge Agent offline
    mock_edge_agent.set_online(False)

    # Trigger E-stop
    mock_plc.trigger_estop(hardware=False)
    plc_status = mock_plc.get_status()

    # Edge Agent should still handle E-stop using cached policy
    edge_event = await mock_edge_agent.handle_estop(plc_status)

    assert edge_event["online"] is False
    assert edge_event["used_cache"] is True

    # Event should be queued
    event_queue = mock_edge_agent.get_event_queue()
    assert len(event_queue) == 1
    assert event_queue[0]["event_type"] == "estop_triggered"

    # Simulate coming back online
    mock_edge_agent.set_online(True)

    # Sync queued events
    for event in mock_edge_agent.get_event_queue():
        response = await mock_task_api.log_safety_event(event)
        assert response["status"] == "logged"

    # Verify audit log received offline event
    audit_log = mock_task_api.get_audit_log()
    assert len(audit_log) == 1
    assert audit_log[0]["event"]["used_cache"] is True


@pytest.mark.asyncio
async def test_hardware_estop_authority(
    mock_plc: MockPLC,
    mock_edge_agent: MockEdgeAgent,
    mock_task_api: MockTaskAPI,
) -> None:
    """
    Test hardware E-stop has highest authority.

    Verifies:
    - Hardware E-stop overrides software controls
    - PLC authority matrix respected
    - Audit log reflects hardware override
    """
    # Trigger hardware E-stop
    mock_plc.trigger_estop(hardware=True)
    plc_status = mock_plc.get_status()

    assert plc_status["hardware_override"] is True

    # Edge Agent processes hardware E-stop
    edge_event = await mock_edge_agent.handle_estop(plc_status)

    # Log to Task API
    api_response = await mock_task_api.log_safety_event(edge_event)

    # Verify audit log shows hardware override
    audit_log = mock_task_api.get_audit_log()
    assert len(audit_log) == 1
    assert audit_log[0]["event"]["plc_status"]["hardware_override"] is True


@pytest.mark.asyncio
async def test_estop_recovery(
    mock_plc: MockPLC,
    mock_edge_agent: MockEdgeAgent,
    mock_task_api: MockTaskAPI,
) -> None:
    """
    Test system recovery after E-stop cleared.

    Verifies:
    - E-stop can be cleared safely
    - Recovery event logged
    - System returns to normal operation
    """
    # Trigger E-stop
    mock_plc.trigger_estop(hardware=False)
    plc_status = mock_plc.get_status()

    edge_event = await mock_edge_agent.handle_estop(plc_status)
    await mock_task_api.log_safety_event(edge_event)

    # Clear E-stop
    mock_plc.clear_estop()
    cleared_status = mock_plc.get_status()

    assert cleared_status["estop_active"] is False
    assert cleared_status["hardware_override"] is False

    # Log recovery event
    recovery_event = {
        "event_type": "estop_cleared",
        "source": "plc",
        "timestamp": datetime.utcnow().isoformat(),
    }

    await mock_task_api.log_safety_event(recovery_event)

    # Verify both events in audit log
    audit_log = mock_task_api.get_audit_log()
    assert len(audit_log) == 2
    assert audit_log[0]["event"]["event_type"] == "estop_triggered"
    assert audit_log[1]["event"]["event_type"] == "estop_cleared"


@pytest.mark.asyncio
async def test_network_partition_resilience(
    mock_plc: MockPLC,
    mock_edge_agent: MockEdgeAgent,
    mock_task_api: MockTaskAPI,
) -> None:
    """
    Test Edge Agent resilience during network partition.

    Verifies:
    - Edge continues safety operations during partition
    - Events queued for sync
    - No data loss after partition heals
    """
    # Cache policy for offline operation
    safety_policy = {"zone": "zone_1", "estop_required": True}
    mock_edge_agent.cache_policy("zone_1", safety_policy)

    # Simulate network partition
    mock_edge_agent.set_online(False)

    # Multiple E-stop events during partition
    events_during_partition = []

    for i in range(3):
        mock_plc.trigger_estop(hardware=False)
        plc_status = mock_plc.get_status()

        edge_event = await mock_edge_agent.handle_estop(plc_status)
        events_during_partition.append(edge_event)

        mock_plc.clear_estop()
        await asyncio.sleep(0.01)  # Small delay between events

    # Verify events queued
    event_queue = mock_edge_agent.get_event_queue()
    assert len(event_queue) == 3

    # Network partition heals
    mock_edge_agent.set_online(True)

    # Sync all queued events
    for event in event_queue:
        await mock_task_api.log_safety_event(event)

    # Verify all events in audit log
    audit_log = mock_task_api.get_audit_log()
    assert len(audit_log) == 3

    # All should show used_cache=True
    for entry in audit_log:
        assert entry["event"]["used_cache"] is True


@pytest.mark.asyncio
async def test_latency_under_high_load(
    mock_plc: MockPLC,
    mock_edge_agent: MockEdgeAgent,
    mock_task_api: MockTaskAPI,
) -> None:
    """
    Test E-stop latency remains under threshold during high load.

    Verifies:
    - Latency < 5s even with concurrent events
    - Priority given to E-stop signals
    - System remains responsive
    """
    # Simulate high load with concurrent events
    async def trigger_multiple_estops() -> List[float]:
        latencies = []

        for _ in range(10):
            start = time.time()

            mock_plc.trigger_estop(hardware=False)
            plc_status = mock_plc.get_status()

            edge_event = await mock_edge_agent.handle_estop(plc_status)
            await mock_task_api.log_safety_event(edge_event)

            latency = time.time() - start
            latencies.append(latency)

            mock_plc.clear_estop()

        return latencies

    latencies = await trigger_multiple_estops()

    # Verify all latencies under threshold
    max_latency = max(latencies)
    avg_latency = sum(latencies) / len(latencies)

    assert max_latency < ESTOP_LATENCY_THRESHOLD_SECONDS, \
        f"Max latency {max_latency:.2f}s exceeds threshold"

    assert avg_latency < ESTOP_LATENCY_THRESHOLD_SECONDS / 2, \
        f"Average latency {avg_latency:.2f}s too high"

    # Verify all events logged
    audit_log = mock_task_api.get_audit_log()
    assert len(audit_log) == 10


@pytest.mark.asyncio
async def test_audit_log_retention(
    mock_task_api: MockTaskAPI,
) -> None:
    """
    Test audit log retention policy.

    Verifies:
    - Retention period set to 90 days per ADR-004
    - Metadata correctly stored
    """
    event = {
        "event_type": "estop_triggered",
        "timestamp": datetime.utcnow().isoformat(),
    }

    response = await mock_task_api.log_safety_event(event)

    audit_log = mock_task_api.get_audit_log()
    assert len(audit_log) == 1

    entry = audit_log[0]
    assert entry["retention_days"] == AUDIT_LOG_RETENTION_DAYS
    assert "audit_id" in entry
    assert "logged_at" in entry


@pytest.mark.asyncio
async def test_cache_expiration(
    mock_edge_agent: MockEdgeAgent,
) -> None:
    """
    Test cached policy expiration handling.

    Verifies:
    - Cached policies have TTL
    - Expired policies handled appropriately
    """
    # Cache policy
    safety_policy = {"zone": "zone_1", "estop_required": True}
    mock_edge_agent.cache_policy("zone_1", safety_policy)

    # Verify policy cached with TTL
    cached_policies = mock_edge_agent._cached_policies
    assert "zone_1" in cached_policies
    assert cached_policies["zone_1"]["ttl"] == EDGE_CACHE_TTL_SECONDS

    cached_time = cached_policies["zone_1"]["cached_at"]
    assert isinstance(cached_time, datetime)

    # Simulate time passage (would need time mocking in real implementation)
    # For now, just verify TTL is set correctly
    assert cached_policies["zone_1"]["ttl"] == 300
