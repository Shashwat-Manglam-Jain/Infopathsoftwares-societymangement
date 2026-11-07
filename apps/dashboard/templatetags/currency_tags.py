from decimal import Decimal

from django import template

register = template.Library()


@register.filter
def indian_currency(value):
    if value is None:
        return '₹0.00'
    try:
        value = Decimal(str(value))
    except Exception:
        return str(value)

    is_negative = value < 0
    value = abs(value)

    integer_part = int(value)
    decimal_part = f'{value - integer_part:.2f}'[1:]

    s = str(integer_part)
    if len(s) <= 3:
        formatted = s
    else:
        last_three = s[-3:]
        remaining = s[:-3]
        groups = []
        while remaining:
            groups.append(remaining[-2:])
            remaining = remaining[:-2]
        groups.reverse()
        formatted = ','.join(groups) + ',' + last_three

    result = f'₹{formatted}{decimal_part}'
    if is_negative:
        result = f'-{result}'
    return result


@register.filter
def short_currency(value):
    if value is None:
        return '₹0'
    try:
        value = Decimal(str(value))
    except Exception:
        return str(value)

    abs_val = abs(value)
    if abs_val >= 10000000:
        return f'₹{value / 10000000:.1f}Cr'
    if abs_val >= 100000:
        return f'₹{value / 100000:.1f}L'
    if abs_val >= 1000:
        return f'₹{value / 1000:.1f}K'
    return f'₹{value:.0f}'
