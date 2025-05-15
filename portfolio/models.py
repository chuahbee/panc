# portfolio/models.py
from django.db import models
from wagtail.models import Page
from wagtail.fields import RichTextField
from wagtail.admin.panels import FieldPanel
from wagtail.api import APIField
from wagtail.images.api.fields import ImageRenditionField


class WorkIndexPage(Page):
    intro = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
    ]

    subpage_types = ["portfolio.WorkPage"]

    # 🔸 关键：把原本写在模板里的查询搬到这里
    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        context["works"] = (
            self.get_children()
                .live()
                .order_by("-first_published_at")
                .specific()
        )
        return context


class AboutPage(Page):
    main_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    body = RichTextField()

    content_panels = Page.content_panels + [
        FieldPanel("main_image"),
        FieldPanel("body"),
    ]

    api_fields = [
        APIField("body"),
        APIField("main_image", serializer=ImageRenditionField('fill-800x400')),
    ]

    parent_page_types = ["home.HomePage"]


class WorkPage(Page):
    date = models.DateField("Published date")
    main_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    body = RichTextField()

    content_panels = Page.content_panels + [
        FieldPanel("date"),
        FieldPanel("main_image"),
        FieldPanel("body"),
    ]

    api_fields = [
        APIField("date"),
        APIField("body"),
        APIField("main_image", serializer=ImageRenditionField('fill-400x250')),
    ]

    parent_page_types = ["portfolio.WorkIndexPage"]


class CryptoIndexPage(Page):
    parent_page_types = ["home.HomePage"]  # 只允许挂在 HomePage 下
    subpage_types = ["portfolio.BitfinexIndexPage", "portfolio.AwesomeIndexPage"]

    # 可选：页面内容可以是空的，也可以重定向或展示子页面列表
    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        context["crypto_sections"] = self.get_children().live().specific()
        return context


class BaseSectionPage(Page):
    body = RichTextField()
    code_block = models.TextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("body"),
        FieldPanel("code_block"),
    ]

    class Meta:
        abstract = True  # 不会生成页面类型，只能继承


class BaseSubsectionPage(Page):
    body = RichTextField()
    code_block = models.TextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("body"),
        FieldPanel("code_block"),
    ]

    class Meta:
        abstract = True


class TabPage(Page):
    body = RichTextField()
    code_block = models.TextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("body"),
        FieldPanel("code_block"),
    ]

    parent_page_types = ["portfolio.AwesomeIndexPage", "portfolio.BitfinexIndexPage", "CreditCardsIndexPage", "P2PIndexPage"]
    subpage_types = ["portfolio.SectionPage"]


class SectionPage(BaseSectionPage):
    parent_page_types = ["portfolio.TabPage"]
    subpage_types = ["portfolio.SubsectionPage"]


class SubsectionPage(BaseSubsectionPage):
    parent_page_types = ["portfolio.SectionPage"]


class AwesomeIndexPage(Page):
    intro = RichTextField(blank=True)
    code_block = models.TextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
        FieldPanel("code_block"),
    ]

    subpage_types = ["portfolio.TabPage"]

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        context["pages"] = (
            self.get_children()
                .live()
                .order_by("-first_published_at")
                .specific()
        )
        return context
    

class BitfinexIndexPage(Page):
    intro = RichTextField(blank=True)
    code_block = models.TextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
        FieldPanel("code_block"),
    ]

    subpage_types = ["portfolio.TabPage"]

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        context["pages"] = (
            self.get_children()
                .live()
                .order_by("-first_published_at")
                .specific()
        )
        return context
    

class CreditCardsIndexPage(Page):
    intro = RichTextField(blank=True)
    code_block = models.TextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
        FieldPanel("code_block"),
    ]

    subpage_types = ["portfolio.TabPage"]

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        context["pages"] = (
            self.get_children()
                .live()
                .order_by("-first_published_at")
                .specific()
        )
        return context
    

class P2PIndexPage(Page):
    intro = RichTextField(blank=True)
    code_block = models.TextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
        FieldPanel("code_block"),
    ]

    subpage_types = ["portfolio.TabPage"]

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        context["pages"] = (
            self.get_children()
                .live()
                .order_by("-first_published_at")
                .specific()
        )
        return context
    

class Task(models.Model):
    title = models.CharField(max_length=255)
    completed = models.BooleanField(default=False)

    def __str__(self):
        return self.title