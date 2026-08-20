"""
Strict output validation — the Python equivalent of the Zod schema layer.
Guarantees action/message_type/confidence/evidence are always contract-valid,
regardless of whether the value came from a rule or from the LLM.
"""
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator

ALLOWED_ACTIONS = ("notify", "digest", "mute")
ALLOWED_TYPES = (
    "personal", "urgent", "event", "payment", "business_update",
    "promotion", "greeting", "forward", "spam", "scam", "unknown",
)


class OutputRow(BaseModel):
    message_id: str
    action: Literal["notify", "digest", "mute"]
    message_type: Literal[
        "personal", "urgent", "event", "payment", "business_update",
        "promotion", "greeting", "forward", "spam", "scam", "unknown",
    ]
    reason: str = Field(min_length=1, max_length=400)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_message_ids: str = "none"

    @field_validator("evidence_message_ids")
    @classmethod
    def normalize_evidence(cls, v: str) -> str:
        v = (v or "none").strip()
        return v if v else "none"

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, v: str) -> str:
        return v.strip()

    def to_csv_row(self) -> dict:
        return {
            "message_id": self.message_id,
            "action": self.action,
            "message_type": self.message_type,
            "reason": self.reason,
            "confidence": round(self.confidence, 2),
            "evidence_message_ids": self.evidence_message_ids,
        }


def validate_or_none(candidate: dict) -> Optional[OutputRow]:
    """Returns a validated OutputRow, or None if the candidate is malformed.
    Never raises — callers should fall back to the rule engine on None."""
    try:
        return OutputRow(**candidate)
    except Exception:
        return None
