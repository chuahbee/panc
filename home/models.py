from django.db import models

from wagtail import blocks
from wagtail.models import Page
from wagtail.admin.panels import FieldPanel, InlinePanel
from wagtail.fields import StreamField
from wagtail.models import Orderable
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
    icon_class = blocks.CharBlock(required=False, max_length=120, help_text="例如: p2p-line")
    image_url = blocks.CharBlock(required=False, max_length=255, help_text="例如: /static/images/bitfinex-logo.webp")
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
        help_text="底部导航显示文字（timeline）。",
    )
    background_image_url = blocks.CharBlock(
        required=False,
        max_length=255,
        default="/static/images/333.jpg",
        help_text="背景图 URL。建议尺寸: 2163x1080px。",
    )
    kicker = blocks.CharBlock(required=True, max_length=100, default="Welcome to")
    title = blocks.CharBlock(required=True, max_length=200, default="Pop Art N Craft")
    main_links = blocks.ListBlock(
        HomeLinkBlock(),
        required=False,
        help_text="顶部主链接，可增删和排序。",
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
