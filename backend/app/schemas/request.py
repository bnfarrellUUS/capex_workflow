from decimal import Decimal

from pydantic import BaseModel, Field


class EquipmentItemIn(BaseModel):
    units: int = 1
    condition: str = "NEW"
    type: str = ""
    make: str = ""
    model: str = ""
    cost: Decimal = Decimal(0)


class RequestDraft(BaseModel):
    description: str | None = None
    budgeted: bool | None = None
    replacement: bool | None = None
    health_safety: bool | None = None
    revenue_generating: bool | None = None
    environmental: bool | None = None
    competitive_bids: bool | None = None
    lease_recommended: bool | None = None
    justification: str | None = None
    effect_on_operations: str | None = None
    asset_life: str | None = None
    irr_after_tax: Decimal | None = None
    first_year_ebit: Decimal | None = None
    annual_savings: Decimal | None = None
    payback_years: Decimal | None = None
    npv_savings: Decimal | None = None
    division_id: str | None = None
    equipment_items: list[EquipmentItemIn] = Field(default_factory=list)


class RequestSubmit(BaseModel):
    description: str = Field(min_length=1)
    justification: str = Field(min_length=1)
    effect_on_operations: str = Field(min_length=1)
    division_id: str = Field(min_length=1)
    equipment_items: list[EquipmentItemIn] = Field(min_length=1)
