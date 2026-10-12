"""All order mutations pass through these PostgreSQL transaction boundaries."""

import hashlib
import json
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.utils import timezone

from catalogue.models import Inventory, Product
from core.errors import APIError
from orders.models import DailySequence, Order, OrderItem, OrderRequest
from orders.serializers import ItemsInput, OrderInput, OrderSerializer


def order_queryset():
    return Order.objects.prefetch_related(
        Prefetch("items", queryset=OrderItem.objects.select_related("product"))
    )


def representation(order):
    return OrderSerializer(order_queryset().get(pk=order.pk)).data


def _number():
    day = timezone.localdate(timezone=ZoneInfo("Asia/Kolkata"))
    DailySequence.objects.get_or_create(day=day)
    counter = DailySequence.objects.select_for_update().get(day=day)
    counter.value += 1
    counter.save(update_fields=["value"])
    return f"ORD-{day:%Y%m%d}-{counter.value:04d}"


def _replace_items(order, items):
    products = Product.objects.in_bulk([item["sku"] for item in items])
    order.items.all().delete()
    OrderItem.objects.bulk_create(
        [
            OrderItem(
                order=order,
                product=products[i["sku"]],
                quantity=i["quantity"],
                unit_price=products[i["sku"]].price,
                name_snapshot=products[i["sku"]].name,
            )
            for i in items
        ]
    )


@transaction.atomic
def create_draft(payload, idempotency_key=None):
    request_record = None
    if idempotency_key:
        if len(idempotency_key) > 255:
            raise APIError("VALIDATION_ERROR", "Idempotency-Key must be at most 255 characters.")
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest()
        # The unique key serializes concurrent inserts; a losing transaction waits for commit.
        request_record, created = OrderRequest.objects.get_or_create(
            key=idempotency_key, defaults={"payload_hash": digest}
        )
        if not created:
            if request_record.payload_hash != digest:
                raise APIError(
                    "IDEMPOTENCY_CONFLICT", "This key was used with a different request body.", 409
                )
            return representation(request_record.order), False
    serializer = OrderInput(data=payload)
    serializer.is_valid(raise_exception=True)
    order = Order.objects.create(
        dealer_id=serializer.validated_data["dealer_id"], order_number=_number()
    )
    _replace_items(order, serializer.validated_data["items"])
    if request_record:
        request_record.order = order
        request_record.save(update_fields=["order"])
    return representation(order), True


@transaction.atomic
def edit_draft(number, payload):
    order = get_object_or_404(Order.objects.select_for_update(), order_number=number)
    if order.status != Order.Status.DRAFT:
        raise APIError("ORDER_LOCKED", "Only DRAFT orders can be edited.", 409)
    serializer = ItemsInput(data=payload)
    serializer.is_valid(raise_exception=True)
    _replace_items(order, serializer.validated_data["items"])
    order.save(update_fields=["updated_at"])
    return representation(order)


TRANSITIONS = {
    "confirm": {Order.Status.DRAFT: Order.Status.CONFIRMED},
    "dispatch": {Order.Status.CONFIRMED: Order.Status.DISPATCHED},
    "deliver": {Order.Status.DISPATCHED: Order.Status.DELIVERED},
    "cancel": {
        Order.Status.DRAFT: Order.Status.CANCELLED,
        Order.Status.CONFIRMED: Order.Status.CANCELLED,
    },
}


@transaction.atomic
def transition(number, action):
    if action not in TRANSITIONS:
        raise APIError("NOT_FOUND", "Unknown order action.", 404)
    # Locking the order first makes repeated confirmation/cancellation mutually exclusive.
    order = get_object_or_404(Order.objects.select_for_update(), order_number=number)
    target = TRANSITIONS[action].get(order.status)
    if target is None:
        raise APIError("INVALID_TRANSITION", f"Cannot {action} an order in {order.status}.", 409)
    items = list(order.items.order_by("product_id"))
    skus = [item.product_id for item in items]
    if action == "confirm" or (action == "cancel" and order.status == Order.Status.DRAFT):
        # Sorted product locks give a consistent price snapshot; writers use the same rows.
        products = {
            p.sku: p
            for p in Product.objects.select_for_update().filter(pk__in=skus).order_by("sku")
        }
        for item in items:
            item.unit_price = products[item.product_id].price
            item.name_snapshot = products[item.product_id].name
        OrderItem.objects.bulk_update(items, ["unit_price", "name_snapshot"])
    if action == "confirm" or (action == "cancel" and order.status == Order.Status.CONFIRMED):
        # All stock rows are locked in SKU order BEFORE validating or changing any line.
        inventory = {
            i.product_id: i
            for i in Inventory.objects.select_for_update()
            .filter(product_id__in=skus)
            .order_by("product_id")
        }
        if action == "confirm":
            shortages = [
                {
                    "sku": i.product_id,
                    "requested": i.quantity,
                    "available": inventory[i.product_id].quantity,
                }
                for i in items
                if i.quantity > inventory[i.product_id].quantity
            ]
            if shortages:
                message = ". ".join(
                    f"Insufficient stock for {products[s['sku']].name}. Available: {s['available']}, Requested: {s['requested']}"
                    for s in shortages
                )
                raise APIError("INSUFFICIENT_STOCK", message, 409, shortages)
        for item in items:
            row = inventory[item.product_id]
            row.quantity += -item.quantity if action == "confirm" else item.quantity
            row.updated_at = timezone.now()
        Inventory.objects.bulk_update(inventory.values(), ["quantity", "updated_at"])
    order.status = target
    order.save(update_fields=["status", "updated_at"])
    return representation(order)
