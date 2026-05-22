from __future__ import annotations

import re
from pathlib import Path


def safe_filename(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z._-]+", "_", value).strip("_")
    return cleaned[:80] or fallback


async def capture_url(url: str, output_path: Path, storage_state: str | None = None) -> Path:
    from playwright.async_api import async_playwright

    output_path.parent.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context_kwargs = {"viewport": {"width": 1400, "height": 900}}
        if storage_state:
            context_kwargs["storage_state"] = storage_state
        context = await browser.new_context(**context_kwargs)
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(2500)
        await page.screenshot(path=str(output_path), full_page=True)
        await browser.close()
    return output_path
