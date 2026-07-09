from decimal import Decimal

from pydantic import BaseModel


class ThresholdIn(BaseModel):
    level: int
    max_amount: Decimal | None = None
    approver_id: str | None = None


class ThresholdsUpdate(BaseModel):
    thresholds: list[ThresholdIn]
