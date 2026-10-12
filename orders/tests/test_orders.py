from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

from django.db import close_old_connections, connections
from django.db.models.deletion import ProtectedError
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from catalogue.models import Inventory, Product
from core.errors import APIError
from core.tests.factories import dealer, product
from orders.models import Order
from orders.services import create_draft, transition


class OrderTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.p = product()
        self.d = dealer()
        self.payload = {"dealer_id": self.d.pk, "items": [{"sku": self.p.pk, "quantity": 2}]}

    def test_draft_stock_and_current_price_then_lock(self):
        data, _ = create_draft(self.payload)
        number = data["order_number"]
        self.assertEqual(Inventory.objects.get(pk=self.p.pk).quantity, 5)
        Product.objects.filter(pk=self.p.pk).update(price=Decimal("20.00"))
        self.assertEqual(
            self.client.get(f"/api/orders/{number}/").json()["items"][0]["unit_price"], "20.00"
        )
        result = transition(number, "confirm")
        self.assertEqual(result["grand_total"], "47.20")
        Product.objects.filter(pk=self.p.pk).update(price=Decimal("50.00"))
        self.assertEqual(
            self.client.get(f"/api/orders/{number}/").json()["items"][0]["unit_price"], "20.00"
        )
        self.assertEqual(Inventory.objects.get(pk=self.p.pk).quantity, 3)

    def test_tax_rounded_per_line_half_up(self):
        Product.objects.filter(pk=self.p.pk).update(price=Decimal("0.25"))
        other = product("BRK-SECOND", price="0.25")
        data, _ = create_draft(
            {
                "dealer_id": self.d.pk,
                "items": [{"sku": self.p.pk, "quantity": 1}, {"sku": other.pk, "quantity": 1}],
            }
        )
        self.assertEqual(data["tax_total"], "0.10")
        self.assertEqual(data["grand_total"], "0.60")

    def test_all_shortages_and_rollback(self):
        other = product("OTHER", stock=0)
        data, _ = create_draft(
            {
                "dealer_id": self.d.pk,
                "items": [{"sku": self.p.pk, "quantity": 10}, {"sku": other.pk, "quantity": 1}],
            }
        )
        response = self.client.post(f"/api/orders/{data['order_number']}/confirm/")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(len(response.json()["error"]["details"]), 2)
        self.assertEqual(Inventory.objects.get(pk=self.p.pk).quantity, 5)
        self.assertEqual(Order.objects.get(order_number=data["order_number"]).status, "DRAFT")

    def test_cancel_once_and_transition_rules(self):
        data, _ = create_draft(self.payload)
        number = data["order_number"]
        transition(number, "confirm")
        transition(number, "cancel")
        self.assertEqual(Inventory.objects.get(pk=self.p.pk).quantity, 5)
        response = self.client.post(f"/api/orders/{number}/cancel/")
        self.assertEqual(response.json()["error"]["code"], "INVALID_TRANSITION")
        self.assertEqual(Inventory.objects.get(pk=self.p.pk).quantity, 5)
        self.assertEqual(
            self.client.put(
                f"/api/orders/{number}/", {"items": self.payload["items"]}, format="json"
            ).json()["error"]["code"],
            "ORDER_LOCKED",
        )

    def test_dispatch_deliver_and_no_cancel(self):
        data, _ = create_draft(self.payload)
        number = data["order_number"]
        transition(number, "confirm")
        transition(number, "dispatch")
        with self.assertRaises(APIError):
            transition(number, "cancel")
        self.assertEqual(transition(number, "deliver")["status"], "DELIVERED")

    def test_edit_replaces_items(self):
        data, _ = create_draft(self.payload)
        number = data["order_number"]
        other = product("OTHER")
        response = self.client.put(
            f"/api/orders/{number}/", {"items": [{"sku": other.pk, "quantity": 3}]}, format="json"
        )
        self.assertEqual([x["sku"] for x in response.json()["items"]], ["OTHER"])

    def test_validation(self):
        payloads = [
            {},
            {"dealer_id": 999999, "items": self.payload["items"]},
            {"dealer_id": self.d.pk, "items": []},
            {"dealer_id": self.d.pk, "items": [{"sku": "UNKNOWN", "quantity": 1}]},
            {"dealer_id": self.d.pk, "items": self.payload["items"] * 2},
        ]
        payloads += [
            {"dealer_id": self.d.pk, "items": [{"sku": self.p.pk, "quantity": q}]}
            for q in [0, -1, 1.2, True, "2"]
        ]
        for payload in payloads:
            with self.subTest(payload=payload):
                self.assertEqual(
                    self.client.post("/api/orders/", payload, format="json").status_code, 400
                )
        self.assertFalse(Order.objects.exists())

    def test_idempotency_conflict(self):
        first, _ = create_draft(self.payload, "same")
        second, created = create_draft(self.payload, "same")
        self.assertEqual(first["order_number"], second["order_number"])
        self.assertFalse(created)
        with self.assertRaises(APIError) as caught:
            create_draft({**self.payload, "items": [{"sku": self.p.pk, "quantity": 1}]}, "same")
        self.assertEqual(caught.exception.code, "IDEMPOTENCY_CONFLICT")

    def test_ist_date_and_protected_relationships(self):
        with patch(
            "django.utils.timezone.now",
            return_value=datetime(2026, 10, 11, 20, 0, tzinfo=timezone.utc),
        ):
            data, _ = create_draft(self.payload)
        self.assertTrue(data["order_number"].startswith("ORD-20261012-"))
        with self.assertRaises(ProtectedError):
            self.d.delete()
        with self.assertRaises(ProtectedError):
            self.p.delete()


class ConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.p = product(stock=1)
        self.d = dealer()
        self.payload = {"dealer_id": self.d.pk, "items": [{"sku": self.p.pk, "quantity": 1}]}

    def parallel(self, functions):
        barrier = Barrier(len(functions))

        def execute(fn):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    return fn()
                except APIError as exc:
                    return exc.code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(functions)) as executor:
            return list(executor.map(execute, functions))

    def test_concurrent_confirm_never_oversells(self):
        numbers = [create_draft(self.payload)[0]["order_number"] for _ in range(4)]
        results = self.parallel([lambda n=n: transition(n, "confirm") for n in numbers])
        self.assertEqual(sum(isinstance(r, dict) for r in results), 1)
        self.assertEqual(results.count("INSUFFICIENT_STOCK"), 3)
        self.assertEqual(Inventory.objects.get(pk=self.p.pk).quantity, 0)

    def test_simultaneous_idempotency_and_daily_numbers(self):
        results = self.parallel(
            [lambda: create_draft(self.payload, "concurrent")[0] for _ in range(4)]
        )
        self.assertEqual(len({r["order_number"] for r in results}), 1)
        self.assertEqual(Order.objects.count(), 1)
        results = self.parallel([lambda: create_draft(self.payload)[0] for _ in range(4)])
        self.assertEqual(len({r["order_number"] for r in results}), 4)

    def test_concurrent_cancel_restores_once(self):
        number = create_draft(self.payload)[0]["order_number"]
        transition(number, "confirm")
        results = self.parallel([lambda: transition(number, "cancel") for _ in range(4)])
        self.assertEqual(sum(isinstance(r, dict) for r in results), 1)
        self.assertEqual(Inventory.objects.get(pk=self.p.pk).quantity, 1)
