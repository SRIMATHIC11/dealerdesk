import React, { useEffect, useState } from "react";
import {
  BarChart3,
  Check,
  ChevronRight,
  ClipboardList,
  Database,
  Layers3,
  Menu,
  Package,
  RefreshCw,
  ShieldCheck,
  ShoppingCart,
  Sparkles,
  Users,
} from "lucide-react";
import { api } from "./api";
import { ErrorBox } from "./components/common";
import Cart from "./components/Cart";
import Catalogue from "./pages/Catalogue";
import Orders from "./pages/Orders";
import Assistant from "./pages/Assistant";
import Reorder from "./pages/Reorder";
import Dealers from "./pages/Dealers";
import Supplier from "./pages/Supplier";

const PAGES = [
  ["catalogue", "Catalogue", Package],
  ["orders", "Orders", ClipboardList],
  ["assistant", "Dealer assistant", Sparkles],
  ["reorder", "Demand & reorder", BarChart3],
  ["dealers", "Dealers", Users],
  ["supplier", "Supplier sync", RefreshCw],
];

export default function App() {
  const [page, setPage] = useState(location.hash.slice(1) || "catalogue"),
    [revision, setRevision] = useState(0),
    [dealers, setDealers] = useState([]),
    [dealerId, setDealerId] = useState(
      localStorage.getItem("dealerdesk-dealer") || "",
    ),
    [cart, setCart] = useState([]),
    [cartOpen, setCartOpen] = useState(false),
    [toast, setToast] = useState(""),
    [initialOrder, setInitialOrder] = useState(null),
    [menu, setMenu] = useState(false),
    [connectionError, setConnectionError] = useState(null);
  useEffect(() => {
    const handler = () => {
      setPage(location.hash.slice(1) || "catalogue");
      setMenu(false);
    };
    window.addEventListener("hashchange", handler);
    return () => window.removeEventListener("hashchange", handler);
  }, []);
  useEffect(() => {
    let active = true;
    async function load() {
      try {
        let data = await api("dealers/?page_size=100");
        let all = [...data.results];
        let n = 2;
        while (data.next) {
          data = await api(`dealers/?page_size=100&page=${n++}`);
          all.push(...data.results);
        }
        if (active) {
          setDealers(all);
          setConnectionError(null);
          setDealerId((current) =>
            all.some((d) => String(d.id) === String(current))
              ? current
              : String(all[0]?.id || ""),
          );
        }
      } catch (err) {
        if (active) setConnectionError(err);
      }
    }
    load();
    return () => {
      active = false;
    };
  }, [revision]);
  useEffect(() => {
    if (dealerId) localStorage.setItem("dealerdesk-dealer", dealerId);
  }, [dealerId]);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 4500);
    return () => clearTimeout(timer);
  }, [toast]);
  function notify(message) {
    setToast(message);
    setRevision((r) => r + 1);
  }
  function navigate(next) {
    location.hash = next;
    setPage(next);
    setMenu(false);
  }
  function addToCart(p) {
    setCart((items) =>
      items.some((i) => i.sku === p.sku)
        ? items.map((i) =>
            i.sku === p.sku ? { ...i, quantity: Number(i.quantity) + 1 } : i,
          )
        : [...items, { ...p, quantity: 1 }],
    );
    setToast("Part added to your basket.");
  }
  function openOrder(number) {
    setInitialOrder(number);
    navigate("orders");
    setRevision((r) => r + 1);
  }
  const active = PAGES.some(([key]) => key === page) ? page : "catalogue";
  return (
    <div className="app-shell">
      <aside className={`sidebar ${menu ? "open" : ""}`}>
        <a className="brand" href="#catalogue">
          <span className="brand-mark">
            <Layers3 size={25} />
          </span>
          <div>
            dealerdesk<span>YOUR EVERYDAY ADVANTAGE</span>
          </div>
        </a>
        <div className="workspace-label">DEALER WORKSPACE</div>
        <nav aria-label="Main navigation">
          {PAGES.map(([key, label, Icon]) => (
            <button
              key={key}
              className={active === key ? "active" : ""}
              onClick={() => navigate(key)}
            >
              <Icon size={19} />
              {label}
              {key === "assistant" && <span className="ai-badge">AI</span>}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <span>
            <ShieldCheck size={19} /> Built for the counter
          </span>
          <p>
            Live stock. Clear orders.
            <br />A better day for your dealership.
          </p>
        </div>
        <div className="sidebar-footer">
          <div className="avatar">DD</div>
          <div>
            <strong>DealerDesk workspace</strong>
            <span>Assignment demo</span>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-button mobile-menu"
              aria-label="Open navigation"
              onClick={() => setMenu(!menu)}
            >
              <Menu size={22} />
            </button>
            <span>Workspace</span>
            <ChevronRight size={13} />
            <strong>{PAGES.find(([key]) => key === active)[1]}</strong>
          </div>
          <div className="header-actions">
            <label className="dealer-select">
              <Users size={16} />
              <select
                aria-label="Current dealer"
                value={dealerId}
                onChange={(e) => setDealerId(e.target.value)}
              >
                {!dealers.length && <option value="">Select dealer</option>}
                {dealers.map((d) => (
                  <option value={d.id} key={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </label>
            <button className="cart-button" onClick={() => setCartOpen(true)}>
              <ShoppingCart size={18} />
              <span>Basket</span>
              <b>{cart.reduce((sum, p) => sum + Number(p.quantity || 0), 0)}</b>
            </button>
          </div>
        </header>
        <main>
          <ErrorBox error={connectionError} />
          {active === "catalogue" && (
            <Catalogue
              addToCart={addToCart}
              revision={revision}
              notify={notify}
            />
          )}{" "}
          {active === "orders" && (
            <Orders
              dealerId={dealerId}
              revision={revision}
              notify={notify}
              initialOrder={initialOrder}
              setInitialOrder={setInitialOrder}
            />
          )}{" "}
          {active === "assistant" && (
            <Assistant key={dealerId} dealerId={dealerId} onOrder={openOrder} />
          )}{" "}
          {active === "reorder" && <Reorder revision={revision} />}{" "}
          {active === "dealers" && (
            <Dealers dealers={dealers} notify={notify} />
          )}{" "}
          {active === "supplier" && <Supplier notify={notify} />}
          <footer className="content-footer">
            <span>
              DealerDesk <b>·</b> Parts, people, progress.
            </span>
            <span>
              <Database size={12} /> Powered by live inventory
            </span>
          </footer>
        </main>
      </div>
      {cartOpen && (
        <Cart
          cart={cart}
          setCart={setCart}
          dealerId={dealerId}
          onClose={() => setCartOpen(false)}
          onCreated={(o) => {
            setCartOpen(false);
            notify("Draft order created.");
            openOrder(o.order_number);
          }}
        />
      )}
      {toast && (
        <div className="toast" role="status">
          <Check size={18} />
          {toast}
        </div>
      )}
    </div>
  );
}
