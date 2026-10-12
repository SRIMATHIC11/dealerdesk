import React, { useRef, useState } from "react";
import { ClipboardList, LoaderCircle, ShoppingCart, X } from "lucide-react";
import { api, inr } from "../api";
import { uid, quantity } from "../utils";
import { ErrorBox, Empty, Modal } from "./common";

export default function Cart({ cart, setCart, dealerId, onClose, onCreated }) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(null);
  const key = useRef(uid());
  const total = cart.reduce(
    (sum, p) => sum + Number(p.price) * Number(p.quantity || 0),
    0,
  );
  function update(sku, value) {
    setCart(cart.map((p) => (p.sku === sku ? { ...p, quantity: value } : p)));
    key.current = uid();
  }
  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const order = await api("orders/", {
        method: "POST",
        headers: { "Idempotency-Key": key.current },
        body: {
          dealer_id: Number(dealerId),
          items: cart.map((p) => ({
            sku: p.sku,
            quantity: Number(p.quantity),
          })),
        },
      });
      setCart([]);
      onCreated(order);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title="Your draft basket" onClose={onClose}>
      <div className="modal-body">
        {!cart.length ? (
          <Empty
            title="Your basket is empty"
            text="Add parts from the catalogue to start an order."
            icon={ShoppingCart}
          />
        ) : (
          <>
            {cart.map((p) => (
              <div className="cart-line" key={p.sku}>
                <div>
                  <strong>{p.name}</strong>
                  <code>{p.sku}</code>
                  <span>{inr(p.price)} / unit</span>
                </div>
                <input
                  aria-label={`Quantity ${p.sku}`}
                  type="number"
                  min="1"
                  step="1"
                  value={p.quantity}
                  onChange={(e) => update(p.sku, e.target.value)}
                />
                <button
                  className="icon-button"
                  aria-label={`Remove ${p.sku}`}
                  onClick={() => {
                    setCart(cart.filter((x) => x.sku !== p.sku));
                    key.current = uid();
                  }}
                >
                  <X size={17} />
                </button>
              </div>
            ))}
            <div className="detail-row">
              <span>Estimated subtotal</span>
              <strong>{inr(total)}</strong>
            </div>
            <p className="muted">
              The server calculates GST and current prices when it creates the
              draft. Stock is reserved only when you confirm.
            </p>
            <ErrorBox error={error} />
            <button
              className="primary full"
              disabled={
                busy || !dealerId || cart.some((p) => !quantity(p.quantity))
              }
              onClick={submit}
            >
              {busy ? (
                <LoaderCircle className="spin" size={18} />
              ) : (
                <ClipboardList size={18} />
              )}{" "}
              Create draft order
            </button>
          </>
        )}
      </div>
    </Modal>
  );
}
