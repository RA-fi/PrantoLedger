"""Reproduce all four synthetic-audit failures."""
import json
import urllib.request
import urllib.error

URL = "http://localhost:8080/analyze-ticket"

def post(body):
    req = urllib.request.Request(
        URL, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {"_raw": str(e)}

cases = [
    ("PAYMENT_FAILED_SYNTH",
     {"ticket_id":"TKT-D-PF","complaint":"recharge fail hoyeche",
      "transaction_history":[{"transaction_id":"TXN-D1","timestamp":"2026-06-01T10:00:00Z",
                              "transaction_type":"payment","amount":500,"currency":"BDT","status":"failed"}]}),
    ("AGENT_CASH_IN_SYNTH",
     {"ticket_id":"TKT-D-ACI","complaint":"agent cash in pending",
      "transaction_history":[{"transaction_id":"TXN-ACI","timestamp":"2026-06-01T09:00:00Z",
                              "transaction_type":"cash_in","amount":2000,"currency":"BDT","status":"pending",
                              "counterparty":"AGENT-318"}]}),
    ("MERCHANT_SETTLEMENT_SYNTH",
     {"ticket_id":"TKT-D-MSD","complaint":"merchant settlement pending","user_type":"merchant",
      "transaction_history":[{"transaction_id":"TXN-MSD","timestamp":"2026-06-01T18:00:00Z",
                              "transaction_type":"settlement","amount":15000,"currency":"BDT","status":"pending",
                              "counterparty":"MERCHANT-SELF"}]}),
    ("INCONSISTENT_SYNTH",
     {"ticket_id":"TKT-HR-1","complaint":"I sent 2000 taka to the wrong number yesterday. Please reverse immediately.",
      "transaction_history":[
          {"transaction_id":"TXN-A","timestamp":"2025-01-01T10:00:00Z",
           "transaction_type":"transfer","amount":2000,"currency":"BDT","status":"completed","counterparty":"01711111111"},
          {"transaction_id":"TXN-B","timestamp":"2025-01-01T11:00:00Z",
           "transaction_type":"transfer","amount":2000,"currency":"BDT","status":"completed","counterparty":"01711111111"},
      ]}),
]

for name, body in cases:
    code, resp = post(body)
    print(f"\n=== {name} -> {code}")
    print(json.dumps(resp, indent=2)[:600])