"""抓取层：RSS 解析 + 全文抓取"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

import feedparser
import httpx
from bs4 import BeautifulSoup
from readability import Document

from src.config import (
    RSSSource,
    FETCH_WINDOW_HOURS,
    MIN_CONTENT_LENGTH,
    HTTP_TIMEOUT,
    USER_AGENT,
)

logger = logging.getLogger(__name__)


@dataclass
class Article:
    """统一的文章数据结构"""
    url: str
    title: str
    author: str
    source_name: str
    published_at: datetime | None
    content: str  # 原文内容（HTML 或纯文本）
    summary_zh: str = ""
    tags: list[str] = field(default_factory=list)
    translation_zh: str = ""
    quotes: list[dict] = field(default_factory=list)  # 金句列表，每个 dict 含 en/zh
    tone: str = ""  # 语气标注，如 "🧪 实验记录"
    title_zh: str = ""  # 中文标题


def _parse_published_time(entry) -> datetime | None:
    """从 feedparser entry 中提取发布时间"""
    # feedparser 会将时间解析为 time.struct_time
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            try:
                return datetime(*parsed[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue
    return None


def _clean_html(html: str) -> str:
    """清理 HTML，提取纯文本，保留段落结构"""
    soup = BeautifulSoup(html, "lxml")

    # 移除 script/style 标签
    for tag in soup(["script", "style"]):
        tag.decompose()

    # 提取文本和图片，用换行分隔段落
    lines = []
    for element in soup.find_all(["p", "h1", "h2", "h3", "h4", "li", "blockquote", "pre", "img"]):
        # 图片：保留为 markdown 格式
        if element.name == "img":
            src = element.get("src", "")
            alt = element.get("alt", "")
            if src:
                lines.append(f"![{alt}]({src})")
            continue

        # 段落内嵌图片也提取出来
        for img in element.find_all("img"):
            src = img.get("src", "")
            alt = img.get("alt", "")
            if src:
                lines.append(f"![{alt}]({src})")

        text = element.get_text(strip=True)
        if text:
            # 保留标题层级
            if element.name in ("h1", "h2", "h3", "h4"):
                lines.append(f"\n{'#' * int(element.name[1])} {text}\n")
            elif element.name == "li":
                lines.append(f"- {text}")
            elif element.name == "blockquote":
                lines.append(f"> {text}")
            elif element.name == "pre":
                lines.append(f"```\n{text}\n```")
            else:
                lines.append(text)

    result = "\n\n".join(lines)

    # 如果提取结果太短，回退到简单文本提取
    if len(result) < 100:
        result = soup.get_text(separator="\n", strip=True)

    return result


def _get_entry_content(entry) -> str:
    """从 feedparser entry 中提取内容（HTML）"""
    # 优先取 content 字段（通常是完整内容）
    if hasattr(entry, "content") and entry.content:
        return entry.content[0].get("value", "")
    # 其次取 summary
    if hasattr(entry, "summary") and entry.summary:
        return entry.summary
    # 最后取 description
    if hasattr(entry, "description") and entry.description:
        return entry.description
    return ""


def fetch_full_text(url: str) -> str:
    """抓取网页全文，用 readability 提取正文"""
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": USER_AGENT})
            resp.raise_for_status()

        doc = Document(resp.text)
        html = doc.summary()
        return _clean_html(html)

    except Exception as e:
        logger.warning(f"全文抓取失败 {url}: {e}")
        return ""


def fetch_feeds(
    sources: list[RSSSource],
    window_hours: int = FETCH_WINDOW_HOURS,
) -> list[Article]:
    """
    遍历 RSS 源，解析并返回时间窗口内的新文章。
    如果 RSS 中的内容太短，自动抓取全文。
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    articles = []

    for source in sources:
        logger.info(f"正在抓取: {source.name} ({source.url})")

        try:
            feed = feedparser.parse(source.url)
        except Exception as e:
            logger.error(f"RSS 解析失败 [{source.name}]: {e}")
            continue

        if feed.bozo and not feed.entries:
            logger.warning(f"RSS 解析异常 [{source.name}]: {feed.bozo_exception}")
            continue

        for entry in feed.entries:
            # 提取发布时间
            pub_time = _parse_published_time(entry)

            # 过滤时间窗口外的文章
            if pub_time and pub_time < cutoff:
                continue

            # 提取 URL
            url = getattr(entry, "link", "") or ""
            if not url:
                continue

            # 提取内容
            raw_content = _get_entry_content(entry)
            content = _clean_html(raw_content) if raw_content else ""

            # 内容太短时抓取全文
            if len(content) < MIN_CONTENT_LENGTH:
                logger.info(f"  内容过短({len(content)}字符)，尝试抓取全文: {url}")
                full_text = fetch_full_text(url)
                if full_text:
                    content = full_text

            title = getattr(entry, "title", "无标题")
            author = getattr(entry, "author", source.name)

            article = Article(
                url=url,
                title=title,
                author=author,
                source_name=source.name,
                published_at=pub_time,
                content=content,
            )
            articles.append(article)
            logger.info(f"  已获取: {title} ({len(content)} 字符)")

        # 礼貌等待，避免请求过快
        time.sleep(1)

    logger.info(f"共获取 {len(articles)} 篇新文章")
    return articles
