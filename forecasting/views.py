import math

from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from catalogue.models import Inventory, Product
from core.errors import APIError
from forecasting.artifacts import WEEKS, load_artifacts


class ForecastView(APIView):
    def get(self, request, sku):
        get_object_or_404(Product, pk=sku)
        _, forecasts, _ = load_artifacts()
        if sku not in forecasts:
            raise APIError("NOT_FOUND", "No forecast exists for this SKU.", 404)
        return Response(
            {
                "sku": sku,
                "forecast": [
                    {"week_start": week, "forecast_units": float(forecasts[sku][week])}
                    for week in WEEKS
                ],
            }
        )


class ReorderView(APIView):
    def get(self, request):
        lead, forecasts, safety = load_artifacts()
        stock = dict(
            Inventory.objects.filter(product_id__in=lead).values_list("product_id", "quantity")
        )
        results = []
        for sku in sorted(lead):
            demand = sum(forecasts[sku][week] for week in WEEKS[: lead[sku]])
            point = demand + safety[sku]
            current = stock.get(sku, 0)
            results.append(
                {
                    "sku": sku,
                    "current_stock": current,
                    "lead_time_weeks": lead[sku],
                    "lead_time_demand": float(demand),
                    "safety_stock": safety[sku],
                    "reorder_point": float(point),
                    "reorder_qty": max(0, math.ceil(point - current)),
                }
            )
        return Response({"results": results})
