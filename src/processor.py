"""AI 处理编排：串联摘要、标签提取、翻译和日报生成"""

from __future__ import annotations

import logging
from collections import defaultdict

from src.fetcher import Article
from src.models.base import LLMProvider
from src.storage import Storage

logger = logging.getLogger(__name__)


def process_articles(
    articles: list[Article],
    llm: LLMProvider,
    storage: Storage,
    dry_run: bool = False,
) -> list[Article]:
    """
    对每篇文章执行 AI 处理流程：
    1. 去重检查
    2. 生成中文摘要
    3. 提取主题标签
    4. 全文翻译
    5. 存入 SQLite

    dry_run=True 时跳过 AI 调用，仅测试抓取流程。
    返回处理成功的文章列表。
    """
    processed = []

    for i, article in enumerate(articles, 1):
        logger.info(f"[{i}/{len(articles)}] 处理: {article.title}")

        # 去重
        if storage.is_processed(article.url):
            logger.info(f"  跳过（已处理过）: {article.url}")
            continue

        if not article.content:
            logger.warning(f"  跳过（无内容）: {article.url}")
            continue

        if dry_run:
            logger.info(f"  [dry-run] 跳过 AI 处理")
            processed.append(article)
            continue

        try:
            # 生成中文摘要
            logger.info(f"  生成摘要...")
            article.summary_zh = llm.summarize(article.content, article.title)

            # 提取主题标签
            logger.info(f"  提取标签...")
            article.tags = llm.extract_tags(article.content, article.title)

            # 全文翻译
            logger.info(f"  全文翻译...")
            article.translation_zh = llm.translate(article.content, article.title)

            # 提取金句 + 语气标注 + 中文标题
            logger.info(f"  提取金句+语气+中文标题...")
            qt_result = llm.extract_quotes_and_tone(article.content, article.title)
            article.quotes = qt_result.get("quotes", [])
            article.tone = qt_result.get("tone", "")
            article.title_zh = qt_result.get("title_zh", "")

            # 存入数据库
            storage.save_article(
                url=article.url,
                title=article.title,
                author=article.author,
                source_name=article.source_name,
                published_at=article.published_at,
                content=article.content,
                summary_zh=article.summary_zh,
                tags=article.tags,
                translation_zh=article.translation_zh,
                quotes=article.quotes,
                tone=article.tone,
                title_zh=article.title_zh,
            )

            processed.append(article)
            logger.info(
                f"  完成: 摘要={len(article.summary_zh)}字, "
                f"标签={article.tags}, "
                f"翻译={len(article.translation_zh)}字, "
                f"金句={len(article.quotes)}条, "
                f"语气={article.tone}"
            )

        except Exception as e:
            logger.error(f"  处理失败: {e}")
            # 单篇失败不阻塞整体
            continue

    logger.info(f"AI 处理完成: {len(processed)}/{len(articles)} 篇成功")
    return processed


def cluster_by_topic(articles: list[Article]) -> dict[str, list[Article]]:
    """
    按主题标签聚类文章。
    同一篇文章可能出现在多个聚类中（因为可以有多个标签）。
    对标签做简单的归类映射，将细分标签合并到大类。
    """
    # 大类映射规则
    CATEGORY_MAP = {
        "LLM": "LLM & AI 工具",
        "AI": "LLM & AI 工具",
        "AI工具": "LLM & AI 工具",
        "大模型": "LLM & AI 工具",
        "GPT": "LLM & AI 工具",
        "Claude": "LLM & AI 工具",
        "机器学习": "LLM & AI 工具",
        "深度学习": "LLM & AI 工具",
        "产品": "产品与增长",
        "增长": "产品与增长",
        "产品策略": "产品与增长",
        "用户体验": "产品与增长",
        "工程": "工程与系统设计",
        "系统设计": "工程与系统设计",
        "架构": "工程与系统设计",
        "数据结构": "工程与系统设计",
        "编程": "工程与系统设计",
        "开源": "工程与系统设计",
        "前端": "工程与系统设计",
        "后端": "工程与系统设计",
    }
    DEFAULT_CATEGORY = "跨界与深度思考"

    clusters: dict[str, list[Article]] = defaultdict(list)

    for article in articles:
        if not article.tags:
            clusters[DEFAULT_CATEGORY].append(article)
            continue

        # 找到文章所属的大类（取第一个匹配的）
        categories_added = set()
        for tag in article.tags:
            category = CATEGORY_MAP.get(tag, DEFAULT_CATEGORY)
            if category not in categories_added:
                clusters[category].append(article)
                categories_added.add(category)

    return dict(clusters)


def generate_daily_digest(
    articles: list[Article],
    llm: LLMProvider,
) -> str:
    """聚类后调用 LLM 生成日报内容"""
    if not articles:
        return "今日暂无新文章。"

    # 构造文章数据给 LLM
    articles_data = []
    for a in articles:
        articles_data.append({
            "title": a.title,
            "author": a.author,
            "source_name": a.source_name,
            "tags": a.tags,
            "summary_zh": a.summary_zh,
        })

    return llm.generate_daily_report(articles_data)
