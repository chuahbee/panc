# portfolio/models.py
from django.db import models
from wagtail.models import Page
from wagtail.fields import RichTextField
from wagtail.admin.panels import FieldPanel


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

    parent_page_types = ["portfolio.WorkIndexPage"]
