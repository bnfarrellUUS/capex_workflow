from pydantic import BaseModel, Field


class DelegateIn(BaseModel):
    delegate_id: str | None = None


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)
