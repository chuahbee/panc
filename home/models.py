from django.db import models

from wagtail.models import Page
from wagtail.admin.panels import FieldPanel
from wagtail.fields import RichTextField


class HomePage(Page):
    intro = RichTextField(blank=True) 

    content_panels = Page.content_panels + [
        FieldPanel('intro'),
    ]
