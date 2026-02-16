"""主入口：串联抓取→AI处理→Feed生成的完整流程"""

import argparse
import logging
import time
from datetime import datetime
from typing import Optional

from src.config import (
    MVP_SOURCES, ALL_SOURCES, FETCH_WINDOW_HOURS,
    ANTHROPIC_API_KEY, MOONSHOT_API_KEY, LLM_PROVIDER,
)
from src.fetcher import fetch_feeds
from src.generator import generate_feed_a, generate_feed_b, generate_html_page
from src.models.base import LLMProvider
from src.processor import process_articles, generate_daily_digest
from src.storage import Storage

logger = logging.getLogger(__name__)


def _create_provider(provider_name: str) -> Optional[LLMProvider]:
    """根据名称实例化对应的 LLM provider，失败返回 None"""
    if provider_name == "kimi":
        if not MOONSHOT_API_KEY:
            logger.error("未配置 MOONSHOT_API_KEY，请在 .env 文件中设置")
            return None
        from src.models.kimi import KimiProvider
        logger.info("使用 Kimi (Moonshot AI) 作为 LLM provider")
        return KimiProvider()
    elif provider_name == "claude":
        if not ANTHROPIC_API_KEY:
            logger.error("未配置 ANTHROPIC_API_KEY，请在 .env 文件中设置")
            return None
        from src.models.claude import ClaudeProvider
        logger.info("使用 Claude (Anthropic) 作为 LLM provider")
        return ClaudeProvider()
    else:
        logger.error(f"未知的 LLM provider: {provider_name}")
        return None


def setup_logging(verbose: bool = False):
    """配置日志"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main():
    parser = argparse.ArgumentParser(description="Newsletter 聚合翻译工具")
    parser.add_argument(
        "--sources",
        choices=["mvp", "all"],
        default="mvp",
        help="使用哪组 RSS 源 (默认: mvp，3个测试源)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅抓取，不调用 AI（用于测试抓取流程）",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="抓取时间窗口，单位天 (默认: 1)",
    )
    parser.add_argument(
        "--provider",
        choices=["kimi", "claude"],
        default=None,
        help="AI 模型提供者 (默认读取 LLM_PROVIDER 环境变量，兜底 kimi)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="显示详细日志",
    )
    args = parser.parse_args()

    # 确定 provider：命令行参数 > 环境变量 > 默认 kimi
    provider_name = args.provider or LLM_PROVIDER

    setup_logging(args.verbose)
    start_time = time.time()

    logger.info("=" * 60)
    logger.info("Newsletter 聚合翻译工具 - 开始运行")
    logger.info("=" * 60)

    # 选择源
    sources = MVP_SOURCES if args.sources == "mvp" else ALL_SOURCES
    logger.info(f"使用 {len(sources)} 个 RSS 源 ({args.sources})")

    window_hours = args.days * 24
    logger.info(f"时间窗口: 过去 {window_hours} 小时")

    # 1. 抓取 RSS
    logger.info("-" * 40)
    logger.info("阶段 1: 抓取 RSS 源")
    articles = fetch_feeds(sources, window_hours=window_hours)

    if not articles:
        logger.info("没有新文章，结束运行。")
        return

    # 2. AI 处理
    logger.info("-" * 40)
    logger.info("阶段 2: AI 处理")

    storage = Storage()

    if args.dry_run:
        logger.info("[dry-run] 跳过 AI 处理")
        processed = articles
        llm = None
    else:
        llm = _create_provider(provider_name)
        if llm is None:
            return
        processed = process_articles(articles, llm, storage, dry_run=False)

    if not processed:
        logger.info("没有需要处理的新文章（可能全部已处理过），结束运行。")
        storage.close()
        return

    # 3. 生成 Feed
    logger.info("-" * 40)
    logger.info("阶段 3: 生成 RSS Feed")

    # Feed B: 独立条目
    generate_feed_b(processed)

    # Feed A: 每日日报
    if args.dry_run or llm is None:
        # dry-run 模式：生成简单的文章列表
        digest_lines = ["## 今日文章\n"]
        for a in processed:
            digest_lines.append(f"- **{a.source_name}**: {a.title}")
        daily_digest = "\n".join(digest_lines)
    else:
        daily_digest = generate_daily_digest(processed, llm)

    today = datetime.now().strftime("%Y-%m-%d")
    generate_feed_a(daily_digest, digest_date=today)

    # HTML 可视化页面（含主题分布图、金句、语气标注）
    today_articles = storage.get_today_articles()
    if not today_articles:
        # 如果当天没有（因为 processed_at 精确到秒），用刚处理的数据
        today_articles = [
            {
                "url": a.url,
                "title": a.title,
                "author": a.author,
                "source_name": a.source_name,
                "summary_zh": a.summary_zh,
                "tags": a.tags,
                "translation_zh": a.translation_zh,
                "quotes": a.quotes,
                "tone": a.tone,
                "title_zh": a.title_zh,
            }
            for a in processed
        ]
    generate_html_page(daily_digest, today_articles, digest_date=today)

    # 4. 运行摘要
    elapsed = time.time() - start_time
    logger.info("-" * 40)
    logger.info("运行摘要:")
    logger.info(f"  抓取文章数: {len(articles)}")
    logger.info(f"  处理成功数: {len(processed)}")
    logger.info(f"  耗时: {elapsed:.1f} 秒")

    if llm:
        usage = llm.get_total_usage()
        logger.info(f"  API 调用次数: {usage['total_calls']}")
        logger.info(f"  总 input tokens: {usage['total_input_tokens']:,}")
        logger.info(f"  总 output tokens: {usage['total_output_tokens']:,}")
        logger.info(f"  按操作统计:")
        for op, stats in usage["by_operation"].items():
            logger.info(
                f"    {op}: {stats['count']}次, "
                f"in={stats['input']:,}, out={stats['output']:,}"
            )

    logger.info("=" * 60)
    logger.info("完成! Feed 文件已生成到 output/ 目录")
    logger.info("  日报: output/daily-digest.xml")
    logger.info("  文章: output/articles.xml")
    logger.info("  启动服务: python -m src.server")
    logger.info("=" * 60)

    storage.close()


if __name__ == "__main__":
    main()
