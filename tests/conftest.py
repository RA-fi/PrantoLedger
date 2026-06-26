"""Pytest session bootstrap.

Point the SQLite audit DB to a per-session temporary file *before* any test
imports ``app.main`` (and therefore triggers the FastAPI lifespan that opens
the DB). This isolates the suite from any stale ``data/auditor.db`` left over
from a previous run or local smoke test, which would otherwise leak cached
responses and make the ``test_sample_case`` assertions flaky.
"""

from __future__ import annotations

import os
import tempfile

_tmp_dir = tempfile.mkdtemp(prefix="prantoledger-session-")
os.environ["AUDIT_DB_PATH"] = os.path.join(_tmp_dir, "auditor.db")

# Guarantee no Groq key is loaded — tests must not hit the network.
os.environ.pop("GROQ_API_KEY", None)
os.environ.pop("GROQ_API_KEYS", None)
# Pin the port so any test that imports ``app.main.PORT`` sees the new value.
os.environ["PORT"] = "8080"