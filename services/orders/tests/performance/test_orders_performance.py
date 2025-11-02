import pytest

pytestmark = pytest.mark.performance


def test_orders_create_throughput_baseline():
    pytest.skip("Performance harness pending Locust/k6 integration.")
