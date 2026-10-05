from django import template


register = template.Library()


@register.filter
def compact_email(value, max_length=35):
    """Keep both ends of a long address within the requested label length."""
    if not value or len(value) <= max_length:
        return value
    suffix_length = min(16, max_length - 4)
    prefix_length = max_length - 3 - suffix_length
    return f"{value[:prefix_length]}...{value[-suffix_length:]}"
