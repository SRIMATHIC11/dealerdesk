import re

from rest_framework import serializers

from assistant.retrieval import check_stock, search_parts
from core.errors import APIError
from core.fields import StrictIntegerField
from orders.serializers import ItemInput
from orders.services import create_draft


class SearchInput(serializers.Serializer):
    query = serializers.CharField(max_length=500, allow_blank=True)
    vehicle = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    limit = StrictIntegerField(min_value=1, max_value=8, required=False, default=6)


class StockInput(serializers.Serializer):
    skus = serializers.ListField(
        child=serializers.CharField(max_length=80), min_length=1, max_length=20
    )


class DraftInput(serializers.Serializer):
    items = ItemInput(many=True, allow_empty=False, max_length=20)


SCHEMAS = {"search_parts": SearchInput, "check_stock": StockInput, "create_draft_order": DraftInput}
ORDER_INTENT = re.compile(
    r"\b(order|buy|purchase|add|draft|book|take|need\s+\d+|want\s+\d+)\b", re.I
)


def order_authorized(message, history):
    if re.search(
        r"\b(don'?t|do not|never|cancel)\b.{0,25}\b(order|buy|draft|purchase)\b", message, re.I
    ):
        return False
    if ORDER_INTENT.search(message):
        return True
    # A short follow-up can resolve a previous explicit order request in this session.
    if re.search(r"\b(yes|please|okay|ok|proceed|\d+)\b", message, re.I):
        for turn in reversed(history[-4:]):
            if turn["role"] == "assistant" and "Draft order ORD-" in turn["content"]:
                return False
            if turn["role"] == "user" and ORDER_INTENT.search(turn["content"]):
                return True
    return False


def execute(name, arguments, *, dealer_id, allowed_order, turn_id, known_skus, actions):
    if name not in SCHEMAS:
        raise APIError("VALIDATION_ERROR", "Unknown assistant tool.")
    if not isinstance(arguments, dict):
        raise APIError("VALIDATION_ERROR", "Tool arguments must be an object.")
    serializer = SCHEMAS[name](data=arguments)
    serializer.is_valid(raise_exception=True)
    values = serializer.validated_data
    if name == "search_parts":
        return search_parts(**values)
    if name == "check_stock":
        return check_stock(**values)
    if not allowed_order:
        raise APIError(
            "VALIDATION_ERROR",
            "Ask the dealer for an explicit order request before creating a draft.",
        )
    if actions:
        raise APIError(
            "VALIDATION_ERROR", "Only one draft can be created in a turn; it was already created."
        )
    if not set(i["sku"] for i in values["items"]).issubset(known_skus):
        raise APIError("VALIDATION_ERROR", "Retrieve or check the selected SKUs before drafting.")
    order, _ = create_draft(
        {"dealer_id": dealer_id, "items": values["items"]}, f"assistant:{turn_id}"
    )
    actions.append({"type": "draft_order_created", "order_number": order["order_number"]})
    return {"order": order, "notice": "DRAFT only. Stock is not reserved."}
