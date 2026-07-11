"""Web-link extraction via Playwright (scope §3).

Renders JavaScript pages before extraction. Point-in-time snapshot; re-ingestion is
required for updates. Password-protected pages are not accessible.
"""

from __future__ import annotations

from app.ingestion.types import Block, ExtractResult


def extract_web(url: str) -> ExtractResult:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)
        title = page.title()
        # innerText yields rendered, visible text without markup.
        text = page.eval_on_selector("body", "el => el.innerText") or ""
        browser.close()

    blocks: list[Block] = []
    if title:
        blocks.append(Block(text=title, heading_path=[title]))
    for para in [t.strip() for t in text.split("\n") if t.strip()]:
        blocks.append(Block(text=para, heading_path=[title] if title else []))

    return ExtractResult(
        fmt="web",
        method="Playwright (JS rendered, point-in-time snapshot)",
        confidence=0.95,
        low_confidence=False,
        blocks=blocks,
    )
