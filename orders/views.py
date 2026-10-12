from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from core.errors import APIError
from core.pagination import paginated
from orders.models import Order
from orders.serializers import OrderSerializer
from orders.services import create_draft, edit_draft, order_queryset, transition


class OrdersView(APIView):
    def get(self, request):
        orders = order_queryset()
        if dealer := request.query_params.get("dealer_id"):
            if not dealer.isdecimal() or int(dealer) < 1:
                raise APIError("VALIDATION_ERROR", "dealer_id must be a positive integer.")
            orders = orders.filter(dealer_id=dealer)
        if status := request.query_params.get("status"):
            if status not in Order.Status.values:
                raise APIError("VALIDATION_ERROR", "Unknown order status.")
            orders = orders.filter(status=status)
        return paginated(request, orders, OrderSerializer)

    def post(self, request):
        data, created = create_draft(request.data, request.headers.get("Idempotency-Key"))
        return Response(data, status=201 if created else 200)


class OrderView(APIView):
    def get(self, request, number):
        return Response(
            OrderSerializer(get_object_or_404(order_queryset(), order_number=number)).data
        )

    def put(self, request, number):
        return Response(edit_draft(number, request.data))


class OrderActionView(APIView):
    def post(self, request, number, action):
        return Response(transition(number, action))
