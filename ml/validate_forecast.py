import csv
from decimal import Decimal
from pathlib import Path


def validate(root):
    with (root / "data/lead_times.csv").open(encoding="utf-8") as source:
        skus = {r["sku"] for r in csv.DictReader(source)}
    weeks = {"2026-09-28", "2026-10-05", "2026-10-12", "2026-10-19"}
    with (root / "ml/forecast.csv").open(encoding="utf-8") as source:
        reader = csv.DictReader(source)
        assert reader.fieldnames == ["sku", "week_start", "forecast_units"], "Wrong columns"
        rows = list(reader)
    assert len(rows) == 160, "Expected exactly 160 rows"
    assert {(r["sku"], r["week_start"]) for r in rows} == {(s, w) for s in skus for w in weeks}, (
        "Missing/duplicate SKU/week"
    )
    assert all(
        Decimal(r["forecast_units"]).is_finite() and Decimal(r["forecast_units"]) >= 0 for r in rows
    ), "Invalid demand"
    return rows


if __name__ == "__main__":
    validate(Path(__file__).resolve().parents[1])
    print("Forecast valid: 160 unique nonnegative SKU/week rows, exact schema and horizon.")
