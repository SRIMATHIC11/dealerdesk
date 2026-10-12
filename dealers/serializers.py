from decimal import Decimal

from rest_framework import serializers

from dealers.models import Dealer


class DealerSerializer(serializers.ModelSerializer):
    dealer_code = serializers.CharField(max_length=80)
    credit_limit = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal(0), required=False
    )

    class Meta:
        model = Dealer
        fields = ["id", "dealer_code", "name", "city", "phone", "email", "gstin", "credit_limit"]
        read_only_fields = ["id"]
