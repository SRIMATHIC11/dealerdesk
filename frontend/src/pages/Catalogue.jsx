import React, { useEffect, useState } from "react";
import {
  Layers3,
  Package,
  Plus,
  Search,
  SlidersHorizontal,
  ShoppingCart,
} from "lucide-react";
import { api, inr } from "../api";
import {
  ErrorBox,
  Busy,
  Empty,
  Stock,
  Modal,
  Pager,
  useLoad,
} from "../components/common";

export default function Catalogue({ addToCart, revision, notify }) {
  const [search, setSearch] = useState(""),
    [debounced, setDebounced] = useState(""),
    [vehicle, setVehicle] = useState(""),
    [category, setCategory] = useState(""),
    [page, setPage] = useState(1),
    [selected, setSelected] = useState(null),
    [editing, setEditing] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebounced(search);
      setPage(1);
    }, 250);
    return () => clearTimeout(timer);
  }, [search]);
  const params = new URLSearchParams({
    page,
    search: debounced,
    vehicle,
    category,
  });
  const { data, error, loading } = useLoad(`products/?${params}`, revision);
  const categories = data?.categories || [];
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">YOUR PARTS COUNTER, CONNECTED</div>
          <h1>The right part. Ready to go.</h1>
          <p>
            Find motorcycle parts, check live availability and build your next
            order.
          </p>
        </div>
        <button className="secondary" onClick={() => setEditing(true)}>
          <Plus size={17} /> Add product
        </button>
      </div>
      <div className="catalogue-banner">
        <div>
          <span className="banner-icon">
            <Layers3 size={24} />
          </span>
          <div>
            <strong>One catalogue. Every dealer.</strong>
            <p>
              Current prices and available stock, straight from your inventory.
            </p>
          </div>
        </div>
        <span className="live-tag">
          <i /> Live inventory
        </span>
      </div>
      <div className="toolbar">
        <label className="search-box">
          <Search size={19} />
          <input
            aria-label="Search catalogue"
            placeholder="Search parts, SKU or brand…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <label className="filter">
          <SlidersHorizontal size={17} />
          <select
            aria-label="Filter category"
            value={category}
            onChange={(e) => {
              setCategory(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All categories</option>
            {categories.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <input
          className="vehicle-filter"
          aria-label="Filter vehicle"
          placeholder="Vehicle, e.g. Pulsar 150"
          value={vehicle}
          onChange={(e) => {
            setVehicle(e.target.value);
            setPage(1);
          }}
        />
      </div>
      <ErrorBox error={error} />
      {loading ? (
        <Busy />
      ) : data?.results?.length ? (
        <>
          <div className="section-line">
            <h2>
              Parts catalogue <span>{data.count}</span>
            </h2>
            <span>Prices exclude 18% GST</span>
          </div>
          <div className="product-grid">
            {data.results.map((p) => (
              <article className="product-card" key={p.sku}>
                <div className="card-top">
                  <span className="part-symbol">
                    <Package size={26} />
                  </span>
                  <span className="category-label">{p.category}</span>
                </div>
                <button
                  className="product-title"
                  onClick={() => setSelected(p)}
                >
                  {p.name}
                </button>
                <div className="product-meta">
                  {p.brand}
                  <span>·</span>
                  <code>{p.sku}</code>
                </div>
                <p className="fitment">{p.vehicle_fitment}</p>
                <Stock value={p.stock} />
                <div className="card-bottom">
                  <strong>
                    {inr(p.price)}
                    <small> / unit</small>
                  </strong>
                  <button
                    className="add-button"
                    aria-label={`Add ${p.sku} to cart`}
                    onClick={() => addToCart(p)}
                  >
                    <Plus size={18} /> Add
                  </button>
                </div>
              </article>
            ))}
          </div>
          <Pager data={data} page={page} setPage={setPage} />
        </>
      ) : (
        !error && (
          <Empty
            title="No matching parts"
            text="Try a different part name, vehicle or category."
          />
        )
      )}
      {selected && (
        <PartDetail
          sku={selected.sku}
          revision={revision}
          notify={notify}
          onClose={() => setSelected(null)}
          addToCart={addToCart}
        />
      )}
      {editing && (
        <ProductForm
          onClose={() => setEditing(false)}
          onSaved={() => {
            setEditing(false);
            notify("Product added. Its starting stock is zero.");
          }}
        />
      )}
    </>
  );
}

function ProductForm({ onClose, onSaved }) {
  const [error, setError] = useState(null),
    [busy, setBusy] = useState(false);
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api("products/", {
        method: "POST",
        body: Object.fromEntries(new FormData(e.currentTarget)),
      });
      onSaved();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title="Add a catalogue part" onClose={onClose}>
      <form className="modal-body form-grid" onSubmit={submit}>
        {[
          ["sku", "SKU"],
          ["name", "Product name"],
          ["brand", "Brand"],
          ["category", "Category"],
          ["vehicle_fitment", "Vehicle fitment"],
          ["price", "Unit price (INR)"],
        ].map(([name, label]) => (
          <label key={name}>
            {label}
            <input
              name={name}
              required={["sku", "name", "price"].includes(name)}
              type={name === "price" ? "number" : "text"}
              min={name === "price" ? "0.01" : undefined}
              step={name === "price" ? "0.01" : undefined}
            />
          </label>
        ))}
        <label className="span-two">
          Description
          <textarea name="description" rows={3} />
        </label>
        <div className="span-two">
          <ErrorBox error={error} />
          <button className="primary full" disabled={busy}>
            {busy ? "Saving…" : "Create product"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function PartDetail({ sku, revision, notify, onClose, addToCart }) {
  const {
    data: p,
    error,
    loading,
  } = useLoad(`products/${encodeURIComponent(sku)}/`, revision);
  const [actionError, setActionError] = useState(null),
    [busy, setBusy] = useState(false);
  async function update(e, kind) {
    e.preventDefault();
    const fields = Object.fromEntries(new FormData(e.currentTarget));
    setBusy(true);
    setActionError(null);
    try {
      await api(kind === "stock" ? `inventory/${sku}/` : `products/${sku}/`, {
        method: kind === "stock" ? "PUT" : "PATCH",
        body:
          kind === "stock"
            ? { quantity: Number(fields.quantity), reason: fields.reason }
            : { price: fields.price },
      });
      notify(
        kind === "stock"
          ? "Available inventory updated."
          : "Catalogue price updated.",
      );
    } catch (err) {
      setActionError(err);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title="Part details" onClose={onClose}>
      <div className="modal-body">
        <ErrorBox error={error} />
        {loading ? (
          <Busy />
        ) : (
          p && (
            <>
              <code>{p.sku}</code>
              <h3>{p.name}</h3>
              <p>{p.description}</p>
              <div className="detail-row">
                <span>Vehicle fitment</span>
                <strong>{p.vehicle_fitment}</strong>
              </div>
              <div className="detail-row">
                <span>Unit price</span>
                <strong>{inr(p.price)}</strong>
              </div>
              <Stock value={p.stock} />
              <button
                className="primary full"
                onClick={() => {
                  addToCart(p);
                  onClose();
                }}
              >
                <ShoppingCart size={17} /> Add to cart
              </button>
              <details className="inventory-tools">
                <summary>Manage price & inventory</summary>
                <form onSubmit={(e) => update(e, "stock")}>
                  <label>
                    Available quantity
                    <input
                      aria-label="Available quantity"
                      name="quantity"
                      type="number"
                      min="0"
                      step="1"
                      required
                      defaultValue={p.stock}
                      key={`stock-${p.stock}`}
                    />
                  </label>
                  <label>
                    Reason
                    <input name="reason" placeholder="Stock count correction" />
                  </label>
                  <button className="secondary" disabled={busy}>
                    Update stock
                  </button>
                </form>
                <form onSubmit={(e) => update(e, "price")}>
                  <label>
                    Unit price (INR)
                    <input
                      aria-label="Update unit price"
                      name="price"
                      type="number"
                      min="0.01"
                      step="0.01"
                      required
                      defaultValue={p.price}
                      key={`price-${p.price}`}
                    />
                  </label>
                  <button className="secondary" disabled={busy}>
                    Update price
                  </button>
                </form>
              </details>
              <ErrorBox error={actionError} />
            </>
          )
        )}
      </div>
    </Modal>
  );
}
