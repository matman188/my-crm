import re

from django import template

register = template.Library()


@register.filter
def telephone(value):
    return re.sub(r"[^+\d]", "", str(value or ""))
