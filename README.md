# PrantoLedger — Internal SupportOps Copilot

A small, CPU-only FastAPI service that ingests **one customer complaint + a
transaction-history snippet** and returns a **structured JSON verdict**:
which transaction (if any) is relevant, what the evidence says, what type of
case this is, who should handle it, how urgent it is, and a **safe** reply
that never asks for credentials and never promises a refund it cannot
authorise.

Built for the SUST CSE Carnival 2026 hackathon — Online Preliminary
(QueueStorm Investigator problem statement).

> **Positioning:** internal **copilot** for support agents. **Never** an
> autonomous financial decision maker. When evidence is unclear, the service
> says so — it does not guess.

[![CI](https://img.shields.io/badge/CI-GitHub_Actions-2f6bff?logo=githubactions&logoColor=white)](./.github/workflows/ci.yml)
[![Deploy on Railway](https://img.shields.io/badge/Deploy_on-Railway-0B0D0E?logo=railway&logoColor=white)](https://railway.app/new/template)
[![Python 3.11](https://img.shields.io/badge/python-3.11%20%7C%203.12-3776AB?logo=python&logoColor=white)](./requirements.txt)

---

## 1. Quick start (local Python)

```bash
# 1. Install pinned dependencies
python -m pip install -r requirements.txt

# 2. (Optional) enable LLM polish — see "AI usage" below
cp .env.example .env
# ...edit .env and paste a Groq key into GROQ_API_KEYS=...

# 3. Run the service (port 8080)
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Then open:

| URL                                  | What it serves                              |
|--------------------------------------|---------------------------------------------|
| <http://localhost:8080/>             | Static frontend console (dark/light theme)  |
| <http://localhost:8080/docs>         | Swagger UI                                  |
| <http://localhost:8080/health>       | Health + LLM pool stats                     |
| <http://localhost:8080/analyze-ticket> | `POST` endpoint (see §4)                   |

## 1.1. Sample round-trips

A complete catalogue of live request → response pairs lives in
[`samples/`](samples/) — every public case from PRD §16 plus seven
adversarial / edge-case round-trips (prompt injection, phishing in EN + BN,
malformed payload, bad enum, reversed history, Banglish). Start at
[`samples/INDEX.md`](samples/INDEX.md) for a one-line routing summary of
every file. To regenerate the whole folder deterministically:

```bash
python scripts/generate_samples.py
```

The service stores its SQLite audit log at `./data/auditor.db` (override with
`AUDIT_DB_PATH`). Open `http://localhost:8080/docs` for the auto-generated
Swagger UI.

## 2. Quick start (Docker)

```bash
docker build -t prantoledger .
docker run --rm -p 8080:8080 \
    -e GROQ_API_KEYS=key1,key2,key3 \
    -v "$(pwd)/data:/app/data" \
    prantoledger
```

The entrypoint hardens the SQLite file to mode `600` on every start. The
image also bundles the static frontend under `/app/frontend/` and serves it
from `/` + `/static/`.

## 2.1 Frontend

The bundled console at `http://localhost:8080/` lets you:

* Pick any of the 10 PRD §16 sample cases (one click fills the form).
* Edit ticket metadata + transaction history inline.
* Switch the theme between **dark** and **light** (persisted in
  `localStorage`; respects `prefers-color-scheme` on first load).
* POST to `/analyze-ticket` and see the structured verdict — case type,
  severity, department, evidence verdict, agent summary, recommended next
  action, safe customer reply, and reason codes.

The frontend is plain HTML / CSS / vanilla JS (no bundler, no dependencies).
Files live in [`frontend/`](frontend/).

## 3. Running the test suite

```bash
python -m pytest tests/ -v
```

The suite covers all 10 public sample cases from
`docs/SUST_Preli_Sample_Cases.json` plus the safety short-circuit tests
(prompt injection, phishing in English + Bangla, refund-promise blocking,
credential-request blocking).

## 4. HTTP contract

### `GET /health`

```json
{
  "status": "ok",
  "version": "1.0.0",
  "llm_pool": { "size": 3, "ready": 3, "used_in_window": 12 }
}
```

### `POST /analyze-ticket`

**Request** (only `ticket_id` + `complaint` are mandatory):

```json
{
  "ticket_id": "TKT-001",
  "complaint": "I sent 5000 taka to the wrong number. Please return my money.",
  "language": "en",
  "channel": "in_app_chat",
  "user_type": "customer",
  "transaction_history": [
    {
      "transaction_id": "TXN-9101",
      "timestamp": "2026-04-14T14:05:00Z",
      "type": "transfer",
      "amount": 5000,
      "counterparty": "+8801719876543",
      "status": "completed"
    }
  ]
}
```

**Response** (real example from the live service):

```json
{
  "ticket_id": "TKT-001",
  "relevant_transaction_id": "TXN-9101",
  "evidence_verdict": "consistent",
  "case_type": "wrong_transfer",
  "severity": "high",
  "department": "dispute_resolution",
  "agent_summary": "Wrong-transfer claim confirmed against transaction TXN-9101. Dispute initiated to the dispute resolution team.",
  "recommended_next_action": "Verify TXN-9101 details with the customer and initiate the wrong-transfer dispute workflow per policy.",
  "customer_reply": "We have noted your concern about transaction TXN-9101. Please do not share your PIN or OTP with anyone. Our dispute team will review the case and contact you through official support channels.",
  "human_review_required": true,
  "confidence": 0.9,
  "reason_codes": ["wrong_transfer", "tx_match", "dispute_initiated"]
}
```

A full verified request/response is in `samples/sample_output.json`.

## 5. How the pipeline works

```
            POST /analyze-ticket
                    │
        ┌───────────▼────────────┐
   1.   │ Pre-LLM injection scan │  short-circuit to fraud_risk payload
        └───────────┬────────────┘
                    │
        ┌───────────▼────────────┐
   2.   │ Phishing keyword scan  │  critical → fraud_risk, no LLM
        └───────────┬────────────┘
                    │
        ┌───────────▼────────────┐
   3.   │ Deterministic auditor  │  pure stdlib rule engine (PRD §7)
        │  amount, wrong/refund, │
        │  duplicate, settlement │
        └───────────┬────────────┘
                    │
        ┌───────────▼────────────┐
   4.   │ Classifier             │  AuditResult → Decision
        └───────────┬────────────┘
                    │
        ┌───────────▼────────────┐
   5.   │ Multilingual template  │  always-safe customer_reply + action
        └───────────┬────────────┘
                    │
        ┌───────────▼────────────┐
   6.   │ Optional LLM polish    │  Groq rotating key pool (PRD §10)
        └───────────┬────────────┘
                    │
        ┌───────────▼────────────┐
   7.   │ Post-LLM sanitizer     │  block PIN/OTP, refund-promise,
        │                        │  unofficial-channel language
        └───────────┬────────────┘
                    │
        ┌───────────▼────────────┐
   8.   │ SQLite audit log +     │  best-effort, never blocks the
        │   decision cache       │  response
        └───────────┬────────────┘
                    │
              JSON response
```

All **categorical decisions** (case_type / severity / department / routing /
human_review / confidence) are made in **pure Python** before any LLM call.
The LLM is used only to lightly paraphrase an already-safe template.

## 6. MODELS section (mandatory for the hackathon submission)

The service uses **one external AI model**, optionally, only for templated
paraphrasing of the customer reply. All routing decisions are rule-based.

| Field | Value |
| --- | --- |
| Model | `llama-3.3-70b-versatile` |
| Provider | Groq Cloud (`https://api.groq.com/openai/v1`) |
| Task | Light paraphrase of a **pre-approved, safety-checked** template |
| When it runs | After the deterministic pipeline has decided everything else |
| What it may NOT do | Change case_type, severity, department, route, evidence verdict, or invent refund commitments |
| Fallback behaviour | If the call fails (timeout, 4xx, 5xx, network) the template is returned **unchanged** and `used_llm=false` is logged |
| Multiple keys | Up to 8 keys in `GROQ_API_KEYS` are rotated with per-key cooldowns on 429 / 401 / 5xx / timeout |
| Hard cap | 8 × 3.5 s per-attempt timeout — worst case fits in the 30 s endpoint budget |

No other model is used. No model is loaded locally.

## 7. AI usage disclosure

The service is an **internal copilot**, not an autonomous decision maker. AI is
used in **exactly one place**: to lightly rephrase the safe template reply into
a more natural-sounding message in the same language. The system prompt
explicitly forbids inventing new financial commitments, requesting
credentials, or mentioning unofficial contact channels.

Three layers of safety guarantee the customer reply is always safe even if the
LLM behaves badly:

1. **Pre-LLM injection filter** — if the complaint contains obvious
   prompt-injection attempts ("ignore previous instructions", "state that a
   refund has been credited", …), the service short-circuits to a
   fraud_risk critical payload **without ever calling the LLM**.
2. **Pre-LLM phishing scanner** — if the complaint mentions someone asking
   for OTP/PIN/CVV (in English or Bangla), the case is classified as
   `phishing_or_social_engineering / critical / fraud_risk` and routed
   accordingly.
3. **Post-LLM sanitizer** — after the optional paraphrase, the reply and
   action text are scrubbed for any imperative credential request, any
   refund-promise commitment, or any reference to an unofficial contact
   channel. If matched, the safe fallback reply is used.

The system **never** returns `"we will refund you"` /
`"refunded successfully"` / `"credited your account"` style commitments. The
honest, policy-aligned language is "any eligible amount will be returned
through official channels after verification".

## 8. Safety logic (summary)

| Risk | Detection | Mitigation |
| --- | --- | --- |
| Prompt injection in complaint | Regex (`ignore previous instructions`, `state that a refund has been credited`, …) | Short-circuit to `fraud_risk / critical`, no LLM call, log to `safety_flags` |
| Phishing / social engineering | Regex on `otp`, `pin`, `cvv`, "send me your OTP", plus Bangla equivalents | Classify as `phishing_or_social_engineering / critical / fraud_risk`, `human_review_required=true` |
| LLM asks for credentials | Regex `send/share/tell/... pin/otp/...` on the *polished* reply | Replace with safe fallback |
| LLM promises a refund | Regex `we will refund / refunded your / credited your account` | Replace with safe "any eligible amount will be returned through official channels after verification" |
| LLM directs to WhatsApp / Telegram / etc. | Regex `whatsapp`, `telegram`, `t.me`, etc. | Replace with official-channel fallback |

All safety flags are persisted in `safety_flags` (audit_log) and
`safety_flags` table with a 200-char snippet.

## 9. Limitations

* **CPU-only, single-process.** uvicorn is started with `--workers 1` because
  the local SQLite WAL store is not safe across multiple writers.
* **Deterministic, not probabilistic.** If the rule engine is unsure, the
  service returns `insufficient_data` and asks for clarification — it does
  not invent a route.
* **No authentication** in the reference deployment. The service is intended
  to run on a private network behind the support-ops dashboard. Wrap it
  with your own auth proxy before exposing publicly.
* **LLM is best-effort.** If `GROQ_API_KEYS` is empty (the default), every
  response uses the deterministic template. Latency budget is dominated by
  template rendering in this mode (< 50 ms typical).
* **No persistent state** beyond SQLite. Cached responses are kept for the
  life of the DB file; clear with `rm data/auditor.db`.

## 10. File layout

```
prantoledger/
├── app/
│   ├── __init__.py
│   ├── main.py              FastAPI orchestrator + error handlers + static frontend mount
│   ├── schemas.py           Pydantic v2 request/response enums
│   ├── core/
│   │   ├── auditor.py       Deterministic rule engine (PRD §7)
│   │   ├── classifier.py    AuditResult → Decision
│   │   ├── language.py      en/bn/mixed + Bangla digit normalisation
│   │   ├── llm.py           Optional Groq wrapper + rotating key pool
│   │   ├── safety.py        3-layer safety (PRD §9)
│   │   └── templates.py     Multilingual reply/action templates
│   └── db/
│       └── sqlite_store.py  Audit log + decision cache + safety flags
├── data/                    SQLite DB lives here (auto-created)
├── docs/
│   ├── PRD.md
│   ├── DEPLOYMENT.md        Local Docker + GitHub Actions + Railway
│   └── SUST_Preli_Sample_Cases.json
├── frontend/
│   ├── index.html           Static SPA shell (dark/light theme toggle)
│   ├── styles.css           CSS-variables themed, responsive
│   ├── app.js               Fetch + render verdict
│   └── samples.js           10 PRD §16 sample cases for quick-load
├── samples/
│   ├── sample_NN.json       Verified request/response pairs
│   ├── edge_*.json          Adversarial / edge-case round-trips
│   └── INDEX.md             One-line routing summary of every file
├── tests/
│   ├── test_auditor.py      10 public sample cases + health
│   ├── test_safety.py       Injection, phishing, refund, credential
│   └── test_frontend.py     Smoke test for / and /static/*
├── scripts/
│   ├── generate_samples.py
│   ├── write_sample_index.py
│   └── routing_summary.py
├── .github/
│   └── workflows/
│       └── ci.yml           pytest on Python 3.11 + 3.12
├── Dockerfile
├── railway.json             Railway deploy config
├── nixpacks.toml            Nixpacks (Python 3.11 pin)
├── requirements.txt
├── .env.example
└── README.md
```

## 11. Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `GROQ_API_KEYS` | _(empty)_ | Comma-separated list of Groq keys for the rotating pool. Supports `alias=value` form. |
| `GROQ_API_KEY` | _(empty)_ | Fallback single key (used only if `GROQ_API_KEYS` is empty). |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Model name sent to the Groq API. |
| `GROQ_TIMEOUT_S` | `3.5` | Per-attempt timeout in seconds. |
| `AUDIT_DB_PATH` | `./data/auditor.db` | Path to the SQLite audit database. |
| `HOST` | `0.0.0.0` | Bind host. |
| `PORT` | `8080` | Bind port. Railway injects its own at runtime. |
| `LOG_LEVEL` | `INFO` | Standard Python logging level. |

---

## 12. Deployment & CI

* **Docker** — `docker build` then `docker run -p 8080:8080 …` (see §2).
* **GitHub Actions** — `.github/workflows/ci.yml` runs `pytest -q` on
  Python 3.11 + 3.12 for every push and pull request.
* **Railway** — `railway.json` + `nixpacks.toml` ship a one-click deploy.
  Set `GROQ_API_KEYS` in the **Variables** tab, attach a **Volume** at
  `/data` for the SQLite file, and Railway will hit `/health` automatically.
  See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for the full guide.

---

## 12. License & attribution

Built for the SUST CSE Carnival 2026 — Codex Community Hackathon — Online
Preliminary. All code in this repository is original. See `docs/PRD.md` for
the full problem statement and `docs/SUST_Preli_Sample_Cases.json` for the
public sample-case pack.
