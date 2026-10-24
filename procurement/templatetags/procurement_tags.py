from decimal import Decimal
from django import template

register = template.Library()


@register.filter
def rupiah(value):
    """
    Format value to Indonesian Rupiah currency with dot separator and without trailing decimals:
    7000000 -> "Rp 7.000.000"
    9500000.00 -> "Rp 9.500.000"
    """
    if value is None or value == "":
        return "Rp 0"
    try:
        val = Decimal(str(value))
        rounded_int = int(round(val))
        formatted = f"{rounded_int:,}".replace(",", ".")
        return f"Rp {formatted}"
    except (ValueError, TypeError):
        return f"Rp {value}"


@register.filter
def rupiah_num(value):
    """
    Format number with dot thousand separator without 'Rp' prefix and without trailing decimals:
    7000000 -> "7.000.000"
    """
    if value is None or value == "":
        return "0"
    try:
        val = Decimal(str(value))
        rounded_int = int(round(val))
        return f"{rounded_int:,}".replace(",", ".")
    except (ValueError, TypeError):
        return str(value)


@register.filter
def qty(value):
    """
    Format quantity: remove trailing zeros.
    100.00 -> "100"
    1.50   -> "1,5"
    2.75   -> "2,75"
    """
    if value is None or value == "":
        return "0"
    try:
        val = Decimal(str(value)).normalize()
        # If no fractional part, return as integer
        if val == val.to_integral_value():
            return str(int(val))
        # Otherwise strip trailing zeros (normalize does this) and use comma as decimal separator
        return str(val).replace(".", ",")
    except (ValueError, TypeError):
        return str(value)
