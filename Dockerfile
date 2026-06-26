# PrantoLedger — internal SupportOps copilot (PRD §4, §11.3).
#
# Single-stage, CPU-only, <500 MB target. Uses python:3.11-slim so we don't
# drag in a full Debian userland. The entrypoint hardens the SQLite DB mode
# (chmod 600) before starting uvicorn.

FROM python:3.11-slim AS base

# Quiet pip + disable bytecode writes (smaller image).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build-time deps for httpx (none on slim, but keep wheel + curl for HEALTHCHECK).
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first so the layer caches when source changes.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Bring in the application code.
COPY app ./app
COPY docs ./docs
COPY samples ./samples
COPY frontend ./frontend
COPY .env.example ./

# The audit DB lives in /app/data — make sure it exists and is writable by
# the unprivileged `app` user.
RUN mkdir -p /app/data \
 && useradd --create-home --shell /bin/bash app \
 && chown -R app:app /app

USER app
ENV AUDIT_DB_PATH=/app/data/auditor.db \
    HOST=0.0.0.0 \
    PORT=8080

EXPOSE 8080

# Pre-start chmod hardening — runs as `app` so it tightens its own DB file.
# ENTRYPOINT is a tiny shell script so we can run multiple steps before uvicorn.
RUN printf '#!/bin/sh\nset -e\nmkdir -p "$(dirname "$AUDIT_DB_PATH")"\nchmod 700 "$(dirname "$AUDIT_DB_PATH")"\n[ -f "$AUDIT_DB_PATH" ] && chmod 600 "$AUDIT_DB_PATH" || true\nexec "$@"\n' > /app/entrypoint.sh \
 && chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["/bin/sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port \"$PORT\" --workers 1"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8080/health || exit 1
