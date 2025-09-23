# listings/templatetags/custom_filters.py
from django import template

register = template.Library()

@register.filter
def get_category_name(categories, category_id):
    try:
        return categories.get(id=category_id).name
    except:
        return "Unknown Category"

@register.filter
def get_location_name(locations, location_value):
    for value, name in locations:
        if value == location_value:
            return name
    return "Unknown Location"

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key, 0)

@register.filter
def user_is_seller(order_items, user):
    """Check if user is seller of any item in order"""
    return order_items.filter(listing__seller=user).exists()