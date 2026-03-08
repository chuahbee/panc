from django import template

from home.models import HomePage

register = template.Library()


@register.inclusion_tag("components/info_top_nav.html", takes_context=True)
def render_info_top_nav(context):
    page = context.get("page")
    links = []

    home_page = HomePage.objects.live().public().first()
    if page is not None:
        site = page.get_site()
        if site is not None:
            site_home = (
                site.root_page.get_children()
                .type(HomePage)
                .live()
                .public()
                .specific()
                .first()
            )
            if site_home is not None:
                home_page = site_home

    if home_page is not None:
        for section in home_page.home_sections:
            if section.block_type == "intro_section":
                links = section.value.get("main_links") or []
                break

    return {
        "page": page,
        "nav_links": links,
    }
