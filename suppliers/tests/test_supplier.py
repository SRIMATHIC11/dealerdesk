from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from catalogue.models import Inventory, Product
from core.errors import APIError
from core.tests.factories import product
from supplier_mock.mock_supplier import SupplierMock, serve
from suppliers.client import fetch_feed
from suppliers.services import synchronize


def item(sku="BRK-TEST", price="12.50", updated="2026-10-02T10:00:00Z"):
    return {
        "supplier_sku": "SUP-" + sku,
        "sku": sku,
        "name": "Updated pad",
        "brand": "B",
        "category": "Brakes",
        "vehicle_fitment": "Pulsar 150",
        "description": "Description",
        "price": price,
        "updated_at": updated,
        "supplier_stock": 999,
    }


def response(status, body=None, headers=None):
    result = MagicMock()
    result.status_code = status
    result.json.return_value = body
    result.headers = headers or {}
    return result


class ApplyTests(TestCase):
    def setUp(self):
        self.p = product(stock=3)

    @patch("suppliers.services.fetch_feed")
    def test_latest_valid_duplicate_idempotency_and_stock(self, fetch):
        fetch.return_value = (
            [
                item(),
                item(price="11.00", updated="2026-10-01T10:00:00Z"),
                item("NEW"),
                item("BAD", "1.234"),
                item("", "9"),
                item(price="NaN", updated="2026-10-03T10:00:00Z"),
            ],
            {"pages_fetched": 2, "requests_made": 3},
        )
        first = synchronize()
        self.assertEqual((first["created"], first["updated"], first["unchanged"]), (1, 1, 0))
        self.assertEqual(len(first["rejected"]), 3)
        self.assertEqual(Product.objects.get(pk=self.p.pk).price, Decimal("12.50"))
        self.assertEqual(Inventory.objects.get(pk=self.p.pk).quantity, 3)
        self.assertEqual(Inventory.objects.get(pk="NEW").quantity, 0)
        second = synchronize()
        self.assertEqual((second["created"], second["updated"], second["unchanged"]), (0, 0, 2))

    @patch(
        "suppliers.services.fetch_feed",
        side_effect=APIError("SUPPLIER_UNAVAILABLE", "Failure", 502),
    )
    def test_failed_fetch_changes_nothing(self, fetch):
        before = list(Product.objects.values())
        with self.assertRaises(APIError):
            synchronize()
        self.assertEqual(list(Product.objects.values()), before)
        self.assertEqual(Inventory.objects.get(pk=self.p.pk).quantity, 3)


@override_settings(SUPPLIER_API_URL="https://supplier.example", SUPPLIER_API_KEY="test-placeholder")
class FetchTests(TestCase):
    @patch("suppliers.client.time.sleep")
    @patch("suppliers.client.requests.Session")
    def test_pagination_retry_after_and_transient(self, session, sleep):
        client = session.return_value.__enter__.return_value
        client.get.side_effect = [
            response(429, headers={"Retry-After": "2"}),
            response(200, {"items": [item()], "next_cursor": "next"}),
            response(503),
            response(200, {"items": [item("NEXT")], "next_cursor": None}),
        ]
        items, stats = fetch_feed()
        self.assertEqual(len(items), 2)
        self.assertEqual(stats, {"pages_fetched": 2, "requests_made": 4})
        sleep.assert_any_call(2.0)
        self.assertNotIn("cursor", client.get.call_args_list[0].kwargs["params"])
        self.assertEqual(client.get.call_args_list[2].kwargs["params"]["cursor"], "next")

    @patch("suppliers.client.time.sleep")
    @patch("suppliers.client.requests.Session")
    def test_exactly_five_attempts_and_401_no_retry(self, session, sleep):
        client = session.return_value.__enter__.return_value
        client.get.return_value = response(503)
        with self.assertRaises(APIError):
            fetch_feed()
        self.assertEqual(client.get.call_count, 5)
        client.get.reset_mock()
        client.get.return_value = response(401)
        with self.assertRaises(APIError):
            fetch_feed()
        self.assertEqual(client.get.call_count, 1)

    @patch("suppliers.client.requests.Session")
    def test_bad_feed_or_cursor_loop_fails(self, session):
        client = session.return_value.__enter__.return_value
        client.get.return_value = response(200, {"items": [], "next_cursor": "loop"})
        with self.assertRaises(APIError):
            fetch_feed()
        self.assertEqual(client.get.call_count, 2)


class LiveMockTests(TestCase):
    def test_real_http_outage_after_first_page_leaves_database_unchanged(self):
        product(stock=3)
        feed = [item()] + [item(f"NEW-{n}") for n in range(21)]
        mock = SupplierMock(feed, "local-test-key", outage_pages=[1])
        server = serve(mock, port=0)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        before = list(Product.objects.values())
        with override_settings(
            SUPPLIER_API_URL=f"http://127.0.0.1:{server.server_port}",
            SUPPLIER_API_KEY="local-test-key",
        ):
            with self.assertRaises(APIError) as failure:
                synchronize()
        self.assertEqual(failure.exception.status_code, 502)
        self.assertEqual(list(Product.objects.values()), before)
        self.assertEqual(Inventory.objects.get(pk="BRK-TEST").quantity, 3)
        self.assertEqual([entry["status"] for entry in mock.log], [200] + [503] * 5)
