from __future__ import annotations

from urllib.parse import quote


def build_search_urls(keyword: str) -> dict[str, str]:
    encoded = quote(keyword)
    return {
        "xiaohongshu": f"https://www.xiaohongshu.com/search_result?keyword={encoded}",
        "douyin": f"https://www.douyin.com/search/{encoded}",
    }
