from pydantic import BaseModel, Field


class DivisionCreate(BaseModel):
    number: str = Field(min_length=1)
    name: str = Field(min_length=1)
    region_id: str | None = None


class DivisionUpdate(BaseModel):
    number: str = Field(min_length=1)
    name: str = Field(min_length=1)
    active: bool = True
    l1_approver_ids: list[str] = []
    region_id: str | None = None
