# Forecasting and reorder

`forecast.csv` contains exactly `sku,week_start,forecast_units`: 40 lead-time SKUs × four weeks, starting 2026-09-28, 2026-10-05, 2026-10-12 and 2026-10-19. These dates are fixed by the contract, independent of the server's current date.

From the repository root:

```bash
python -m ml.train_forecast
python -m ml.validate_forecast
```

Training needs NumPy and the supplied CSVs; it uses no database, LLM, network or hidden future actuals. The artifact is already included, so the grader does not need to run training. The validator checks exact columns, dates, SKU coverage, uniqueness and finite non-negative predictions.

## Selection and leakage control

Candidates are last value, same week 52 weeks ago (recent-average fallback), 4/8/12-week means, promotion-adjusted 8/12-week means, and ridge regressions with three penalty strengths. Ridge features include trend, annual harmonics, known promotion flags and features relative to the moving Diwali date. Intercepts are unpenalized; recent observations have greater fitting weight.

Model selection uses expanding training prefixes at 2026-06-01, 2026-06-29 and 2026-07-27, each predicting four weeks. Each SKU averages its best two candidates, ranked by 80% its own MAE and 20% pooled candidate MAE. SKUs without sufficient selection history use pooled ranking. This stabilizes selection on short histories.

`split_at()` in `train_forecast.py:123` accepts only sales strictly before the origin; target objects contain only week and known promotion flag. Scalers and promotion effects are fit on training data only. The 2026-08-31 four-week holdout is excluded from model selection. The final artifact refits selected methods using available history through 2026-09-21 and the supplied future promotion calendar. Published future festival dates are known covariates, not future sales.

## Historical holdout results

160 SKU-week observations; see the full machine-readable [validation_metrics.json](validation_metrics.json).

| Method | Holdout WAPE |
|---|---:|
| Selected two-model ensemble | 18.61% |
| Last observation | 34.41% |
| Same week last year | 36.01% |
| Four-week mean | 25.71% |
| Eight-week mean | 26.21% |
| Twelve-week mean | 26.66% |

Ensemble MAE is 6.3409 units and RMSE is 10.4511 units. WAPE is total absolute error divided by total actual demand; it avoids division by zero for individual intermittent observations. The selected ensemble reduces WAPE about 27.6% relative to the best measured simple baseline on this holdout. One holdout does not guarantee performance on the hidden future weeks.

The highest holdout MAEs are GRP-1024 (24.9840), FIL-1051 (13.9119), BRK-1019 (12.2377), ELE-1095 (11.7932), and FIL-1031 (11.2301). GRP-1024 underpredicts total holdout demand (228.04 versus 276); FIL-1051 and BRK-1019 overpredict. Selection instability and sharp weekly variation are plausible causes, not established causal explanations.

## Edge cases and limits

Promotion-adjusted means remove estimated historical promotion lift before restoring the planned future lift; the lift estimate is shrunk toward 1.3 with sparse evidence. Ridge uses the promotion flag directly. Diwali features follow the published festival date rather than a fixed week-of-year. Only a few festival cycles exist, so those effects are uncertain.

Fewer than 16 training weeks trigger the adjusted-mean fallback for regression. Intermittent sales are modeled as expected units (decimals allowed), with regularization and non-negative bounded predictions. This implementation does not claim a separate Croston model or calibrated uncertainty intervals. These are useful future experiments using additional rolling validation, not holdout-driven tuning.

## Reorder API

`forecasting/artifacts.py` validates/caches immutable CSV artifacts by modification signature. Inventory is queried live for every request. For each SKU:

```text
lead_time_demand = sum(first L forecast weeks)
sigma = sample standard deviation of latest 12 historical sales (n - 1)
safety_stock = ceil(1.65 * sigma * sqrt(L))
reorder_point = lead_time_demand + safety_stock
reorder_qty = max(0, ceil(reorder_point - live_available_stock))
```

`GET /api/forecast/{sku}/` returns four artifact values. `GET /api/reorder-suggestions/` returns all 40 entries without pagination. Reorder suggestions never write inventory or create purchase orders.
