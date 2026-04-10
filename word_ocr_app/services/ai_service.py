"""
AI 服务封装
复用 grammar_app 的 provider 工厂
"""

import sys
import os
import json
import base64

# 添加 grammar_app 到路径以复用 provider
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "grammar_app"))

from providers.factory import create_provider


class AIService:
    """AI 服务封装"""

    def __init__(self, provider_name: str = "ark", model: str = None):
        """
        初始化 AI 服务

        Args:
            provider_name: 提供商名称，默认 ark（豆包）
            model: 模型名称，默认从环境变量读取
        """
        self.provider = create_provider(provider_name, model, thinking=False)

    def recognize_image(self, image_path: str) -> dict:
        """
        识别图片中的单词和例句

        Args:
            image_path: 图片文件路径

        Returns:
            {
                "word": "单词",
                "cet4_count": 28,
                "examples": [
                    {
                        "seq_num": 1,
                        "original_text": "完整英文原文",
                        "source": "四级2025-6-第2套 听力"
                    }
                ]
            }
        """
        # 读取图片并转为 base64
        with open(image_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode("utf-8")

        system_prompt = """你是一个专业的英语真题 OCR 识别助手。请仔细识别图片中的单词和例句信息。

## 图片结构说明
图片包含以下部分：
1. **顶部**：单词（大字标题）、音标、词性释义
2. **标签栏**：柯林斯、例句、派生、词根、近义、真题、笔记
3. **考试类型标签**：中考、高考、四级、六级、考研、专升本、雅思（通常"四级"被选中）
4. **出现次数**："在历年真题中出现 X 次"
5. **例句列表**：每个例句包含：
   - 序号（如 6.、7.、21.）
   - 英文题目或句子原文（可能包含 A/B/C/D 选项）
   - 来源信息（如"四级 2025-6-第 2 套 听力"）

## 输出格式
输出严格的 JSON 格式：
{
  "word": "单词",
  "cet4_count": 28,
  "examples": [
    {
      "seq_num": 6,
      "original_text": "完整的英文原文，包括题目和选项",
      "source": "四级2025-6-第2套 听力"
    }
  ]
}

## 字段提取规则

1. **word**：提取图片顶部最大的单词标题（如 "abandon"）

2. **cet4_count**：提取"在历年真题中出现 X 次"中的数字 X

3. **examples 数组**：每个例句一个对象
   - **seq_num**：提取序号（只取数字，如 "6."→6, "21."→21）
   - **original_text**：提取完整的英文原文
     - 如果是选择题，保留题目和所有选项 A/B/C/D
     - 保留完整的句子或段落
     - 去除来源信息（如"四级 2025-6-第 2 套 听力"）
   - **source**：提取来源信息，格式化为"四级YYYY-M-第N套 类型"
     - 从原文底部提取，如"四级 2025-6-第 2 套 听力"→"四级2025-6-第2套 听力"
     - 类型包括：听力、阅读、写作、翻译

## 注意事项
- 严格按照图片中的顺序排列 examples
- 确保 seq_num 与图片中的序号一致
- source 字段去除多余空格，统一格式
- 如果某个字段无法识别，使用空字符串或 0"""

        user_prompt = """请识别这张图片中的单词和例句信息。

重点关注：
1. 图片顶部的大字单词是什么？
2. "在历年真题中出现 X 次"中的 X 是多少？
3. 列出所有例句，每个例句包含：
   - 序号（如 6、7、21）
   - 完整英文原文（题目+选项，或完整句子）
   - 来源（如"四级2025-6-第2套 听力"）

请严格按照 system_prompt 中的 JSON 格式输出。"""

        # 构建消息，包含图片
        print(f"[DEBUG] 开始调用 AI API，模型: {self.provider.model}")
        from openai import OpenAI

        client = OpenAI(
            api_key=self.provider.api_key,
            base_url=self.provider.base_url,
        )

        print(f"[DEBUG] 发送请求到 AI...")
        try:
            response = client.chat.completions.create(
                model=self.provider.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                },
                            },
                        ],
                    },
                ],
                temperature=0.1,
            )
        except Exception as e:
            print(f"[ERROR] AI API 调用失败: {str(e)}")
            raise

        print(f"[DEBUG] AI 响应收到")
        result_text = response.choices[0].message.content or ""
        print(f"[DEBUG] 原始响应长度: {len(result_text)}")
        result_text = self._clean_json_response(result_text)

        try:
            result = json.loads(result_text)
            print(f"[DEBUG] JSON 解析成功")
            return result
        except json.JSONDecodeError as e:
            raise Exception(f"JSON 解析失败: {str(e)}\n原始响应: {result_text}")

    def translate_text(self, text: str) -> str:
        """
        翻译英文文本

        Args:
            text: 英文原文

        Returns:
            中文翻译
        """
        system_prompt = """你是一个专业的英译中翻译助手。请将以下英文翻译成中文。

注意：
1. 如果是题目，保留选项格式（A/B/C/D）
2. 翻译要准确、通顺
3. 保持原文的段落和格式

输出严格的 JSON 格式：
{
  "translation": "中文翻译内容"
}"""

        user_prompt = f"请翻译以下内容：\n\n{text}"

        from openai import OpenAI

        client = OpenAI(
            api_key=self.provider.api_key,
            base_url=self.provider.base_url,
        )

        response = client.chat.completions.create(
            model=self.provider.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )

        result_text = response.choices[0].message.content or ""
        result_text = self._clean_json_response(result_text)

        try:
            result = json.loads(result_text)
            return result.get("translation", "")
        except json.JSONDecodeError:
            # 如果解析失败，返回原始内容
            return result_text

    def _clean_json_response(self, text: str) -> str:
        """清理 markdown 代码块标记，并提取 JSON 对象"""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        # 定位第一个 { 和最后一个 }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]

        return text
