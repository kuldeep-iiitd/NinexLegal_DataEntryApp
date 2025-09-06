from django import template

register = template.Library()

@register.filter
def dict_get(d, key):
    """Safely get a key from a dict in templates."""
    if isinstance(d, dict):
        return d.get(key, 0)
    return 0

@register.filter
def count_by_status(cases, status):
    """Count cases by status."""
    return len([c for c in cases if c.status == status])

@register.filter
def count_by_advocate(cases, has_advocate=True):
    """Count cases by whether they have an assigned advocate."""
    if has_advocate:
        return len([c for c in cases if c.assigned_advocate is not None])
    else:
        return len([c for c in cases if c.assigned_advocate is None])
        
@register.filter
def filter_by_status(cases, status):
    """Filter cases by status."""
    return [c for c in cases if c.status == status]

@register.filter
def dictsortbykey(value, key):
    """
    Takes a list of dictionaries and returns that list sorted by the property given in the argument.
    For cases, allows checking if any cases have a particular status.
    """
    if isinstance(value, list):
        filtered_items = [item for item in value if hasattr(item, 'status') and item.status == key]
        return filtered_items
    return value
