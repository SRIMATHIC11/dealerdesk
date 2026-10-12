from decimal import Decimal

from rest_framework import serializers

from catalogue.models import Product
from core.fields import StrictIntegerField
from core.money import line_amounts, money
from dealers.models import Dealer
from orders.models import Order


class ItemInput(serializers.Serializer):
    sku = serializers.CharField(max_length=80)
    quantity = StrictIntegerField(min_value=1, max_value=2147483647)


class ItemsInput(serializers.Serializer):
    items = ItemInput(many=True, allow_empty=False, max_length=600)

    def validate_items(self, items):
        skus = [item["sku"] for item in items]
        if len(skus) != len(set(skus)):
            raise serializers.ValidationError("The same SKU cannot appear twice.")
        existing = set(Product.objects.filter(sku__in=skus).values_list("sku", flat=True))
        if missing := sorted(set(skus) - existing):
            raise serializers.ValidationError(f"Unknown SKU(s): {', '.join(missing)}")
        return items


class OrderInput(ItemsInput):
    dealer_id = StrictIntegerField(min_value=1)

    def validate_dealer_id(self, value):
        if not Dealer.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Unknown dealer.")
        return value


class OrderSerializer(serializers.BaseSerializer):
    def to_representation(self, order):
        items, subtotal, tax = [], Decimal(0), Decimal(0)
        # Queryset prefetches this relation on list/detail; services prefetch at return.
        for item in order.items.all():
            draft = order.status == Order.Status.DRAFT
            price = item.product.price if draft else item.unit_price
            name = item.product.name if draft else item.name_snapshot
            line_subtotal, line_tax, line_total = line_amounts(price, item.quantity)
            subtotal += line_subtotal
            tax += line_tax
            items.append(
                {
                    "sku": item.product_id,
                    "name": name,
                    "quantity": item.quantity,
                    "unit_price": money(price),
                    "line_subtotal": money(line_subtotal),
                    "line_tax": money(line_tax),
                    "line_total": money(line_total),
                }
            )
        return {
            "order_number": order.order_number,
            "dealer_id": order.dealer_id,
            "status": order.status,
            "items": items,
            "subtotal": money(subtotal),
            "tax_total": money(tax),
            "grand_total": money(subtotal + tax),
            "created_at": order.created_at.isoformat(),
            "updated_at": order.updated_at.isoformat(),
        }
