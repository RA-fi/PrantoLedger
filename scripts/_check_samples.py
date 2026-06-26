import json, os
os.chdir(r"D:\prantoledger")
for i in range(1, 11):
    path = f"samples/sample_{i:02d}.json"
    try:
        s = json.load(open(path, encoding="utf-8"))
        req = s.get("request", {})
        exp = s.get("expected_output", {})
        print(f"\n--- sample_{i:02d} ---")
        print(f"  ticket_id        : {req.get('ticket_id')}")
        print(f"  history tx_ids   : {[t.get('transaction_id') for t in req.get('transaction_history') or []]}")
        print(f"  expected tx_id   : {exp.get('relevant_transaction_id')}")
        print(f"  expected verdict : {exp.get('evidence_verdict')}")
        print(f"  expected case    : {exp.get('case_type')}")
        print(f"  expected severity: {exp.get('severity')}")
        print(f"  expected dept    : {exp.get('department')}")
    except Exception as e:
        print(f"  sample_{i:02d}: ERROR {e}")