"""配置管理：加载环境变量、定义 RSS 源列表和各类参数"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# === 路径 ===
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "articles.db"

# 确保目录存在
OUTPUT_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

# === API Keys ===
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MOONSHOT_API_KEY = os.getenv("MOONSHOT_API_KEY", "")

# === LLM Provider 切换 ===
# 可选值: "kimi" / "claude"，默认 kimi
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "kimi")

# === Claude 模型配置 ===
# 摘要 + 标签提取：用 haiku（成本低、速度快）
HAIKU_MODEL = "claude-haiku-4-5-20251001"
# 翻译 + 日报生成：用 sonnet（质量优先）
SONNET_MODEL = "claude-sonnet-4-5-20250929"

# === Kimi Code 模型配置 ===
# 摘要 + 标签提取：轻量快速
KIMI_LIGHT_MODEL = "kimi-k2"
# 翻译 + 日报生成：质量优先
KIMI_MODEL = "kimi-k2"

# === 抓取配置 ===
# 默认时间窗口（小时），只抓取这个时间范围内的文章
FETCH_WINDOW_HOURS = 24
# RSS content 长度阈值，低于此值时自动抓取全文
MIN_CONTENT_LENGTH = 500
# HTTP 请求超时（秒）
HTTP_TIMEOUT = 30
# HTTP 请求 User-Agent
USER_AGENT = "NewsletterDigest/0.1 (+https://github.com/newsletter-digest)"

# === 服务器配置 ===
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8080

# === Feed 元数据 ===
FEED_TITLE = "AI/产品/技术日报"
FEED_DESCRIPTION = "每日聚合 12 个英文 Newsletter/博客，AI 翻译生成中文摘要和全文"
FEED_LINK = os.getenv("FEED_LINK", f"http://localhost:{SERVER_PORT}")


@dataclass
class RSSSource:
    """RSS 订阅源定义"""
    name: str
    url: str
    category: str  # 分类标签，如 "AI工具"、"工程"、"产品"
    note: str = ""  # 备注


# MVP 阶段使用 3 个源测试
MVP_SOURCES = [
    RSSSource(
        name="Simon Willison",
        url="https://simonwillison.net/atom/everything/",
        category="AI工具",
        note="AI工具实操，HN连续3年#1",
    ),
    RSSSource(
        name="Gary Marcus",
        url="https://garymarcus.substack.com/feed",
        category="AI评论",
        note="AI怀疑派视角，平衡hype",
    ),
    RSSSource(
        name="TLDR AI",
        url="https://tldr.tech/api/rss/ai",
        category="AI综合",
        note="每日AI/ML/论文短摘要",
    ),
]

# 全量源（12个）
ALL_SOURCES = [
    RSSSource(
        name="Simon Willison",
        url="https://simonwillison.net/atom/everything/",
        category="AI工具",
        note="AI工具实操，HN连续3年#1",
    ),
    RSSSource(
        name="Mitchell Hashimoto",
        url="https://mitchellh.com/feed.xml",
        category="工程",
        note="HashiCorp联创，底层工程原理",
    ),
    RSSSource(
        name="Antirez",
        url="http://antirez.com/rss",
        category="工程",
        note="Redis作者，系统设计",
    ),
    RSSSource(
        name="Andrej Karpathy",
        url="https://karpathy.bearblog.dev/feed/",
        category="AI研究",
        note="AI研究+教育",
    ),
    RSSSource(
        name="Dan Abramov",
        url="https://overreacted.io/rss.xml",
        category="前端",
        note="React核心，编程思维",
    ),
    RSSSource(
        name="Dwarkesh Patel",
        url="https://www.dwarkesh.com/feed",
        category="AI访谈",
        note="深度AI访谈，含完整文字稿",
    ),
    RSSSource(
        name="Gary Marcus",
        url="https://garymarcus.substack.com/feed",
        category="AI评论",
        note="AI怀疑派视角，平衡hype",
    ),
    RSSSource(
        name="Lenny's Newsletter",
        url="https://www.lennysnewsletter.com/feed",
        category="产品",
        note="仅抓免费部分，产品增长",
    ),
    RSSSource(
        name="Zara Zhang",
        url="https://zarazhang.substack.com/feed",
        category="AI人文",
        note="AI+人文视角",
    ),
    RSSSource(
        name="Construction Physics",
        url="https://www.construction-physics.com/feed",
        category="行业分析",
        note="工程创新与行业变革分析",
    ),
    RSSSource(
        name="Latent Space",
        url="https://latent.space/feed",
        category="AI工程",
        note="swyx主理，AI工程师深度访谈+日报",
    ),
    RSSSource(
        name="TLDR AI",
        url="https://tldr.tech/api/rss/ai",
        category="AI综合",
        note="每日AI/ML/论文短摘要",
    ),
]
