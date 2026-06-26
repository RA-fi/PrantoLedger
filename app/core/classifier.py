"""Map an AuditResult to a categorical Decision (PRD §7.2 + §7.3 + §9.4)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from ..schemas import (
    AnalyzeTicketRequest,
    CaseTypeEnum,
    DepartmentEnum,
    EvidenceVerdictEnum,
    SeverityEnum,
)
from .auditor import AuditResult


HIGH_VALUE_BDT = 1000.0


@dataclass
class Decision:
    """Categorical output of the pipeline (post-auditor, pre-template)."""

    relevant_transaction_id: Optional[str]
    evidence_verdict: EvidenceVerdictEnum
    case_type: CaseTypeEnum
    severity: SeverityEnum
    department: DepartmentEnum
    human_review_required: bool
    confidence: float
    reason_codes: List[str] = field(default_factory=list)


def classify(audit: AuditResult, req: AnalyzeTicketRequest) -> Decision:
    """Pick case_type/department/severity based on the audit findings.

    Order matters: more specific patterns (phishing, duplicate) win over
    generic ones. The decision tree below mirrors PRD §7.1 top-to-bottom.
    """
    user_type = (req.user_type.value if req.user_type else "customer")

    # --- Phishing / safety short-circuits ---------------------------------
    if audit.phishing:
        return Decision(
            relevant_transaction_id=None,
            evidence_verdict=EvidenceVerdictEnum.insufficient_data,
            case_type=CaseTypeEnum.phishing_or_social_engineering,
            severity=SeverityEnum.critical,
            department=DepartmentEnum.fraud_risk,
            human_review_required=True,
            confidence=0.95,
            reason_codes=audit.reason_codes
            + ["phishing_keywords_detected"],
        )

    # --- Empty history + non-phishing (SAMPLE-06 vibe) ---------------------
    if audit.history_empty:
        return Decision(
            relevant_transaction_id=None,
            evidence_verdict=EvidenceVerdictEnum.insufficient_data,
            case_type=CaseTypeEnum.other,
            severity=SeverityEnum.low,
            department=DepartmentEnum.customer_support,
            human_review_required=False,
            confidence=0.6,
            reason_codes=audit.reason_codes,
        )

    # --- Duplicate payment (SAMPLE-10) -------------------------------------
    if audit.duplicate is not None:
        return Decision(
            relevant_transaction_id=audit.duplicate.transaction_id,
            evidence_verdict=EvidenceVerdictEnum.consistent,
            case_type=CaseTypeEnum.duplicate_payment,
            severity=SeverityEnum.high,
            department=DepartmentEnum.payments_ops,
            human_review_required=True,
            confidence=0.95,
            reason_codes=audit.reason_codes
            + ["duplicate_detected", "biller_verification_required"],
        )

    # --- Wrong-transfer pattern (SAMPLE-02 — established recipient) --------
    # PRD §16: an established-recipient pattern (≥ 2 prior transfers to the same
    # counterparty) down-grades severity to medium regardless of amount, because
    # the customer's claim is far weaker than a first-time wrong transfer.
    if audit.wrong_transfer_pattern and audit.amount_matches:
        tx = audit.amount_matches[0]
        return Decision(
            relevant_transaction_id=tx.transaction_id,
            evidence_verdict=EvidenceVerdictEnum.inconsistent,
            case_type=CaseTypeEnum.wrong_transfer,
            severity=SeverityEnum.medium,
            department=DepartmentEnum.dispute_resolution,
            human_review_required=True,
            confidence=0.75,
            reason_codes=audit.reason_codes
            + ["wrong_transfer_claim", "evidence_inconsistent"],
        )

    # --- Ambiguous match (SAMPLE-08) ---------------------------------------
    if audit.ambiguous_match:
        return Decision(
            relevant_transaction_id=None,
            evidence_verdict=EvidenceVerdictEnum.insufficient_data,
            case_type=CaseTypeEnum.wrong_transfer,
            severity=SeverityEnum.medium,
            department=DepartmentEnum.dispute_resolution,
            human_review_required=False,
            confidence=0.65,
            reason_codes=audit.reason_codes + ["needs_clarification"],
        )

    # --- Status conflict (SAMPLE-03 — failed + balance deducted) -----------
    if audit.status_conflict is not None:
        return Decision(
            relevant_transaction_id=audit.status_conflict.transaction_id,
            evidence_verdict=EvidenceVerdictEnum.consistent,
            case_type=CaseTypeEnum.payment_failed,
            severity=SeverityEnum.high,
            department=DepartmentEnum.payments_ops,
            human_review_required=False,
            confidence=0.9,
            reason_codes=audit.reason_codes + ["potential_balance_deduction"],
        )

    # --- Pending settlement (SAMPLE-09) ------------------------------------
    if audit.pending_settlement is not None:
        tx = audit.pending_settlement
        return Decision(
            relevant_transaction_id=tx.transaction_id,
            evidence_verdict=EvidenceVerdictEnum.consistent,
            case_type=CaseTypeEnum.merchant_settlement_delay,
            severity=SeverityEnum.medium,
            department=DepartmentEnum.merchant_operations,
            human_review_required=False,
            confidence=0.92,
            reason_codes=audit.reason_codes
            + ["merchant_settlement", "delay"],
        )

    # --- Agent cash-in pending (SAMPLE-07) ---------------------------------
    if audit.pending_cash_in is not None:
        tx = audit.pending_cash_in
        return Decision(
            relevant_transaction_id=tx.transaction_id,
            evidence_verdict=EvidenceVerdictEnum.consistent,
            case_type=CaseTypeEnum.agent_cash_in_issue,
            severity=SeverityEnum.high,
            department=DepartmentEnum.agent_operations,
            human_review_required=True,
            confidence=0.88,
            reason_codes=audit.reason_codes + ["agent_cash_in", "agent_ops"],
        )

    # --- Refund request (SAMPLE-04) ----------------------------------------
    if audit.refund_match is not None:
        tx = audit.refund_match
        high_value = tx.amount >= HIGH_VALUE_BDT
        return Decision(
            relevant_transaction_id=tx.transaction_id,
            evidence_verdict=EvidenceVerdictEnum.consistent,
            case_type=CaseTypeEnum.refund_request,
            severity=SeverityEnum.medium if high_value else SeverityEnum.low,
            department=(
                DepartmentEnum.dispute_resolution
                if high_value
                else DepartmentEnum.customer_support
            ),
            human_review_required=high_value,
            confidence=0.85,
            reason_codes=audit.reason_codes + ["merchant_policy_dependent"],
        )

    # --- Single wrong-transfer (SAMPLE-01) ---------------------------------
    if audit.single_wrong_transfer is not None:
        tx = audit.single_wrong_transfer
        high_value = tx.amount >= HIGH_VALUE_BDT
        return Decision(
            relevant_transaction_id=tx.transaction_id,
            evidence_verdict=EvidenceVerdictEnum.consistent,
            case_type=CaseTypeEnum.wrong_transfer,
            severity=SeverityEnum.high if high_value else SeverityEnum.medium,
            department=DepartmentEnum.dispute_resolution,
            human_review_required=True,
            confidence=0.9,
            reason_codes=audit.reason_codes
            + ["wrong_transfer", "dispute_initiated"],
        )

    # --- Single amount match, no special pattern ---------------------------
    if len(audit.amount_matches) == 1:
        tx = audit.amount_matches[0]
        return Decision(
            relevant_transaction_id=tx.transaction_id,
            evidence_verdict=EvidenceVerdictEnum.consistent,
            case_type=CaseTypeEnum.other,
            severity=SeverityEnum.low,
            department=_default_department_for_user(user_type),
            human_review_required=False,
            confidence=0.8,
            reason_codes=audit.reason_codes,
        )

    # --- Default / insufficient_data ---------------------------------------
    return Decision(
        relevant_transaction_id=None,
        evidence_verdict=EvidenceVerdictEnum.insufficient_data,
        case_type=CaseTypeEnum.other,
        severity=SeverityEnum.low,
        department=_default_department_for_user(user_type),
        human_review_required=False,
        confidence=0.6,
        reason_codes=audit.reason_codes,
    )


def _default_department_for_user(user_type: str) -> DepartmentEnum:
    """Best-fit department for the 'other' / insufficient_data cases."""
    if user_type == "merchant":
        return DepartmentEnum.merchant_operations
    if user_type == "agent":
        return DepartmentEnum.agent_operations
    return DepartmentEnum.customer_support