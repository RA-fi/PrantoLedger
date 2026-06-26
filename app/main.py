"""FastAPI orchestrator for PrantoLedger (PRD §12).

Pipeline:
    1. inject-scan            — short-circuit BEFORE any LLM call
    2. audit + classify       — deterministic, no I/O
    3. template               — multilingual, always safe
    4. maybe_polish (LLM)     — optional, fully fault-tolerant
    5. sanitize               — strip any forbidden language from final reply
    6. log + cache            — best-effort SQLite writes
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from . import __version__
from .core import llm as llm_mod
from .core.auditor import run_audit
from .core.classifier import classify
from .core.language import detect_language
from .core.safety import (
    injection_fallback_payload,
    is_injection,
    is_phishing,
    sanitize,
)
from .core.templates import pick_action, pick_template
from .db import sqlite_store
from .schemas import AnalyzeTicketRequest, AnalyzeTicketResponse


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("prantoledger.main")


# ---------------------------------------------------------------------------
# Lifespan: init DB + LLM pool once at startup
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    sqlite_store.init_db()
    llm_mod.init_pool()
    log.info(
        "prantoledger %s ready | llm_pool=%d (ready=%d)",
        __version__,
        llm_mod.pool_size(),
        llm_mod.pool_ready(),
    )
    yield


app = FastAPI(
    title="PrantoLedger — Internal SupportOps Copilot",
    version=__version__,
    lifespan=lifespan,
    # Hide the internal stack-trace path from 500 bodies (we override anyway).
)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def _build_payload(req: AnalyzeTicketRequest) -> Dict[str, Any]:
    """Single-pass orchestration. Returns a dict ready for the response model.

    Always returns a structurally-valid payload — never raises. The HTTP layer
    can wrap the dict directly into AnalyzeTicketResponse.
    """
    started = time.monotonic()

    # --- 1. Pre-LLM injection short-circuit (PRD §9.1) --------------------
    if is_injection(req.complaint or ""):
        sqlite_store.flag_safety(req.ticket_id, "prompt_injection", req.complaint)
        return injection_fallback_payload(req.ticket_id)

    # --- 2. Detect language (for templates + normalisation) ----------------
    language = detect_language(req.complaint or "", req.language.value if req.language else None)
    user_type = req.user_type.value if req.user_type else "customer"

    # --- 3. Audit (deterministic rule engine) -------------------------------
    phishing = is_phishing(req.complaint or "")
    audit = run_audit(req, phishing_flag=phishing)

    # --- 4. Classify (map AuditResult → Decision) ---------------------------
    decision = classify(audit, req)

    # --- 5. Template (multilingual customer reply + action text) ------------
    template_text = pick_template(
        language=language,
        user_type=user_type,
        case_type=decision.case_type.value,
        tx_id=decision.relevant_transaction_id,
    )
    # Variant-aware action text (handles "wrong_transfer_inconsistent" etc.)
    action_variant = "default"
    if decision.case_type.value == "wrong_transfer":
        if decision.evidence_verdict.value == "inconsistent":
            action_variant = "inconsistent"
        elif audit.ambiguous_match:
            action_variant = "ambiguous"
    if audit.history_empty and decision.case_type.value == "other":
        action_variant = "vague_complaint"
    if decision.case_type.value == "phishing_or_social_engineering" and not audit.amount_matches:
        action_variant = "default"
    action_text = pick_action(
        case_type=decision.case_type.value,
        variant=action_variant,
        tx_id=decision.relevant_transaction_id,
    )

    # --- 6. Optional LLM polish (PRD §10) -----------------------------------
    polish = llm_mod.maybe_polish(template_text, language=language)

    # --- 7. Sanitize (post-LLM safety scrub, PRD §9.3) ---------------------
    safe_reply, safe_action = sanitize(polish.text, action_text)

    # --- 8. Compose final payload ------------------------------------------
    tx_id_for_reply = decision.relevant_transaction_id
    if not safe_reply.strip():
        safe_reply = (
            "We have received your request. Please do not share your PIN or OTP "
            "with anyone. Our support team will review the case and contact you "
            "through official support channels."
        )
    if "{tx}" in safe_reply or (tx_id_for_reply and "{tx}" in safe_reply):
        safe_reply = safe_reply.replace("{tx}", tx_id_for_reply or "")

    if phishing:
        decision.reason_codes = list(decision.reason_codes or []) + ["phishing_keywords_detected"]

    agent_summary = _build_agent_summary(req, audit, decision)
    recommended_next_action = safe_action
    if len(recommended_next_action) < 10:
        recommended_next_action = (
            "Review the case and respond through official channels. "
            "Do not request or share customer credentials."
        )

    payload: Dict[str, Any] = {
        "ticket_id": req.ticket_id,
        "relevant_transaction_id": decision.relevant_transaction_id,
        "evidence_verdict": decision.evidence_verdict.value,
        "case_type": decision.case_type.value,
        "severity": decision.severity.value,
        "department": decision.department.value,
        "agent_summary": agent_summary,
        "recommended_next_action": recommended_next_action,
        "customer_reply": safe_reply,
        "human_review_required": bool(decision.human_review_required),
        "confidence": float(decision.confidence),
        "reason_codes": list(decision.reason_codes or []),
    }

    # --- 9. Cache + audit log (best-effort, non-blocking) ------------------
    elapsed_ms = int((time.monotonic() - started) * 1000)
    request_hash = sqlite_store.cache_key(req.complaint, [t.model_dump() for t in (req.transaction_history or [])])
    try:
        sqlite_store.put_cached(request_hash, payload)
    except Exception:  # pragma: no cover
        pass

    safety_flags = []
    if phishing:
        safety_flags.append("phishing_keywords_detected")
    if is_injection(req.complaint or ""):
        safety_flags.append("prompt_injection_blocked")

    sqlite_store.log_audit(
        {
            "ticket_id": req.ticket_id,
            "request_hash": request_hash,
            "verdict": decision.evidence_verdict.value,
            "case_type": decision.case_type.value,
            "severity": decision.severity.value,
            "department": decision.department.value,
            "human_review": decision.human_review_required,
            "safety_flags": ",".join(safety_flags),
            "latency_ms": elapsed_ms,
            "used_llm": polish.used_llm,
            "groq_attempts": polish.groq_attempts,
            "groq_last_alias": polish.groq_last_alias,
        }
    )

    return payload


def _build_agent_summary(req: AnalyzeTicketRequest, audit, decision) -> str:
    """One short paragraph for the agent — describes what was found."""
    tx = decision.relevant_transaction_id
    if decision.case_type.value == "phishing_or_social_engineering":
        return (
            "Reported social-engineering or credential-request attempt. "
            "The complaint itself contains phishing or credential-request language. "
            "Routed to fraud_risk without evaluating transaction history."
        )
    if decision.case_type.value == "other" and audit.history_empty:
        return (
            "Customer complaint received but transaction history is empty and the "
            "complaint is vague. Insufficient data to make a deterministic finding."
        )
    if audit.ambiguous_match:
        return (
            "Multiple possible matches found for the mentioned amount of "
            f"{req.complaint or ''}. Request needs more disambiguating detail "
            "(such as the recipient phone or reference)."
        )
    if decision.case_type.value == "wrong_transfer" and decision.evidence_verdict.value == "inconsistent":
        return (
            f"Wrong-transfer claim for transaction {tx}, but the recipient has an "
            "established transaction pattern. Flagged for human review."
        )
    if decision.case_type.value == "wrong_transfer":
        return (
            f"Wrong-transfer claim confirmed against transaction {tx}. "
            "Dispute initiated to the dispute resolution team."
        )
    if decision.case_type.value == "payment_failed":
        return (
            f"Failed transaction {tx} with apparent balance deduction noted. "
            "Payments team will investigate."
        )
    if decision.case_type.value == "duplicate_payment":
        return (
            f"Possible duplicate payment detected for transaction {tx}. "
            "Payments team will verify with the biller."
        )
    if decision.case_type.value == "merchant_settlement_delay":
        return (
            f"Settlement transaction {tx} is pending. Merchant operations will "
            "verify batch status and ETA."
        )
    if decision.case_type.value == "agent_cash_in_issue":
        return (
            f"Pending agent cash-in {tx} flagged for agent operations review."
        )
    if decision.case_type.value == "refund_request":
        return (
            f"Refund request for completed merchant payment {tx}. Eligibility "
            "depends on the merchant's own policy."
        )
    return (
        f"Ticket logged. Single transaction match found ({tx}). Routed to "
        f"{decision.department.value} for follow-up."
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": __version__,
        "llm_pool": {
            "size": llm_mod.pool_size(),
            "ready": llm_mod.pool_ready(),
            "used_in_window": llm_mod.pool_used(),
        },
    }


@app.post("/analyze-ticket")
def analyze_ticket(payload: Dict[str, Any]):
    # Coerce to the request model first so validation errors are uniform.
    try:
        req = AnalyzeTicketRequest.model_validate(payload)
    except ValidationError as e:
        errors = e.errors()
        is_blank_complaint = False
        for err in errors:
            loc = err.get("loc", ())
            msg = str(err.get("msg", "")).lower()
            if "complaint" in loc and ("blank" in msg or "too_short" in msg or "at least 1 character" in msg):
                is_blank_complaint = True
                break

        if is_blank_complaint:
            return JSONResponse(
                status_code=422,
                content={"error": "semantic_invalid", "detail": "complaint is empty"},
            )

        # Otherwise, schema validation failed
        detail_msg = "schema validation failed"
        if errors:
            err = errors[0]
            loc_str = ".".join(str(x) for x in err.get("loc", ()))
            detail_msg = f"Field {loc_str}: {err.get('msg', 'invalid value')}"

        return JSONResponse(
            status_code=400,
            content={"error": "malformed_input", "detail": detail_msg},
        )

    # Cache short-circuit (PRD §12) — return the previous response if exact same input.
    request_hash = sqlite_store.cache_key(req.complaint, [t.model_dump() for t in (req.transaction_history or [])])
    cached = sqlite_store.get_cached(request_hash)
    if cached is not None:
        # Echo current ticket_id (caching is by request, not by ticket_id).
        cached["ticket_id"] = req.ticket_id
        return _coerce_response(cached)

    out = _build_payload(req)
    return _coerce_response(out)


def _coerce_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run the payload through AnalyzeTicketResponse for a final schema check."""
    try:
        return AnalyzeTicketResponse.model_validate(payload).model_dump(mode="json")
    except ValidationError:
        # Last-resort scrub: pad any too-short text fields so min_length passes.
        for k in ("agent_summary", "recommended_next_action", "customer_reply"):
            v = payload.get(k) or ""
            if not isinstance(v, str) or len(v.strip()) < 10:
                payload[k] = (
                    "Review the case and respond through official channels. "
                    "Do not request or share customer credentials."
                )
        return AnalyzeTicketResponse.model_validate(payload).model_dump(mode="json")


# ---------------------------------------------------------------------------
# Global error handlers — never leak stack traces / secrets
# ---------------------------------------------------------------------------


from fastapi.exceptions import RequestValidationError


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    errors = exc.errors()
    is_blank_complaint = False
    for err in errors:
        loc = err.get("loc", ())
        msg = str(err.get("msg", "")).lower()
        if "complaint" in loc and ("blank" in msg or "too_short" in msg or "at least 1 character" in msg):
            is_blank_complaint = True
            break

    if is_blank_complaint:
        return JSONResponse(
            status_code=422,
            content={"error": "semantic_invalid", "detail": "complaint is empty"},
        )

    detail_msg = "schema validation failed"
    if errors:
        err = errors[0]
        loc_str = ".".join(str(x) for x in err.get("loc", ()))
        detail_msg = f"Field {loc_str}: {err.get('msg', 'invalid value')}"

    return JSONResponse(
        status_code=400,
        content={"error": "malformed_input", "detail": detail_msg},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException):
    # If it is already a flat error dictionary, return it.
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail,
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "http_error", "detail": str(exc.detail)},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, _exc: Exception):
    log.exception("unhandled error in /analyze-ticket")
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "detail": "An internal error occurred."},
    )


# ---------------------------------------------------------------------------
# Static frontend (single-page dark/light console)
# ---------------------------------------------------------------------------

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.is_dir():
    # Serve assets like styles.css / app.js from /static/* and the SPA shell
    # from /.
    app.mount(
        "/static",
        StaticFiles(directory=str(FRONTEND_DIR)),
        name="frontend-static",
    )

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(str(FRONTEND_DIR / "index.html"))

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon() -> Response:
        # 1x1 transparent PNG so the browser never 404s in dev.
        import base64

        png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
        )
        return Response(content=png, media_type="image/png")


# Expose the resolved port for tests / health handlers.
PORT = int(os.getenv("PORT", "8080"))
