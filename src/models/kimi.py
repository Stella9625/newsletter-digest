"""Kimi (Moonshot AI) 适配器：通过 OpenAI 兼容 API 实现摘要、翻译、标签提取和日报生成"""

import json
import logging

from openai import OpenAI

from src.config import MOONSHOT_API_KEY, KIMI_LIGHT_MODEL, KIMI_MODEL
from src.models.base import LLMProvider, TokenUsage

logger = logging.getLogger(__name__)

# 截断超长文本，避免 token 浪费
MAX_TEXT_LENGTH = 30000


def _truncate(text: str, max_len: int = MAX_TEXT_LENGTH) -> str:
    if len(text) > max_len:
        return text[:max_len] + "\n\n[... 内容过长，已截断]"
    return text


class KimiProvider(LLMProvider):
    def __init__(self, api_key: str = MOONSHOT_API_KEY):
        super().__init__()
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.kimi.com/coding/v1",
            default_headers={"User-Agent": "claude-code/1.0"},
        )

    def _call(self, model: str, system: str, user_msg: str, operation: str) -> str:
        """统一的 API 调用入口，记录 token 用量"""
        response = self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.3,
        )

        # 记录 token 用量
        usage = TokenUsage(
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            model=model,
            operation=operation,
        )
        self.usage_log.append(usage)
        logger.debug(
            f"  [{operation}] {model} - input: {usage.input_tokens}, output: {usage.output_tokens}"
        )

        return response.choices[0].message.content

    def summarize(self, text: str, title: str = "") -> str:
        """用轻量模型生成中文摘要"""
        system = "你是一个专业的科技内容编辑。请为以下英文文章生成简洁的中文摘要（1-2句话），要求准确传达核心观点，语言流畅自然。"
        user_msg = f"文章标题: {title}\n\n文章内容:\n{_truncate(text)}"

        return self._call(KIMI_LIGHT_MODEL, system, user_msg, "summarize")

    def extract_tags(self, text: str, title: str = "") -> list[str]:
        """用轻量模型提取主题标签"""
        system = (
            "你是一个内容分类专家。请为以下英文文章提取 2-4 个中文主题标签。"
            "标签应该简洁（2-4字），覆盖文章的核心主题。"
            "只返回 JSON 数组格式，例如: [\"LLM\", \"开源\", \"工具\"]"
        )
        user_msg = f"文章标题: {title}\n\n文章内容:\n{_truncate(text, 5000)}"

        result = self._call(KIMI_LIGHT_MODEL, system, user_msg, "extract_tags")

        # 解析 JSON 数组
        try:
            cleaned = result.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            tags = json.loads(cleaned)
            if isinstance(tags, list):
                return [str(t) for t in tags]
        except (json.JSONDecodeError, ValueError):
            logger.warning(f"标签解析失败，原始返回: {result}")
            return [t.strip().strip('"#') for t in result.split(",") if t.strip()]

        return []

    def translate(self, text: str, title: str = "") -> str:
        """用 32k 模型全文翻译，输出双语对照 HTML"""
        system = (
            "你是一个专业的英中翻译。请将以下英文科技文章翻译为双语对照格式的 HTML。\n\n"
            "**输出格式要求（严格遵守）：**\n"
            "- 逐段翻译：每一段英文原文后紧跟其中文翻译\n"
            "- 英文原文直接展示，用 <div style=\"color:#8e8e93;font-size:14px;line-height:1.7;margin:20px 0 6px;\"> 包裹。注意：原文中如果有引用、列表、代码等格式，需要在 div 内部用对应 HTML 标签正确渲染，不要丢弃原文格式。\n"
            "- 中文翻译用 <p style=\"margin:4px 0 24px;line-height:1.8;font-size:15px;\"> 包裹，与下一段英文原文之间通过较大的 margin 留白分隔。\n"
            "- 如果原文中有图片（markdown 格式 ![alt](url)），在对应位置输出 <img src=\"url\" alt=\"alt\" style=\"max-width:100%;border-radius:8px;margin:12px 0;\"/>\n"
            "- 代码块用 <pre style=\"background:#1d1d1f;color:#f5f5f7;padding:16px;border-radius:8px;overflow-x:auto;font-size:13px;margin:12px 0;\"><code>代码内容</code></pre>\n"
            "- 行内代码用 <code style=\"background:#f0f0f5;padding:2px 6px;border-radius:4px;font-size:13px;\">代码</code>\n"
            "- **关键词高亮**：对文章中的重要术语、产品名、技术概念，用 <strong style=\"color:#c0392b;background:#fdf2f2;padding:1px 4px;border-radius:3px;\">关键词</strong>（红色高亮）标注；对人名、公司名用 <strong style=\"color:#2471a3;background:#eaf4fd;padding:1px 4px;border-radius:3px;\">名称</strong>（蓝色高亮）标注。中英文段落都可以标注关键词，每段标注 2-4 个即可，不要过度标注。\n"
            "- 标题用 <h3 style=\"margin:24px 0 12px;\"> 或 <h4>\n"
            "- 原文中的引用块用 <blockquote style=\"border-left:3px solid #c0c0c0;padding:8px 16px;margin:8px 0;background:#f9f9fb;\"> 正确渲染\n"
            "- 原文中的列表用 <ul>/<ol> + <li> 正确渲染\n"
            "- 专业术语保留英文原文（首次出现时在括号内标注中文）\n"
            "- 翻译风格：准确、流畅、不过度意译\n\n"
            "**直接输出 HTML，不要包裹在 markdown 代码块中。**"
        )
        user_msg = f"文章标题: {title}\n\n请翻译以下内容:\n\n{_truncate(text)}"

        return self._call(KIMI_MODEL, system, user_msg, "translate")

    def extract_quotes_and_tone(self, text: str, title: str = "") -> dict:
        """用轻量模型提取金句 + 检测语气 + 翻译标题（一次调用）"""
        system = (
            "你是一个专业的内容分析师。请完成以下三个任务：\n"
            "1. 将文章英文标题翻译为简洁的中文标题\n"
            "2. 从文章中提取 1-2 句最有作者个人风格的原文金句，并翻译为中文\n"
            "3. 判断文章的整体语气，从以下 6 种中选 1 个：\n"
            "   🤔 思辨 / 😤 批评 / 🎉 兴奋 / 🧪 实验记录 / 📊 分析 / 💡 洞察\n\n"
            "返回 JSON 格式，不要包含 markdown 代码块标记：\n"
            '{"title_zh": "中文标题", "quotes": [{"en": "原文句子", "zh": "中文翻译"}], "tone": "🧪 实验记录"}'
        )
        user_msg = f"文章标题: {title}\n\n文章内容:\n{_truncate(text, 8000)}"

        result = self._call(KIMI_LIGHT_MODEL, system, user_msg, "quotes_and_tone")

        try:
            cleaned = result.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            data = json.loads(cleaned)
            quotes = data.get("quotes", [])
            tone = data.get("tone", "💡 洞察")
            title_zh = data.get("title_zh", "")
            valid_quotes = []
            for q in quotes:
                if isinstance(q, dict) and "en" in q and "zh" in q:
                    valid_quotes.append({"en": q["en"], "zh": q["zh"]})
            return {"quotes": valid_quotes, "tone": tone, "title_zh": title_zh}
        except (json.JSONDecodeError, ValueError):
            logger.warning(f"金句+语气解析失败，原始返回: {result}")
            return {"quotes": [], "tone": "💡 洞察", "title_zh": ""}

    def generate_daily_report(self, articles_data: list[dict]) -> str:
        """用 32k 模型生成每日日报"""
        system = (
            "你是一个科技领域的内容编辑，负责编写每日 AI/产品/技术日报。\n"
            "请根据提供的文章信息，按主题分类组织成一份简洁的日报。\n"
            "格式要求：\n"
            "- 按主题聚类（如：LLM & AI 工具、产品与增长、工程与系统设计、跨界与深度思考）\n"
            "- 每个板块下列出相关文章，用 1-2 句话总结要点\n"
            "- 标注作者来源\n"
            "- 语言简洁，突出关键信息"
        )

        articles_text = ""
        for a in articles_data:
            tags_str = ", ".join(a.get("tags", []))
            articles_text += (
                f"---\n"
                f"标题: {a['title']}\n"
                f"作者: {a.get('author', '未知')}\n"
                f"来源: {a.get('source_name', '未知')}\n"
                f"标签: {tags_str}\n"
                f"摘要: {a.get('summary_zh', '')}\n\n"
            )

        user_msg = f"以下是今日收集的文章信息，请生成日报:\n\n{articles_text}"

        return self._call(KIMI_MODEL, system, user_msg, "daily_report")
