from django import template
from django.urls import reverse

register = template.Library()



@register.filter
def has_active_filters(querydict):
    if not querydict:
        return False
    ignored = {"page", "sort"}
    return any(key not in ignored and value for key, value in querydict.items())


@register.simple_tag(takes_context=True)
def active_filter_count(context):
    filterset = context.get("filter")
    request = context.get("request")
    if not filterset or not request:
        return 0

    return sum(
        1
        for name in filterset.form.fields
        if any(value not in ("", None) for value in request.GET.getlist(name))
    )


@register.simple_tag
def route_url(route_name, *args):
    return reverse(route_name, args=args)
