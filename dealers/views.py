from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from core.errors import APIError
from core.pagination import paginated
from dealers.models import Dealer
from dealers.serializers import DealerSerializer


class DealersView(APIView):
    def get(self, request):
        return paginated(request, Dealer.objects.all(), DealerSerializer)

    def post(self, request):
        serializer = DealerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                if Dealer.objects.filter(
                    dealer_code=serializer.validated_data["dealer_code"]
                ).exists():
                    raise APIError("DUPLICATE", "Dealer code already exists.", 409)
                dealer = serializer.save()
        except IntegrityError:
            raise APIError("DUPLICATE", "Dealer code already exists.", 409)
        return Response(DealerSerializer(dealer).data, status=201)


class DealerView(APIView):
    def get(self, request, pk):
        return Response(DealerSerializer(get_object_or_404(Dealer, pk=pk)).data)
