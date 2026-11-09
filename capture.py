# /// script
# requires-python = ">=3.14"
# dependencies = ["playwright>=1.49"]
# ///
"""Capture 4 presentation screenshots of the running app into screenshots/.

    uv run uvicorn app.main:app          # in one terminal (Ollama running for shot 2)
    uv run capture.py                    # in another

Inline metadata above lets `uv run` fetch Playwright in an isolated environment, leaving the app's
dependencies untouched. It drives an installed Chrome or Edge, so no browser download is needed
(falls back to Playwright's Chromium: `uv run --with playwright playwright install chromium`).
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from playwright.async_api import Browser, Page, Playwright, async_playwright

BASE = os.environ.get("TITANIC_URL", "http://127.0.0.1:8000")
OUT = Path(__file__).resolve().parent / "screenshots"
VIEWPORT = {"width": 1440, "height": 900}
QUESTION = "How many women were on board?"


async def launch(p: Playwright) -> Browser:
    for channel in ("chrome", "msedge", None):
        try:
            return await p.chromium.launch(channel=channel) if channel else await p.chromium.launch()
        except Exception as exc:  # channel not installed: try the next one
            last = exc
    raise SystemExit(f"No Chromium-based browser found: {last}")


async def new_page(browser: Browser, errors: list[str]) -> Page:
    ctx = await browser.new_context(viewport=VIEWPORT, device_scale_factor=2)
    page = await ctx.new_page()
    page.on("pageerror", lambda e: errors.append(str(e)))
    return page


async def hide_chrome(page: Page) -> None:
    """Hide the floating sound toggle and toasts so they don't sit on top of the content."""
    await page.add_style_tag(content=".sound-toggle, .toast { display: none !important; }")


async def shot_home(browser: Browser, errors: list[str]) -> Path:
    page = await new_page(browser, errors)
    await page.goto(f"{BASE}/")
    await page.wait_for_timeout(7000)  # fog rolls away, title lands, ship emerges
    await hide_chrome(page)
    path = OUT / "1-home.png"
    await page.screenshot(path=path)
    await page.context.close()
    return path


async def shot_telegraphist(browser: Browser, errors: list[str]) -> Path:
    page = await new_page(browser, errors)
    await page.goto(f"{BASE}/telegraphist")
    await page.wait_for_selector('.lamp:not([data-state="checking"])')
    if await page.get_attribute(".lamp", "data-state") != "online":
        print("  ! Ollama looks offline: the screenshot will show the LINE CUT reply")
    # the buttons rock at sea forever, so they're never "stable": force the click
    await page.get_by_role("button", name=QUESTION).click(force=True)
    await page.wait_for_selector(".telegram.incoming:not(:has(.receiving))", timeout=180_000)
    await page.locator(".log").click(force=True)  # skip the typewriter
    await page.wait_for_function(
        "() => { const b = [...document.querySelectorAll('.telegram.incoming .slip-body')].pop();"
        " return b && !b.classList.contains('caret') && b.querySelector('.stop'); }",
        timeout=60_000,
    )
    await page.wait_for_timeout(800)
    await hide_chrome(page)
    path = OUT / "2-telegraphist.png"
    await page.locator(".wireless").screenshot(path=path)
    reply = await page.locator(".telegram.incoming .slip-body").last.inner_text()
    print(f"  Harold: {reply[:160]}")
    await page.context.close()
    return path


async def shot_regatta(browser: Browser, errors: list[str]) -> Path:
    page = await new_page(browser, errors)
    await page.goto(f"{BASE}/bridge")
    await page.locator(".regatta").scroll_into_view_if_needed()
    await page.wait_for_selector(".lane.winner.crowned", timeout=15_000)
    await page.wait_for_timeout(1300)  # crown lands, fireworks burst
    await hide_chrome(page)
    path = OUT / "3-regatta.png"
    await page.locator(".regatta").screenshot(path=path)
    await page.context.close()
    return path


async def shot_chart(browser: Browser, errors: list[str]) -> Path:
    page = await new_page(browser, errors)
    await page.goto(f"{BASE}/bridge")
    await page.wait_for_function("() => window.Plotly !== undefined", timeout=30_000)
    await page.fill("input[name=name]", "You")
    await page.locator(".board").click(force=True)
    await page.wait_for_selector("#scatter .main-svg", timeout=30_000)
    await page.wait_for_timeout(8500)  # let the gauge effects play out and recede
    await page.evaluate("document.querySelector('.telegram-pop').hidden = true")
    await hide_chrome(page)
    panel = page.locator(".chart-panel")
    await panel.scroll_into_view_if_needed()
    await page.wait_for_timeout(600)
    path = OUT / "4-chart.png"
    await panel.screenshot(path=path)
    prob = await page.locator(".readout .pct").inner_text()
    print(f"  Your survival odds on the gauge: {prob}%")
    await page.context.close()
    return path


async def main() -> None:
    OUT.mkdir(exist_ok=True)
    errors: list[str] = []
    async with async_playwright() as p:
        browser = await launch(p)
        for name, fn in [("home", shot_home), ("telegraphist", shot_telegraphist),
                         ("regatta", shot_regatta), ("chart", shot_chart)]:
            print(f"Capturing {name}...")
            path = await fn(browser, errors)
            print(f"  saved {path.relative_to(OUT.parent)}")
        await browser.close()
    if errors:
        print("Page errors:\n  " + "\n  ".join(errors))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
