"""Debug why §9.4/§7/§8 tests return None body."""
import json, urllib.request, urllib.error

URL = "http://localhost:8080/analyze-ticket"

def post(body, raw=None):
    data = raw if raw is not None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(URL, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        body_bytes = e.read()
        try:
            return e.code, json.loads(body_bytes)
        except Exception:
            return e.code, {"_raw": body_bytes[:300].decode("utf-8", "replace")}

# HR inconsistent test
code, body = post({
    "ticket_id": "TKT-HR-1",
    "complaint": "I sent 2000 taka to the wrong number yesterday. Please reverse immediately.",
    "transaction_history": [
        {"transaction_id": "TXN-A", "timestamp": "2025-01-01T10:00:00Z", "transaction_type": "transfer", "amount": 2000, "currency": "BDT", "status": "completed", "counterparty": "01711111111"},
        {"transaction_id": "TXN-B", "timestamp": "2025-01-01T11:00:00Z", "transaction_type": "transfer", "amount": 2000, "currency": "BDT", "status": "completed", "counterparty": "01711111111"},
    ],
})
print(f"HR-1 inconsistent: code={code} body={body}")

# payment_failed detector
code, body = post({"ticket_id": "TKT-D-PF", "complaint": "recharge fail hoyeche", "transaction_history": [
    {"transaction_id": "TXN-D1", "timestamp": "2025-06-01T10:00:00Z", "transaction_type": "payment", "amount": 500, "currency": "BDT", "status": "failed"}
]})
print(f"D-PF: code={code} body={body}")

# duplicate
code, body = post({"ticket_id": "TKT-D-DUP", "complaint": "bills deducted twice", "transaction_history": [
    {"transaction_id": "TXN-DUP1", "timestamp": "2025-06-01T10:00:00Z", "transaction_type": "payment", "amount": 850, "currency": "BDT", "status": "completed"},
    {"transaction_id": "TXN-DUP2", "timestamp": "2025-06-01T10:00:12Z", "transaction_type": "payment", "amount": 850, "currency": "BDT", "status": "completed"},
]})
print(f"D-DUP: code={code} body={body}")
