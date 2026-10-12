"""Reproducible expanding-window selection, untouched holdout, then final fitting.

Run: python -m ml.train_forecast. No Django/database/provider access is needed.
"""

import csv
import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FORECAST_START = date(2026, 9, 28)
SELECTION_ORIGINS = [date(2026, 6, 1), date(2026, 6, 29), date(2026, 7, 27)]
HOLDOUT_ORIGIN = date(2026, 8, 31)
METHODS = [
    "last",
    "seasonal52",
    "mean4",
    "mean8",
    "mean12",
    "adjusted8",
    "adjusted12",
    "ridge2",
    "ridge12",
    "ridge40",
]


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def load_data():
    history = defaultdict(list)
    for r in read_csv(ROOT / "data/sales_history.csv"):
        history[r["sku"]].append(
            {
                "week": date.fromisoformat(r["week_start"]),
                "units": float(r["units_sold"]),
                "promo": int(r["promo_flag"]),
            }
        )
    for values in history.values():
        values.sort(key=lambda r: r["week"])
    festivals = [
        date.fromisoformat(r["date"]) for r in read_csv(ROOT / "data/festival_calendar.csv")
    ]
    future = defaultdict(list)
    for r in read_csv(ROOT / "data/promo_calendar.csv"):
        future[r["sku"]].append(
            {"week": date.fromisoformat(r["week_start"]), "promo": int(r["promo_flag"])}
        )
    return history, festivals, future


def features(row, festivals):
    t = (row["week"] - date(2024, 1, 1)).days / 365.25
    distance = min(((d - row["week"]).days for d in festivals), key=abs) / 7
    return [
        1.0,
        t,
        np.sin(2 * np.pi * t),
        np.cos(2 * np.pi * t),
        np.sin(4 * np.pi * t),
        np.cos(4 * np.pi * t),
        row["promo"],
        np.exp(-0.5 * ((distance - 1) / 2) ** 2),
        float(0 <= distance <= 4),
    ]


def promo_factor(training):
    # Estimate only from the supplied training prefix; shrink sparse promo evidence.
    normal = [r["units"] for r in training if not r["promo"]]
    promo = [r["units"] for r in training if r["promo"]]
    if not normal or not promo or np.mean(normal) <= 0:
        return 1.3
    observed = float(np.mean(promo) / np.mean(normal))
    weight = len(promo) / (len(promo) + 8)
    return float(np.clip(weight * observed + (1 - weight) * 1.3, 1, 3))


def predict(method, training, targets, festivals):
    if not training:
        return np.zeros(len(targets))
    y = np.array([r["units"] for r in training])
    if method == "last":
        return np.repeat(y[-1], len(targets))
    if method == "seasonal52":
        past = {r["week"]: r["units"] for r in training}
        return np.array(
            [past.get(r["week"] - timedelta(weeks=52), float(np.mean(y[-8:]))) for r in targets]
        )
    if method.startswith("mean"):
        return np.repeat(np.mean(y[-int(method[4:]) :]), len(targets))
    factor = promo_factor(training)
    if method.startswith("adjusted") or len(training) < 16:
        window = int(method[8:]) if method.startswith("adjusted") else 8
        recent = training[-window:]
        base = np.mean([r["units"] / (factor if r["promo"] else 1) for r in recent])
        return np.array([base * (factor if r["promo"] else 1) for r in targets])
    x = np.array([features(r, festivals) for r in training])
    future_x = np.array([features(r, festivals) for r in targets])
    # Fit centering/scaling on training rows only, including the trend origin.
    mean, scale = x[:, 1:].mean(axis=0), x[:, 1:].std(axis=0)
    scale[scale < 1e-8] = 1
    x[:, 1:] = (x[:, 1:] - mean) / scale
    future_x[:, 1:] = (future_x[:, 1:] - mean) / scale
    penalty = np.eye(x.shape[1]) * float(method[5:])
    penalty[0, 0] = 0
    weights = np.linspace(0.6, 1.0, len(y))
    beta = np.linalg.solve(x.T @ (weights[:, None] * x) + penalty, x.T @ (weights * y))
    result = future_x @ beta
    # Guard against unstable extrapolation on new/intermittent series.
    ceiling = max(2.5 * np.quantile(y, 0.95), 2 * np.mean(y[-12:]), 1)
    return np.clip(result, 0, ceiling)


def split_at(history, origin):
    training = [
        r for r in history if r["week"] < origin
    ]  # Leakage barrier: NO target/future sales.
    actual = [r for r in history if origin <= r["week"] < origin + timedelta(weeks=4)]
    targets = [{"week": r["week"], "promo": r["promo"]} for r in actual]
    return training, targets, np.array([r["units"] for r in actual])


def main():
    history, festivals, future = load_data()
    skus = sorted(r["sku"] for r in read_csv(ROOT / "data/lead_times.csv"))
    scores = {sku: {m: [] for m in METHODS} for sku in skus}
    pooled = {m: [] for m in METHODS}
    for origin in SELECTION_ORIGINS:
        for sku in skus:
            train, targets, actual = split_at(history[sku], origin)
            if len(train) < 8 or len(actual) != 4:
                continue
            for method in METHODS:
                error = float(np.abs(predict(method, train, targets, festivals) - actual).mean())
                scores[sku][method].append(error)
                pooled[method].append(error)
    overall = {m: float(np.mean(v)) for m, v in pooled.items()}
    selected = {}
    for sku in skus:
        ranked = sorted(
            METHODS,
            key=lambda m: (
                0.8 * np.mean(scores[sku][m]) + 0.2 * overall[m] if scores[sku][m] else overall[m]
            ),
        )
        selected[sku] = ranked[:2]
    holdout, totals = (
        [],
        {"absolute_error": 0.0, "actual_units": 0.0, "squared_error": 0.0, "rows": 0},
    )
    baseline_errors = defaultdict(float)
    for sku in skus:
        train, targets, actual = split_at(history[sku], HOLDOUT_ORIGIN)
        if not train or not len(actual):
            continue
        pred = np.mean([predict(m, train, targets, festivals) for m in selected[sku]], axis=0)
        errors = np.abs(pred - actual)
        for method in ["last", "seasonal52", "mean4", "mean8", "mean12"]:
            baseline_errors[method] += float(
                np.abs(predict(method, train, targets, festivals) - actual).sum()
            )
        holdout.append(
            {
                "sku": sku,
                "methods": selected[sku],
                "training_weeks": len(train),
                "mae": round(float(errors.mean()), 4),
                "actual_units": float(actual.sum()),
                "forecast_units": round(float(pred.sum()), 4),
            }
        )
        totals["absolute_error"] += float(errors.sum())
        totals["actual_units"] += float(actual.sum())
        totals["squared_error"] += float(((pred - actual) ** 2).sum())
        totals["rows"] += len(actual)
    output = ROOT / "ml/forecast.csv"
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["sku", "week_start", "forecast_units"])
        for sku in skus:
            train = [r for r in history[sku] if r["week"] < FORECAST_START]
            targets = sorted(future[sku], key=lambda r: r["week"])
            prediction = np.mean(
                [predict(m, train, targets, festivals) for m in selected[sku]], axis=0
            )
            for target, value in zip(targets, prediction):
                writer.writerow([sku, target["week"].isoformat(), f"{max(0, value):.4f}"])
    report = {
        "selection_origins": [str(d) for d in SELECTION_ORIGINS],
        "untouched_holdout_origin": str(HOLDOUT_ORIGIN),
        "selection_mean_mae": overall,
        "holdout": {
            "mae": totals["absolute_error"] / totals["rows"],
            "rmse": (totals["squared_error"] / totals["rows"]) ** 0.5,
            "wape": totals["absolute_error"] / totals["actual_units"],
            "rows": totals["rows"],
        },
        "baseline_holdout_wape": {
            m: e / totals["actual_units"] for m, e in baseline_errors.items()
        },
        "worst_holdout_skus": sorted(holdout, key=lambda r: r["mae"], reverse=True),
        "selected_methods": selected,
        "future_actuals_used": False,
        "note": "Promotion flags and published festival dates are known covariates. Model selection excludes the final holdout.",
    }
    (ROOT / "ml/validation_metrics.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["holdout"], indent=2))
    print(f"Wrote {len(skus) * 4} forecasts to ml/forecast.csv")


if __name__ == "__main__":
    main()
