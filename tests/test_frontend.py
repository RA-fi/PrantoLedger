"""Smoke tests for the static frontend mount.

These tests do not require a browser; they only assert that FastAPI is serving
the frontend at `/` and the bundled assets at `/static/*`. They are intended
to fail loudly in CI if anyone forgets to include the `frontend/` directory in
the Docker image (or accidentally renames `index.html`).
"""

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_index_returns_html_with_title() -> None:
    """GET / returns 200 + text/html containing the brand name."""
    resp = client.get("/")
    assert resp.status_code == 200, resp.text
    ctype = resp.headers.get("content-type", "")
    assert ctype.startswith("text/html"), ctype
    assert "PrantoLedger" in resp.text
    assert 'id="theme-toggle"' in resp.text
    # The verdict card must surface amount + counterparty alongside the
    # existing badges (regression for "output response not show mount").
    for slot in ("r-amount", "r-cp", "r-tx"):
        assert f'id="{slot}"' in resp.text, slot


def test_static_assets_are_served() -> None:
    """Static CSS + JS bundles are reachable at /static/."""
    for path, expected_fragments in [
        ("/static/styles.css", ["data-theme", "--bg"]),
        ("/static/app.js", ["PRANTOLEDGER_SAMPLES", "analyze-ticket"]),
        ("/static/samples.js", ["SAMPLE-01", "SAMPLE-10"]),
    ]:
        resp = client.get(path)
        assert resp.status_code == 200, (path, resp.text)
        body = resp.text
        for frag in expected_fragments:
            assert frag in body, (path, frag)


def test_favicon_route_returns_a_png() -> None:
    """GET /favicon.ico returns a tiny PNG with the right media type."""
    resp = client.get("/favicon.ico")
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("image/png"), resp.headers
    # PNG magic header: 89 50 4E 47 0D 0A 1A 0A
    assert resp.content[:8] == b"\x89PNG\r\n\x1a\n", resp.content[:8]


def test_frontend_directory_is_present_on_disk() -> None:
    """Sanity check that the frontend bundle is actually shipped with the repo."""
    repo_root = Path(__file__).resolve().parent.parent
    frontend = repo_root / "frontend"
    assert frontend.is_dir(), frontend
    for name in ("index.html", "styles.css", "app.js", "samples.js"):
        assert (frontend / name).is_file(), name


def test_renderresult_uses_setbadge_not_outerhtml() -> None:
    """Regression guard: renderResult must update badges in place.

    The previous implementation called `.outerHTML = ...` on the verdict /
    case-type / severity / department / review `<strong id="r-...">` elements
    on every render. After the first render the new `<span>` had no `id`
    attribute, so the second submit threw
    `can't access property "outerHTML", $(...) is null`. The fix is a
    `setBadge(id, text, cls)` helper that mutates `textContent` + `className`
    in place. This test makes sure the regression cannot return silently.
    """
    js = (Path(__file__).resolve().parent.parent / "frontend" / "app.js").read_text(
        encoding="utf-8"
    )
    # Normalize whitespace so multi-line setBadge(...) calls still match.
    flat = " ".join(js.split())
    assert "function setBadge(" in js, "setBadge helper must be defined"
    for badge_id in (
        "r-verdict",
        "r-case",
        "r-severity",
        "r-dept",
        "r-review",
    ):
        # Each badge id must be updated via setBadge(...), not via outerHTML.
        assert (
            f'setBadge("{badge_id}"' in flat
            or f"setBadge('{badge_id}'" in flat
            or f'setBadge( "{badge_id}"' in flat
        ), f"expected setBadge(\"{badge_id}\", ...) in app.js"
    # None of the badge slots should still be mutated via outerHTML.
    for badge_id in (
        "r-verdict",
        "r-case",
        "r-severity",
        "r-dept",
        "r-review",
    ):
        assert f'$("#{badge_id}").outerHTML' not in js, (
            f"$('#{badge_id}').outerHTML is back — re-introduces the null-ref bug"
        )


def test_renderresult_shows_amount_and_counterparty() -> None:
    """Regression guard: verdict card must display amount + counterparty.

    The backend response only echoes transaction_id. The frontend now caches
    the submitted payload (`lastPayload`) and resolves the relevant txn to
    fill in the amount + counterparty slots. Both the slot ids and the
    resolver must remain in place.
    """
    js = (Path(__file__).resolve().parent.parent / "frontend" / "app.js").read_text(
        encoding="utf-8"
    )
    flat = " ".join(js.split())
    assert "let lastPayload" in js or "var lastPayload" in js, (
        "lastPayload cache must exist so renderResult can resolve txn details"
    )
    assert "r-amount" in js and "r-cp" in js, (
        "renderResult must write #r-amount and #r-cp"
    )
    assert "transaction_history" in js, (
        "renderResult must read transaction_history from the cached payload"
    )
