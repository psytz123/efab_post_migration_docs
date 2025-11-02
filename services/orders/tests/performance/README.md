# Orders Service Load Test

## Prerequisites
- Orders service deployed locally or accessible via URL
- Locust installed in the virtual environment (`pip install locust`)

## Running
```bash
locust -f services/orders/tests/performance/locustfile.py --host http://localhost:8080
```

## Targets
- 100 order creations per minute (p95 latency <200ms)
- Monitor Prometheus metrics: `orders_created_total`, `orders_state_transition_denied_total`
- Validate Kafka publish latency once aiokafka hooked to real broker
