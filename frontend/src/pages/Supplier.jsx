import React, { useState } from "react";
import { Truck, Check, RefreshCw, LoaderCircle } from "lucide-react";
import { api } from "../api";
import { ErrorBox, Empty } from "../components/common";

export default function Supplier({ notify }) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(null),
    [result, setResult] = useState(null);
  async function sync() {
    setBusy(true);
    setError(null);
    try {
      const data = await api("sync/supplier/", { method: "POST" });
      setResult(data);
      notify("Supplier catalogue synchronized. Inventory was preserved.");
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">KEEP YOUR CATALOGUE CURRENT</div>
          <h1>Connected to your supplier.</h1>
          <p>
            Bring in new parts and current prices without changing your
            warehouse stock.
          </p>
        </div>
      </div>
      <div className="sync-layout">
        <div className="panel sync-card">
          <span className="welcome-icon">
            <Truck size={34} />
          </span>
          <h2>Supplier catalogue sync</h2>
          <p>
            Fetch the complete supplier feed, validate records and apply the
            latest version of each SKU.
          </p>
          <div className="sync-points">
            <span>
              <Check size={17} /> All pages checked before changes
            </span>
            <span>
              <Check size={17} /> Existing inventory stays unchanged
            </span>
            <span>
              <Check size={17} /> Repeated syncs avoid duplicate records
            </span>
          </div>
          <ErrorBox error={error} />
          <button className="primary full" onClick={sync} disabled={busy}>
            {busy ? (
              <LoaderCircle className="spin" size={18} />
            ) : (
              <RefreshCw size={18} />
            )}{" "}
            {busy ? "Fetching and validating…" : "Synchronize catalogue"}
          </button>
          <small>Temporary upstream failures may take a moment to retry.</small>
        </div>
        <div className="panel sync-results">
          <h2>Latest sync result</h2>
          {!result ? (
            <Empty
              title="Ready when you are"
              text="Run a sync to see created, updated and unchanged parts."
              icon={RefreshCw}
            />
          ) : (
            <>
              <div className="sync-counts">
                {["created", "updated", "unchanged"].map((k) => (
                  <div key={k}>
                    <strong>{result[k]}</strong>
                    <span>{k}</span>
                  </div>
                ))}
              </div>
              <p className="muted">
                {result.pages_fetched} pages fetched · {result.requests_made}{" "}
                requests made
              </p>
              <h3>Rejected records ({result.rejected.length})</h3>
              {result.rejected.length ? (
                <ul className="rejected-list">
                  {result.rejected.map((r, i) => (
                    <li key={i}>
                      <code>{r.supplier_sku || "Unknown supplier SKU"}</code>
                      <span>{r.reason}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p>No invalid records.</p>
              )}
            </>
          )}
        </div>
      </div>
    </>
  );
}
