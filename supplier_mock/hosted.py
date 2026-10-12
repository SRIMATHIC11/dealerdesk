"""Optional public-host adapter; the supplied mock_supplier.py remains unchanged."""

import os
import threading
from pathlib import Path

from supplier_mock.mock_supplier import SupplierMock, build_public_feed, serve


def main():
    key = os.environ.get("SUPPLIER_API_KEY")
    if not key:
        raise SystemExit("Set SUPPLIER_API_KEY privately.")
    feed = build_public_feed(Path(__file__).resolve().parents[1] / "data/catalogue.csv")

    class HostedMock(SupplierMock):
        def handle(self, path, query, headers):
            if path.rstrip("/") == "/health":
                return 200, {"status": "ok"}, {}
            return super().handle(path, query, headers)

    mock = HostedMock(feed, key, throttle_every=4, retry_after=1, transient={2: [500]})
    server = serve(mock, host="0.0.0.0", port=int(os.environ.get("PORT", "8099")))
    print("Supplier mock ready. Credentials are not logged.", flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
