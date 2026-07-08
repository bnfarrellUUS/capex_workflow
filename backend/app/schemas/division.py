from pydantic import BaseModel, Field


class DivisionCreate(BaseModel):
    number: str = Field(min_length=1)
    name: str = Field(min_length=1)


class DivisionUpdate(BaseModel):
    number: str = Field(min_length=1)
    name: str = Field(min_length=1)
    active: bool = True
    l1_approver_id: str | None = None
