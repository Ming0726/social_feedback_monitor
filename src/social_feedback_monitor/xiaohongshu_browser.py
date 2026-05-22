from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from .analyzer import analyze_item
from .config import MonitorConfig
from .models import FeedbackItem


XHS_HOME_URL = "https://www.xiaohongshu.com"
XHS_SEARCH_URL = "https://www.xiaohongshu.com/search_result?keyword={keyword}"


@dataclass(frozen=True)
class BrowserCollectOptions:
    max_items: int = 30
    scrolls: int = 6
    headless: bool = False
    min_delay_ms: int = 1800
    max_delay_ms: int = 4200
    diagnostics_dir: Path | None = None
    log_dir: Path | None = None
    manual_pause: bool = True


async def login_xiaohongshu(storage_state_path: Path) -> Path:
    from playwright.async_api import async_playwright

    storage_state_path.parent.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1400, "height": 900},
            locale="zh-CN",
        )
        page = await context.new_page()
        await page.goto(XHS_HOME_URL, wait_until="domcontentloaded", timeout=60000)
        print("浏览器已打开。请在页面里完成小红书登录。")
        print("登录完成后回到这个终端按 Enter，我会保存登录态。")
        await asyncio.to_thread(input)
        await context.storage_state(path=str(storage_state_path))
        await browser.close()
    return storage_state_path


async def collect_xiaohongshu_search(
    keyword: str,
    config: MonitorConfig,
    storage_state_path: Path,
    max_items: int = 30,
    scrolls: int = 6,
    headless: bool = False,
    min_delay_ms: int = 1800,
    max_delay_ms: int = 4200,
    diagnostics_dir: Path | None = None,
    log_dir: Path | None = None,
    manual_pause: bool = True,
) -> list[FeedbackItem]:
    from playwright.async_api import async_playwright

    options = BrowserCollectOptions(
        max_items=max_items,
        scrolls=scrolls,
        headless=headless,
        min_delay_ms=min_delay_ms,
        max_delay_ms=max_delay_ms,
        diagnostics_dir=diagnostics_dir,
        log_dir=log_dir,
        manual_pause=manual_pause,
    )
    url = XHS_SEARCH_URL.format(keyword=quote(keyword))
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context_kwargs = {
            "viewport": {"width": 1400, "height": 900},
            "locale": "zh-CN",
        }
        if storage_state_path.exists():
            context_kwargs["storage_state"] = str(storage_state_path)
        else:
            print(f"未找到登录态：{storage_state_path}")
            print("如果页面要求登录，请先运行：python main.py login --platform xiaohongshu")

        context = await browser.new_context(**context_kwargs)
        page = await context.new_page()
        _log(options, f"开始采集小红书搜索页 keyword={keyword} url={url}")

        try:
            print(f"正在打开小红书搜索页：{keyword}")
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await _random_wait(page, options)

            blocked = await _handle_possible_manual_step(page, options)
            if blocked:
                await _save_diagnostics(page, options, keyword, "manual_check")

            for index in range(max(scrolls, 0)):
                await page.mouse.wheel(0, random.randint(800, 1700))
                await _random_wait(page, options)
                print(f"滚动加载：{index + 1}/{scrolls}")

            raw_items = await _extract_search_items(page, max_items=max_items)
            _log(options, f"页面解析完成 keyword={keyword} raw_items={len(raw_items)}")
            if not raw_items:
                await _save_diagnostics(page, options, keyword, "empty_result")
        except Exception as exc:
            _log(options, f"采集异常 keyword={keyword} error={exc!r}")
            await _save_diagnostics(page, options, keyword, "error")
            raise
        finally:
            await browser.close()

    items: list[FeedbackItem] = []
    for raw in raw_items:
        text = _clean_text(raw.get("text", ""))
        item_url = raw.get("url", "")
        if not text or not item_url:
            continue
        item = FeedbackItem(
            item_type="post",
            platform="xiaohongshu",
            keyword=keyword,
            text=text,
            url=item_url,
            author=_clean_text(raw.get("author", "")),
            likes_count=_parse_count(raw.get("likes_count", "")),
        )
        items.append(analyze_item(item, config))

    return _dedupe_items(items)[:max_items]


async def diagnose_xiaohongshu_parser(
    html_path: Path,
    config: MonitorConfig,
    keyword: str,
    max_items: int = 30,
) -> list[FeedbackItem]:
    from playwright.async_api import async_playwright

    html = html_path.read_text(encoding="utf-8")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(html, wait_until="domcontentloaded")
        raw_items = await _extract_search_items(page, max_items=max_items)
        await browser.close()

    items: list[FeedbackItem] = []
    for raw in raw_items:
        item = FeedbackItem(
            item_type="post",
            platform="xiaohongshu",
            keyword=keyword,
            text=_clean_text(raw.get("text", "")),
            url=raw.get("url", ""),
            author=_clean_text(raw.get("author", "")),
            likes_count=_parse_count(raw.get("likes_count", "")),
        )
        items.append(analyze_item(item, config))
    return _dedupe_items(items)[:max_items]


async def _handle_possible_manual_step(page, options: BrowserCollectOptions) -> bool:
    text = await page.locator("body").inner_text(timeout=10000)
    markers = [
        "登录",
        "请先登录",
        "登录后查看",
        "验证码",
        "验证",
        "安全验证",
        "扫码",
        "访问频繁",
        "操作频繁",
        "请稍后",
    ]
    if any(marker in text for marker in markers):
        _log(options, "检测到页面可能需要登录或验证")
        print("页面可能需要登录或验证。")
        if options.manual_pause:
            print("请在浏览器里处理完成；如果页面已正常显示搜索结果，也可以直接按 Enter 继续。")
            await asyncio.to_thread(input)
        else:
            print("当前禁用了人工暂停，本次会继续尝试解析。")
        await page.wait_for_timeout(2000)
        return True
    return False


async def _extract_search_items(page, max_items: int) -> list[dict[str, str]]:
    return await page.evaluate(
        """
        (maxItems) => {
          const normalizeUrl = (href) => {
            try {
              const base = window.location.origin && window.location.origin !== "null"
                ? window.location.origin
                : "https://www.xiaohongshu.com";
              const url = new URL(href, base);
              url.hash = "";
              return url.toString();
            } catch (_) {
              return "";
            }
          };

          const closestCard = (node) => {
            const bySelector = node.closest("section, li, [class*=note], [class*=card], [class*=item]");
            if (bySelector) {
              return bySelector;
            }
            let current = node;
            for (let i = 0; i < 8 && current; i += 1) {
              const text = (current.innerText || "").trim();
              if (text.length >= 4 && text.length <= 1200) {
                return current;
              }
              current = current.parentElement;
            }
            return node.parentElement || node;
          };

          const anchors = Array.from(document.querySelectorAll("a[href]"));
          const results = [];
          const seen = new Set();
          for (const anchor of anchors) {
            const href = anchor.getAttribute("href") || "";
            if (!href.includes("/explore/") && !href.includes("/discovery/item/")) {
              continue;
            }
            const url = normalizeUrl(href);
            if (!url || seen.has(url)) {
              continue;
            }
            const card = closestCard(anchor);
            const text = (card.innerText || anchor.innerText || "").trim();
            if (!text || text.length < 4) {
              continue;
            }
            const authorNode = card.querySelector(".author, .name, .user-name, [class*=author], [class*=name]");
            const likeNode = card.querySelector(".like-wrapper, .count, [class*=like], [class*=count]");
            results.push({
              url,
              text,
              author: authorNode ? authorNode.innerText.trim() : "",
              likes_count: likeNode ? likeNode.innerText.trim() : "",
            });
            seen.add(url);
            if (results.length >= maxItems) {
              break;
            }
          }
          return results;
        }
        """,
        max_items,
    )


def _clean_text(value: str) -> str:
    lines = [" ".join(line.split()) for line in (value or "").splitlines()]
    useful = [line for line in lines if line]
    return "\n".join(useful).strip()


def _parse_count(value: str) -> int | None:
    value = (value or "").strip().replace(",", "")
    if not value:
        return None
    try:
        if "万" in value:
            return int(float(value.replace("万", "")) * 10000)
        digits = "".join(ch for ch in value if ch.isdigit())
        return int(digits) if digits else None
    except ValueError:
        return None


def _dedupe_items(items: list[FeedbackItem]) -> list[FeedbackItem]:
    result: list[FeedbackItem] = []
    seen = set()
    for item in items:
        key = item.fingerprint()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


async def _random_wait(page, options: BrowserCollectOptions) -> None:
    min_delay = max(options.min_delay_ms, 0)
    max_delay = max(options.max_delay_ms, min_delay)
    await page.wait_for_timeout(random.randint(min_delay, max_delay))


async def _save_diagnostics(page, options: BrowserCollectOptions, keyword: str, reason: str) -> None:
    if not options.diagnostics_dir:
        return

    options.diagnostics_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_keyword = "".join(ch if ch.isalnum() else "_" for ch in keyword)[:40] or "keyword"
    base = options.diagnostics_dir / f"xhs_{safe_keyword}_{reason}_{stamp}"
    html_path = base.with_suffix(".html")
    png_path = base.with_suffix(".png")

    try:
        html_path.write_text(await page.content(), encoding="utf-8")
        await page.screenshot(path=str(png_path), full_page=True)
        _log(options, f"已保存诊断现场 html={html_path} screenshot={png_path}")
        print(f"已保存诊断现场：{html_path} 和 {png_path}")
    except Exception as exc:  # noqa: BLE001
        _log(options, f"保存诊断现场失败 error={exc!r}")


def _log(options: BrowserCollectOptions, message: str) -> None:
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {message}"
    print(line)
    if not options.log_dir:
        return
    options.log_dir.mkdir(parents=True, exist_ok=True)
    log_path = options.log_dir / f"collector_{datetime.now().strftime('%Y%m%d')}.log"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
