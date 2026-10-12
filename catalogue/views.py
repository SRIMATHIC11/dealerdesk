from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from catalogue.models import Inventory, Product
from catalogue.serializers import InventorySerializer, ProductSerializer
from core.errors import APIError
from core.pagination import paginated


class ProductsView(APIView):
    def get(self, request):
        products = Product.objects.select_related("inventory")
        if search := request.query_params.get("search"):
            products = products.filter(
                Q(sku__icontains=search) | Q(name__icontains=search) | Q(brand__icontains=search)
            )
        if category := request.query_params.get("category"):
            products = products.filter(category=category)
        if vehicle := request.query_params.get("vehicle"):
            products = products.filter(vehicle_fitment__icontains=vehicle)
        response = paginated(request, products, ProductSerializer)
        response.data["categories"] = list(
            Product.objects.order_by("category").values_list("category", flat=True).distinct()
        )
        return response

    def post(self, request):
        serializer = ProductSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                if Product.objects.filter(pk=serializer.validated_data["sku"]).exists():
                    raise APIError("DUPLICATE", "A product with this SKU already exists.", 409)
                product = serializer.save()
                Inventory.objects.create(product=product)
        except IntegrityError:
            raise APIError("DUPLICATE", "A product with this SKU already exists.", 409)
        return Response(ProductSerializer(product).data, status=201)


class ProductView(APIView):
    def get(self, request, sku):
        return Response(
            ProductSerializer(
                get_object_or_404(Product.objects.select_related("inventory"), pk=sku)
            ).data
        )

    @transaction.atomic
    def patch(self, request, sku):
        product = get_object_or_404(Product.objects.select_for_update(), pk=sku)
        serializer = ProductSerializer(product, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class InventoryView(APIView):
    @transaction.atomic
    def put(self, request, sku):
        inventory = get_object_or_404(Inventory.objects.select_for_update(), product_id=sku)
        serializer = InventorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        inventory.quantity = serializer.validated_data["quantity"]
        inventory.last_reason = serializer.validated_data["reason"]
        inventory.save(update_fields=["quantity", "last_reason", "updated_at"])
        return Response({"sku": sku, "quantity": inventory.quantity})
