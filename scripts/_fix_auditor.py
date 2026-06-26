"""Replace tx.type.value with tx.transaction_type.value (and same for status)."""
import re
path = r"D:\prantoledger\app\core\auditor.py"
with open(path, encoding="utf-8") as f:
    src = f.read()
new = src
# tx.type.value (the old schema) -> tx.transaction_type.value (PRD §6.2)
new = re.sub(r"\btx\.type\b", "tx.transaction_type", new)
new = re.sub(r"\btx\.status\b", "tx.status", new)  # status field unchanged
# Also fix the counterparty uppercase check (still works since .upper() exists)
with open(path, "w", encoding="utf-8") as f:
    f.write(new)
print("done; counts:", src.count("tx.type"), "->", new.count("tx.type"), "remaining tx.type")
print("transaction_type:", new.count("tx.transaction_type"))