"""Pydantic v2 request/response schemas for PrantoLedger.

Exact enum spellings and field shapes per PRD §6.1 and §6.2, matching the
problem statement byte-for-byte. Variants are scored as schema violations,
so this module is intentionally strict and minimal.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, AliasChoices


# ---------------------------------------------------------------------------
# Request enums
# ---------------------------------------------------------------------------


class LanguageEnum(str, Enum):
    en = "en"
    bn = "bn"
    mixed = "mixed"


class ChannelEnum(str, Enum):
    in_app_chat = "in_app_chat"
    call_center = "call_center"
    email = "email"
    merchant_portal = "merchant_portal"
    field_agent = "field_agent"


class UserTypeEnum(str, Enum):
    customer = "customer"
    merchant = "merchant"
    agent = "agent"
    unknown = "unknown"


class TransactionTypeEnum(str, Enum):
    transfer = "transfer"
    payment = "payment"
    cash_in = "cash_in"
    cash_out = "cash_out"
    settlement = "settlement"
    refund = "refund"


class TransactionStatusEnum(str, Enum):
    completed = "completed"
    failed = "failed"
    pending = "pending"
    reversed = "reversed"


# ---------------------------------------------------------------------------
# Response enums
# ---------------------------------------------------------------------------


class EvidenceVerdictEnum(str, Enum):
    consistent = "consistent"
    inconsistent = "inconsistent"
    insufficient_data = "insufficient_data"


class CaseTypeEnum(str, Enum):
    wrong_transfer = "wrong_transfer"
    payment_failed = "payment_failed"
    refund_request = "refund_request"
    duplicate_payment = "duplicate_payment"
    merchant_settlement_delay = "merchant_settlement_delay"
    agent_cash_in_issue = "agent_cash_in_issue"
    phishing_or_social_engineering = "phishing_or_social_engineering"
    other = "other"


class SeverityEnum(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class DepartmentEnum(str, Enum):
    customer_support = "customer_support"
    dispute_resolution = "dispute_resolution"
    payments_ops = "payments_ops"
    merchant_operations = "merchant_operations"
    agent_operations = "agent_operations"
    fraud_risk = "fraud_risk"


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------


class TransactionHistoryEntry(BaseModel):
    """A single transaction entry from the harness-provided snippet.

    Field names match PRD Â§6.2 exactly: `transaction_type` (not `type`),
    `currency` and `counterparty` are optional.
    """

    model_config = ConfigDict(extra="ignore")  # forward-compat for fields the harness may add later

    transaction_id: str = Field(..., min_length=1)
    timestamp: str = Field(..., min_length=1)  # ISO 8601, may end with Z
    # PRD §6.2 field name is `transaction_type`. We also accept `type` on the
    # wire (sample harness uses `type`) via `validation_alias`, and we expose
    # the attribute as `transaction_type` internally so the rest of the codebase
    # can read `tx.transaction_type` cleanly.
    #
    # `serialization_alias="type"` keeps JSON serialisation producing the
    # shorter `type` key that the existing sample harness (and our own
    # sample_*.json files) already use, so re-serialised payloads round-trip
    # cleanly through any cache, log, or downstream JSON consumer.
    transaction_type: TransactionTypeEnum = Field(
        ...,
        validation_alias=AliasChoices("type", "transaction_type"),
        serialization_alias="type",
    )
    amount: float
    currency: Optional[str] = Field(default="BDT", min_length=1, max_length=8)
    counterparty: Optional[str] = None
    status: TransactionStatusEnum


class AnalyzeTicketRequest(BaseModel):
    """Input to POST /analyze-ticket."""

    model_config = ConfigDict(extra="ignore")  # forward-compat: harness may add optional fields

    ticket_id: str = Field(..., min_length=1)
    complaint: str = Field(..., min_length=1)
    language: Optional[LanguageEnum] = None
    channel: Optional[ChannelEnum] = None
    user_type: Optional[UserTypeEnum] = None
    campaign_context: Optional[str] = None
    transaction_history: Optional[List[TransactionHistoryEntry]] = Field(default_factory=list)
    metadata: Optional[Dict] = Field(default_factory=dict)

    @field_validator("complaint")
    @classmethod
    def complaint_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("complaint must not be blank")
        return v


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------


class AnalyzeTicketResponse(BaseModel):
    """Output of POST /analyze-ticket."""

    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    relevant_transaction_id: Optional[str] = None  # JSON null when no match
    evidence_verdict: EvidenceVerdictEnum
    case_type: CaseTypeEnum
    severity: SeverityEnum
    department: DepartmentEnum
    agent_summary: str = Field(..., min_length=10)
    recommended_next_action: str = Field(..., min_length=10)
    customer_reply: str = Field(..., min_length=10)
    human_review_required: bool
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    reason_codes: List[str] = Field(default_factory=list)