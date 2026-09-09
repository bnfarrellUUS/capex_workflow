"""Input shapes for /api/pings.

Constraints are TYPES, not raising validators: a field_validator that raises
puts an unserializable object under errors()['ctx'] and the 400 becomes a 500
through create_app's ValidationError handler (same trap CommentIn avoids). The
blank-note and cap checks therefore live in ping_service as ServiceErrors.
"""
from pydantic import BaseModel, ConfigDict, Field


class PingCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipient_ids: list[str] = Field(min_length=1)
    note: str
    request_id: str | None = None


class PingReplyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str
