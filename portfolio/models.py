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


class ContactPage(Page):
    working_days = models.CharField(max_length=255, blank=True)
    intro = models.TextField(blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=64, blank=True)
    address = models.CharField(max_length=255, blank=True)
    business_hours = models.CharField(max_length=255, blank=True)
    body = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("working_days"),
        FieldPanel("intro"),
        FieldPanel("email"),
        FieldPanel("phone"),
        FieldPanel("address"),
        FieldPanel("business_hours"),
        FieldPanel("body"),
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
        

class ProductIndexPage(Page):
    intro = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
    ]

    subpage_types = ["portfolio.ProductPage"]

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        context["products"] = (
            self.get_children()
                .live()
                .order_by("-first_published_at")
                .specific()
        )
        return context


class ProductPage(Page):
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+"
    )
    description = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("price"),
        FieldPanel("image"),
        FieldPanel("description"),
    ]

    parent_page_types = ["portfolio.ProductIndexPage"]


class Task(models.Model):
    title = models.CharField(max_length=255)
    completed = models.BooleanField(default=False)

    def __str__(self):
        return self.title
