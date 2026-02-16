"""SQLite 存储层：文章去重和历史记录"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, date

from src.config import DB_PATH


def _url_hash(url: str) -> str:
    """对 URL 取 SHA-256 哈希，用于去重"""
    return hashlib.sha256(url.encode()).hexdigest()


class Storage:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        """建表（如果不存在）+ 兼容旧数据库的列迁移"""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                url_hash TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                title TEXT,
                author TEXT,
                source_name TEXT,
                published_at TEXT,
                content TEXT,
                summary_zh TEXT,
                tags TEXT,
                translation_zh TEXT,
                quotes TEXT,
                tone TEXT,
                processed_at TEXT NOT NULL
            )
        """)
        # 兼容旧数据库：尝试添加新列，已存在则忽略
        for col in ("quotes TEXT", "tone TEXT", "title_zh TEXT"):
            try:
                self.conn.execute(f"ALTER TABLE articles ADD COLUMN {col}")
            except sqlite3.OperationalError:
                pass  # 列已存在
        self.conn.commit()

    def is_processed(self, url: str) -> bool:
        """检查文章是否已处理过（去重）"""
        h = _url_hash(url)
        row = self.conn.execute(
            "SELECT 1 FROM articles WHERE url_hash = ?", (h,)
        ).fetchone()
        return row is not None

    def save_article(
        self,
        url: str,
        title: str,
        author: str,
        source_name: str,
        published_at: datetime | None,
        content: str,
        summary_zh: str,
        tags: list[str],
        translation_zh: str,
        quotes: list[dict] | None = None,
        tone: str = "",
        title_zh: str = "",
    ):
        """保存处理完成的文章"""
        self.conn.execute(
            """
            INSERT OR REPLACE INTO articles
            (url_hash, url, title, author, source_name, published_at,
             content, summary_zh, tags, translation_zh, quotes, tone, title_zh, processed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _url_hash(url),
                url,
                title,
                author,
                source_name,
                published_at.isoformat() if published_at else None,
                content,
                summary_zh,
                json.dumps(tags, ensure_ascii=False),
                translation_zh,
                json.dumps(quotes or [], ensure_ascii=False),
                tone,
                title_zh,
                datetime.now().isoformat(),
            ),
        )
        self.conn.commit()

    def get_today_articles(self, target_date: date | None = None) -> list[dict]:
        """获取指定日期处理的文章（默认今天）"""
        if target_date is None:
            target_date = date.today()
        date_prefix = target_date.isoformat()  # "2026-02-14"

        rows = self.conn.execute(
            "SELECT * FROM articles WHERE processed_at LIKE ? ORDER BY published_at DESC",
            (f"{date_prefix}%",),
        ).fetchall()

        results = []
        for row in rows:
            d = dict(row)
            d["tags"] = json.loads(d["tags"]) if d["tags"] else []
            d["quotes"] = json.loads(d["quotes"]) if d.get("quotes") else []
            d["tone"] = d.get("tone") or ""
            d["title_zh"] = d.get("title_zh") or ""
            results.append(d)
        return results

    def close(self):
        self.conn.close()
