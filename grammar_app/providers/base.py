"""
AI Provider 基类
所有厂家都需要继承这个基类并实现 check_grammar 方法
"""

from abc import ABC, abstractmethod


CHECK_LIST = """## 检查清单
按以下维度逐项检查，不要遗漏：
1. **拼写**：错别字、英文拼写错误、同音字混淆
2. **语法**：主谓搭配、时态、语序、句式完整性
3. **标点**：标点使用是否正确、中英文标点是否混用
4. **语义**：用词是否准确、搭配是否得当、是否有歧义
5. **格式**：中英文间空格、全半角一致性"""


EXAMPLE = """## 示例

输入："我今天去了一个很好得餐厅，the food is delicous。"

输出：
{
  "has_error": true,
  "errors": [
    {
      "error_text": "好得",
      "correct_text": "好的",
      "reason": "结构助词误用：修饰名词应使用「的」而非「得」"
    },
    {
      "error_text": "delicous",
      "correct_text": "delicious",
      "reason": "英文拼写错误：缺少字母 i"
    },
    {
      "error_text": "。",
      "correct_text": ".",
      "reason": "英文句子末尾使用了中文句号，应统一标点风格"
    }
  ],
  "optimized_text": "我今天去了一个很好的餐厅，the food is delicious."
}"""


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
    def check_grammar(self, text: str = "", image: str = "") -> dict:
        """
        检查语法语义

        Args:
            text: 待检查的文本（文本模式）
            image: 图片 data URL，形如 "data:image/jpeg;base64,..."（图片模式）
            text 与 image 二选一。

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
        """文本模式提示词"""
        return f"""请检查以下文本，找出所有语法、拼写、标点和语义错误。

{CHECK_LIST}

{EXAMPLE}

## 输出格式
严格返回以下 JSON，不要包含任何其他文字：

{{
  "has_error": true/false,
  "errors": [
    {{
      "error_text": "原文中错误的精确子串",
      "correct_text": "修正后的文本",
      "reason": "错误类型 + 具体原因"
    }}
  ],
  "optimized_text": "修正后的完整文本"
}}

## 格式规则（重要，不得违反）
- optimized_text 必须与下方"待检查文本"的换行和段落结构完全一致（行数、空行位置、缩进、列表分行方式全部相同），仅在原位替换错误片段，不得重排、合并或拆分段落。
- 在 JSON 字符串中使用 \\n 表示换行；不要使用真实换行字符破坏 JSON。
- error_text 必须是原文的精确子串（含换行前后的字符）。
- 如果无错误，has_error 为 false，errors 为空数组，optimized_text 与原文完全相同（含换行结构）。

## 待检查文本
{text}"""

    def get_image_prompt(self) -> str:
        """图片模式提示词：先 OCR 再按相同规则检查"""
        return f"""请先准确识别图片中的所有文本（OCR），再对识别出的文本找出所有语法、拼写、标点和语义错误。

{CHECK_LIST}

{EXAMPLE}

## 输出格式
严格返回以下 JSON，不要包含任何其他文字：

{{
  "recognized_text": "从图片中识别出的完整原文",
  "has_error": true/false,
  "errors": [
    {{
      "error_text": "识别原文中错误的精确子串",
      "correct_text": "修正后的文本",
      "reason": "错误类型 + 具体原因"
    }}
  ],
  "optimized_text": "修正后的完整文本"
}}

## 格式规则（重要，不得违反）
- recognized_text 必须完整保留图片原文的段落与换行结构：标题、每个段落、每条列表项 / 题目选项（如 A. B. C. D.、1. 2. 3.）必须独立成行；图片中存在的空行也要保留为空行。绝对不允许把多段或多个选项合并成一行用空格分隔。
- optimized_text 必须与 recognized_text 的换行和段落结构完全一致（行数、空行位置、缩进、列表分行方式全部相同），仅在原位替换错误片段，不得重排、合并或拆分段落。
- 在 JSON 字符串中使用 \\n 表示换行；不要使用真实换行字符破坏 JSON。
- error_text 必须是 recognized_text 的精确子串（含换行前后的字符）。
- 如果无错误，has_error 为 false，errors 为空数组，optimized_text 与 recognized_text 完全相同（含换行结构）。"""

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

        # 容错：模型有时输出双大括号 {{ }}，修正为单大括号
        if text.startswith("{{") and not text.startswith("{"):
            text = "{" + text[2:]
        if text.endswith("}}") and not text.endswith("}"):
            text = text[:-2] + "}"

        # LLM 有时在 JSON 前后输出说明文字，直接定位第一个 { 和最后一个 }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            inner = text[start : end + 1]
            # 如果提取的内容内部有双大括号包裹，也尝试修正
            if inner.startswith("{{") and inner.endswith("}}"):
                inner = "{" + inner[2:-2] + "}"
            text = inner

        return text
