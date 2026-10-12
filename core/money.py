from decimal import ROUND_HALF_UP, Decimal

PAISA = Decimal("0.01")
GST = Decimal("0.18")


def money(value):
    return format(value.quantize(PAISA, rounding=ROUND_HALF_UP), ".2f")


def line_amounts(price, quantity):
    subtotal = price * quantity
    tax = (subtotal * GST).quantize(PAISA, rounding=ROUND_HALF_UP)
    return subtotal, tax, subtotal + tax
