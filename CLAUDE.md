# Newsletter 聚合翻译工具

## 项目概述

将 12 个英文 Newsletter/博客源每日聚合，通过 AI 进行主题聚类、翻译和摘要，生成 RSS feed 供 Reeder 阅读器订阅。目标是每天早上在 Reeder 里用中文快速浏览全球 AI/产品/技术领域的重要内容。

## 订阅源清单

所有源均通过 RSS 获取，不走邮件。

| # | 名称 | RSS Feed URL | 类型 | 更新频率 | 备注 |
|---|------|-------------|------|---------|------|
| 1 | Simon Willison | `simonwillison.net/atom/everything/` | 独立博客 | 每日多篇 | AI工具实操，HN连续3年#1 |
| 2 | Mitchell Hashimoto | `mitchellh.com/feed.xml` | 独立博客 | 每月1-2篇 | HashiCorp联创，底层工程原理 |
| 3 | Antirez | `antirez.com/rss` | 独立博客 | 每月1-2篇 | Redis作者，系统设计 |
| 4 | Andrej Karpathy | `karpathy.bearblog.dev/feed/` | 独立博客 | 每1-2周 | AI研究+教育（Substack已弃用） |
| 5 | Dan Abramov | `overreacted.io/rss.xml` | 独立博客 | 每月1篇 | React核心，编程思维 |
| 6 | Dwarkesh Patel | `www.dwarkesh.com/feed` | Substack | 每1-2周 | 深度AI访谈，含完整文字稿 |
| 7 | Gary Marcus | `garymarcus.substack.com/feed` | Substack | 每日1-2篇 | AI怀疑派视角，平衡hype |
| 8 | Lenny's Newsletter | `lennysnewsletter.com/feed` | Substack(付费) | 每日/隔日 | 仅抓免费部分，产品增长 |
| 9 | Zara Zhang | `zarazhang.substack.com/feed` | Substack | 每月1篇 | AI+人文视角 |
| 10 | Construction Physics | `construction-physics.com/feed` | Substack | 每周2-3篇 | 工程创新与行业变革分析 |
| 11 | Latent Space | `latent.space/feed` | Substack | 每周1-2篇 | swyx主理，AI工程师深度访谈+日报 |
| 12 | TLDR AI | `tldr.tech/api/rss/ai` | TLDR | 每个工作日 | 每日AI/ML/论文短摘要，信息雷达 |

**每日预计内容量**: 高频源（Simon Willison、Gary Marcus、Lenny、Construction Physics、TLDR AI、Latent Space）每天可产出 8-15 篇，低频源月更。

## 核心功能流程

```
GitHub Actions 定时触发 (每天北京时间 6:00)
    │
    ▼
1. 抓取层：拉取12个RSS源的最新内容（过去24小时）
    │
    ▼
2. 解析层：提取标题、正文、作者、发布时间、原文链接
    │
    ▼
3. AI处理层：
    ├── 3a. 对每篇文章生成中文摘要（1-2句话 TL;DR）
    ├── 3b. 对每篇文章进行主题标签提取（如：LLM、产品策略、开源…）
    ├── 3c. 按主题聚类：同一话题下合并不同来源的观点
    ├── 3d. 双语逐段翻译（英文原文 + 中文译文对照，关键词高亮）
    ├── 3e. 提取1-2句作者金句（中英对照）
    └── 3f. 语气标注（🤔思辨/😤批评/🎉兴奋/🧪实验记录/📊分析/💡洞察）
    │
    ▼
4. 输出层：生成两个 RSS feed + HTML 页面
    ├── Feed A：每日日报（一条合并条目，按主题分板块）
    ├── Feed B：独立条目（每篇文章一条，含中文标题+双语翻译+关键词高亮）
    └── HTML：可视化页面（主题分布图+文章卡片+金句+语气标注）
    │
    ▼
5. 托管层：GitHub Pages 静态托管，供 Reeder 订阅
```

## 输出格式设计

### Feed B - 独立条目（Reeder 主要阅读体验）

```
标题: [翻译] Simon Willison: Claude的MCP协议实践体验  （中文标题，附英文原标题对照）
标签: #LLM #工具 #MCP
摘要: Simon分享了他使用Claude MCP协议的实际体验...
---
双语逐段翻译（英文原文灰色 #9a9ea6 + 中文译文深色 #2c2c2e）
关键词红色高亮（术语）+ 蓝色高亮（人名/公司名）
保留原文图片、代码块、引用等格式
---
🔗 原文链接
```

## 技术栈

- **语言**: Python 3.11+
- **RSS 解析**: feedparser
- **RSS 生成**: feedgen (python-feedgen)
- **AI API**: Kimi (Moonshot AI) 通过 OpenAI 兼容 API
  - 摘要+标签+金句+语气+中文标题: kimi-k2（轻量快速）
  - 双语翻译+日报生成: kimi-k2
  - 备选: Claude (anthropic SDK)，通过 LLM_PROVIDER 环境变量切换
- **定时任务**: GitHub Actions cron（每天 UTC 22:00 = 北京时间 6:00）
- **托管**: GitHub Pages（gh-pages 分支）
- **数据存储**: SQLite（记录已处理文章，避免重复翻译）

## 部署架构

- **源码**: `main` 分支 → GitHub Actions 读取执行
- **输出**: `gh-pages` 分支 → GitHub Pages 静态托管
- **RSS 订阅地址**:
  - 文章全文: `https://stella9625.github.io/newsletter-digest/articles.xml`
  - 每日日报: `https://stella9625.github.io/newsletter-digest/daily-digest.xml`
- **GitHub Secrets**: `MOONSHOT_API_KEY`

## 项目结构

```
newsletter-digest/
├── CLAUDE.md              # 本文件
├── pyproject.toml         # 依赖管理
├── .env                   # 本地环境变量（不提交）
├── src/
│   ├── __init__.py
│   ├── main.py            # 入口：串联整个流程
│   ├── config.py          # 配置：源列表、API keys、输出路径
│   ├── fetcher.py         # 抓取层：RSS解析 + 全文抓取
│   ├── processor.py       # AI处理层：摘要、翻译、聚类、金句、语气
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py        # AI模型抽象接口（LLMProvider）
│   │   ├── claude.py      # Claude适配器
│   │   └── kimi.py        # Kimi适配器（当前默认）
│   ├── generator.py       # 输出层：生成RSS feed XML + HTML页面
│   ├── storage.py         # SQLite：去重和历史记录
│   └── server.py          # 本地HTTP服务（调试用）
├── output/                # 生成的文件（gh-pages 分支独立管理）
├── data/                  # SQLite 数据库（不提交）
└── .github/
    └── workflows/
        └── daily.yml      # GitHub Actions 每日定时任务
```

## Article 数据结构

```python
@dataclass
class Article:
    url: str
    title: str                    # 英文原标题
    author: str
    source_name: str
    published_at: datetime | None
    content: str                  # 原文内容
    summary_zh: str = ""          # 中文摘要
    tags: list[str]               # 主题标签
    translation_zh: str = ""      # 双语翻译（HTML格式）
    quotes: list[dict]            # 金句 [{"en": "...", "zh": "..."}]
    tone: str = ""                # 语气标注，如 "🧪 实验记录"
    title_zh: str = ""            # 中文标题
```

## 运行命令

```bash
# 本地手动运行（所有源，过去1天）
python3 -m src.main --sources all --days 1

# 扩大时间窗口（过去3天）
python3 -m src.main --sources all --days 3

# 仅测试抓取，不调用AI
python3 -m src.main --sources all --dry-run

# 启动本地HTTP服务
python3 -m src.server

# 手动触发 GitHub Actions
gh workflow run daily.yml --repo Stella9625/newsletter-digest --ref main
```

## 成本估算（基于实际运行数据）

17 篇文章一次运行：
- 摘要: 17次, ~22K tokens
- 标签: 17次, ~23K tokens
- 翻译: 17次, ~108K tokens（双语HTML格式，输出较长）
- 金句+语气+标题: 17次, ~35K tokens
- 日报: 1次, ~4K tokens
- **总计**: ~190K tokens/次，Kimi 计费约几毛钱人民币

## 开发者偏好

- 讲解技术操作时，附带简短的原理/逻辑说明，便于举一反三
- 优先理解底层原理再动手，不要死记流程
- 代码注释用中文
- commit message 用英文
