from decimal import Decimal

from pydantic import BaseModel


class ThresholdIn(BaseModel):
    level: int
    max_amount: Decimal | None = None
    approver_ids: list[str] = []


class ThresholdsUpdate(BaseModel):
    thresholds: list[ThresholdIn]
