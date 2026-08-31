from pydantic import BaseModel, Field


class RegionCreate(BaseModel):
    name: str = Field(min_length=1)
    active: bool = True
    vp_approver_ids: list[str] = []


class RegionUpdate(BaseModel):
    name: str = Field(min_length=1)
    active: bool = True
    vp_approver_ids: list[str] = []
