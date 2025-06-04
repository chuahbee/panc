from django.db import models
from wagtail.models import Page
from wagtail.fields import RichTextField
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.images.models import Image


class CoursePage(Page):
    teacher = models.CharField(max_length=100, help_text="教师姓名")
    location = models.CharField(max_length=255, help_text="上课地点")
    date = models.DateField(help_text="开课日期")
    start_time = models.TimeField()
    end_time = models.TimeField()

    COURSE_TYPE_CHOICES = [
        ('monthly', '按月课程'),
        ('holiday', '假期课程'),
        ('yearly', '一年课程'),
    ]
    course_type = models.CharField(max_length=20, choices=COURSE_TYPE_CHOICES)

    description = RichTextField(blank=True)
    image = models.ForeignKey(
        Image,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='+'
    )

    content_panels = Page.content_panels + [
        FieldPanel('teacher'),
        FieldPanel('location'),
        FieldPanel('date'),
        MultiFieldPanel([
            FieldPanel('start_time'),
            FieldPanel('end_time'),
        ], heading="上课时间"),
        FieldPanel('course_type'),
        FieldPanel('description'),
        FieldPanel('image'),
    ]

class CoursesPage(Page):
    intro = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
    ]

    subpage_types = ['courses.CoursePage']  # 限制只能加 CoursePage

    def get_context(self, request):
        context = super().get_context(request)
        context['courses'] = self.get_children().live().specific()
        return context
