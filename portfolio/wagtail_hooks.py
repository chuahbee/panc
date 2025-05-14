from wagtail import hooks
from django.utils.html import format_html
from django.forms import Media  # 要加这个
from .models import Task


class TaskSummaryPanel:
    order = 100

    def render(self):
        count = Task.objects.count()
        return format_html('<div class="panel"><h2>Tasks</h2><p>{} tasks total</p></div>', count)

    @property
    def media(self):
        return Media()  # 空的 Media，不加载任何 CSS/JS
        

@hooks.register('construct_homepage_panels')
def add_task_panel(request, panels):
    panels.append(TaskSummaryPanel())
