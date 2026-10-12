from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from django.db import connection, transaction

from catalogue.models import Inventory, Product
from suppliers.client import fetch_feed

FIELDS = ("name", "category", "brand", "vehicle_fitment", "description", "price")


def normalize_feed(items):
    selected, rejected = {}, []
    for index, item in enumerate(items):
        supplier_sku = item.get("supplier_sku", "") if isinstance(item, dict) else ""
        reason = None
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("sku"), str)
            or not item["sku"].strip()
        ):
            reason = "missing or empty sku"
        else:
            try:
                price = Decimal(str(item.get("price", "")))
                if (
                    not price.is_finite()
                    or price <= 0
                    or price.as_tuple().exponent < -2
                    or price >= Decimal("1000000000000")
                ):
                    reason = "invalid price"
            except (InvalidOperation, ValueError):
                reason = "invalid price"
        if reason:
            rejected.append({"supplier_sku": supplier_sku, "reason": reason})
            continue
        sku = item["sku"].strip()
        if len(sku) > 80 or "/" in sku or any(c.isspace() for c in sku):
            rejected.append({"supplier_sku": supplier_sku, "reason": "invalid sku"})
            continue
        try:
            updated = datetime.fromisoformat(str(item.get("updated_at", "")).replace("Z", "+00:00"))
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
        except ValueError:
            updated = datetime.min.replace(tzinfo=timezone.utc)
        values = {f: str(item.get(f, "") or "") for f in FIELDS if f != "price"}
        if any(
            len(values[f]) > limit
            for f, limit in [
                ("name", 255),
                ("category", 120),
                ("brand", 120),
                ("vehicle_fitment", 255),
            ]
        ):
            rejected.append(
                {"supplier_sku": supplier_sku, "reason": "field exceeds maximum length"}
            )
            continue
        values["price"] = price
        if sku not in selected or updated > selected[sku][0]:
            selected[sku] = (updated, values)
    return {sku: values for sku, (_, values) in selected.items()}, rejected


def synchronize():
    items, stats = fetch_feed()
    feed, rejected = normalize_feed(items)
    counts = {"created": 0, "updated": 0, "unchanged": 0}
    with transaction.atomic():
        # Serialize apply phases only; HTTP retries never hold catalogue/stock locks.
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout = '8s'")
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [73194052])
        for sku, values in sorted(feed.items()):
            product, created = Product.objects.get_or_create(sku=sku, defaults=values)
            if created:
                Inventory.objects.create(product=product, quantity=0)
                counts["created"] += 1
                continue
            product = Product.objects.select_for_update().get(pk=sku)
            changed = [f for f in FIELDS if getattr(product, f) != values[f]]
            if changed:
                for field in changed:
                    setattr(product, field, values[field])
                product.save(update_fields=changed)
                counts["updated"] += 1
            else:
                counts["unchanged"] += 1
    return {**counts, "rejected": rejected, **stats}
