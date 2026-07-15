from pydantic import BaseModel, Field


class SetPasswordIn(BaseModel):
    new_password: str = Field(min_length=8)
