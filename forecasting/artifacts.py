"""Validated, immutable CSV artifacts; current inventory is deliberately not cached."""

import csv
import math
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from django.conf import settings

WEEKS = ("2026-09-28", "2026-10-05", "2026-10-12", "2026-10-19")


@lru_cache(maxsize=4)
def _read(data_path, forecast_path, signatures):
    data = Path(data_path)

    def rows(path):
        with path.open(encoding="utf-8", newline="") as source:
            return list(csv.DictReader(source))

    lead = {r["sku"]: int(r["lead_time_weeks"]) for r in rows(data / "lead_times.csv")}
    forecasts = {sku: {} for sku in lead}
    forecast_rows = rows(Path(forecast_path))
    for row in forecast_rows:
        if list(row) != ["sku", "week_start", "forecast_units"]:
            raise ValueError("Invalid forecast columns.")
        sku, week, value = row["sku"], row["week_start"], Decimal(row["forecast_units"])
        if (
            sku not in lead
            or week not in WEEKS
            or week in forecasts[sku]
            or not value.is_finite()
            or value < 0
        ):
            raise ValueError("Invalid or duplicate forecast row.")
        forecasts[sku][week] = value
    if len(forecast_rows) != len(lead) * 4 or any(
        set(values) != set(WEEKS) for values in forecasts.values()
    ):
        raise ValueError("Forecast must contain one row for every SKU and forecast week.")
    history = {sku: [] for sku in lead}
    for row in rows(data / "sales_history.csv"):
        if row["sku"] in history:
            history[row["sku"]].append((row["week_start"], float(row["units_sold"])))
    safety = {}
    for sku, values in history.items():
        recent = [v for _, v in sorted(values)[-12:]]
        mean = sum(recent) / len(recent) if recent else 0
        sigma = (
            math.sqrt(sum((x - mean) ** 2 for x in recent) / (len(recent) - 1))
            if len(recent) > 1
            else 0
        )
        safety[sku] = math.ceil(1.65 * sigma * math.sqrt(lead[sku]))
    return lead, forecasts, safety


def load_artifacts():
    data, forecast = settings.DATA_DIR, settings.BASE_DIR / "ml" / "forecast.csv"
    paths = [data / "lead_times.csv", data / "sales_history.csv", forecast]
    return _read(
        str(data), str(forecast), tuple((p.stat().st_mtime_ns, p.stat().st_size) for p in paths)
    )
