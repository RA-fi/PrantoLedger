/* PrantoLedger frontend — small SPA glue.
 * - Wires the form to POST /analyze-ticket
 * - Loads the 10 PRD §16 sample cases into quick-load buttons
 * - Manages dark/light theme via localStorage + the data-theme attribute
 * - Renders the structured verdict into the right-hand panel
 */
(function () {
  "use strict";

  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  // ---------------------------------------------------------------------
  // Theme handling
  // ---------------------------------------------------------------------
  const THEME_KEY = "prantoledger.theme";
  const root = document.documentElement;

  function applyTheme(theme) {
    root.setAttribute("data-theme", theme);
    const icon = $("[data-theme-icon]");
    const label = $(".theme-label");
    if (icon) icon.textContent = theme === "dark" ? "☀" : "☾";
    if (label) label.textContent = theme === "dark" ? "Light" : "Dark";
    const btn = $("#theme-toggle");
    if (btn) btn.setAttribute("aria-pressed", String(theme === "light"));
  }

  function initTheme() {
    let saved = null;
    try {
      saved = localStorage.getItem(THEME_KEY);
    } catch (_) {
      /* localStorage can throw in privacy modes — ignore. */
    }
    if (saved !== "dark" && saved !== "light") {
      saved = window.matchMedia &&
        window.matchMedia("(prefers-color-scheme: light)").matches
        ? "light"
        : "dark";
    }
    applyTheme(saved);
  }

  $("#theme-toggle").addEventListener("click", () => {
    const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    applyTheme(next);
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch (_) {
      /* ignore */
    }
  });

  // ---------------------------------------------------------------------
  // Transaction-history repeater
  // ---------------------------------------------------------------------
  const txnList = $("#txn-list");
  const txnTpl = $("#txn-template");

  function addTxnRow(initial) {
    const node = txnTpl.content.firstElementChild.cloneNode(true);
    if (initial) {
      node.querySelector(".txn-id").value = initial.transaction_id || "";
      node.querySelector(".txn-amount").value =
        initial.amount !== undefined && initial.amount !== null
          ? initial.amount
          : "";
      node.querySelector(".txn-type").value = initial.type || "transfer";
      node.querySelector(".txn-status").value = initial.status || "completed";
      node.querySelector(".txn-cp").value = initial.counterparty || "";
      const tsEl = node.querySelector(".txn-ts");
      if (initial.timestamp) {
        tsEl.value = isoToLocalInput(initial.timestamp);
      } else {
        tsEl.value = nowLocalInput();
      }
    } else {
      node.querySelector(".txn-ts").value = nowLocalInput();
    }
    node.querySelector(".txn-remove").addEventListener("click", () => {
      node.remove();
    });
    txnList.appendChild(node);
  }

  function pad2(n) {
    return String(n).padStart(2, "0");
  }

  function nowLocalInput() {
    const d = new Date();
    return (
      d.getFullYear() +
      "-" +
      pad2(d.getMonth() + 1) +
      "-" +
      pad2(d.getDate()) +
      "T" +
      pad2(d.getHours()) +
      ":" +
      pad2(d.getMinutes()) +
      ":" +
      pad2(d.getSeconds())
    );
  }

  function isoToLocalInput(iso) {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return "";
    return (
      d.getFullYear() +
      "-" +
      pad2(d.getMonth() + 1) +
      "-" +
      pad2(d.getDate()) +
      "T" +
      pad2(d.getHours()) +
      ":" +
      pad2(d.getMinutes()) +
      ":" +
      pad2(d.getSeconds())
    );
  }

  function localInputToIso(local) {
    if (!local) return null;
    const d = new Date(local);
    if (isNaN(d.getTime())) return null;
    return d.toISOString();
  }

  $("#add-txn").addEventListener("click", () => addTxnRow());

  function readTxns() {
    return $$(".txn-row", txnList)
      .map((row) => {
        const local = row.querySelector(".txn-ts").value;
        const iso = localInputToIso(local);
        const obj = {
          transaction_id: row.querySelector(".txn-id").value.trim(),
          type: row.querySelector(".txn-type").value,
          amount: parseFloat(row.querySelector(".txn-amount").value),
          counterparty: row.querySelector(".txn-cp").value.trim(),
          status: row.querySelector(".txn-status").value,
        };
        if (iso) obj.timestamp = iso;
        return obj;
      })
      .filter((t) => t.transaction_id);
  }

  // ---------------------------------------------------------------------
  // Quick-load sample buttons
  // ---------------------------------------------------------------------
  function renderQuickLoad() {
    const grid = $("#quick-load-grid");
    const samples = window.PRANTOLEDGER_SAMPLES || [];
    grid.innerHTML = "";
    samples.forEach((s) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "btn btn-ghost";
      b.setAttribute("role", "listitem");
      b.dataset.sampleId = s.id;
      b.innerHTML = `<strong>${s.id}</strong><br/><span class="muted small">${s.label}</span>`;
      b.addEventListener("click", () => loadSample(s));
      grid.appendChild(b);
    });
  }

  function loadSample(s) {
    $("#ticket_id").value = s.ticket_id;
    $("#language").value = s.language || "";
    $("#channel").value = s.channel || "";
    $("#user_type").value = s.user_type || "customer";
    $("#complaint").value = s.complaint;
    txnList.innerHTML = "";
    (s.transaction_history || []).forEach(addTxnRow);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  // ---------------------------------------------------------------------
  // Form submission
  // ---------------------------------------------------------------------
  let lastPayload = null;

  function setStatus(kind, text) {
    const el = $("#status-line");
    if (!text) {
      el.hidden = true;
      el.textContent = "";
      el.className = "status-line";
      return;
    }
    el.hidden = false;
    el.textContent = text;
    el.className = "status-line " + kind;
  }

  function clearResult() {
    $("#result").hidden = true;
    $("#empty-state").hidden = false;
    $("#verdict-sub").textContent =
      "Submit a ticket to see routing, severity, and a safe reply.";
  }

  function badge(text, cls) {
    return `<span class="badge ${cls || ""}">${text}</span>`;
  }

  // Update an existing badge element in place: replace its text and class list
  // (idempotent — safe to call repeatedly, no outerHTML mutation needed).
  function setBadge(id, text, cls) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = text;
    el.className = "badge " + (cls || "");
  }

  function renderResult(r) {
    $("#empty-state").hidden = true;
    $("#result").hidden = false;

    $("#r-ticket").textContent = r.ticket_id || "—";
    $("#r-tx").textContent = r.relevant_transaction_id || "—";

    // Pull amount + counterparty from the most recent submitted payload.
    // The backend only echoes back transaction IDs, so we resolve them
    // against the form data we already sent.
    const txns = (lastPayload && lastPayload.transaction_history) || [];
    const matched = txns.find(
      (t) =>
        r.relevant_transaction_id &&
        t.transaction_id === r.relevant_transaction_id
    );
    if (matched) {
      const amt =
        typeof matched.amount === "number"
          ? matched.amount.toLocaleString(undefined, {
              minimumFractionDigits: 0,
              maximumFractionDigits: 2,
            })
          : "—";
      $("#r-amount").textContent = `${amt} BDT`;
      $("#r-cp").textContent = matched.counterparty || "—";
    } else {
      $("#r-amount").textContent = "—";
      $("#r-cp").textContent = "—";
    }

    setBadge(
      "r-verdict",
      r.evidence_verdict || "—",
      "verdict-" + (r.evidence_verdict || "default")
    );
    setBadge(
      "r-case",
      r.case_type || "—",
      "case-" + (r.case_type || "default")
    );
    setBadge(
      "r-severity",
      r.severity || "—",
      "severity-" + (r.severity || "default")
    );
    setBadge("r-dept", r.department || "—", "dept-default");
    setBadge(
      "r-review",
      r.human_review_required ? "yes" : "no",
      "human_review-" + (r.human_review_required ? "yes" : "no")
    );
    $("#r-confidence").textContent =
      r.confidence !== undefined && r.confidence !== null
        ? Number(r.confidence).toFixed(2)
        : "—";

    $("#r-agent-summary").textContent = r.agent_summary || "";
    $("#r-action").textContent = r.recommended_next_action || "";
    $("#r-reply").textContent = r.customer_reply || "";

    const ul = $("#r-codes");
    ul.innerHTML = "";
    (r.reason_codes || []).forEach((c) => {
      const li = document.createElement("li");
      li.textContent = c;
      ul.appendChild(li);
    });

    $("#r-raw").textContent = JSON.stringify(r, null, 2);
  }

  $("#ticket-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    setStatus(null);
    clearResult();

    const payload = {
      ticket_id: $("#ticket_id").value.trim(),
      complaint: $("#complaint").value.trim(),
    };
    const lang = $("#language").value;
    const ch = $("#channel").value;
    const ut = $("#user_type").value;
    if (lang) payload.language = lang;
    if (ch) payload.channel = ch;
    if (ut) payload.user_type = ut;

    const txns = readTxns();
    if (txns.length) payload.transaction_history = txns;

    if (!payload.ticket_id || !payload.complaint) {
      setStatus("err", "Ticket ID and Complaint are required.");
      return;
    }

    const missingTs = (payload.transaction_history || []).find(
      (t) => !t.timestamp
    );
    if (missingTs) {
      setStatus(
        "err",
        `Transaction ${missingTs.transaction_id} is missing a timestamp.`
      );
      return;
    }

    const btn = $("#submit");
    btn.disabled = true;
    btn.textContent = "Analyzing…";
    lastPayload = payload;
    try {
      const res = await fetch("/analyze-ticket", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = await res.json().catch(() => ({}));
      if (res.status >= 200 && res.status < 300) {
        setStatus("ok", `Analyzed in ${res.headers.get("X-Latency-Ms") || "—"} ms`);
        renderResult(body);
        $("#verdict-sub").textContent =
          "Routing, severity, and safe reply — all deterministic unless the LLM polish layer is enabled.";
      } else {
        const detail = (body && body.error) || body || "Unknown error";
        const msg =
          typeof detail === "string"
            ? detail
            : detail.message || JSON.stringify(detail);
        setStatus("err", `HTTP ${res.status} — ${msg}`);
      }
    } catch (e) {
      setStatus("err", "Network error: " + (e && e.message ? e.message : e));
    } finally {
      btn.disabled = false;
      btn.textContent = "Analyze ticket";
    }
  });

  $("#reset").addEventListener("click", () => {
    setStatus(null);
    clearResult();
    txnList.innerHTML = "";
  });

  // ---------------------------------------------------------------------
  // Bootstrap
  // ---------------------------------------------------------------------
  initTheme();
  renderQuickLoad();
  fetch("/health")
    .then((r) => (r.ok ? r.json() : null))
    .then((j) => {
      if (j && j.version) $("#app-version").textContent = j.version;
    })
    .catch(() => {
      /* offline or proxy weirdness — fine */
    });
})();
