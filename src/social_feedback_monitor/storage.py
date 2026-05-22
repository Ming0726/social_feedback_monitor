from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from .models import FeedbackItem, now_iso


SCHEMA = """
CREATE TABLE IF NOT EXISTS feedback_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint TEXT NOT NULL UNIQUE,
    item_type TEXT NOT NULL,
    platform TEXT NOT NULL,
    keyword TEXT,
    text TEXT NOT NULL,
    url TEXT,
    published_at TEXT,
    author TEXT,
    likes_count INTEGER,
    comments_count INTEGER,
    parent_url TEXT,
    screenshot_path TEXT,
    sentiment TEXT,
    category TEXT,
    matched_keyword TEXT,
    feedback_category TEXT,
    mentioned_competitors TEXT,
    captured_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_feedback_platform ON feedback_items(platform);
CREATE INDEX IF NOT EXISTS idx_feedback_captured_at ON feedback_items(captured_at);
CREATE INDEX IF NOT EXISTS idx_feedback_keyword ON feedback_items(keyword);
"""


class FeedbackStore:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def _migrate(self) -> None:
        columns = {row["name"] for row in self.conn.execute("PRAGMA table_info(feedback_items)")}
        migrations = {
            "matched_keyword": "ALTER TABLE feedback_items ADD COLUMN matched_keyword TEXT",
            "feedback_category": "ALTER TABLE feedback_items ADD COLUMN feedback_category TEXT DEFAULT 'feedback'",
            "mentioned_competitors": "ALTER TABLE feedback_items ADD COLUMN mentioned_competitors TEXT",
        }
        for column, sql in migrations.items():
            if column not in columns:
                self.conn.execute(sql)

    def upsert_items(self, items: Iterable[FeedbackItem]) -> tuple[int, int]:
        inserted = 0
        skipped = 0
        for item in items:
            item.captured_at = item.captured_at or now_iso()
            try:
                self.conn.execute(
                    """
                    INSERT INTO feedback_items (
                        fingerprint, item_type, platform, keyword, text, url,
                        published_at, author, likes_count, comments_count,
                        parent_url, screenshot_path, sentiment, category,
                        matched_keyword, feedback_category, mentioned_competitors,
                        captured_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.fingerprint(),
                        item.item_type,
                        item.platform,
                        item.keyword,
                        item.text,
                        item.url,
                        item.published_at,
                        item.author,
                        item.likes_count,
                        item.comments_count,
                        item.parent_url,
                        item.screenshot_path,
                        item.sentiment,
                        item.category,
                        item.matched_keyword,
                        item.feedback_category,
                        item.mentioned_competitors,
                        item.captured_at,
                    ),
                )
                inserted += 1
            except sqlite3.IntegrityError:
                skipped += 1
        self.conn.commit()
        return inserted, skipped

    def update_screenshot(self, item_id: int, screenshot_path: str) -> None:
        self.conn.execute(
            "UPDATE feedback_items SET screenshot_path = ? WHERE id = ?",
            (screenshot_path, item_id),
        )
        self.conn.commit()

    def fetch_all(self) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM feedback_items ORDER BY captured_at DESC, id DESC"))

    def fetch_posts_without_screenshot(self, limit: int) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """
                SELECT * FROM feedback_items
                WHERE item_type = 'post'
                  AND COALESCE(url, '') != ''
                  AND COALESCE(screenshot_path, '') = ''
                ORDER BY captured_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            )
        )
