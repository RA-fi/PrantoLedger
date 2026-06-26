# Deployment guide

This document describes the three supported deployment paths for
**PrantoLedger**: a local Docker container, a GitHub Actions CI pipeline, and a
one-click Railway deploy.

---

## 1. Local — Docker (port `8080`)

The image is `python:3.11-slim` based, runs as a non-root user, and serves both
the API and the static frontend.

```bash
# 1. Build the image
docker build -t prantoledger:dev .

# 2. Run it on port 8080
docker run --rm -p 8080:8080 \
  -e GROQ_API_KEYS="sk-or-..." \
  --name prantoledger \
  prantoledger:dev

# 3. Verify
curl http://localhost:8080/health
open http://localhost:8080/          # static frontend
curl -X POST http://localhost:8080/analyze-ticket \
  -H 'Content-Type: application/json' \
  -d @samples/sample_01.json
```

Useful env vars (see `.env.example` for the full list):

| Variable          | Default | Purpose                                      |
|-------------------|---------|----------------------------------------------|
| `PORT`            | `8080`  | Uvicorn bind port                            |
| `DB_PATH`         | `data/prantoledger.db` | SQLite file (mounted volume in production) |
| `GROQ_API_KEYS`   | _empty_ | Comma-separated rotating key pool (optional)  |
| `GROQ_MODEL`      | `llama-3.3-70b-versatile` | LLM model name (optional)             |
| `ENABLE_LLM`      | `auto`  | `auto` (only if keys present), `on`, or `off`|
| `LOG_LEVEL`       | `INFO`  | `DEBUG` / `INFO` / `WARNING` / `ERROR`       |

---

## 2. GitHub Actions CI

`.github/workflows/ci.yml` runs on every push and pull request to `main` /
`master`. It:

1. Sets up Python `3.11` and `3.12` in a matrix.
2. Installs pinned dependencies from `requirements.txt`.
3. Runs `pytest -q` (deterministic — no LLM key required).
4. Re-generates the samples and refreshes `samples/INDEX.md`.

Add the badge to your `README.md`:

```markdown
![CI](https://github.com/<you>/<repo>/actions/workflows/ci.yml/badge.svg)
```

---

## 3. Railway (one-click)

Two files make Railway happy out of the box:

- `railway.json` — healthcheck + start command
- `nixpacks.toml` — pinned Python 3.11 + install/start commands

### One-click deploy

1. Push the repo to GitHub.
2. In Railway, click **New Project → Deploy from GitHub repo**.
3. Pick this repository. Railway will detect `railway.json` and use
   Nixpacks as the builder.
4. Open the **Variables** tab and (optionally) set:
   - `GROQ_API_KEYS` — comma-separated list of Groq keys (rotating pool).
   - `GROQ_MODEL` — defaults to `llama-3.3-70b-versatile`.
   - `PORT` — leave blank; Railway injects its own (Railway will fall back to
     our `8080` default).
5. Wait for the build to finish, then open the generated URL.

### Healthcheck

Railway will hit `/health` every 30s; if the service returns non-200 three
times in a row, the deploy is marked unhealthy.

### Persistent storage (optional)

SQLite is the system-of-record for the demo. For Railway, attach a **Volume**
and set `DB_PATH=/data/prantoledger.db`.

---

## 4. Frontend

The static frontend lives in `frontend/` and is served from FastAPI's
`StaticFiles` mount at `/static/`, with `GET /` returning `index.html`. No
build step, no bundler — vanilla HTML/CSS/JS only. The theme toggle
(dark/light) writes `prantoledger.theme` to `localStorage` and respects
`prefers-color-scheme` on first load.

---

## 5. Troubleshooting

| Symptom                                  | Likely cause                          | Fix                                                |
|------------------------------------------|---------------------------------------|----------------------------------------------------|
| `/health` returns 503                    | DB file unwritable                   | Set `DB_PATH` to a writable directory              |
| `/analyze-ticket` returns 422            | Schema validation                    | Inspect `error.detail`                             |
| `/analyze-ticket` is slow (~3.5s)        | LLM polish enabled                   | Drop `GROQ_API_KEYS` to disable the polish layer   |
| Frontend loads but styles are missing    | `frontend/` missing from image       | Confirm `COPY frontend ./frontend` in Dockerfile   |
| Railway: "Application failed to start"   | PORT misconfigured                   | Ensure Railway injects `PORT` or set it to `8080`  |

