from datetime import datetime, timezone
from uuid import uuid4

from locust import HttpUser, between, task


class OrdersUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        self.base_payload = {
            "customer_ref": "LOCUST-PO",
            "sku": "LOCUST-SKU",
            "quantity": 10,
            "site_id": "bk-mill-01",
        }

    @task(3)
    def create_order(self):
        payload = {
            **self.base_payload,
            "due_date": datetime.now(timezone.utc).isoformat(),
            "lots": [
                {"lot_id": f"LOCUST-{uuid4().hex}", "quantity": 10, "cell_id": "CellX"}
            ],
        }
        response = self.client.post("/orders", json=payload)
        if response.status_code == 201:
            order_id = response.json()["order_id"]
            self.client.get(f"/orders/{order_id}")

    @task(1)
    def list_orders(self):
        self.client.get("/orders?state=draft")


# Run via: locust -f services/orders/tests/performance/locustfile.py --host http://localhost:8080
