from django import template
from django.urls import reverse

register = template.Library()


@register.inclusion_tag("includes/breadcrumb.html")
def breadcrumb(*items):
    breadcrumb_items = []
    pending_label = None

    for item in items:
        if item is None:
            continue
        if pending_label is None:
            pending_label = item
        else:
            breadcrumb_items.append({"label": pending_label, "url": item or None})
            pending_label = None

    if pending_label is not None:
        breadcrumb_items.append({"label": pending_label, "url": None})

    return {"breadcrumb_items": breadcrumb_items}


@register.filter
def has_active_filters(querydict):
    if not querydict:
        return False
    ignored = {"page", "sort"}
    return any(key not in ignored and value for key, value in querydict.items())


@register.simple_tag
def route_url(route_name, *args):
    return reverse(route_name, args=args)
