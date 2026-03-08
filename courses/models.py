from django.db import models
from wagtail.models import Page
from wagtail.fields import RichTextField
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.images.models import Image


class CoursePage(Page):
    teacher = models.CharField(max_length=100, help_text="\u6559\u5e08\u59d3\u540d")
    location = models.CharField(max_length=255, help_text="\u4e0a\u8bfe\u5730\u70b9")
    date = models.DateField(help_text="\u5f00\u8bfe\u65e5\u671f")
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    age = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="\u9002\u5408\u5e74\u9f84\uff08\u4f8b\u5982\uff1a10-12\uff09",
    )

    WEEKDAY_CHOICES = [
        ("monday", "Monday"),
        ("tuesday", "Tuesday"),
        ("wednesday", "Wednesday"),
        ("thursday", "Thursday"),
        ("friday", "Friday"),
        ("saturday", "Saturday"),
        ("sunday", "Sunday"),
    ]
    weekday = models.CharField(
        max_length=10,
        choices=WEEKDAY_CHOICES,
        default="monday",
        help_text="\u661f\u671f\u51e0",
    )

    start_time = models.TimeField()
    end_time = models.TimeField()

    COURSE_TYPE_CHOICES = [
        ("monthly", "Monthly"),
        ("holiday", "Holiday"),
        ("yearly", "Yearly"),
    ]
    course_type = models.CharField(max_length=20, choices=COURSE_TYPE_CHOICES)

    description = RichTextField(blank=True)
    image = models.ForeignKey(
        Image,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    content_panels = Page.content_panels + [
        FieldPanel("teacher"),
        FieldPanel("location"),
        FieldPanel("date"),
        FieldPanel("price"),
        FieldPanel("age"),
        FieldPanel("weekday"),
        MultiFieldPanel(
            [
                FieldPanel("start_time"),
                FieldPanel("end_time"),
            ],
            heading="\u4e0a\u8bfe\u65f6\u95f4",
        ),
        FieldPanel("course_type"),
        FieldPanel("description"),
        FieldPanel("image"),
    ]


class CoursesPage(Page):
    intro = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
    ]

    subpage_types = ["courses.CoursePage"]

    def get_context(self, request):
        context = super().get_context(request)
        context["courses"] = self.get_children().live().order_by("-first_published_at").specific()
        return context
