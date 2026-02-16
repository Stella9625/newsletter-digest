"""RSS Feed 生成：输出 Feed A（每日日报）、Feed B（独立条目）和 HTML 页面"""

from __future__ import annotations

import html
import json
import logging
import re
from collections import Counter
from datetime import datetime, timezone

from feedgen.feed import FeedGenerator

from src.config import OUTPUT_DIR, FEED_TITLE, FEED_DESCRIPTION, FEED_LINK
from src.fetcher import Article

logger = logging.getLogger(__name__)


def _create_base_feed(feed_id: str, title: str, description: str) -> FeedGenerator:
    """创建基础 Feed 对象"""
    fg = FeedGenerator()
    fg.id(f"{FEED_LINK}/{feed_id}")
    fg.title(title)
    fg.description(description)
    fg.link(href=FEED_LINK, rel="alternate")
    fg.language("zh-CN")
    fg.lastBuildDate(datetime.now(timezone.utc))
    return fg


def generate_feed_a(daily_digest: str, digest_date: str | None = None) -> str:
    """
    生成 Feed A：每日日报（单条合并条目）。
    返回输出文件路径。
    """
    if digest_date is None:
        digest_date = datetime.now().strftime("%Y-%m-%d")

    fg = _create_base_feed(
        feed_id="daily-digest",
        title=f"{FEED_TITLE}",
        description=FEED_DESCRIPTION,
    )

    # 添加日报条目
    entry = fg.add_entry()
    entry.id(f"{FEED_LINK}/daily-digest/{digest_date}")
    entry.title(f"📰 {FEED_TITLE} - {digest_date}")
    entry.content(_markdown_to_html(daily_digest), type="html")
    entry.published(datetime.now(timezone.utc))
    entry.updated(datetime.now(timezone.utc))

    output_path = OUTPUT_DIR / "daily-digest.xml"
    fg.rss_file(str(output_path), pretty=True)
    logger.info(f"Feed A (日报) 已生成: {output_path}")
    return str(output_path)


def generate_feed_b(articles: list[Article]) -> str:
    """
    生成 Feed B：独立条目（每篇文章一条，含标签+摘要+翻译）。
    返回输出文件路径。
    """
    fg = _create_base_feed(
        feed_id="articles",
        title=f"{FEED_TITLE} - 文章全文",
        description="每篇文章的中文摘要和全文翻译",
    )

    for article in articles:
        entry = fg.add_entry()
        entry.id(article.url)
        entry.link(href=article.url, rel="alternate")

        # 标题：优先使用中文标题，附带英文原标题
        display_title = article.title_zh or article.title
        entry.title(f"[翻译] {article.source_name}: {display_title}")

        # 构建内容：标签 + 摘要 + 英文原标题 + 翻译 + 原文链接
        tags_str = " ".join(f"#{t}" for t in article.tags) if article.tags else ""

        content_parts = []
        if tags_str:
            content_parts.append(f"<p><strong>标签:</strong> {_escape(tags_str)}</p>")
        if article.summary_zh:
            content_parts.append(
                f"<p><strong>摘要:</strong> {_escape(article.summary_zh)}</p>"
            )
        # 英文原标题对照
        if article.title_zh and article.title:
            content_parts.append(
                f'<p style="color:#888;font-size:13px;">原标题: {_escape(article.title)}</p>'
            )
        content_parts.append("<hr/>")
        if article.translation_zh:
            # 翻译已经是 HTML 格式（双语对照+关键词高亮），直接透传
            content_parts.append(article.translation_zh)
        content_parts.append("<hr/>")
        content_parts.append(
            f'<p>🔗 <a href="{_escape(article.url)}">阅读原文</a></p>'
        )

        entry.content("\n".join(content_parts), type="html")

        if article.published_at:
            entry.published(article.published_at)
            entry.updated(article.published_at)
        else:
            now = datetime.now(timezone.utc)
            entry.published(now)
            entry.updated(now)

        entry.author({"name": article.author or article.source_name})

    output_path = OUTPUT_DIR / "articles.xml"
    fg.rss_file(str(output_path), pretty=True)
    logger.info(f"Feed B (文章) 已生成: {output_path} ({len(articles)} 条)")
    return str(output_path)


# === 语气 → 颜色映射，用于 pill 标签背景色 ===
TONE_COLORS = {
    "🤔 思辨": ("#f0e6ff", "#6b21a8"),
    "😤 批评": ("#ffe4e6", "#be123c"),
    "🎉 兴奋": ("#fef3c7", "#b45309"),
    "🧪 实验记录": ("#d1fae5", "#047857"),
    "📊 分析": ("#dbeafe", "#1d4ed8"),
    "💡 洞察": ("#fef9c3", "#a16207"),
}

# 主题分布条形图的颜色列表
BAR_COLORS = [
    "#0071e3", "#34c759", "#ff9500", "#af52de",
    "#ff3b30", "#5ac8fa", "#ff2d55", "#ffcc00",
]


def _escape(text: str) -> str:
    """HTML 转义"""
    return html.escape(text, quote=True)


def _inline_md(text: str) -> str:
    """处理行内 markdown 语法：**bold**、`code`、[link](url)"""
    # 先转义 HTML 特殊字符
    text = _escape(text)
    # **bold** → <strong>
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # `code` → <code>
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    # [text](url) → <a>
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank">\1</a>', text)
    return text


def _markdown_to_html(md: str) -> str:
    """
    将 LLM 输出的 markdown 转换为 HTML。
    支持：标题(##/###)、粗体、列表(- / *)、引用(>)、分隔线(---)、代码块、段落。
    """
    lines = md.split("\n")
    result = []
    in_list = False  # 是否在 <ul> 内
    in_code = False  # 是否在代码块内
    code_buf = []

    for line in lines:
        stripped = line.strip()

        # 代码块 ``` 切换
        if stripped.startswith("```"):
            if in_code:
                result.append(f'<pre><code>{_escape(chr(10).join(code_buf))}</code></pre>')
                code_buf = []
                in_code = False
            else:
                # 关闭未闭合的 <ul>
                if in_list:
                    result.append("</ul>")
                    in_list = False
                in_code = True
            continue

        if in_code:
            code_buf.append(line)
            continue

        # 空行：关闭 <ul>，跳过
        if not stripped:
            if in_list:
                result.append("</ul>")
                in_list = False
            continue

        # 分隔线 ---
        if re.match(r'^-{3,}$', stripped):
            if in_list:
                result.append("</ul>")
                in_list = False
            result.append("<hr>")
            continue

        # 标题 ## / ###
        heading_match = re.match(r'^(#{1,4})\s+(.+)$', stripped)
        if heading_match:
            if in_list:
                result.append("</ul>")
                in_list = False
            level = len(heading_match.group(1))
            # 限制在 h2-h4 范围内
            tag = f"h{min(level + 1, 4)}"
            result.append(f"<{tag}>{_inline_md(heading_match.group(2))}</{tag}>")
            continue

        # 引用 >
        if stripped.startswith("> ") or stripped == ">":
            if in_list:
                result.append("</ul>")
                in_list = False
            quote_text = stripped[2:] if stripped.startswith("> ") else ""
            result.append(f"<blockquote>{_inline_md(quote_text)}</blockquote>")
            continue

        # 无序列表 - / *
        list_match = re.match(r'^[-*]\s+(.+)$', stripped)
        if list_match:
            if not in_list:
                result.append("<ul>")
                in_list = True
            result.append(f"<li>{_inline_md(list_match.group(1))}</li>")
            continue

        # 普通段落
        if in_list:
            result.append("</ul>")
            in_list = False
        result.append(f"<p>{_inline_md(stripped)}</p>")

    # 收尾：关闭未闭合标签
    if in_code:
        result.append(f'<pre><code>{_escape(chr(10).join(code_buf))}</code></pre>')
    if in_list:
        result.append("</ul>")

    return "\n".join(result)


def _build_topic_chart_html(articles_data: list[dict]) -> str:
    """生成主题分布条形图的 HTML（纯 CSS 横条）"""
    tag_counter: Counter = Counter()
    for a in articles_data:
        for tag in a.get("tags", []):
            tag_counter[tag] += 1

    if not tag_counter:
        return ""

    # 取 top 8
    top_tags = tag_counter.most_common(8)
    max_count = top_tags[0][1] if top_tags else 1

    rows = []
    for i, (tag, count) in enumerate(top_tags):
        color = BAR_COLORS[i % len(BAR_COLORS)]
        pct = int(count / max_count * 100)
        rows.append(
            f'<div class="chart-row">'
            f'<span class="chart-label">{_escape(tag)}</span>'
            f'<div class="chart-bar-bg">'
            f'<div class="chart-bar" style="width:{pct}%;background:{color}"></div>'
            f'</div>'
            f'<span class="chart-count">{count}</span>'
            f'</div>'
        )
    return (
        '<div class="topic-chart">'
        '<h2>今日主题分布</h2>'
        + "\n".join(rows)
        + '</div>'
    )


def _build_quotes_html(quotes: list[dict]) -> str:
    """生成金句区域的 HTML"""
    if not quotes:
        return ""
    parts = ['<div class="quotes-section">']
    for q in quotes:
        en = _escape(q.get("en", ""))
        zh = _escape(q.get("zh", ""))
        if en:
            parts.append(
                f'<div class="quote-block">'
                f'<div class="quote-en">{en}</div>'
                f'<div class="quote-zh">{zh}</div>'
                f'</div>'
            )
    parts.append('</div>')
    return "\n".join(parts)


def _build_tone_pill(tone: str) -> str:
    """生成语气 pill 标签"""
    if not tone:
        return ""
    bg, fg = TONE_COLORS.get(tone, ("#f0f0f5", "#515154"))
    return f'<span class="tone-pill" style="background:{bg};color:{fg}">{_escape(tone)}</span>'


def generate_html_page(
    daily_digest: str,
    articles_data: list[dict],
    digest_date: str | None = None,
) -> str:
    """
    生成可视化 HTML 页面，包含：
    - 主题分布条形图
    - 文章卡片（含金句、语气标注）
    - 日报 Tab
    返回输出文件路径。
    """
    if digest_date is None:
        digest_date = datetime.now().strftime("%Y-%m-%d")

    article_count = len(articles_data)
    topic_chart = _build_topic_chart_html(articles_data)

    # 构建文章卡片 HTML
    article_cards = []
    for a in articles_data:
        tags_html = "".join(
            f'<span class="tag">{_escape(t)}</span>' for t in a.get("tags", [])
        )
        tone_html = _build_tone_pill(a.get("tone", ""))
        quotes_html = _build_quotes_html(a.get("quotes", []))
        summary = _escape(a.get("summary_zh", ""))
        translation = a.get("translation_zh", "")
        # 翻译已是 HTML 格式，直接使用
        trans_html = translation if translation else ""

        url = _escape(a.get("url", ""))
        source = _escape(a.get("source_name", ""))
        title_zh = _escape(a.get("title_zh", ""))
        title_en = _escape(a.get("title", ""))
        title = title_zh or title_en

        en_title_line = f'<div class="title-en">{title_en}</div>' if title_zh and title_en else ""
        card = f'''<div class="article-card">
      <div class="source">{source}</div>
      <div class="title-row">
        <div class="title">{title}</div>
        {tone_html}
      </div>
      {en_title_line}
      <div class="tags">{tags_html}</div>
      <div class="summary">{summary}</div>
      {quotes_html}
      <div class="translation">{trans_html}</div>
      <button class="toggle-btn" onclick="toggleTranslation(this)">展开全文翻译</button>
      <a class="link" href="{url}" target="_blank">阅读原文 &rarr;</a>
    </div>'''
        article_cards.append(card)

    articles_html = "\n\n".join(article_cards)

    # 用 markdown 转换器处理日报内容
    digest_html = _markdown_to_html(daily_digest)

    page = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI/产品/技术日报</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", sans-serif;
    background: #f5f5f7;
    color: #1d1d1f;
    line-height: 1.6;
  }}
  .header {{
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    color: white;
    padding: 40px 20px;
    text-align: center;
  }}
  .header h1 {{ font-size: 28px; font-weight: 700; margin-bottom: 8px; }}
  .header p {{ font-size: 14px; opacity: 0.7; }}
  .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}

  /* Tab 切换 */
  .tabs {{
    display: flex;
    gap: 0;
    margin: 24px 0 0;
    border-bottom: 2px solid #e5e5e5;
  }}
  .tab {{
    padding: 12px 24px;
    cursor: pointer;
    font-size: 15px;
    font-weight: 600;
    color: #86868b;
    border-bottom: 2px solid transparent;
    margin-bottom: -2px;
    transition: all 0.2s;
    background: none;
    border-top: none; border-left: none; border-right: none;
  }}
  .tab:hover {{ color: #1d1d1f; }}
  .tab.active {{ color: #0071e3; border-bottom-color: #0071e3; }}
  .tab-content {{ display: none; }}
  .tab-content.active {{ display: block; }}

  /* 主题分布条形图 */
  .topic-chart {{
    background: white;
    border-radius: 16px;
    padding: 24px;
    margin: 24px 0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  }}
  .topic-chart h2 {{
    font-size: 13px;
    color: #0071e3;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 16px;
  }}
  .chart-row {{
    display: flex;
    align-items: center;
    margin: 8px 0;
    gap: 12px;
  }}
  .chart-label {{
    width: 80px;
    font-size: 13px;
    font-weight: 600;
    color: #515154;
    text-align: right;
    flex-shrink: 0;
  }}
  .chart-bar-bg {{
    flex: 1;
    height: 20px;
    background: #f0f0f5;
    border-radius: 10px;
    overflow: hidden;
  }}
  .chart-bar {{
    height: 100%;
    border-radius: 10px;
    transition: width 0.6s ease;
    min-width: 4px;
  }}
  .chart-count {{
    width: 24px;
    font-size: 13px;
    font-weight: 700;
    color: #1d1d1f;
    flex-shrink: 0;
  }}

  /* 日报样式 */
  .digest-card {{
    background: white;
    border-radius: 16px;
    padding: 32px;
    margin: 24px 0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  }}
  .digest-card h2 {{
    font-size: 13px;
    color: #0071e3;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 20px;
  }}
  .digest-card h3 {{
    font-size: 18px;
    font-weight: 700;
    margin: 24px 0 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid #f0f0f0;
  }}
  .digest-card li {{
    margin: 10px 0;
    padding-left: 4px;
    font-size: 15px;
    line-height: 1.7;
  }}
  .digest-card strong {{ color: #1d1d1f; }}

  /* 文章卡片 */
  .article-card {{
    background: white;
    border-radius: 16px;
    padding: 24px;
    margin: 16px 0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    transition: box-shadow 0.2s;
  }}
  .article-card:hover {{ box-shadow: 0 4px 12px rgba(0,0,0,0.12); }}
  .article-card .source {{
    font-size: 12px;
    color: #86868b;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}
  .title-row {{
    display: flex;
    align-items: flex-start;
    gap: 10px;
    margin: 8px 0;
  }}
  .article-card .title {{
    font-size: 18px;
    font-weight: 700;
    color: #1d1d1f;
    flex: 1;
  }}
  .tone-pill {{
    display: inline-block;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 600;
    white-space: nowrap;
    flex-shrink: 0;
    margin-top: 2px;
  }}
  .title-en {{
    font-size: 13px;
    color: #86868b;
    margin: 2px 0 6px;
    font-style: italic;
  }}
  .article-card .tags {{
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin: 10px 0;
  }}
  .tag {{
    display: inline-block;
    background: #f0f0f5;
    color: #515154;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 500;
  }}
  .article-card .summary {{
    font-size: 15px;
    color: #515154;
    margin: 12px 0;
    line-height: 1.7;
  }}

  /* 金句区域 */
  .quotes-section {{
    margin: 16px 0;
    padding: 0;
  }}
  .quote-block {{
    border-left: 3px solid #0071e3;
    padding: 10px 16px;
    margin: 10px 0;
    background: #f9f9fb;
    border-radius: 0 8px 8px 0;
  }}
  .quote-en {{
    font-style: italic;
    font-size: 14px;
    color: #1d1d1f;
    line-height: 1.7;
  }}
  .quote-zh {{
    font-size: 13px;
    color: #86868b;
    margin-top: 6px;
    line-height: 1.6;
  }}

  .article-card .translation {{
    display: none;
    margin-top: 16px;
    padding-top: 16px;
    border-top: 1px solid #f0f0f0;
    font-size: 15px;
    line-height: 1.8;
    color: #333;
  }}
  .article-card .translation p {{ margin: 12px 0; }}
  .article-card .translation blockquote {{
    border-left: 3px solid #0071e3;
    padding: 8px 16px;
    margin: 12px 0;
    background: #f9f9fb;
    color: #515154;
    border-radius: 0 8px 8px 0;
  }}
  .article-card .translation code {{
    background: #f0f0f5;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 13px;
  }}
  .article-card .translation pre {{
    background: #1d1d1f;
    color: #f5f5f7;
    padding: 16px;
    border-radius: 8px;
    overflow-x: auto;
    font-size: 13px;
    margin: 12px 0;
  }}
  .toggle-btn {{
    display: inline-block;
    padding: 6px 16px;
    font-size: 13px;
    font-weight: 600;
    color: #0071e3;
    background: none;
    border: 1.5px solid #0071e3;
    border-radius: 20px;
    cursor: pointer;
    transition: all 0.2s;
  }}
  .toggle-btn:hover {{ background: #0071e3; color: white; }}
  .article-card .link {{
    display: inline-block;
    margin-top: 12px;
    margin-left: 8px;
    font-size: 13px;
    color: #0071e3;
    text-decoration: none;
    font-weight: 500;
  }}
  .article-card .link:hover {{ text-decoration: underline; }}
  .footer {{
    text-align: center;
    padding: 40px;
    color: #86868b;
    font-size: 13px;
  }}
</style>
</head>
<body>

<div class="header">
  <h1>AI / 产品 / 技术日报</h1>
  <p>每日聚合英文 Newsletter &amp; 博客，AI 翻译生成中文摘要和全文</p>
</div>

<div class="container">
  <div class="tabs">
    <button class="tab active" onclick="switchTab('digest')">每日日报</button>
    <button class="tab" onclick="switchTab('articles')">全部文章 ({article_count})</button>
  </div>

  <!-- 日报 Tab -->
  <div id="tab-digest" class="tab-content active">
    {topic_chart}
    <div class="digest-card">
      <h2>{_escape(digest_date)} 日报</h2>
      {digest_html}
    </div>
  </div>

  <!-- 文章 Tab -->
  <div id="tab-articles" class="tab-content">
    {articles_html}
  </div>
</div>

<div class="footer">
  Newsletter 聚合翻译工具 &middot; Powered by AI &middot; {_escape(digest_date)}
</div>

<script>
function switchTab(name) {{
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  event.target.classList.add('active');
  document.getElementById('tab-' + name).classList.add('active');
}}

function toggleTranslation(btn) {{
  const card = btn.closest('.article-card');
  const trans = card.querySelector('.translation');
  if (trans.style.display === 'block') {{
    trans.style.display = 'none';
    btn.textContent = '展开全文翻译';
  }} else {{
    trans.style.display = 'block';
    btn.textContent = '收起全文翻译';
  }}
}}
</script>
</body>
</html>'''

    output_path = OUTPUT_DIR / "index.html"
    output_path.write_text(page, encoding="utf-8")
    logger.info(f"HTML 页面已生成: {output_path} ({article_count} 篇文章)")
    return str(output_path)
