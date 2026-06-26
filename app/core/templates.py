"""Multilingual customer-reply templates (PRD §8.4).

The reply is always built from a template — the LLM only lightly paraphrases
it later (PRD §10.1). Falling back to `("en", "customer", "other")` is
explicit so missing combinations never crash the pipeline.
"""

from __future__ import annotations

from typing import Optional

from ..schemas import CaseTypeEnum


# All user-visible strings live here, keyed by (language, user_type, case_type).
# Missing keys fall back to ("en", "customer", "other") per PRD §8.4.
TEMPLATES: dict[tuple[str, str, str], str] = {
    # ---------------------------- English — customer -------------------------
    ("en", "customer", "wrong_transfer"): (
        "We have noted your concern about transaction {tx}. "
        "Please do not share your PIN or OTP with anyone. "
        "Our dispute team will review the case and contact you through official support channels."
    ),
    ("en", "customer", "payment_failed"): (
        "We have noted that transaction {tx} may have caused an unexpected balance deduction. "
        "Our payments team will review the case and any eligible amount will be returned through "
        "official channels. Please do not share your PIN or OTP with anyone."
    ),
    ("en", "customer", "refund_request"): (
        "Thank you for reaching out. Refunds for completed merchant payments depend on the "
        "merchant's own policy. We recommend contacting the merchant directly. If you need help "
        "reaching them, please reply and we will guide you. Please do not share your PIN or OTP "
        "with anyone."
    ),
    ("en", "customer", "duplicate_payment"): (
        "We have noted the possible duplicate payment for transaction {tx}. "
        "Our payments team will verify with the biller and any eligible amount will be returned "
        "through official channels. Please do not share your PIN or OTP with anyone."
    ),
    ("en", "customer", "phishing_or_social_engineering"): (
        "Thank you for reaching out before sharing any information. We never ask for your PIN, "
        "OTP, or password under any circumstances. Please do not share these with anyone, even "
        "if they claim to be from us. Our fraud team has been notified of this incident."
    ),
    ("en", "customer", "merchant_settlement_delay"): (
        "We have noted your concern about settlement {tx}. Our merchant operations team will "
        "check the batch status and update you on the expected settlement time through official "
        "channels."
    ),
    ("en", "customer", "agent_cash_in_issue"): (
        "We have noted your concern about transaction {tx}. Our agent operations team will "
        "verify the pending cash-in status and contact you through official channels. "
        "Please do not share your PIN or OTP with anyone."
    ),
    ("en", "customer", "other"): (
        "Thank you for reaching out. To help you faster, please share the transaction ID, "
        "the amount involved, and a short description of what went wrong. "
        "Please do not share your PIN or OTP with anyone."
    ),

    # ---------------------------- English — merchant ------------------------
    ("en", "merchant", "merchant_settlement_delay"): (
        "We have logged your settlement dispute under transaction {tx}. "
        "The merchant operations team will resolve the delay within standard SLA windows."
    ),
    ("en", "merchant", "refund_request"): (
        "Thank you for flagging this. Refund eligibility for completed merchant payments depends "
        "on the merchant's own policy and the original transaction terms. Please share the "
        "disputed transaction ID so we can guide you on next steps. Do not share your account "
        "PIN or OTP with anyone."
    ),
    ("en", "merchant", "payment_failed"): (
        "We have noted the failed payment transaction {tx}. Our payments operations team will "
        "investigate the ledger state and contact you through official channels regarding the "
        "resolution timeline."
    ),
    ("en", "merchant", "wrong_transfer"): (
        "We have logged your wrong-transfer dispute for transaction {tx}. Our dispute resolution "
        "team will review the case and contact you through official channels. Please do not "
        "share your account PIN or OTP with anyone."
    ),
    ("en", "merchant", "duplicate_payment"): (
        "We have noted the possible duplicate payment for transaction {tx}. Our payments team "
        "will verify with the biller and any eligible amount will be returned through official "
        "channels. Please do not share your PIN or OTP with anyone."
    ),
    ("en", "merchant", "phishing_or_social_engineering"): (
        "Thank you for alerting us. The company never asks merchants for PINs, OTPs, or "
        "passwords. Our fraud risk team has been notified and will follow up through official "
        "channels."
    ),
    ("en", "merchant", "agent_cash_in_issue"): (
        "We have noted your concern about transaction {tx}. Our agent operations team will "
        "verify the pending cash-in status and contact you through official channels. "
        "Please do not share your PIN or OTP with anyone."
    ),
    ("en", "merchant", "other"): (
        "Thank you for reaching out. To help you faster, please share the transaction ID, the "
        "amount involved, and a short description of what went wrong. "
        "Please do not share your account PIN or OTP with anyone."
    ),

    # ---------------------------- English — agent ---------------------------
    ("en", "agent", "agent_cash_in_issue"): (
        "Pending transaction {tx} has been flagged for agent operations review. Please retain "
        "the customer reference and the agent till slip until the operations team confirms the "
        "ledger state."
    ),
    ("en", "agent", "payment_failed"): (
        "Failed transaction {tx} flagged. Payments operations team will inspect the ledger and "
        "reply through official channels."
    ),
    ("en", "agent", "wrong_transfer"): (
        "Wrong-transfer dispute logged for transaction {tx}. Dispute resolution team will follow "
        "up through official channels."
    ),
    ("en", "agent", "refund_request"): (
        "Refund request logged for transaction {tx}. Follow the standard refund dispute workflow "
        "through official channels. Do not share credentials with the customer or any third party."
    ),
    ("en", "agent", "duplicate_payment"): (
        "Duplicate payment flagged for transaction {tx}. Payments team will verify with the "
        "biller through official channels."
    ),
    ("en", "agent", "merchant_settlement_delay"): (
        "Settlement {tx} flagged for merchant operations review. Provide the merchant reference "
        "and batch ID through official channels for SLA tracking."
    ),
    ("en", "agent", "phishing_or_social_engineering"): (
        "Suspicious activity report logged. Fraud risk team will follow up through official "
        "channels. Do not engage with the suspicious contact."
    ),
    ("en", "agent", "other"): (
        "Ticket logged. Please provide the transaction ID, amount, and a short description "
        "through official channels. Do not request or share customer credentials."
    ),

    # ---------------------------- Bangla — customer -------------------------
    ("bn", "customer", "wrong_transfer"): (
        "লেনদেন {tx} সম্পর্কে আপনার অভিযোগ আমরা গ্রহণ করেছি। অনুগ্রহ করে কারো সাথে আপনার "
        "পিন বা ওটিপি শেয়ার করবেন না। আমাদের ডিসপিউট টিম বিষয়টি পর্যালোচনা করে অফিসিয়াল "
        "সাপোর্ট চ্যানেলের মাধ্যমে আপনার সাথে যোগাযোগ করবে।"
    ),
    ("bn", "customer", "payment_failed"): (
        "লেনদেন {tx} এর ফলে অপ্রত্যাশিত ব্যালেন্স কর্তন হতে পারে বলে আমরা অবগত হয়েছি। "
        "আমাদের পেমেন্টস টিম বিষয়টি পর্যালোচনা করবে এবং যোগ্য পরিমাণ অফিসিয়াল চ্যানেলের "
        "মাধ্যমে ফেরত দেওয়া হবে। অনুগ্রহ করে কারো সাথে পিন বা ওটিপি শেয়ার করবেন না।"
    ),
    ("bn", "customer", "refund_request"): (
        "যোগাযোগ করার জন্য ধন্যবাদ। সম্পন্ন মার্চেন্ট পেমেন্টের রিফান্ড মার্চেন্টের নিজস্ব "
        "নীতির উপর নির্ভর করে। আমরা সরাসরি মার্চেন্টের সাথে যোগাযোগ করার পরামর্শ দিচ্ছি। "
        "প্রয়োজনে আমাদের জানান, আমরা সাহায্য করব। অনুগ্রহ করে কারো সাথে পিন বা ওটিপি "
        "শেয়ার করবেন না।"
    ),
    ("bn", "customer", "duplicate_payment"): (
        "লেনদেন {tx} সংক্রান্ত সম্ভাব্য ডুপ্লিকেট পেমেন্টের বিষয়টি আমরা অবগত হয়েছি। "
        "আমাদের পেমেন্টস টিম বিলারের সাথে যাচাই করবে এবং যোগ্য পরিমাণ অফিসিয়াল চ্যানেলের "
        "মাধ্যমে ফেরত দেওয়া হবে। অনুগ্রহ করে কারো সাথে পিন বা ওটিপি শেয়ার করবেন না।"
    ),
    ("bn", "customer", "phishing_or_social_engineering"): (
        "তথ্য শেয়ার না করায় ধন্যবাদ। আমরা কখনো আপনার পিন, ওটিপি বা পাসওয়ার্ড চাই না। "
        "কেউ আমাদের পক্ষ থেকে দাবি করলেও এই তথ্য শেয়ার করবেন না। আমাদের ফ্রড টিম এই ঘটনা "
        "সম্পর্কে অবহিত হয়েছে।"
    ),
    ("bn", "customer", "merchant_settlement_delay"): (
        "সেটেলমেন্ট {tx} সম্পর্কে আপনার অভিযোগ আমরা অবগত হয়েছি। আমাদের মার্চেন্ট "
        "অপারেশন্স টিম ব্যাচের অবস্থা যাচাই করে অফিসিয়াল চ্যানেলের মাধ্যমে প্রত্যাশিত "
        "সেটেলমেন্ট সময়ের আপডেট দেবে।"
    ),
    ("bn", "customer", "agent_cash_in_issue"): (
        "আপনার লেনদেন {tx} এর বিষয়ে আমরা অবগত হয়েছি। আমাদের এজেন্ট অপারেশন্স দল এটি দ্রুত "
        "যাচাই করবে এবং অফিসিয়াল চ্যানেলে আপনাকে জানাবে। অনুগ্রহ করে কারো সাথে আপনার "
        "পিন বা ওটিপি শেয়ার করবেন না।"
    ),
    ("bn", "customer", "other"): (
        "যোগাযোগ করার জন্য ধন্যবাদ। দ্রুত সাহায্য করতে, অনুগ্রহ করে লেনদেন আইডি, পরিমাণ "
        "এবং সমস্যাটির একটি সংক্ষিপ্ত বিবরণ শেয়ার করুন। অনুগ্রহ করে কারো সাথে আপনার পিন "
        "বা ওটিপি শেয়ার করবেন না।"
    ),

    # ---------------------------- Bangla — merchant ------------------------
    ("bn", "merchant", "merchant_settlement_delay"): (
        "সেটেলমেন্ট {tx} সংক্রান্ত অভিযোগ আমরা গ্রহণ করেছি। মার্চেন্ট অপারেশন্স টিম "
        "স্ট্যান্ডার্ড এসএলএ উইন্ডোতে বিষয়টি সমাধান করবে।"
    ),
    ("bn", "merchant", "refund_request"): (
        "সম্পন্ন মার্চেন্ট পেমেন্টের রিফান্ড মার্চেন্টের নিজস্ব নীতি ও লেনদেনের শর্তাবলীর "
        "উপর নির্ভর করে। দয়া করে বিতর্কিত লেনদেন আইডি শেয়ার করুন যাতে আমরা পরবর্তী পদক্ষেপ "
        "জানাতে পারি। অনুগ্রহ করে কারো সাথে পিন বা ওটিপি শেয়ার করবেন না।"
    ),
    ("bn", "merchant", "payment_failed"): (
        "ব্যর্থ লেনদেন {tx} এর বিষয়টি আমরা অবগত হয়েছি। পেমেন্টস অপারেশন্স টিম লেজারের "
        "অবস্থা যাচাই করে অফিসিয়াল চ্যানেলে সমাধানের সময়সীমা জানাবে।"
    ),
    ("bn", "merchant", "wrong_transfer"): (
        "লেনদেন {tx} এর ভুল-প্রাপক অভিযোগ আমরা গ্রহণ করেছি। ডিসপিউট রেজোলিউশন টিম "
        "বিষয়টি পর্যালোচনা করে অফিসিয়াল চ্যানেলে যোগাযোগ করবে। অনুগ্রহ করে অ্যাকাউন্টের "
        "পিন বা ওটিপি কারো সাথে শেয়ার করবেন না।"
    ),
    ("bn", "merchant", "duplicate_payment"): (
        "লেনদেন {tx} এর সম্ভাব্য ডুপ্লিকেট পেমেন্টের বিষয়টি আমরা অবগত হয়েছি। আমাদের "
        "পেমেন্টস টিম বিলারের সাথে যাচাই করবে এবং যোগ্য পরিমাণ অফিসিয়াল চ্যানেলের মাধ্যমে "
        "ফেরত দেওয়া হবে। অনুগ্রহ করে পিন বা ওটিপি শেয়ার করবেন না।"
    ),
    ("bn", "merchant", "phishing_or_social_engineering"): (
        "আমাদের সতর্ক করার জন্য ধন্যবাদ। প্রতিষ্ঠান কখনো মার্চেন্টদের কাছ থেকে পিন, ওটিপি "
        "বা পাসওয়ার্ড চায় না। আমাদের ফ্রড রিস্ক টিম অবহিত হয়েছে এবং অফিসিয়াল চ্যানেলে "
        "যোগাযোগ করবে।"
    ),
    ("bn", "merchant", "agent_cash_in_issue"): (
        "লেনদেন {tx} সংক্রান্ত অভিযোগ আমরা অবগত হয়েছি। এজেন্ট অপারেশন্স টিম পেন্ডিং "
        "ক্যাশ-ইনের অবস্থা যাচাই করে অফিসিয়াল চ্যানেলে যোগাযোগ করবে। অনুগ্রহ করে পিন বা "
        "ওটিপি শেয়ার করবেন না।"
    ),
    ("bn", "merchant", "other"): (
        "যোগাযোগ করার জন্য ধন্যবাদ। দ্রুত সাহায্য করতে, অনুগ্রহ করে লেনদেন আইডি, পরিমাণ "
        "এবং সমস্যার সংক্ষিপ্ত বিবরণ শেয়ার করুন। অনুগ্রহ করে অ্যাকাউন্টের পিন বা ওটিপি কারো "
        "সাথে শেয়ার করবেন না।"
    ),

    # ---------------------------- Bangla — agent ---------------------------
    ("bn", "agent", "agent_cash_in_issue"): (
        "পেন্ডিং লেনদেন {tx} এজেন্ট অপারেশন্স পর্যালোচনার জন্য ফ্ল্যাগ করা হয়েছে। "
        "অপারেশন্স টিম লেজার নিশ্চিত না হওয়া পর্যন্ত কাস্টমার রেফারেন্স ও এজেন্ট তিল স্লিপ "
        "সংরক্ষণ করুন।"
    ),
    ("bn", "agent", "payment_failed"): (
        "ব্যর্থ লেনদেন {tx} ফ্ল্যাগ করা হয়েছে। পেমেন্টস অপারেশন্স টিম লেজার পরীক্ষা করে "
        "অফিসিয়াল চ্যানেলে জানাবে।"
    ),
    ("bn", "agent", "wrong_transfer"): (
        "লেনদেন {tx} এর ভুল-প্রাপক অভিযোগ লগ করা হয়েছে। ডিসপিউট রেজোলিউশন টিম অফিসিয়াল "
        "চ্যানেলে ফলো-আপ করবে।"
    ),
    ("bn", "agent", "refund_request"): (
        "লেনদেন {tx} এর রিফান্ড অনুরোধ লগ করা হয়েছে। অফিসিয়াল চ্যানেলে স্ট্যান্ডার্ড রিফান্ড "
        "ডিসপিউট ওয়ার্কফ্লো অনুসরণ করুন। কাস্টমার বা তৃতীয় পক্ষের সাথে শংসাপত্র শেয়ার করবেন না।"
    ),
    ("bn", "agent", "duplicate_payment"): (
        "লেনদেন {tx} এর ডুপ্লিকেট পেমেন্ট ফ্ল্যাগ করা হয়েছে। পেমেন্টস টিম অফিসিয়াল "
        "চ্যানেলে বিলারের সাথে যাচাই করবে।"
    ),
    ("bn", "agent", "merchant_settlement_delay"): (
        "সেটেলমেন্ট {tx} মার্চেন্ট অপারেশন্স পর্যালোচনার জন্য ফ্ল্যাগ করা হয়েছে। এসএলএ "
        "ট্র্যাকিংয়ের জন্য অফিসিয়াল চ্যানেলে মার্চেন্ট রেফারেন্স ও ব্যাচ আইডি প্রদান করুন।"
    ),
    ("bn", "agent", "phishing_or_social_engineering"): (
        "সন্দেহজনক কার্যকলাপের রিপোর্ট লগ করা হয়েছে। ফ্রড রিস্ক টিম অফিসিয়াল চ্যানেলে "
        "ফলো-আপ করবে। সন্দেহজনক যোগাযোগে সাড়া দেবেন না।"
    ),
    ("bn", "agent", "other"): (
        "টিকিট লগ করা হয়েছে। অফিসিয়াল চ্যানেলে লেনদেন আইডি, পরিমাণ ও সংক্ষিপ্ত বিবরণ "
        "প্রদান করুন। কাস্টমারের শংসাপত্র অনুরোধ বা শেয়ার করবেন না।"
    ),
}


# Action-text templates — short, operationally useful, always safe.
ACTION_TEMPLATES: dict[str, str] = {
    "wrong_transfer": (
        "Verify {tx} details with the customer and initiate the wrong-transfer "
        "dispute workflow per policy."
    ),
    "wrong_transfer_inconsistent": (
        "Flag for human review. Verify with the customer whether this was genuinely "
        "a wrong transfer given the established transaction pattern with this recipient."
    ),
    "payment_failed": (
        "Investigate {tx} ledger status. If balance was deducted on a failed payment, "
        "initiate the automatic reversal flow within standard SLA."
    ),
    "refund_request": (
        "Inform the customer that refund eligibility depends on the merchant's own "
        "policy. Provide guidance on contacting the merchant directly for a refund."
    ),
    "duplicate_payment": (
        "Verify the duplicate with payments_ops. If the biller confirms only one "
        "payment was received, initiate reversal of {tx}."
    ),
    "phishing": (
        "Escalate to fraud_risk team immediately. Confirm to customer that the company "
        "never asks for OTP. Log the reported number for fraud pattern analysis."
    ),
    "phishing_or_social_engineering": (
        "Escalate to fraud_risk team immediately. Confirm to customer that the company "
        "never asks for OTP. Log the reported number for fraud pattern analysis."
    ),
    "phishing_injection": (
        "Bypass LLM, route ticket to security team, and log sender's metadata for "
        "fraud review."
    ),
    "merchant_settlement_delay": (
        "Route to merchant_operations to verify settlement batch status. If the batch "
        "is delayed, communicate a revised ETA to the merchant."
    ),
    "agent_cash_in_issue": (
        "Investigate {tx} pending status with agent operations. Confirm settlement "
        "state and resolve within the standard cash-in SLA."
    ),
    "ambiguous_match": (
        "Reply to customer asking for the disambiguating detail (recipient or "
        "transaction reference). Do not initiate dispute until the transaction is confirmed."
    ),
    "vague_complaint": (
        "Reply to customer asking for specific details: which transaction, what "
        "amount, what went wrong, and approximate time."
    ),
    "other_low": (
        "Reply to customer asking for the transaction ID, amount, and a short "
        "description of what went wrong."
    ),
}


def pick_template(
    language: str,
    user_type: str,
    case_type: str,
    tx_id: Optional[str],
) -> str:
    """Render a template reply, with safe fallbacks at every level."""
    lang = language if language in ("en", "bn", "mixed") else "en"
    # Mixed always falls back to English (no mixed templates today) — PRD §8.1.
    if lang == "mixed":
        lang = "en"

    ut = user_type if user_type in ("customer", "merchant", "agent") else "customer"
    ct = case_type if case_type in {ct.value for ct in CaseTypeEnum} else "other"

    key = (lang, ut, ct)
    template = TEMPLATES.get(key)
    if template is None:
        # Try same case_type with user_type=customer first, then en/customer/other.
        template = TEMPLATES.get((lang, "customer", ct))
    if template is None:
        template = TEMPLATES.get(("en", ut, ct))
    if template is None:
        template = TEMPLATES[("en", "customer", "other")]

    return template.format(tx=tx_id if tx_id else "")


def pick_action(case_type: str, variant: str = "default", tx_id: Optional[str] = None) -> str:
    """Render an action text. `variant` selects between normal / inconsistent /
    ambiguous / vague keys.
    """
    key = case_type if variant == "default" else f"{case_type}_{variant}"
    # Map the long enum value to the short action key when applicable.
    aliases = {"phishing_or_social_engineering": "phishing"}
    canonical = aliases.get(case_type, case_type)
    canonical_key = canonical if variant == "default" else f"{canonical}_{variant}"
    template = (
        ACTION_TEMPLATES.get(key)
        or ACTION_TEMPLATES.get(canonical_key)
        or ACTION_TEMPLATES.get(case_type)
        or ACTION_TEMPLATES.get(canonical)
        or ACTION_TEMPLATES["other_low"]
    )
    return template.format(tx=tx_id if tx_id else "")