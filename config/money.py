from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal('0.01')


def r2(value):
    """Round to two decimals, halves go up (0.125 -> 0.13), the way invoices are rounded by hand."""
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)
