import sqlite3, os
DB = os.getenv("AUDIT_DB_PATH", "data/auditor.db")
c = sqlite3.connect(DB)
print("DB:", DB)
for tbl in ("audit_log", "decision_cache", "safety_flags"):
    try:
        cols = [r[1] for r in c.execute(f"PRAGMA table_info({tbl})")]
        print(f"{tbl}: {cols}")
    except Exception as e:
        print(f"{tbl}: ERROR {e}")
print("row counts:")
for tbl in ("audit_log", "decision_cache", "safety_flags"):
    n = c.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
    print(f"  {tbl} = {n}")