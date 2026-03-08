import json
import os
from io import BytesIO
from unittest.mock import patch

from django.conf import settings
from django.middleware.csrf import _get_new_csrf_string
from django.test import Client, SimpleTestCase, override_settings

from cms.views import (
    _age_matches_rule,
    _build_age_match_hint,
    _build_age_template_reply,
    _extract_requested_age,
    _extract_requested_ages,
    _extract_structured_courses,
)


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

        with patch("cms.views.os.environ", {"OPENAI_API_KEY": "", "AI_ASSISTANT_API_TOKEN": ""}):
            response = client.post(
                "/api/ai-assistant/",
                data=json.dumps({"messages": []}),
                content_type="application/json",
                HTTP_X_CSRFTOKEN=csrf_token,
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json().get("error"), "OPENAI_API_KEY is not configured.")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "", "AI_ASSISTANT_API_TOKEN": ""}, clear=False)
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
        with patch("cms.views.os.environ", {"OPENAI_API_KEY": "", "AI_ASSISTANT_API_TOKEN": ""}):
            response = client.post(
                "/api/ai-assistant/",
                data=json.dumps({"messages": [{"role": "user", "content": "你好"}]}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json().get("error"), "OPENAI_API_KEY is not configured.")

    def test_ai_assistant_returns_age_template_without_openai_key(self):
        client = Client()
        with patch("cms.views.os.environ", {"OPENAI_API_KEY": "", "AI_ASSISTANT_API_TOKEN": ""}):
            response = client.post(
                "/api/ai-assistant/",
                data=json.dumps(
                    {
                        "messages": [{"role": "user", "content": "7 years old"}],
                        "page_context": (
                            "Structured course data:\n"
                            "Course: Digital Art | Price: RM500.00 | Age: 6-12 | Weekday: Monday | "
                            "Time: 10:00 a.m. - 12:00 p.m. | Location: Cheras\n"
                            "Course: Water Color | Price: RM600.00 | Age: 10-18 | Weekday: Monday | "
                            "Time: 10:00 a.m. - 12:00 p.m. | Location: Cheras"
                        ),
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        reply = response.json().get("reply", "")
        self.assertIn("For age 7", reply)
        self.assertIn("Course: Digital Art", reply)

    def test_ai_assistant_returns_age_ranges_without_openai_key(self):
        client = Client()
        with patch("cms.views.os.environ", {"OPENAI_API_KEY": "", "AI_ASSISTANT_API_TOKEN": ""}):
            response = client.post(
                "/api/ai-assistant/",
                data=json.dumps(
                    {
                        "messages": [{"role": "user", "content": "what age do you teach?"}],
                        "page_context": (
                            "Structured course data:\n"
                            "Course: Digital Art | Price: RM500.00 | Age: 6-12 | Weekday: Monday | "
                            "Time: 10:00 a.m. - 12:00 p.m. | Location: Cheras\n"
                            "Course: Water Color | Price: RM600.00 | Age: 10-18 | Weekday: Monday | "
                            "Time: 10:00 a.m. - 12:00 p.m. | Location: Cheras"
                        ),
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        reply = response.json().get("reply", "")
        self.assertIn("Available age ranges: 6-12, 10-18", reply)
        self.assertIn("Course: Digital Art (6-12)", reply)

    def test_ai_assistant_returns_course_list_without_openai_key(self):
        client = Client()
        with patch("cms.views.os.environ", {"OPENAI_API_KEY": "", "AI_ASSISTANT_API_TOKEN": ""}):
            response = client.post(
                "/api/ai-assistant/",
                data=json.dumps(
                    {
                        "messages": [{"role": "user", "content": "show me your courses"}],
                        "page_context": (
                            "Structured course data:\n"
                            "Course: Digital Art | Price: RM500.00 | URL: /courses/digital-art/ | Age: 6-12 | Weekday: Monday | "
                            "Time: 10:00 a.m. - 12:00 p.m. | Location: Cheras\n"
                            "Course: Water Color | Price: RM600.00 | URL: /courses/water-color/ | Age: 10-18 | Weekday: Monday | "
                            "Time: 10:00 a.m. - 12:00 p.m. | Location: Cheras"
                        ),
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        reply = response.json().get("reply", "")
        self.assertIn("Current courses on this page:", reply)
        self.assertIn("Digital Art", reply)
        self.assertIn("Page: /courses/digital-art/", reply)

    def test_ai_assistant_returns_course_list_for_chinese_query_with_plain_text_context(self):
        client = Client()
        with patch("cms.views.os.environ", {"OPENAI_API_KEY": "", "AI_ASSISTANT_API_TOKEN": ""}):
            response = client.post(
                "/api/ai-assistant/",
                data=json.dumps(
                    {
                        "messages": [{"role": "user", "content": "你们有什么课程"}],
                        "page_context": (
                            "Digital Art\n"
                            "RM500.00\n"
                            "Teacher: Chuah\n"
                            "Location: Cheras\n"
                            "Start Date: March 5, 2026\n"
                            "Age: 6-12\n"
                            "Weekday: Monday\n"
                            "Time: 10:00 a.m. - 12:00 p.m.\n"
                            "Type: Monthly\n"
                        ),
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        reply = response.json().get("reply", "")
        self.assertIn("本页课程如下", reply)
        self.assertIn("Digital Art", reply)

    def test_ai_assistant_returns_course_pages_for_page_query(self):
        client = Client()
        with patch("cms.views.os.environ", {"OPENAI_API_KEY": "", "AI_ASSISTANT_API_TOKEN": ""}):
            response = client.post(
                "/api/ai-assistant/",
                data=json.dumps(
                    {
                        "messages": [{"role": "user", "content": "课程在哪一页?"}],
                        "page_context": (
                            "Structured course data:\n"
                            "Course: Digital Art | Price: RM500.00 | URL: /courses/digital-art/ | Age: 6-12\n"
                            "Course: Water Color | Price: RM600.00 | URL: /courses/water-color/ | Age: 10-18"
                        ),
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        reply = response.json().get("reply", "")
        self.assertIn("课程页面如下", reply)
        self.assertIn("Digital Art -> /courses/digital-art/", reply)

    def test_ai_assistant_returns_natural_registration_steps(self):
        client = Client()
        with patch("cms.views.os.environ", {"OPENAI_API_KEY": "", "AI_ASSISTANT_API_TOKEN": ""}):
            response = client.post(
                "/api/ai-assistant/",
                data=json.dumps(
                    {
                        "messages": [{"role": "user", "content": "我要怎样报名?"}],
                        "page_context": (
                            "Structured course data:\n"
                            "Course: Digital Art | Price: RM500.00 | URL: /courses/digital-art/ | Age: 6-12\n"
                            "Course: Water Color | Price: RM600.00 | URL: /courses/water-color/ | Age: 10-18"
                        ),
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        reply = response.json().get("reply", "")
        self.assertIn("可以按这 3 步报名", reply)
        self.assertIn("你可以先看这些页面", reply)
        self.assertIn("/courses/digital-art/", reply)

    def test_ai_assistant_returns_art_interest_recommendation(self):
        client = Client()
        with patch("cms.views.os.environ", {"OPENAI_API_KEY": "", "AI_ASSISTANT_API_TOKEN": ""}):
            response = client.post(
                "/api/ai-assistant/",
                data=json.dumps(
                    {
                        "messages": [{"role": "user", "content": "我想给我孩子学习画画"}],
                        "page_context": (
                            "Structured course data:\n"
                            "Course: Digital Art | Price: RM500.00 | URL: /courses/digital-art/ | Age: 6-12 | "
                            "Time: 10:00 a.m. - 12:00 p.m. | Location: Cheras\n"
                            "Course: Water Color | Price: RM600.00 | URL: /courses/water-color/ | Age: 10-18 | "
                            "Time: 10:00 a.m. - 12:00 p.m. | Location: Cheras"
                        ),
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        reply = response.json().get("reply", "")
        self.assertIn("以下课程可能适合孩子", reply)
        self.assertIn("Digital Art", reply)

    def test_ai_assistant_returns_product_list_for_product_query(self):
        client = Client()
        with patch("cms.views.os.environ", {"OPENAI_API_KEY": "", "AI_ASSISTANT_API_TOKEN": ""}):
            response = client.post(
                "/api/ai-assistant/",
                data=json.dumps(
                    {
                        "messages": [{"role": "user", "content": "你们有卖什么东西?"}],
                        "page_context": (
                            "Structured product data:\n"
                            "Product: DIY Craft Kit | Price: RM120.00 | URL: /product/diy-craft-kit/\n"
                            "Product: Watercolor Set | Price: RM80.00 | URL: /product/watercolor-set/"
                        ),
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        reply = response.json().get("reply", "")
        self.assertIn("我们目前有这些产品", reply)
        self.assertIn("DIY Craft Kit", reply)

    def test_ai_assistant_handles_multiple_ages_without_openai_key(self):
        client = Client()
        with patch("cms.views.os.environ", {"OPENAI_API_KEY": "", "AI_ASSISTANT_API_TOKEN": ""}):
            response = client.post(
                "/api/ai-assistant/",
                data=json.dumps(
                    {
                        "messages": [{"role": "user", "content": "my kids are 5 and 6, recommend courses"}],
                        "page_context": (
                            "Structured course data:\n"
                            "Course: Digital Art | Price: RM500.00 | Age: 6-12 | Weekday: Monday | "
                            "Time: 10:00 a.m. - 12:00 p.m. | Location: Cheras\n"
                            "Course: Water Color | Price: RM600.00 | Age: 10-18 | Weekday: Monday | "
                            "Time: 10:00 a.m. - 12:00 p.m. | Location: Cheras"
                        ),
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        reply = response.json().get("reply", "")
        self.assertIn("Age 5: no matching course", reply)
        self.assertIn("Age 6: Digital Art (6-12)", reply)

    def test_ai_assistant_returns_local_art_benefits_without_openai_key(self):
        client = Client()
        with patch("cms.views.os.environ", {"OPENAI_API_KEY": "", "AI_ASSISTANT_API_TOKEN": ""}):
            response = client.post(
                "/api/ai-assistant/",
                data=json.dumps(
                    {
                        "messages": [{"role": "user", "content": "what are the benefits of kids learning art?"}],
                        "page_context": "",
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        reply = response.json().get("reply", "")
        self.assertIn("Art learning helps children", reply)
        self.assertIn("Builds creativity", reply)

    def test_ai_assistant_returns_ai_era_art_benefits_from_conversation_context(self):
        client = Client()
        with patch("cms.views.os.environ", {"OPENAI_API_KEY": "", "AI_ASSISTANT_API_TOKEN": ""}):
            response = client.post(
                "/api/ai-assistant/",
                data=json.dumps(
                    {
                        "messages": [
                            {"role": "user", "content": "kids learning art benefits"},
                            {"role": "assistant", "content": "Art learning helps children."},
                            {"role": "user", "content": "how does it help in the future AI era?"},
                        ],
                        "page_context": "",
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        reply = response.json().get("reply", "")
        self.assertIn("AI era", reply)
        self.assertIn("Creativity", reply)

    def test_ai_assistant_returns_expand_skills_reply_from_conversation_context(self):
        client = Client()
        with patch("cms.views.os.environ", {"OPENAI_API_KEY": "", "AI_ASSISTANT_API_TOKEN": ""}):
            response = client.post(
                "/api/ai-assistant/",
                data=json.dumps(
                    {
                        "messages": [
                            {"role": "user", "content": "kids learning art benefits"},
                            {"role": "assistant", "content": "Art learning helps children."},
                            {"role": "user", "content": "besides drawing what else can they learn?"},
                        ],
                        "page_context": "",
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        reply = response.json().get("reply", "")
        self.assertIn("Besides drawing", reply)
        self.assertIn("Observation", reply)

    def test_ai_assistant_validates_messages_type(self):
        client = Client()
        response = client.post(
            "/api/ai-assistant/",
            data=json.dumps({"messages": "invalid"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get("error"), "messages must be a list.")

    def test_ai_assistant_validates_page_context_type(self):
        client = Client()
        response = client.post(
            "/api/ai-assistant/",
            data=json.dumps({"messages": [], "page_context": ["invalid"]}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get("error"), "page_context must be a string.")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False)
    @patch("cms.views.request.urlopen")
    def test_ai_assistant_ignores_non_string_message_content(self, mock_urlopen):
        mock_response = mock_urlopen.return_value.__enter__.return_value
        mock_response.read.return_value = BytesIO(
            json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": "ok",
                            }
                        }
                    ]
                }
            ).encode("utf-8")
        ).getvalue()

        client = Client()
        response = client.post(
            "/api/ai-assistant/",
            data=json.dumps(
                {
                    "messages": [
                        {"role": "user", "content": 123},
                        {"role": "assistant", "content": None},
                        {"role": "user", "content": "保留这条"},
                    ]
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("reply"), "ok")

class SettingsContractTests(SimpleTestCase):
    def test_csrf_context_processor_is_enabled(self):
        context_processors = settings.TEMPLATES[0]["OPTIONS"]["context_processors"]
        self.assertIn("django.template.context_processors.csrf", context_processors)


class AIAssistantAgeRuleTests(SimpleTestCase):
    def test_extract_requested_age_from_short_followup(self):
        self.assertEqual(_extract_requested_age("7岁呢？"), 7)

    def test_age_range_match_for_6_to_12(self):
        self.assertTrue(_age_matches_rule(7, "6-12"))
        self.assertFalse(_age_matches_rule(13, "6-12"))

    def test_build_age_match_hint_uses_structured_course_data(self):
        messages = [{"role": "user", "content": "7岁呢？"}]
        page_context = (
            "Structured course data:\n"
            "Course: Digital Art | Price: RM500.00 | Age: 6-12 | Time: 10:00 a.m. - 12:00 p.m. | Location: Cheras\n"
            "Course: Water Color | Price: RM600.00 | Age: 10-18 | Time: 10:00 a.m. - 12:00 p.m. | Location: Cheras"
        )

        hint = _build_age_match_hint(messages, page_context)
        self.assertIn("年龄 7 岁", hint)
        self.assertIn("Digital Art", hint)
        self.assertNotIn("Water Color", hint)


class AIAssistantAgeTemplateTests(SimpleTestCase):
    def test_build_age_template_reply_uses_three_line_pattern(self):
        messages = [{"role": "user", "content": "7 years old"}]
        page_context = (
            "Structured course data:\n"
            "Course: Digital Art | Price: RM500.00 | Age: 6-12 | Weekday: Monday | "
            "Time: 10:00 a.m. - 12:00 p.m. | Location: Cheras"
        )

        reply = _build_age_template_reply(messages, page_context, "English")
        self.assertIn("Course: Digital Art", reply)
        self.assertIn("Age: 6-12", reply)
        self.assertIn("Time/Location: Monday, 10:00 a.m. - 12:00 p.m., Cheras", reply)


class AIAssistantAgeExtractionTests(SimpleTestCase):
    def test_extract_requested_ages_from_multi_age_query(self):
        self.assertEqual(_extract_requested_ages("my kids are 5 and 6"), [5, 6])

    def test_extract_structured_courses_fallback_from_plain_text(self):
        page_context = (
            "Digital Art\n"
            "RM500.00\n"
            "Location: Cheras\n"
            "Age: 6-12\n"
            "Time: 10:00 a.m. - 12:00 p.m.\n"
        )
        courses = _extract_structured_courses(page_context)
        self.assertEqual(courses[0].get("Course"), "Digital Art")
        self.assertEqual(courses[0].get("Age"), "6-12")
