import React, { useState } from "react";
import { Plus } from "lucide-react";
import { api, inr } from "../api";
import { ErrorBox, Modal } from "../components/common";

export default function Dealers({ dealers, notify }) {
  const [creating, setCreating] = useState(false),
    [error, setError] = useState(null),
    [busy, setBusy] = useState(false);
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api("dealers/", {
        method: "POST",
        body: Object.fromEntries(new FormData(e.currentTarget)),
      });
      setCreating(false);
      notify("Dealer added.");
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
          <div className="eyebrow">THE PEOPLE BEHIND EVERY ORDER</div>
          <h1>Your dealer network.</h1>
          <p>
            Select a dealer in the header to work with their orders and
            assistant session.
          </p>
        </div>
        <button className="primary" onClick={() => setCreating(true)}>
          <Plus size={17} /> Add dealer
        </button>
      </div>
      <div className="dealer-grid">
        {dealers.map((d) => (
          <article className="panel dealer-card" key={d.id}>
            <span className="dealer-avatar">
              {d.name.slice(0, 2).toUpperCase()}
            </span>
            <h3>{d.name}</h3>
            <code>{d.dealer_code}</code>
            <p>{d.city || "City not provided"}</p>
            <div className="dealer-contact">
              {d.email || "No email"}
              <br />
              {d.phone || "No phone"}
            </div>
            <div className="detail-row">
              <span>Credit limit</span>
              <strong>{inr(d.credit_limit)}</strong>
            </div>
          </article>
        ))}
      </div>
      {creating && (
        <Modal title="Add dealer" onClose={() => setCreating(false)}>
          <form className="modal-body form-grid" onSubmit={submit}>
            {[
              ["dealer_code", "Dealer code"],
              ["name", "Business name"],
              ["city", "City"],
              ["phone", "Phone"],
              ["email", "Email"],
              ["gstin", "GSTIN"],
              ["credit_limit", "Credit limit (INR)"],
            ].map(([name, label]) => (
              <label key={name}>
                {label}
                <input
                  name={name}
                  required={["dealer_code", "name"].includes(name)}
                  type={
                    name === "email"
                      ? "email"
                      : name === "credit_limit"
                        ? "number"
                        : "text"
                  }
                  min={name === "credit_limit" ? "0" : undefined}
                  step={name === "credit_limit" ? "0.01" : undefined}
                  defaultValue={name === "credit_limit" ? "0.00" : undefined}
                />
              </label>
            ))}
            <div className="span-two">
              <ErrorBox error={error} />
              <button className="primary full" disabled={busy}>
                Save dealer
              </button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}
