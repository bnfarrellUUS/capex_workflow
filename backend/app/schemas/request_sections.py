from typing import Literal

from pydantic import BaseModel, field_validator

# Wizard sections an admin may hide. Basic Info holds the Division that drives
# Level-1 routing and Review carries Submit, so neither is hideable — they are
# absent from the Literal below, so the API rejects them with a 400.
HIDEABLE = ("description", "effect_on_ops", "asset_details", "economic", "attachments")

HideableSection = Literal["description", "effect_on_ops", "asset_details",
                          "economic", "attachments"]


class HiddenSectionsIn(BaseModel):
    # Typed as a Literal rather than validated with a raising field_validator:
    # a ValueError from a validator lands in the error's `ctx` and the app-wide
    # ValidationError handler cannot JSON-serialize it.
    hidden: list[HideableSection] = []

    @field_validator("hidden")
    @classmethod
    def _dedupe(cls, v: list[str]) -> list[str]:
        return list(dict.fromkeys(v))
