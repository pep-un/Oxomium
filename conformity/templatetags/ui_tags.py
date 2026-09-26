from django import template
from django.urls import reverse

register = template.Library()


@register.inclusion_tag("includes/breadcrumb.html")
def breadcrumb(*items):
    breadcrumb_items = []
    for item in items:
        if not item:
            continue
        if isinstance(item, (list, tuple)) and len(item) == 2:
            label, url = item
        else:
            label, url = item, None
        breadcrumb_items.append({"label": label, "url": url})
    return {"breadcrumb_items": breadcrumb_items}


@register.simple_tag
def route_url(route_name, *args):
    return reverse(route_name, args=args)
