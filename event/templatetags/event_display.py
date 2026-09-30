from django import template


register = template.Library()


@register.filter
def compact_email(value):
    """Keep both ends of a long address within a 35-character label."""
    if not value or len(value) <= 35:
        return value
    return f"{value[:16]}...{value[-16:]}"
