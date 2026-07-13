import re
from typing import Literal

from pydantic import BaseModel, field_validator

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class EmailSettingsIn(BaseModel):
    mode: Literal["test", "live"]
    test_recipient: str

    @field_validator("test_recipient")
    @classmethod
    def _valid_email(cls, v: str) -> str:
        v = v.strip()
        if not _EMAIL.match(v):
            raise ValueError("test_recipient must be a valid email address")
        return v
