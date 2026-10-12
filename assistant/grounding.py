"""Render factual answers server-side; unverified model prose never reaches the dealer."""

import json
import re

from assistant.retrieval import check_stock
from orders.serializers import OrderSerializer
from orders.services import order_queryset


def render_reply(content, known_skus, actions, fallback_intent="products"):
    try:
        clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
        answer = json.loads(clean)
        if not isinstance(answer, dict):
            raise ValueError()
    except (ValueError, TypeError):
        # Plain labels avoid some tool models mistaking a JSON final answer for a
        # call to a fictitious formatting function. Neither format supplies facts.
        match = re.fullmatch(
            r"\s*INTENT:\s*([a-z_]+)[ \t]*\r?\nSKUS:[ \t]*([^\r\n]*)\s*",
            content,
        )
        answer = (
            {
                "intent": match[1],
                "skus": [sku.strip() for sku in match[2].split(",") if sku.strip()],
            }
            if match
            else {"intent": fallback_intent, "skus": list(known_skus)[:6]}
        )
    intent = answer.get("intent", fallback_intent)
    proposed = answer.get("skus", [])
    if not isinstance(proposed, list):
        proposed = []
    selected = [s for s in proposed if isinstance(s, str) and s in known_skus]
    if not selected and intent in ("products", "stock", "draft_created"):
        selected = list(known_skus)[:6]
    selected = list(dict.fromkeys(selected))[:8]
    parts = []
    if actions:
        order = OrderSerializer(order_queryset().get(order_number=actions[0]["order_number"])).data
        parts.append(
            f"Draft order {order['order_number']} created for dealer {order['dealer_id']}. Total including GST: INR {order['grand_total']}. Stock is not reserved. Review and confirm it in Orders."
        )
        selected = [i["sku"] for i in order["items"]]
        for item in order["items"]:
            parts.append(
                f"Draft item: {item['sku']}, quantity {item['quantity']}, unit price INR {item['unit_price']}."
            )
    elif intent == "off_topic":
        return (
            "I can help with motorcycle parts, live prices and stock, and draft orders. Please ask about your parts requirement.",
            [],
        )
    elif intent == "greeting":
        return (
            "Hello! I can find motorcycle parts, check live prices and stock, and create a draft order for your selected dealer. Tell me the part and vehicle you need.",
            [],
        )
    elif intent == "draft_confirmation":
        parts.append(
            "I can create drafts only. To reserve stock, review your draft and use Confirm in Orders."
        )
    elif intent == "clarify":
        parts.append(
            "Please specify the part, vehicle model or SKU. For an order, also tell me the quantity and which option you want."
        )
    elif intent == "error":
        parts.append(
            "I could not complete that request. Please check the SKU, quantity and dealer, then try again."
        )
    facts = check_stock(selected)["products"]
    for p in facts:
        availability = "Out of stock" if p["stock"] == 0 else f"Available stock: {p['stock']}"
        parts.append(
            f"{p['name']} ({p['sku']}) | {p['brand']} | Fits: {p['vehicle_fitment']} | Price: INR {p['price']} | {availability}."
        )
    if not parts:
        parts.append(
            "I couldn't find a matching catalogue part. Try a part name, brand, exact SKU or a more specific vehicle model."
        )
    return "\n\n".join(parts), [p["sku"] for p in facts]
