from decimal import Decimal

from rest_framework import serializers

from catalogue.models import Product
from core.fields import StrictIntegerField


class ProductSerializer(serializers.ModelSerializer):
    sku = serializers.CharField(max_length=80)
    stock = serializers.IntegerField(source="inventory.quantity", read_only=True, default=0)
    price = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))

    class Meta:
        model = Product
        fields = [
            "sku",
            "name",
            "category",
            "brand",
            "vehicle_fitment",
            "price",
            "stock",
            "description",
        ]

    def validate_sku(self, value):
        if "/" in value or any(c.isspace() for c in value):
            raise serializers.ValidationError("SKU cannot contain whitespace or a slash.")
        if self.instance and value != self.instance.sku:
            raise serializers.ValidationError("SKU cannot change.")
        return value


class InventorySerializer(serializers.Serializer):
    quantity = StrictIntegerField(min_value=0, max_value=2147483647)
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
