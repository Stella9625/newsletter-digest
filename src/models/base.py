"""AI 模型抽象基类：定义统一接口，方便切换不同的 LLM provider"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class TokenUsage:
    """Token 用量统计"""
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    operation: str = ""  # "summarize" / "translate" / "extract_tags" / "daily_report"


class LLMProvider(ABC):
    """LLM 提供者的抽象接口"""

    def __init__(self):
        # 累积所有调用的 token 用量
        self.usage_log: list[TokenUsage] = []

    @abstractmethod
    def summarize(self, text: str, title: str = "") -> str:
        """生成中文摘要（1-2 句话 TL;DR）"""
        ...

    @abstractmethod
    def extract_tags(self, text: str, title: str = "") -> list[str]:
        """提取主题标签（如：LLM、产品策略、开源）"""
        ...

    @abstractmethod
    def translate(self, text: str, title: str = "") -> str:
        """全文翻译为中文"""
        ...

    @abstractmethod
    def generate_daily_report(self, articles_data: list[dict]) -> str:
        """根据已处理文章生成每日日报内容"""
        ...

    @abstractmethod
    def extract_quotes_and_tone(self, text: str, title: str = "") -> dict:
        """
        提取金句 + 检测语气（合并为一次调用以节省 token）。
        返回格式: {"quotes": [{"en": "...", "zh": "..."}], "tone": "🧪 实验记录"}
        """
        ...

    def get_total_usage(self) -> dict:
        """统计总 token 用量"""
        total_input = sum(u.input_tokens for u in self.usage_log)
        total_output = sum(u.output_tokens for u in self.usage_log)

        # 按操作类型汇总
        by_operation: dict[str, dict] = {}
        for u in self.usage_log:
            if u.operation not in by_operation:
                by_operation[u.operation] = {"input": 0, "output": 0, "count": 0}
            by_operation[u.operation]["input"] += u.input_tokens
            by_operation[u.operation]["output"] += u.output_tokens
            by_operation[u.operation]["count"] += 1

        return {
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_calls": len(self.usage_log),
            "by_operation": by_operation,
        }
