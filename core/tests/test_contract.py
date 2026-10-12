from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient

from catalogue.models import Inventory, Product
from core.tests.factories import dealer, product
from dealers.models import Dealer


class ContractTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.product = product()
        self.dealer = dealer()

    def test_health_and_pagination(self):
        self.assertEqual(self.client.get("/api/health/").json(), {"status": "ok"})
        result = self.client.get("/api/products/?search=pulsar&page_size=200").json()
        self.assertTrue({"count", "next", "previous", "results"}.issubset(result))
        self.assertEqual(result["results"][0]["price"], "10.03")
        self.assertEqual(result["results"][0]["stock"], 5)
        self.assertEqual(self.client.get("/api/products/?vehicle=wrong").json()["count"], 0)
        self.assertEqual(self.client.get("/api/products/?category=Brakes").json()["count"], 1)

    def test_product_create_zero_inventory_and_duplicate(self):
        payload = {"sku": "NEW", "name": "New part", "price": "1.25"}
        response = self.client.post("/api/products/", payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["stock"], 0)
        self.assertEqual(
            self.client.post("/api/products/", payload, format="json").json()["error"]["code"],
            "DUPLICATE",
        )

    def test_invalid_prices(self):
        for value in ["0", "-1", "2.001", "NaN", "Infinity", "abc"]:
            with self.subTest(value=value):
                response = self.client.post(
                    "/api/products/", {"sku": "BAD", "name": "Bad", "price": value}, format="json"
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")

    def test_sku_cannot_change(self):
        response = self.client.patch("/api/products/BRK-TEST/", {"sku": "OTHER"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertTrue(Product.objects.filter(pk="BRK-TEST").exists())

    def test_inventory_strict_integer(self):
        for value in [-1, 1.5, True, "3"]:
            self.assertEqual(
                self.client.put(
                    "/api/inventory/BRK-TEST/", {"quantity": value}, format="json"
                ).status_code,
                400,
            )
        response = self.client.put(
            "/api/inventory/BRK-TEST/", {"quantity": 0, "reason": "stock count"}, format="json"
        )
        self.assertEqual(response.json(), {"sku": "BRK-TEST", "quantity": 0})
        self.assertEqual(
            self.client.put("/api/inventory/NOPE/", {"quantity": 1}, format="json").status_code, 404
        )

    def test_dealer_validation_and_duplicate(self):
        response = self.client.post(
            "/api/dealers/", {"dealer_code": "D2", "name": "Second"}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["credit_limit"], "0.00")
        self.assertEqual(
            self.client.post(
                "/api/dealers/", {"dealer_code": "D2", "name": "Second"}, format="json"
            ).status_code,
            409,
        )
        self.assertEqual(
            self.client.post("/api/dealers/", {"name": "Missing code"}, format="json").status_code,
            400,
        )

    def test_error_envelopes(self):
        for path in ["/api/products/MISSING/", "/api/dealers/999999/", "/api/products/?page=0"]:
            response = self.client.get(path)
            self.assertEqual(set(response.json()["error"]), {"code", "message", "details"})
        response = self.client.post("/api/products/", "{bad", content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_database_constraints(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Inventory.objects.filter(pk=self.product.pk).update(quantity=-1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Product.objects.filter(pk=self.product.pk).update(price=Decimal(0))

    def test_unknown_api_route_is_json_even_in_debug(self):
        response = self.client.get("/api/not-a-real-endpoint/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "NOT_FOUND")


class SeedTests(TestCase):
    def test_seed_twice_and_preserve_changes(self):
        call_command("seed_data", stdout=StringIO())
        self.assertEqual(Product.objects.count(), 600)
        self.assertEqual(Inventory.objects.count(), 600)
        self.assertEqual(Dealer.objects.count(), 25)
        chosen = Product.objects.first()
        Product.objects.filter(pk=chosen.pk).update(price=Decimal("99.99"))
        Inventory.objects.filter(pk=chosen.pk).update(quantity=3)
        call_command("seed_data", stdout=StringIO())
        self.assertEqual(Product.objects.count(), 600)
        self.assertEqual(Dealer.objects.count(), 25)
        chosen.refresh_from_db()
        self.assertEqual(chosen.price, Decimal("99.99"))
        self.assertEqual(chosen.inventory.quantity, 3)
