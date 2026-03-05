from django.db import models

from wagtail import blocks
from wagtail.models import Page
from wagtail.admin.panels import FieldPanel
from wagtail.fields import StreamField


class HomeLinkBlock(blocks.StructBlock):
    label = blocks.CharBlock(required=True, max_length=100)
    url = blocks.CharBlock(required=True, max_length=255)
    icon_class = blocks.CharBlock(required=False, max_length=120, help_text="例如: p2p-line")
    image_url = blocks.CharBlock(required=False, max_length=255, help_text="例如: /static/images/bitfinex-logo.webp")
    image_alt = blocks.CharBlock(required=False, max_length=120)


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
