import csv
import math
import statistics

from django.conf import settings
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from catalogue.models import Inventory
from core.tests.factories import product
from forecasting.artifacts import WEEKS, load_artifacts
from ml.train_forecast import HOLDOUT_ORIGIN, load_data, split_at
from ml.validate_forecast import validate


class ArtifactTests(SimpleTestCase):
    def test_schema_and_exact_160_rows(self):
        self.assertEqual(len(validate(settings.BASE_DIR)), 160)

    def test_training_excludes_future_and_targets_have_no_sales(self):
        history, _, _ = load_data()
        for rows in history.values():
            train, targets, actual = split_at(rows, HOLDOUT_ORIGIN)
            self.assertTrue(all(r["week"] < HOLDOUT_ORIGIN for r in train))
            self.assertTrue(all(r["week"] >= HOLDOUT_ORIGIN for r in targets))
            self.assertTrue(all("units" not in r for r in targets))


class ReorderTests(TestCase):
    def test_formula_and_live_inventory(self):
        lead, forecasts, safety = load_artifacts()
        sku = next(iter(lead))
        product(sku, stock=0)
        client = APIClient()
        response = client.get(f"/api/forecast/{sku}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([r["week_start"] for r in response.json()["forecast"]], list(WEEKS))
        with (settings.DATA_DIR / "sales_history.csv").open(encoding="utf-8") as stream:
            rows = sorted(
                (r for r in csv.DictReader(stream) if r["sku"] == sku),
                key=lambda r: r["week_start"],
            )[-12:]
        expected = math.ceil(
            1.65 * statistics.stdev(float(r["units_sold"]) for r in rows) * math.sqrt(lead[sku])
        )
        results = client.get("/api/reorder-suggestions/").json()["results"]
        self.assertEqual(len(results), 40)
        entry = next(r for r in results if r["sku"] == sku)
        self.assertEqual(entry["safety_stock"], expected)
        self.assertEqual(entry["reorder_qty"], math.ceil(entry["reorder_point"]))
        Inventory.objects.filter(pk=sku).update(quantity=100000)
        entry = next(
            r for r in client.get("/api/reorder-suggestions/").json()["results"] if r["sku"] == sku
        )
        self.assertEqual(entry["current_stock"], 100000)
        self.assertEqual(entry["reorder_qty"], 0)
        self.assertEqual(client.get("/api/forecast/MISSING/").status_code, 404)
