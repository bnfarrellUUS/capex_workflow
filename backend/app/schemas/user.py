from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1)
    roles: list[str] = Field(default_factory=lambda: ["REQUESTOR"])
    division_id: str | None = None


class UserUpdate(BaseModel):
    name: str = Field(min_length=1)
    email: EmailStr
    roles: list[str]
    division_id: str | None = None
    active: bool = True
