"""Probe live behaviour for single-transfer wrong-transfer case."""
import json
import urllib.request

body = {
    "ticket_id": "TKT-X",
    "complaint": "I sent 5000 taka to a wrong number around 2pm today",
    "transaction_history": [
        {
            "transaction_id": "TXN-9101",
            "timestamp": "2026-04-14T08:00:00Z",
            "transaction_type": "transfer",
            "amount": 5000,
            "currency": "BDT",
            "status": "completed",
            "counterparty": "01711111111",
        }
    ],
}
req = urllib.request.Request(
    "http://localhost:8080/analyze-ticket",
    data=json.dumps(body).encode(),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req, timeout=10) as r:
    print("status:", r.status)
    print(json.dumps(json.loads(r.read()), indent=2)[:600])
