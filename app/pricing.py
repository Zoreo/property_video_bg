"""All prices in one place, in euro cents."""

BASE_PRICE_CENTS = 1500
STAGING_PRICE_CENTS = 500
CURRENCY = "eur"


def order_price_cents(staging: bool) -> int:
    return BASE_PRICE_CENTS + (STAGING_PRICE_CENTS if staging else 0)


def format_eur(cents: int) -> str:
    euros, rest = divmod(cents, 100)
    return f"{euros} EUR" if rest == 0 else f"{euros}.{rest:02d} EUR"
