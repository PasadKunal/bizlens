"""Capture dashboard screenshots for the README using headless Chromium.

Run with the dashboard serving on http://127.0.0.1:8050::

    python -m bizlens.dashboard.app &          # (or `make dashboard`)
    python scripts/capture_screenshots.py

Writes PNGs into docs/screenshots/.
"""
from __future__ import annotations

import time
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8050/"
OUT = Path("docs/screenshots")
NL_QUESTION = "how much money did we make each day recently"


def _wait_for_plotly(page, expected: int = 3) -> None:
    page.wait_for_selector(".js-plotly-plot .main-svg", timeout=30_000)
    # Give every chart time to finish its entrance transition.
    for _ in range(30):
        if page.eval_on_selector_all(".js-plotly-plot", "els => els.length") >= expected:
            break
        time.sleep(0.3)
    time.sleep(1.5)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900}, device_scale_factor=2)
        page.goto(URL, wait_until="networkidle")
        _wait_for_plotly(page)

        # 1. Full dashboard (hero).
        page.screenshot(path=str(OUT / "dashboard.png"), full_page=True)

        # 2. Retention heatmap close-up (3rd Plotly graph: trend, retention, funnel).
        page.locator(".js-plotly-plot").nth(1).screenshot(path=str(OUT / "retention.png"))

        # 3. NL-to-SQL: type a reworded question and capture the returned SQL.
        page.fill("#nl-input", NL_QUESTION)
        page.wait_for_function(
            "() => { const el = document.querySelector('#nl-output');"
            " return el && el.textContent.includes('SELECT'); }",
            timeout=15_000,
        )
        time.sleep(0.5)
        page.locator("#nl-section").scroll_into_view_if_needed()
        page.locator("#nl-section").screenshot(path=str(OUT / "nl_to_sql.png"))

        browser.close()
    print("saved:", *[p.name for p in sorted(OUT.glob("*.png"))])


if __name__ == "__main__":
    main()
