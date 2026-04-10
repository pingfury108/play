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

    def get_system_prompt(self) -> str:
        """获取系统提示词，可以被子类覆盖"""
        return """你是一位资深的中英文语言校对专家，具备以下能力：
- 语法分析：主谓一致、时态、句式结构、中文语序
- 拼写检查：英文单词拼写、中文错别字、同音字混淆
- 标点规范：中英文标点使用规范、全半角一致性
- 语义审查：用词准确性、搭配是否得当、表达是否自然
- 格式规范：中英文之间的空格、数字与单位的使用

## 核心原则
1. 只标注确定的错误，不标注风格偏好或可接受的表达变体
2. error_text 必须是原文的精确子串，逐字符匹配（包括空格和标点）
3. 每个错误独立标注，不合并相邻错误
4. 如果文本无错误，直接返回无错误结果"""

    def get_prompt(self, text: str) -> str:
        """获取检查提示词，可以被子类覆盖"""
        return f"""请检查以下文本，找出所有语法、拼写、标点和语义错误。

## 检查清单
按以下维度逐项检查，不要遗漏：
1. **拼写**：错别字、英文拼写错误、同音字混淆
2. **语法**：主谓搭配、时态、语序、句式完整性
3. **标点**：标点使用是否正确、中英文标点是否混用
4. **语义**：用词是否准确、搭配是否得当、是否有歧义
5. **格式**：中英文间空格、全半角一致性

## 示例

输入："我今天去了一个很好得餐厅，the food is delicous。"

输出：
{{{{
  "has_error": true,
  "errors": [
    {{{{
      "error_text": "好得",
      "correct_text": "好的",
      "reason": "结构助词误用：修饰名词应使用「的」而非「得」"
    }}}},
    {{{{
      "error_text": "delicous",
      "correct_text": "delicious",
      "reason": "英文拼写错误：缺少字母 i"
    }}}},
    {{{{
      "error_text": "。",
      "correct_text": "。",
      "reason": "英文句子末尾使用了中文句号，应统一标点风格"
    }}}}
  ],
  "optimized_text": "我今天去了一个很好的餐厅，the food is delicious."
}}}}

## 输出格式
严格返回以下 JSON，不要包含任何其他文字：

{{{{
  "has_error": true/false,
  "errors": [
    {{{{
      "error_text": "原文中错误的精确子串",
      "correct_text": "修正后的文本",
      "reason": "错误类型 + 具体原因"
    }}}}
  ],
  "optimized_text": "修正后的完整文本"
}}}}

如果无错误，has_error 为 false，errors 为空数组，optimized_text 与原文相同。

## 待检查文本
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
