import React, { useState } from "react";
import { ArrowDownToLine, ArrowUpRight, CircleHelp } from "lucide-react";
import { ErrorBox, Busy, Empty, Modal, useLoad } from "../components/common";

export default function Reorder({ revision }) {
  const { data, error, loading } = useLoad("reorder-suggestions/", revision);
  const [sku, setSku] = useState(null),
    [onlyNeeded, setOnlyNeeded] = useState(false);
  const rows = data?.results || [];
  const needed = rows.filter((r) => r.reorder_qty > 0);
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">PLAN THE NEXT FOUR WEEKS</div>
          <h1>Stay ahead of demand.</h1>
          <p>
            Forecasts for 28 Sep–19 Oct 2026, paired with current stock and
            supplier lead times.
          </p>
        </div>
        <a className="secondary" href="/forecast.csv" download>
          <ArrowDownToLine size={17} /> Forecast CSV
        </a>
      </div>
      <div className="metrics">
        <div>
          <span>Forecast SKUs</span>
          <strong>{rows.length || "—"}</strong>
          <small>Four weekly predictions each</small>
        </div>
        <div>
          <span>Need replenishment</span>
          <strong>{data ? needed.length : "—"}</strong>
          <small>Based on live available stock</small>
        </div>
        <div>
          <span>Suggested units</span>
          <strong>
            {data
              ? needed
                  .reduce((s, r) => s + r.reorder_qty, 0)
                  .toLocaleString("en-IN")
              : "—"}
          </strong>
          <small>Across all reorder suggestions</small>
        </div>
      </div>
      <ErrorBox error={error} />
      {loading ? (
        <Busy />
      ) : (
        data && (
          <div className="panel">
            <div className="panel-heading">
              <h2>Reorder suggestions</h2>
              <label className="check-label">
                <input
                  type="checkbox"
                  checked={onlyNeeded}
                  onChange={(e) => setOnlyNeeded(e.target.checked)}
                />{" "}
                Needs reorder only
              </label>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Part SKU</th>
                    <th>Available</th>
                    <th>Lead time</th>
                    <th>Lead-time demand</th>
                    <th>Safety stock</th>
                    <th>Reorder point</th>
                    <th>Order units</th>
                  </tr>
                </thead>
                <tbody>
                  {(onlyNeeded ? needed : rows).map((r) => (
                    <tr key={r.sku}>
                      <td>
                        <button
                          className="text-button"
                          onClick={() => setSku(r.sku)}
                        >
                          {r.sku}
                          <ArrowUpRight size={13} />
                        </button>
                      </td>
                      <td>{r.current_stock}</td>
                      <td>{r.lead_time_weeks} weeks</td>
                      <td>{r.lead_time_demand.toFixed(2)}</td>
                      <td>{r.safety_stock}</td>
                      <td>{r.reorder_point.toFixed(2)}</td>
                      <td>
                        <span
                          className={r.reorder_qty ? "reorder-number" : "muted"}
                        >
                          {r.reorder_qty}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {onlyNeeded && !needed.length && (
              <Empty
                title="Stock covers the reorder points"
                text="No replenishment is suggested at the moment."
              />
            )}
            <div className="table-note">
              <CircleHelp size={15} /> Suggestions help you plan purchasing;
              they do not change inventory or create orders.
            </div>
          </div>
        )
      )}
      {sku && <ForecastDetail sku={sku} onClose={() => setSku(null)} />}
    </>
  );
}

function ForecastDetail({ sku, onClose }) {
  const { data, error, loading } = useLoad(`forecast/${sku}/`);
  const max = Math.max(
    ...(data?.forecast.map((r) => r.forecast_units) || [1]),
    1,
  );
  return (
    <Modal title={`Weekly demand · ${sku}`} onClose={onClose}>
      <div className="modal-body">
        <ErrorBox error={error} />
        {loading ? (
          <Busy />
        ) : (
          data?.forecast.map((r) => (
            <div className="forecast-bar" key={r.week_start}>
              <div>
                <span>{r.week_start}</span>
                <strong>{r.forecast_units.toFixed(2)} units</strong>
              </div>
              <div>
                <i style={{ width: `${(r.forecast_units / max) * 100}%` }} />
              </div>
            </div>
          ))
        )}
      </div>
    </Modal>
  );
}
