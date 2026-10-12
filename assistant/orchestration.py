import json
import time
import uuid
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from assistant.grounding import render_reply
from assistant.models import ChatSession
from assistant.prompts import SYSTEM_PROMPT, TOOL_SCHEMAS
from assistant.provider import Provider
from assistant.tools import execute, order_authorized
from core.errors import APIError


@transaction.atomic
def acquire_session(session_id, dealer_id, token):
    ChatSession.objects.get_or_create(session_id=session_id, defaults={"dealer_id": dealer_id})
    session = ChatSession.objects.select_for_update().get(pk=session_id)
    if session.dealer_id != dealer_id:
        raise APIError(
            "VALIDATION_ERROR", "This session belongs to another dealer. Start a new session."
        )
    if session.lease_until and session.lease_until > timezone.now():
        raise APIError(
            "SESSION_BUSY", "Another message is being processed in this session. Please wait.", 409
        )
    session.lease_token = token
    session.lease_until = timezone.now() + timedelta(seconds=70)
    session.save(update_fields=["lease_token", "lease_until"])
    return session


def chat(session_id, dealer_id, message):
    deadline = time.monotonic() + 53
    provider = Provider()  # Fail clearly before acquiring a session when credentials are absent.
    token = str(uuid.uuid4())
    session = acquire_session(session_id, dealer_id, token)
    history = session.messages[-12:]
    known_skus = list(session.last_skus)
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
            + "\nCurrent dealer_id: "
            + str(dealer_id)
            + "\nLast ordered result SKUs: "
            + json.dumps(known_skus),
        }
    ]
    messages.extend(history)
    messages.append({"role": "user", "content": message})
    actions, trace, content = [], [], ""
    allowed_order = order_authorized(message, history)
    try:
        for _ in range(5):
            if time.monotonic() >= deadline:
                break
            try:
                result = provider.complete(messages, TOOL_SCHEMAS, deadline)
            except APIError:
                if actions or trace:
                    break  # Preserve successful actions/grounded tool data if the final model call fails.
                raise
            calls = result.get("tool_calls") or []
            content = result.get("content") or ""
            if not calls:
                break
            if not isinstance(calls, list) or len(calls) > 8 or len(trace) + len(calls) > 12:
                raise APIError(
                    "ASSISTANT_UNAVAILABLE", "The model exceeded its tool-call budget.", 503
                )
            messages.append(result)
            for call in calls:
                name = call.get("function", {}).get("name", "")
                try:
                    arguments = json.loads(call.get("function", {}).get("arguments", "{}"))
                    trace.append({"name": name, "arguments": arguments})
                    if time.monotonic() >= deadline:
                        raise APIError(
                            "VALIDATION_ERROR",
                            "Turn deadline reached; no further actions permitted.",
                        )
                    output = execute(
                        name,
                        arguments,
                        dealer_id=dealer_id,
                        allowed_order=allowed_order,
                        turn_id=token,
                        known_skus=set(known_skus),
                        actions=actions,
                    )
                    for product in output.get("products", []):
                        if product["sku"] not in known_skus:
                            known_skus.append(product["sku"])
                except (ValueError, TypeError, APIError, ValidationError) as exc:
                    output = {"error": str(exc)}
                messages.append(
                    {
                        "role": "tool",
                        "name": name,
                        "tool_call_id": call.get("id", "invalid"),
                        "content": json.dumps(output, ensure_ascii=False, default=str),
                    }
                )
        reply, cited = render_reply(
            content, known_skus, actions, "products" if known_skus else "clarify"
        )
        new_history = (
            history
            + [{"role": "user", "content": message}, {"role": "assistant", "content": reply}]
        )[-12:]
        ChatSession.objects.filter(pk=session_id, lease_token=token).update(
            messages=new_history, last_skus=cited, updated_at=timezone.now()
        )
        return {"reply": reply, "cited_skus": cited, "tool_calls": trace, "actions": actions}
    finally:
        ChatSession.objects.filter(pk=session_id, lease_token=token).update(
            lease_token="", lease_until=None
        )
