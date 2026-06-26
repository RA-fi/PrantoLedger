"""Quick CLI to print one-line routing summary for every sample."""
import glob
import json
import os
import sys

paths = sorted(glob.glob("D:/prantoledger/samples/sample_*.json")) + sorted(
    glob.glob("D:/prantoledger/samples/edge_*.json")
)
for p in paths:
    j = json.load(open(p, "r", encoding="utf-8"))
    r = j.get("response", {})
    if "case_type" in r:
        print(
            f"{os.path.basename(p):35s} {r.get('case_type',''):35s} "
            f"{r.get('severity',''):10s} {r.get('department','')}"
        )
    else:
        err = (r.get("error") or {}) if isinstance(r, dict) else {}
        print(f"{os.path.basename(p):35s} HTTP-error ({err.get('error','?')})")