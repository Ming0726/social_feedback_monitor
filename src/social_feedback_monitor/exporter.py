from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook


POST_COLUMNS = [
    "id",
    "platform",
    "keyword",
    "published_at",
    "captured_at",
    "text",
    "url",
    "screenshot_path",
    "likes_count",
    "comments_count",
    "sentiment",
    "category",
    "author",
]

COMMENT_COLUMNS = [
    "id",
    "platform",
    "keyword",
    "published_at",
    "captured_at",
    "text",
    "url",
    "parent_url",
    "likes_count",
    "sentiment",
    "category",
    "author",
]


def export_excel(rows: list, output_path: Path | str) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    dict_rows = [dict(row) for row in rows]
    posts = [row for row in dict_rows if row.get("item_type") == "post"]
    comments = [row for row in dict_rows if row.get("item_type") == "comment"]

    wb = Workbook()
    default = wb.active
    wb.remove(default)
    _write_sheet(wb, "主帖明细", POST_COLUMNS, posts)
    _write_sheet(wb, "评论明细", COMMENT_COLUMNS, comments)
    _write_sheet(wb, "每日统计", ["date", "platform", "keyword", "新增主帖数", "新增评论数", "正向数", "负向数", "中性数"], _daily_stats(dict_rows))
    _write_sheet(wb, "归因分析", ["问题类型", "出现次数", "平台分布", "典型原文"], _attribution_stats(dict_rows))
    _format_workbook(wb)
    wb.save(output)

    return output


def _daily_stats(rows: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str, str], list[dict]] = {}
    for row in rows:
        key = (str(row.get("captured_at", ""))[:10], row.get("platform", ""), row.get("keyword", ""))
        grouped.setdefault(key, []).append(row)

    result = []
    for (date, platform, keyword), group in grouped.items():
        result.append(
            {
                "date": date,
                "platform": platform,
                "keyword": keyword,
                "新增主帖数": sum(1 for row in group if row.get("item_type") == "post"),
                "新增评论数": sum(1 for row in group if row.get("item_type") == "comment"),
                "正向数": sum(1 for row in group if row.get("sentiment") == "正向"),
                "负向数": sum(1 for row in group if row.get("sentiment") == "负向"),
                "中性数": sum(1 for row in group if row.get("sentiment") == "中性"),
            }
        )
    return sorted(result, key=lambda item: (item["date"], item["platform"], item["keyword"]), reverse=True)


def _attribution_stats(rows: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row.get("category") or "其他", []).append(row)
    rows = []
    for category, group in grouped.items():
        platform_counts: dict[str, int] = {}
        for item in group:
            platform = item.get("platform", "")
            platform_counts[platform] = platform_counts.get(platform, 0) + 1
        example = sorted(group, key=lambda item: item.get("captured_at", ""), reverse=True)[0].get("text", "")
        rows.append(
            {
                "问题类型": category or "其他",
                "出现次数": len(group),
                "平台分布": "；".join(f"{k}:{v}" for k, v in platform_counts.items()),
                "典型原文": example,
            }
        )
    return sorted(rows, key=lambda item: item["出现次数"], reverse=True)


def _write_sheet(wb: Workbook, title: str, columns: list[str], rows: list[dict]) -> None:
    ws = wb.create_sheet(title=title)
    ws.append(columns)
    for row in rows:
        ws.append([row.get(column, "") for column in columns])


def _format_workbook(wb: Workbook) -> None:
    for worksheet in wb.worksheets:
        worksheet.freeze_panes = "A2"
        for column_cells in worksheet.columns:
            max_length = max(len(str(cell.value or "")) for cell in column_cells[:80])
            width = min(max(max_length + 2, 10), 60)
            worksheet.column_dimensions[column_cells[0].column_letter].width = width
