from pathlib import Path

# Create your tests here.
from django.conf import settings
from django.test import Client, SimpleTestCase
from django.urls import resolve

from cms import urls as cms_urls
from portfolio.views import test_page


class UrlConfigurationTests(SimpleTestCase):
    def test_test_page_route_resolves_to_expected_view(self):
        match = resolve("/test/")
        self.assertEqual(match.func, test_page)

    def test_wagtail_catch_all_route_is_declared_once(self):
        empty_route_count = sum(
            1
            for pattern in cms_urls.urlpatterns
            if getattr(pattern.pattern, "_route", None) == ""
        )
        self.assertEqual(empty_route_count, 1)


class TemplateContractTests(SimpleTestCase):
    def test_courses_template_iterates_with_courses_context(self):
        template_path = Path(settings.BASE_DIR) / "cms" / "templates" / "courses" / "courses_page.html"
        template_source = template_path.read_text(encoding="utf-8")

        self.assertIn("{% for course in courses %}", template_source)
        self.assertIn("{% empty %}", template_source)
        self.assertIn("暂时没有课程", template_source)
        self.assertNotIn("{% for course in page.get_children.specific.live %}", template_source)

    def test_home_template_loads_static_tag_library(self):
        template_path = Path(settings.BASE_DIR) / "home" / "templates" / "home" / "home_page.html"
        template_source = template_path.read_text(encoding="utf-8")

        self.assertIn("{% load static %}", template_source)


class ViewSmokeTests(SimpleTestCase):
    def test_test_page_is_renderable(self):
        response = Client().get("/test/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "portfolio/test.html")