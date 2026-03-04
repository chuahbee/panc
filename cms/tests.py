import json
import os
from io import BytesIO
from unittest.mock import patch

from django.conf import settings
from django.middleware.csrf import _get_new_csrf_string
from django.test import Client, SimpleTestCase, override_settings


@override_settings(ROOT_URLCONF="cms.urls")
class AIAssistantEndpointTests(SimpleTestCase):
    def test_ai_assistant_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(
            "/api/ai-assistant/",
            data=json.dumps({"messages": []}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    def test_ai_assistant_accepts_valid_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        csrf_token = _get_new_csrf_string()
        client.cookies["csrftoken"] = csrf_token

        response = client.post(
            "/api/ai-assistant/",
            data=json.dumps({"messages": []}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json().get("error"), "OPENAI_API_KEY is not configured.")

    def test_ai_assistant_requires_token_when_configured(self):
        client = Client()
        with patch.dict(os.environ, {"AI_ASSISTANT_API_TOKEN": "expected-token"}, clear=False):
            response = client.post(
                "/api/ai-assistant/",
                data=json.dumps({"messages": []}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json().get("error"), "Unauthorized")

    def test_ai_assistant_returns_503_without_openai_key(self):
        client = Client()
        response = client.post(
            "/api/ai-assistant/",
            data=json.dumps({"messages": [{"role": "user", "content": "你好"}]}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json().get("error"), "OPENAI_API_KEY is not configured.")

    def test_ai_assistant_validates_messages_type(self):
        client = Client()
        response = client.post(
            "/api/ai-assistant/",
            data=json.dumps({"messages": "invalid"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get("error"), "messages must be a list.")


class SettingsContractTests(SimpleTestCase):
    def test_csrf_context_processor_is_enabled(self):
        context_processors = settings.TEMPLATES[0]["OPTIONS"]["context_processors"]
        self.assertIn("django.template.context_processors.csrf", context_processors)