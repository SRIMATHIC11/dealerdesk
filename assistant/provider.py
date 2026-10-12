"""Thin provider transport. Tool execution is always owned by our service layer."""

import json
import time

import requests
from django.conf import settings

from core.errors import APIError

DEFAULT_MODELS = {
    "groq": "openai/gpt-oss-120b",
    "openai": "gpt-4.1-mini",
    "gemini": "gemini-3.5-flash-lite",
    "anthropic": "claude-haiku-4-5",
}


def configuration():
    provider = settings.LLM_PROVIDER
    if not provider:
        provider = next(
            (
                p
                for p in [settings.LLM_DEFAULT_PROVIDER, "gemini", "openai", "anthropic"]
                if getattr(settings, p.upper() + "_API_KEY", "")
            ),
            settings.LLM_DEFAULT_PROVIDER,
        )
    if provider not in DEFAULT_MODELS:
        raise APIError("ASSISTANT_UNAVAILABLE", "The configured LLM provider is unsupported.", 503)
    key = getattr(settings, provider.upper() + "_API_KEY", "")
    if not key:
        raise APIError(
            "ASSISTANT_UNAVAILABLE",
            f"Configure {provider.upper()}_API_KEY privately to enable the assistant.",
            503,
        )
    return provider, settings.LLM_MODEL or DEFAULT_MODELS[provider], key


class Provider:
    def __init__(self):
        self.provider, self.model, self.key = configuration()

    def complete(self, messages, tools, deadline):
        remaining = deadline - time.monotonic()
        if remaining < 2:
            raise APIError(
                "ASSISTANT_UNAVAILABLE",
                "Assistant response deadline reached. Please try again.",
                503,
            )
        if self.provider in ("groq", "openai"):
            base = (
                "https://api.groq.com/openai/v1"
                if self.provider == "groq"
                else "https://api.openai.com/v1"
            )
            url = base + "/chat/completions"
            headers = {"Authorization": f"Bearer {self.key}"}
            payload = {
                "model": self.model,
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto",
                "temperature": 0,
                "max_completion_tokens": 1800,
            }
            if self.provider == "groq" and "gpt-oss" in self.model:
                payload["reasoning_effort"] = "low"
                payload["include_reasoning"] = False
        elif self.provider == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
            headers = {"x-goog-api-key": self.key}
            contents = []
            for message in messages[1:]:
                if message["role"] == "tool":
                    part = {
                        "functionResponse": {
                            "name": message["name"],
                            "response": json.loads(message["content"]),
                        }
                    }
                    contents.append({"role": "user", "parts": [part]})
                elif "_gemini_content" in message:
                    contents.append(message["_gemini_content"])
                else:
                    contents.append(
                        {
                            "role": "model" if message["role"] == "assistant" else "user",
                            "parts": [{"text": message.get("content") or ""}],
                        }
                    )
            payload = {
                "systemInstruction": {"parts": [{"text": messages[0]["content"]}]},
                "contents": contents,
                "tools": [{"functionDeclarations": [t["function"] for t in tools]}],
                "generationConfig": {"temperature": 0, "maxOutputTokens": 1800},
            }
        else:
            url = "https://api.anthropic.com/v1/messages"
            headers = {"x-api-key": self.key, "anthropic-version": "2023-06-01"}
            contents = []
            for message in messages[1:]:
                if message["role"] == "tool":
                    contents.append(
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": message["tool_call_id"],
                                    "content": message["content"],
                                }
                            ],
                        }
                    )
                elif "_anthropic_content" in message:
                    contents.append({"role": "assistant", "content": message["_anthropic_content"]})
                else:
                    contents.append(
                        {"role": message["role"], "content": message.get("content") or ""}
                    )
            payload = {
                "model": self.model,
                "system": messages[0]["content"],
                "messages": contents,
                "max_tokens": 1800,
                "tools": [
                    {
                        "name": t["function"]["name"],
                        "description": t["function"]["description"],
                        "input_schema": t["function"]["parameters"],
                    }
                    for t in tools
                ],
            }
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=(min(3, remaining / 4), min(18, remaining / 2)),
            )
            response.raise_for_status()
            data = response.json()
            if self.provider in ("groq", "openai"):
                result = data["choices"][0]["message"]
                return {
                    key: result[key] for key in ("role", "content", "tool_calls") if key in result
                }
            if self.provider == "gemini":
                native = data["candidates"][0]["content"]
                calls = [
                    {
                        "id": f"call_{n}",
                        "type": "function",
                        "function": {
                            "name": p["functionCall"]["name"],
                            "arguments": json.dumps(p["functionCall"].get("args", {})),
                        },
                    }
                    for n, p in enumerate(native["parts"])
                    if "functionCall" in p
                ]
                return {
                    "role": "assistant",
                    "content": "".join(
                        p.get("text", "") for p in native["parts"] if not p.get("thought")
                    ),
                    "tool_calls": calls,
                    "_gemini_content": native,
                }
            native = data["content"]
            calls = [
                {
                    "id": p["id"],
                    "type": "function",
                    "function": {"name": p["name"], "arguments": json.dumps(p["input"])},
                }
                for p in native
                if p["type"] == "tool_use"
            ]
            return {
                "role": "assistant",
                "content": "".join(p.get("text", "") for p in native if p["type"] == "text"),
                "tool_calls": calls,
                "_anthropic_content": native,
            }
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
            # Never expose provider bodies, authorization headers or requests with secrets.
            raise APIError(
                "ASSISTANT_UNAVAILABLE",
                "The model provider is unavailable or returned an invalid response. Check model access and quota, then retry.",
                503,
            )
