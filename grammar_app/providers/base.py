"""
AI Provider 基类
所有厂家都需要继承这个基类并实现 check_grammar 方法
"""

from abc import ABC, abstractmethod


class BaseProvider(ABC):
    """AI 语法检查 Provider 基类"""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        json_mode: bool = False,
        thinking: bool = False,
        thinking_params: dict = None,
        thinking_disable_params: dict = None,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.json_mode = json_mode
        self.thinking = thinking
        self.thinking_params = thinking_params or {}
        self.thinking_disable_params = thinking_disable_params or {}

    @abstractmethod
    def check_grammar(self, text: str) -> dict:
        """
        检查语法语义

        Args:
            text: 待检查的文本

        Returns:
            {
                "format": "json" | "raw",
                "data": {...} | "原始文本"
            }
        """
        pass

    def get_prompt(self, text: str) -> str:
        """获取检查提示词，可以被子类覆盖"""
        return f"""你是一个专业的语法语义检查助手。请仔细检查以下文本的语法、语义和词汇拼写错误。

重要要求：
1. 请找出文本中所有可能的错误，不要遗漏任何一处
2. 包括语法错误、语义错误、拼写错误、标点错误、用词不当等
3. 即使是轻微的错误也应该标注
4. **重要**：error_text 必须与原文完全一致，逐字逐句，包括所有空格、标点符号
5. 不要标注原文中不存在的错误

请严格按照以下 JSON 格式返回结果，不要包含任何其他文字：

{{
  "has_error": true/false,
  "errors": [
    {{
      "error_text": "错误的文本内容（必须与原文完全一致）",
      "correct_text": "正确的文本内容",
      "reason": "错误原因说明"
    }}
  ],
  "optimized_text": "修正后的完整文本"
}}

如果未发现任何错误，has_error 为 false，errors 为空数组。

待检查的文本：
{text}"""

    def clean_json_response(self, text: str) -> str:
        """清理 markdown 代码块标记，并提取 JSON 对象"""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        # LLM 有时在 JSON 前后输出说明文字，直接定位第一个 { 和最后一个 }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]
        return text
