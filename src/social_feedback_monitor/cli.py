from __future__ import annotations

import argparse
import asyncio
import random
import time
from datetime import datetime
from pathlib import Path

from .analyzer import analyze_item
from .config import DEFAULT_CONFIG, load_config
from .importer import import_csv
from .models import FeedbackItem
from .screenshots import capture_url, safe_filename
from .search_urls import build_search_urls
from .storage import FeedbackStore


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "data" / "feedback.sqlite3"
DEFAULT_OUTPUT = ROOT / "outputs" / f"feedback_{datetime.now().strftime('%Y%m%d')}.xlsx"
DEFAULT_SCREENSHOT_DIR = ROOT / "screenshots"
DEFAULT_AUTH_DIR = ROOT / "auth"
DEFAULT_DIAGNOSTICS_DIR = ROOT / "diagnostics"
DEFAULT_LOG_DIR = ROOT / "logs"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="小红书/抖音反馈监控 MVP 工具")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="关键词与分类配置 YAML")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite 数据库路径")

    sub = parser.add_subparsers(dest="command", required=True)

    import_cmd = sub.add_parser("import-csv", help="导入 CSV 明细并写入本地库")
    import_cmd.add_argument("--input", required=True, help="CSV 文件路径")

    add_cmd = sub.add_parser("add", help="添加单条主帖或评论")
    add_cmd.add_argument("--item-type", choices=["post", "comment"], default="post")
    add_cmd.add_argument("--platform", required=True, help="xiaohongshu 或 douyin")
    add_cmd.add_argument("--keyword", default="")
    add_cmd.add_argument("--text", required=True)
    add_cmd.add_argument("--url", default="")
    add_cmd.add_argument("--published-at", default="")
    add_cmd.add_argument("--author", default="")
    add_cmd.add_argument("--parent-url", default="")

    export_cmd = sub.add_parser("export", help="导出 Excel")
    export_cmd.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Excel 输出路径")

    shot_cmd = sub.add_parser("screenshot", help="为库内未截图主帖抓页面截图")
    shot_cmd.add_argument("--limit", type=int, default=10)
    shot_cmd.add_argument("--output-dir", default=str(DEFAULT_SCREENSHOT_DIR))
    shot_cmd.add_argument("--storage-state", default="", help="Playwright 登录态 JSON，可选")

    search_cmd = sub.add_parser("search-urls", help="打印关键词对应的平台搜索入口")
    search_cmd.add_argument("--keyword", default="", help="为空则使用配置中的全部关键词")

    login_cmd = sub.add_parser("login", help="打开浏览器登录平台并保存登录态")
    login_cmd.add_argument("--platform", choices=["xiaohongshu"], required=True)
    login_cmd.add_argument("--storage-state", default="", help="登录态保存路径，默认 auth/xiaohongshu.json")

    collect_cmd = sub.add_parser("collect", help="使用浏览器自动采集平台搜索页内容")
    collect_cmd.add_argument("--platform", choices=["xiaohongshu"], required=True)
    collect_cmd.add_argument("--keyword", required=True)
    collect_cmd.add_argument("--max-items", type=int, default=30)
    collect_cmd.add_argument("--scrolls", type=int, default=6)
    collect_cmd.add_argument("--headless", action="store_true", help="无头浏览器模式，平台风控较严时不建议开启")
    collect_cmd.add_argument("--storage-state", default="", help="登录态路径，默认 auth/xiaohongshu.json")
    collect_cmd.add_argument("--export", action="store_true", help="采集后自动导出 Excel")
    collect_cmd.add_argument("--output", default=str(DEFAULT_OUTPUT), help="配合 --export 使用的 Excel 输出路径")
    collect_cmd.add_argument("--min-delay-ms", type=int, default=1800, help="每次动作后的最小随机等待毫秒数")
    collect_cmd.add_argument("--max-delay-ms", type=int, default=4200, help="每次动作后的最大随机等待毫秒数")
    collect_cmd.add_argument("--diagnostics-dir", default=str(DEFAULT_DIAGNOSTICS_DIR), help="失败或空结果时保存 HTML/截图的目录")
    collect_cmd.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR), help="采集日志目录")
    collect_cmd.add_argument("--no-manual-pause", action="store_true", help="检测到登录/验证文案时不暂停等待人工处理")

    batch_cmd = sub.add_parser("collect-batch", help="按多个关键词分批采集，关键词之间随机休息")
    batch_cmd.add_argument("--platform", choices=["xiaohongshu"], required=True)
    batch_cmd.add_argument("--keywords", nargs="*", default=[], help="不填则使用配置文件里的全部关键词")
    batch_cmd.add_argument("--max-items-per-keyword", type=int, default=30)
    batch_cmd.add_argument("--scrolls", type=int, default=6)
    batch_cmd.add_argument("--headless", action="store_true", help="无头浏览器模式，平台风控较严时不建议开启")
    batch_cmd.add_argument("--storage-state", default="", help="登录态路径，默认 auth/xiaohongshu.json")
    batch_cmd.add_argument("--export", action="store_true", help="全部关键词采集后自动导出 Excel")
    batch_cmd.add_argument("--output", default=str(DEFAULT_OUTPUT), help="配合 --export 使用的 Excel 输出路径")
    batch_cmd.add_argument("--min-delay-ms", type=int, default=1800, help="每次动作后的最小随机等待毫秒数")
    batch_cmd.add_argument("--max-delay-ms", type=int, default=4200, help="每次动作后的最大随机等待毫秒数")
    batch_cmd.add_argument("--rest-min-seconds", type=int, default=30, help="关键词之间最短休息秒数")
    batch_cmd.add_argument("--rest-max-seconds", type=int, default=60, help="关键词之间最长休息秒数")
    batch_cmd.add_argument("--diagnostics-dir", default=str(DEFAULT_DIAGNOSTICS_DIR), help="失败或空结果时保存 HTML/截图的目录")
    batch_cmd.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR), help="采集日志目录")
    batch_cmd.add_argument("--no-manual-pause", action="store_true", help="检测到登录/验证文案时不暂停等待人工处理")
    batch_cmd.add_argument("--stop-on-error", action="store_true", help="某个关键词失败时停止整个批次")

    diagnose_cmd = sub.add_parser("diagnose-xhs-parser", help="用本地 HTML 测试小红书搜索页解析器")
    diagnose_cmd.add_argument("--html", required=True)
    diagnose_cmd.add_argument("--keyword", default="面对面红包")
    diagnose_cmd.add_argument("--max-items", type=int, default=30)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = load_config(args.config)
    store = FeedbackStore(args.db)

    try:
        if args.command == "import-csv":
            items = import_csv(args.input, config)
            inserted, skipped = store.upsert_items(items)
            print(f"导入完成：新增 {inserted} 条，重复跳过 {skipped} 条。")
            return 0

        if args.command == "add":
            item = FeedbackItem(
                item_type=args.item_type,
                platform=args.platform,
                keyword=args.keyword,
                text=args.text,
                url=args.url,
                published_at=args.published_at,
                author=args.author,
                parent_url=args.parent_url,
            )
            from .keyword_filter import match_keywords

            if not match_keywords(item.text, config):
                print("添加失败：文本未通过取词过滤规则，不会入库。")
                return 1
            inserted, skipped = store.upsert_items([analyze_item(item, config)])
            print(f"添加完成：新增 {inserted} 条，重复跳过 {skipped} 条。")
            return 0

        if args.command == "export":
            from .exporter import export_excel

            output = export_excel(store.fetch_all(), args.output)
            print(f"Excel 已导出：{output}")
            return 0

        if args.command == "screenshot":
            asyncio.run(_capture_missing_screenshots(store, args.limit, Path(args.output_dir), args.storage_state or None))
            return 0

        if args.command == "search-urls":
            keywords = [args.keyword] if args.keyword else config.keywords
            for keyword in keywords:
                print(f"\n关键词：{keyword}")
                for platform, url in build_search_urls(keyword).items():
                    print(f"  {platform}: {url}")
            return 0

        if args.command == "login":
            if args.platform == "xiaohongshu":
                from .xiaohongshu_browser import login_xiaohongshu

                storage_state = Path(args.storage_state) if args.storage_state else DEFAULT_AUTH_DIR / "xiaohongshu.json"
                saved = asyncio.run(login_xiaohongshu(storage_state))
                print(f"登录态已保存：{saved}")
                return 0

        if args.command == "collect":
            if args.platform == "xiaohongshu":
                from .xiaohongshu_browser import collect_xiaohongshu_search

                storage_state = Path(args.storage_state) if args.storage_state else DEFAULT_AUTH_DIR / "xiaohongshu.json"
                items = asyncio.run(
                    collect_xiaohongshu_search(
                        keyword=args.keyword,
                        config=config,
                        storage_state_path=storage_state,
                        max_items=args.max_items,
                        scrolls=args.scrolls,
                        headless=args.headless,
                        min_delay_ms=args.min_delay_ms,
                        max_delay_ms=args.max_delay_ms,
                        diagnostics_dir=Path(args.diagnostics_dir) if args.diagnostics_dir else None,
                        log_dir=Path(args.log_dir) if args.log_dir else None,
                        manual_pause=not args.no_manual_pause,
                    )
                )
                inserted, skipped = store.upsert_items(items)
                print(f"采集完成：发现 {len(items)} 条，新增 {inserted} 条，重复跳过 {skipped} 条。")
                if args.export:
                    from .exporter import export_excel

                    output = export_excel(store.fetch_all(), args.output)
                    print(f"Excel 已导出：{output}")
                return 0

        if args.command == "collect-batch":
            if args.platform == "xiaohongshu":
                from .xiaohongshu_browser import collect_xiaohongshu_search

                storage_state = Path(args.storage_state) if args.storage_state else DEFAULT_AUTH_DIR / "xiaohongshu.json"
                keywords = args.keywords or config.keywords
                diagnostics_dir = Path(args.diagnostics_dir) if args.diagnostics_dir else None
                log_dir = Path(args.log_dir) if args.log_dir else None
                total_found = 0
                total_inserted = 0
                total_skipped = 0
                failed: list[tuple[str, str]] = []

                if not keywords:
                    print("没有关键词。请在 config/keywords.yaml 配置，或使用 --keywords 指定。")
                    return 1

                _append_run_log(log_dir, f"批量采集开始 platform=xiaohongshu keywords={keywords}")
                for index, keyword in enumerate(keywords, start=1):
                    print(f"\n开始关键词 {index}/{len(keywords)}：{keyword}")
                    try:
                        items = asyncio.run(
                            collect_xiaohongshu_search(
                                keyword=keyword,
                                config=config,
                                storage_state_path=storage_state,
                                max_items=args.max_items_per_keyword,
                                scrolls=args.scrolls,
                                headless=args.headless,
                                min_delay_ms=args.min_delay_ms,
                                max_delay_ms=args.max_delay_ms,
                                diagnostics_dir=diagnostics_dir,
                                log_dir=log_dir,
                                manual_pause=not args.no_manual_pause,
                            )
                        )
                        inserted, skipped = store.upsert_items(items)
                        total_found += len(items)
                        total_inserted += inserted
                        total_skipped += skipped
                        msg = f"关键词完成 keyword={keyword} found={len(items)} inserted={inserted} skipped={skipped}"
                        print(msg)
                        _append_run_log(log_dir, msg)
                    except Exception as exc:  # noqa: BLE001
                        reason = repr(exc)
                        failed.append((keyword, reason))
                        msg = f"关键词失败 keyword={keyword} error={reason}"
                        print(msg)
                        _append_run_log(log_dir, msg)
                        if args.stop_on_error:
                            break

                    if index < len(keywords):
                        rest_min = max(args.rest_min_seconds, 0)
                        rest_max = max(args.rest_max_seconds, rest_min)
                        rest_seconds = random.randint(rest_min, rest_max)
                        print(f"关键词之间休息 {rest_seconds} 秒。")
                        _append_run_log(log_dir, f"关键词间休息 seconds={rest_seconds}")
                        time.sleep(rest_seconds)

                print(
                    f"\n批量采集完成：发现 {total_found} 条，新增 {total_inserted} 条，"
                    f"重复跳过 {total_skipped} 条，失败 {len(failed)} 个关键词。"
                )
                if failed:
                    for keyword, reason in failed:
                        print(f"- 失败关键词：{keyword}，原因：{reason}")
                _append_run_log(
                    log_dir,
                    f"批量采集结束 found={total_found} inserted={total_inserted} skipped={total_skipped} failed={len(failed)}",
                )

                if args.export:
                    from .exporter import export_excel

                    output = export_excel(store.fetch_all(), args.output)
                    print(f"Excel 已导出：{output}")
                return 0 if not failed else 2

        if args.command == "diagnose-xhs-parser":
            from .xiaohongshu_browser import diagnose_xiaohongshu_parser

            items = asyncio.run(
                diagnose_xiaohongshu_parser(
                    html_path=Path(args.html),
                    config=config,
                    keyword=args.keyword,
                    max_items=args.max_items,
                )
            )
            for item in items:
                print(f"- [{item.sentiment}/{item.category}] {item.text[:80]} -> {item.url}")
            print(f"解析完成：{len(items)} 条。")
            return 0

    finally:
        store.close()

    return 1


async def _capture_missing_screenshots(
    store: FeedbackStore,
    limit: int,
    output_dir: Path,
    storage_state: str | None,
) -> None:
    rows = store.fetch_posts_without_screenshot(limit)
    if not rows:
        print("没有需要截图的主帖。")
        return

    for row in rows:
        filename = safe_filename(f"{row['platform']}_{row['id']}_{row['keyword']}", f"item_{row['id']}") + ".png"
        output_path = output_dir / filename
        try:
            await capture_url(row["url"], output_path, storage_state)
            store.update_screenshot(row["id"], str(output_path))
            print(f"截图成功：{row['id']} -> {output_path}")
        except Exception as exc:  # noqa: BLE001
            print(f"截图失败：{row['id']} {row['url']}，原因：{exc}")


def _append_run_log(log_dir: Path | None, message: str) -> None:
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {message}"
    if not log_dir:
        return
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"collector_{datetime.now().strftime('%Y%m%d')}.log"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
