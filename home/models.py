from django.db import models

from wagtail import blocks
from wagtail.models import Page
from wagtail.admin.panels import FieldPanel, InlinePanel
from wagtail.fields import StreamField
from wagtail.models import Orderable
from wagtail.images.blocks import ImageChooserBlock
from wagtail.snippets.models import register_snippet
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from django.core.exceptions import ValidationError


class HomeLinkBlock(blocks.StructBlock):
    label = blocks.CharBlock(required=True, max_length=100)
    page = blocks.PageChooserBlock(
        required=False,
        help_text="Select an internal page.",
    )
    custom_url = blocks.CharBlock(
        required=False,
        max_length=255,
        help_text="Custom URL, e.g. /our-product/ or https://example.com",
    )
    icon_class = blocks.CharBlock(required=False, max_length=120, help_text="Example: p2p-line")
    image = ImageChooserBlock(
        required=False,
        help_text="Upload link image.",
    )
    image_alt = blocks.CharBlock(required=False, max_length=120)

    def clean(self, value):
        value = super().clean(value)
        if not value.get("page") and not value.get("custom_url"):
            raise ValidationError("Please select a page or set a custom URL.")
        return value


class IntroSectionBlock(blocks.StructBlock):
    section_class = blocks.ChoiceBlock(
        choices=[("intro", "intro")],
        default="intro",
        required=True,
    )
    menu_label = blocks.CharBlock(
        required=False,
        max_length=80,
        default="Home",
        help_text="Text shown in bottom timeline navigation.",
    )
    background_image = ImageChooserBlock(
        required=False,
        help_text="Upload a background image (recommended size: 2163x1080).",
    )
    kicker = blocks.CharBlock(required=True, max_length=100, default="Welcome to")
    title = blocks.CharBlock(required=True, max_length=200, default="Pop Art N Craft")
    main_links = blocks.ListBlock(
        HomeLinkBlock(),
        required=False,
        help_text="Top main links; you can add, remove, and reorder.",
    )


class HomePage(Page):
    home_sections = StreamField(
        [
            ("intro_section", IntroSectionBlock()),
        ],
        use_json_field=True,
        blank=True,
    )

    content_panels = Page.content_panels + [
        FieldPanel("home_sections"),
    ]


@register_snippet
class SiteMenu(ClusterableModel):
    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=80, unique=True)

    panels = [
        FieldPanel("name"),
        FieldPanel("slug"),
        InlinePanel("menu_items", label="Menu items"),
    ]

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Top navigation menu"
        verbose_name_plural = "Top navigation menus"


class SiteMenuItem(Orderable):
    menu = ParentalKey(
        "home.SiteMenu",
        on_delete=models.CASCADE,
        related_name="menu_items",
    )
    label = models.CharField(max_length=120)
    page = models.ForeignKey(
        "wagtailcore.Page",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    custom_url = models.CharField(max_length=255, blank=True)

    panels = [
        FieldPanel("label"),
        FieldPanel("page"),
        FieldPanel("custom_url"),
    ]

    def clean(self):
        super().clean()
        if not self.page and not self.custom_url:
            raise ValidationError("Please select a page or set a custom URL.")

    @property
    def resolved_url(self):
        if self.page:
            return self.page.url
        return self.custom_url

