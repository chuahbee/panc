from django import template

from home.models import SiteMenu

register = template.Library()


def _build_menu_context(page, slug):
    items = []

    menu = SiteMenu.objects.filter(slug=slug).prefetch_related("menu_items__page").first()
    if menu is not None:
        for item in menu.menu_items.all():
            url = item.resolved_url
            if not url:
                continue
            items.append(
                {
                    "label": item.label,
                    "url": url,
                }
            )

    return {
        "page": page,
        "nav_links": items,
    }


@register.inclusion_tag("components/info_top_nav.html", takes_context=True)
def render_site_menu(context, slug="info-top"):
    page = context.get("page")
    return _build_menu_context(page, slug)


@register.inclusion_tag("components/info_footer.html", takes_context=True)
def render_site_footer_menu(context, slug="info-top"):
    page = context.get("page")
    return _build_menu_context(page, slug)
