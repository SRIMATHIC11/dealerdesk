import React, { useEffect, useState } from "react";
import { ClipboardList, ArrowUpRight } from "lucide-react";
import { api, inr } from "../api";
import { quantity } from "../utils";
import {
  ErrorBox,
  Busy,
  Empty,
  Status,
  Modal,
  Pager,
  useLoad,
} from "../components/common";

export default function Orders({
  dealerId,
  revision,
  notify,
  initialOrder,
  setInitialOrder,
}) {
  const [page, setPage] = useState(1),
    [status, setStatus] = useState(""),
    [number, setNumber] = useState(initialOrder || null);
  useEffect(() => {
    if (initialOrder) {
      setNumber(initialOrder);
      setInitialOrder(null);
    }
  }, [initialOrder, setInitialOrder]);
  useEffect(() => setPage(1), [dealerId]);
  const { data, error, loading } = useLoad(
    `orders/?${new URLSearchParams({ dealer_id: dealerId || "", status, page })}`,
    revision,
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">FROM DRAFT TO DELIVERY</div>
          <h1>Orders, under control.</h1>
          <p>Review line totals, confirm availability and track every step.</p>
        </div>
        <select
          aria-label="Filter order status"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All statuses</option>
          {["DRAFT", "CONFIRMED", "DISPATCHED", "DELIVERED", "CANCELLED"].map(
            (s) => (
              <option key={s}>{s}</option>
            ),
          )}
        </select>
      </div>
      <ErrorBox error={error} />
      {loading ? (
        <Busy />
      ) : data?.results.length ? (
        <div className="panel">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Order</th>
                  <th>Created</th>
                  <th>Status</th>
                  <th>Items</th>
                  <th>Total incl. GST</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {data.results.map((o) => (
                  <tr key={o.order_number}>
                    <td>
                      <button
                        className="text-button"
                        onClick={() => setNumber(o.order_number)}
                      >
                        {o.order_number}
                      </button>
                    </td>
                    <td>
                      {new Date(o.created_at).toLocaleDateString("en-IN")}
                    </td>
                    <td>
                      <Status value={o.status} />
                    </td>
                    <td>{o.items.length}</td>
                    <td className="strong">{inr(o.grand_total)}</td>
                    <td>
                      <button
                        className="icon-button"
                        aria-label={`View ${o.order_number}`}
                        onClick={() => setNumber(o.order_number)}
                      >
                        <ArrowUpRight size={17} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager data={data} page={page} setPage={setPage} />
        </div>
      ) : (
        !error && (
          <Empty
            title="No orders yet"
            text="Add parts to your basket or ask the assistant to create a draft."
            icon={ClipboardList}
          />
        )
      )}
      {number && (
        <OrderDetail
          number={number}
          revision={revision}
          onClose={() => setNumber(null)}
          notify={notify}
        />
      )}
    </>
  );
}

function OrderDetail({ number, revision, onClose, notify }) {
  const {
    data: order,
    error,
    loading,
  } = useLoad(`orders/${encodeURIComponent(number)}/`, revision);
  const [busy, setBusy] = useState(false),
    [actionError, setActionError] = useState(null),
    [edit, setEdit] = useState(null);
  const actions = {
    DRAFT: ["confirm", "cancel"],
    CONFIRMED: ["dispatch", "cancel"],
    DISPATCHED: ["deliver"],
    DELIVERED: [],
    CANCELLED: [],
  };
  async function act(action) {
    if (
      action === "cancel" &&
      !window.confirm("Cancel this order? Confirmed stock will be restored.")
    )
      return;
    setBusy(true);
    setActionError(null);
    try {
      await api(`orders/${number}/${action}/`, { method: "POST" });
      notify(
        `Order ${action === "cancel" ? "cancelled" : action === "confirm" ? "confirmed" : action === "dispatch" ? "dispatched" : "delivered"}.`,
      );
    } catch (err) {
      setActionError(err);
    } finally {
      setBusy(false);
    }
  }
  async function save() {
    setBusy(true);
    setActionError(null);
    try {
      await api(`orders/${number}/`, {
        method: "PUT",
        body: {
          items: edit.map((i) => ({
            sku: i.sku,
            quantity: Number(i.quantity),
          })),
        },
      });
      setEdit(null);
      notify("Draft updated.");
    } catch (err) {
      setActionError(err);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title={number} onClose={onClose} wide>
      <div className="modal-body">
        <ErrorBox error={error} />
        {loading ? (
          <Busy />
        ) : (
          order && (
            <>
              <div className="order-summary">
                <Status value={order.status} />
                <span>Dealer #{order.dealer_id}</span>
                <span>
                  {new Date(order.created_at).toLocaleString("en-IN")}
                </span>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Part</th>
                      <th>Qty</th>
                      <th>Unit price</th>
                      <th>Subtotal</th>
                      <th>GST 18%</th>
                      <th>Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(edit || order.items).map((i, index) => (
                      <tr key={i.sku}>
                        <td>
                          <strong>{i.name}</strong>
                          <code>{i.sku}</code>
                        </td>
                        <td>
                          {edit ? (
                            <input
                              aria-label={`Edit quantity ${i.sku}`}
                              className="quantity"
                              type="number"
                              min="1"
                              step="1"
                              value={i.quantity}
                              onChange={(e) =>
                                setEdit(
                                  edit.map((x, n) =>
                                    n === index
                                      ? { ...x, quantity: e.target.value }
                                      : x,
                                  ),
                                )
                              }
                            />
                          ) : (
                            i.quantity
                          )}
                        </td>
                        <td>{inr(i.unit_price)}</td>
                        <td>{inr(i.line_subtotal)}</td>
                        <td>{inr(i.line_tax)}</td>
                        <td>{inr(i.line_total)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="totals">
                <div>
                  <span>Subtotal</span>
                  <strong>{inr(order.subtotal)}</strong>
                </div>
                <div>
                  <span>GST</span>
                  <strong>{inr(order.tax_total)}</strong>
                </div>
                <div className="grand">
                  <span>Order total</span>
                  <strong>{inr(order.grand_total)}</strong>
                </div>
              </div>
              <p className="muted">
                {order.status === "DRAFT"
                  ? "Draft prices follow the current catalogue. Confirming checks all stock and locks prices."
                  : "Prices were locked when this order left draft status."}
              </p>
              <ErrorBox error={actionError} />
              <div className="actions">
                {edit ? (
                  <>
                    <button className="secondary" onClick={() => setEdit(null)}>
                      Discard edits
                    </button>
                    <button
                      className="primary"
                      disabled={busy || edit.some((i) => !quantity(i.quantity))}
                      onClick={save}
                    >
                      Save quantities
                    </button>
                  </>
                ) : (
                  <>
                    {order.status === "DRAFT" && (
                      <button
                        className="secondary"
                        onClick={() => setEdit(order.items)}
                      >
                        Edit quantities
                      </button>
                    )}
                    {actions[order.status].map((action) => (
                      <button
                        key={action}
                        className={action === "cancel" ? "danger" : "primary"}
                        disabled={busy}
                        onClick={() => act(action)}
                      >
                        {action[0].toUpperCase() + action.slice(1)}
                      </button>
                    ))}
                  </>
                )}
              </div>
            </>
          )
        )}
      </div>
    </Modal>
  );
}
