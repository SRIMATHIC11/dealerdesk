import React, { useEffect, useRef, useState } from "react";
import {
  LoaderCircle,
  Package,
  X,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { api } from "../api";

export function ErrorBox({ error }) {
  if (!error) return null;
  return (
    <div className="error-box" role="alert">
      <strong>{error.message || String(error)}</strong>
      {error.details?.map((detail, index) => (
        <div key={index}>
          {typeof detail === "object"
            ? detail.sku
              ? `${detail.sku}: requested ${detail.requested}, available ${detail.available}`
              : Object.entries(detail)
                  .map(([key, value]) => `${key}: ${value}`)
                  .join(" · ")
            : String(detail)}
        </div>
      ))}
    </div>
  );
}

export function Empty({ title, text, icon: Icon = Package }) {
  return (
    <div className="empty">
      <Icon size={34} />
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  );
}

export function Busy() {
  return (
    <div className="loading" role="status">
      <LoaderCircle className="spin" size={20} /> Loading live data…
    </div>
  );
}

export function Status({ value }) {
  return (
    <span className={`status ${value?.toLowerCase()}`}>
      {value?.replaceAll("_", " ")}
    </span>
  );
}

export function Stock({ value }) {
  return (
    <span className={`stock ${value === 0 ? "none" : value < 10 ? "low" : ""}`}>
      <i />
      {value === 0 ? "Out of stock" : `${value} in stock`}
    </span>
  );
}

export function Modal({ title, children, onClose, wide = false }) {
  const ref = useRef();
  useEffect(() => {
    const previous = document.activeElement;
    ref.current?.focus();
    const handler = (e) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => {
      document.removeEventListener("keydown", handler);
      previous?.focus?.();
    };
  }, [onClose]);
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <section
        className={`modal ${wide ? "wide" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        ref={ref}
      >
        <header>
          <h2>{title}</h2>
          <button
            className="icon-button"
            aria-label="Close dialog"
            onClick={onClose}
          >
            <X />
          </button>
        </header>
        {children}
      </section>
    </div>
  );
}

export function Pager({ data, page, setPage }) {
  return (
    <div className="pager">
      <span>
        {data.count
          ? `${(page - 1) * 20 + 1}–${Math.min(page * 20, data.count)} of ${data.count}`
          : "0 results"}
      </span>
      <div>
        <button
          className="icon-button"
          disabled={!data.previous}
          aria-label="Previous page"
          onClick={() => setPage(page - 1)}
        >
          <ChevronLeft size={18} />
        </button>
        <span>Page {page}</span>
        <button
          className="icon-button"
          disabled={!data.next}
          aria-label="Next page"
          onClick={() => setPage(page + 1)}
        >
          <ChevronRight size={18} />
        </button>
      </div>
    </div>
  );
}

export function useLoad(path, revision = 0) {
  const [state, setState] = useState({
    data: null,
    error: null,
    loading: true,
  });
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    setState((s) => ({ ...s, error: null, loading: true }));
    api(path, { signal: controller.signal })
      .then((data) => active && setState({ data, error: null, loading: false }))
      .catch((error) => {
        if (active && error.name !== "AbortError")
          setState({ data: null, error, loading: false });
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [path, revision]);
  return state;
}
