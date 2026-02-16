# Newsletter 聚合翻译工具

## 项目概述

将 12 个英文 Newsletter/博客源每日聚合，通过 AI 进行主题聚类、翻译和摘要，生成 RSS feed 供 Feeder 阅读器订阅。目标是每天早上在 Feeder 里用中文快速浏览全球 AI/产品/技术领域的重要内容。

## 订阅源清单

所有源均通过 RSS 获取，不走邮件。

| # | 名称 | RSS Feed URL | 类型 | 备注 |
|---|------|-------------|------|------|
| 1 | Simon Willison | `simonwillison.net/atom/everything/` | 独立博客 | AI工具实操，更新极高频 |
| 2 | Mitchell Hashimoto | `mitchellh.com/feed` | 独立博客 | 底层工程原理 |
| 3 | Antirez | `antirez.com/rss` | 独立博客 | Redis作者，系统设计 |
| 4 | Andrej Karpathy | `karpathy.bearblog.dev/feed/` + `karpathy.substack.com/feed` | 博客+Substack | AI研究+教育，两个源合并 |
| 5 | Dan Abramov | `overreacted.io/rss.xml` | 独立博客 | React核心，编程思维 |
| 6 | Dwarkesh Patel | `dwarkesh.com` (需确认feed路径) | 独立博客 | 深度AI访谈 |
| 7 | Gary Marcus | `garymarcus.substack.com/feed` | Substack | AI怀疑派视角 |
| 8 | Lenny's Newsletter | `lennysnewsletter.com/feed` | Substack(付费) | 仅抓免费部分，产品增长 |
| 9 | Zara Zhang | `zarazhang.substack.com/feed` | Substack | AI+人文视角 |
| 10 | Gwern | `gwern.net/feed` | 独立博客 | 深度长文，AI/心理学/统计 |
| 11 | Construction Physics | `construction-physics.com/feed` | Substack | 工程创新与行业分析 |
| 12 | AI News by swyx | `buttondown.email/ainews/rss` | Buttondown | 每日AI领域全景汇总 |

## 核心功能流程

```
定时触发 (每天一次)
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
    └── 3d. 全文翻译（中文）
    │
    ▼
4. 输出层：生成两个 RSS feed
    ├── Feed A：每日日报（一条合并条目，按主题分板块）
    └── Feed B：独立条目（每篇文章一条，附主题标签+中文摘要+全文翻译）
    │
    ▼
5. 托管层：本地HTTP服务或静态文件，供 Feeder 订阅
```

## 输出格式设计

### Feed A - 每日日报（单条）

```
标题: 📰 AI/产品/技术日报 - 2026-02-15
内容:
  ## 🔥 LLM & AI 工具
  - Simon Willison 讨论了 Claude 的新 MCP 功能...
  - Karpathy 发布了关于 microGPT 的新文章...
  - Gary Marcus 对最新 benchmark 结果表示质疑...

  ## 📦 产品与增长
  - Lenny 分析了生态系统作为增长渠道的趋势...
  - Zara Zhang 探讨了非技术背景PM的AI转型路径...

  ## 🔧 工程与系统设计
  - Mitchell Hashimoto 深入讲解了终端渲染管线...
  - Antirez 发布了关于数据结构优化的思考...

  ## 🌍 跨界与深度思考
  - Gwern 更新了关于缩放假说的长文...
  - Construction Physics 分析了为什么核电站造价越来越高...
```

### Feed B - 独立条目（每篇一条）

```
标题: [翻译] Simon Willison: Claude的MCP协议实践体验
标签: #LLM #工具 #MCP
摘要: Simon分享了他使用Claude MCP协议连接本地数据库的实际体验，认为这是目前最实用的AI-工具集成方案。
---
全文翻译内容...
---
🔗 原文链接: https://simonwillison.net/...
```

## 技术栈

- **语言**: Python 3.11+
- **RSS 解析**: feedparser
- **RSS 生成**: feedgen (python-feedgen)
- **AI API**: anthropic SDK (Claude)
  - 摘要+标签提取: claude-haiku（成本低、速度快）
  - 全文翻译: claude-sonnet（翻译质量优先）
  - 主题聚类+日报生成: claude-sonnet
- **HTTP 服务**: 简单的 Python http.server 或 Flask 托管生成的 RSS XML
- **定时任务**: 
  - 开发阶段: 手动触发
  - 过渡阶段: GitHub Actions cron
  - 最终: macOS launchd
- **数据存储**: SQLite（记录已处理文章，避免重复翻译）

## 架构设计原则

1. **模块化**: 抓取、AI处理、输出各自独立，方便单独调试和替换
2. **模型可切换**: AI 调用层抽象为接口，预留 Kimi/GPT 等模型适配器
3. **幂等性**: 同一篇文章不会重复翻译，用 SQLite 记录文章 URL 的 hash
4. **容错**: 单个源抓取失败不影响其他源，AI 调用失败有重试机制
5. **成本可控**: 日志记录每次 API 调用的 token 消耗和费用

## 项目结构（建议）

```
newsletter-digest/
├── CLAUDE.md              # 本文件
├── README.md              # 项目说明
├── pyproject.toml         # 依赖管理
├── src/
│   ├── __init__.py
│   ├── main.py            # 入口：串联整个流程
│   ├── config.py          # 配置：源列表、API keys、输出路径
│   ├── fetcher.py         # 抓取层：RSS解析
│   ├── processor.py       # AI处理层：摘要、翻译、聚类
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py        # AI模型抽象接口
│   │   ├── claude.py      # Claude适配器
│   │   └── kimi.py        # Kimi适配器（预留）
│   ├── generator.py       # 输出层：生成RSS feed XML
│   ├── storage.py         # SQLite：去重和历史记录
│   └── server.py          # 本地HTTP服务托管RSS
├── output/                # 生成的RSS XML文件
├── data/                  # SQLite 数据库
├── tests/
└── .github/
    └── workflows/
        └── daily.yml      # GitHub Actions 定时任务
```

## 部署路径

### 阶段1: MacBook 本地开发
- 手动运行 `python src/main.py`
- 验证完整流程：抓取→翻译→生成RSS→Feeder能订阅
- 本地起 http.server 在 localhost:8080 托管 RSS

### 阶段2: GitHub Actions 过渡
- 每天定时触发（如北京时间早上7点）
- 生成的 RSS XML 推送到 GitHub Pages 或 R2/S3
- Feeder 订阅这个公网 URL

### 阶段3: Mac mini 长期运行
- git pull 代码到 Mac mini
- launchd 配置每日定时任务
- 本地 HTTP 服务托管 RSS
- 可选：配置 Tailscale 远程管理

## 成本估算（待开发时精算）

每日大约处理 5-15 篇新文章（不是所有源每天都更新），估算：
- 摘要+标签 (Haiku): ~2K tokens/篇 × 15篇 = ~30K tokens/天
- 全文翻译 (Sonnet): ~5K tokens/篇 × 15篇 = ~75K tokens/天  
- 日报聚合 (Sonnet): ~10K tokens/天
- 预估月费用: 需要根据实际文章长度测算，开发时加入 token 计数日志

## 开发者偏好

- 讲解技术操作时，附带简短的原理/逻辑说明，便于举一反三
- 优先理解底层原理再动手，不要死记流程
- 代码注释用中文
- commit message 用英文
