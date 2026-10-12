from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from assistant.orchestration import chat
from core.fields import StrictIntegerField
from dealers.models import Dealer


class ChatInput(serializers.Serializer):
    session_id = serializers.CharField(max_length=120)
    dealer_id = StrictIntegerField(min_value=1)
    message = serializers.CharField(max_length=4000)

    def validate_dealer_id(self, value):
        if not Dealer.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Unknown dealer.")
        return value


class ChatView(APIView):
    def post(self, request):
        serializer = ChatInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(chat(**serializer.validated_data))
