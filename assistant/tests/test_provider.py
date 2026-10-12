import time
from unittest.mock import MagicMock, patch

import requests
from django.test import SimpleTestCase, override_settings

from assistant.prompts import TOOL_SCHEMAS
from assistant.provider import Provider, configuration
from core.errors import APIError


@override_settings(LLM_PROVIDER="groq", LLM_MODEL="", GROQ_API_KEY="test-placeholder-key")
class ProviderTransportTests(SimpleTestCase):
    @patch("assistant.provider.requests.post")
    def test_groq_tool_request_and_response_preserve_function_arguments(self, post):
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {"name": "search_parts", "arguments": '{"query":"brake"}'},
                }
            ],
            "reasoning": "Private reasoning is not forwarded.",
        }
        post.return_value.json.return_value = {"choices": [{"message": message}]}
        result = Provider().complete(
            [{"role": "user", "content": "Find brake pads"}], TOOL_SCHEMAS, time.monotonic() + 30
        )
        self.assertEqual(post.call_args.args[0], "https://api.groq.com/openai/v1/chat/completions")
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "openai/gpt-oss-120b")
        self.assertEqual(payload["tools"], TOOL_SCHEMAS)
        self.assertEqual(payload["tool_choice"], "auto")
        self.assertFalse(payload["include_reasoning"])
        self.assertEqual(result["tool_calls"], message["tool_calls"])
        self.assertNotIn("reasoning", result)

    @patch("assistant.provider.requests.post")
    def test_provider_failure_does_not_expose_response_or_key(self, post):
        response = MagicMock()
        response.raise_for_status.side_effect = requests.HTTPError(
            "test-placeholder-key upstream body"
        )
        post.return_value = response
        with self.assertRaises(APIError) as failure:
            Provider().complete([], TOOL_SCHEMAS, time.monotonic() + 30)
        self.assertEqual(failure.exception.status_code, 503)
        self.assertNotIn("test-placeholder-key", str(failure.exception))

    @patch("assistant.provider.requests.post")
    def test_expired_deadline_does_not_start_network_request(self, post):
        with self.assertRaises(APIError):
            Provider().complete([], TOOL_SCHEMAS, time.monotonic() - 1)
        post.assert_not_called()

    @override_settings(
        LLM_PROVIDER="",
        GROQ_API_KEY="",
        OPENAI_API_KEY="test-openai",
        GEMINI_API_KEY="",
        ANTHROPIC_API_KEY="",
    )
    def test_standard_key_detection_works_without_optional_provider_override(self):
        self.assertEqual(configuration()[:2], ("openai", "gpt-4.1-mini"))
