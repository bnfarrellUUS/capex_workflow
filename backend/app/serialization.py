from decimal import Decimal
from typing import Optional


def money_str(value: Optional[Decimal]) -> Optional[str]:
    """Serialize a Decimal money value as a clean string (no trailing zeros,
    no scientific notation), or None."""
    if value is None:
        return None
    s = format(value, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s
