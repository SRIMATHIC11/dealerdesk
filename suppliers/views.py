from django.db import OperationalError
from rest_framework.response import Response
from rest_framework.views import APIView

from suppliers.client import unavailable
from suppliers.services import synchronize


class SupplierSyncView(APIView):
    def post(self, request):
        try:
            return Response(synchronize())
        except OperationalError:
            raise unavailable()
