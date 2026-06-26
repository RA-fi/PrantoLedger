"""Rewrite the §16 expected table + use encoding='utf-8'."""
import re
path = r"D:\prantoledger\scripts\_prd_audit.py"
with open(path, encoding="utf-8") as f:
    src = f.read()

new_block = '''expected = [
    ("TKT-001", "TXN-9101",  "consistent",      "wrong_transfer",                "high",   "dispute_resolution"),
    ("TKT-002", "TXN-9202",  "inconsistent",    "wrong_transfer",                "medium", "dispute_resolution"),
    ("TKT-003", "TXN-9301",  "consistent",      "payment_failed",                "high",   "payments_ops"),
    ("TKT-004", "TXN-9401",  "consistent",      "refund_request",                "low",    "customer_support"),
    ("TKT-005", None,        "insufficient_data","phishing_or_social_engineering","critical","fraud_risk"),
    ("TKT-006", None,        "insufficient_data","other",                        "low",    "customer_support"),
    ("TKT-007", "TXN-9701",  "consistent",      "agent_cash_in_issue",           "high",   "agent_operations"),
    ("TKT-008", None,        "insufficient_data","wrong_transfer",               "medium", "dispute_resolution"),
    ("TKT-009", "TXN-9901",  "consistent",      "merchant_settlement_delay",     "medium", "merchant_operations"),
    ("TKT-010", "TXN-10002", "consistent",      "duplicate_payment",             "high",   "payments_ops"),
]'''
src = re.sub(r'expected = \[.*?\n\]', new_block, src, count=1, flags=re.DOTALL)
src = src.replace(
    'json.load(open(f"samples/sample_{_sample_index(fn):02d}.json"))',
    'json.load(open(f"samples/sample_{_sample_index(fn):02d}.json", encoding="utf-8"))',
)
with open(path, "w", encoding="utf-8") as f:
    f.write(src)
print("OK; new expected table + utf-8 encoding applied")