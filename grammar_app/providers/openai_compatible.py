"""
OpenAI 兼容格式的 Provider
支持：DeepSeek、OpenAI、智谱 AI、阿里云百炼、火山云 Ark 等
"""

import json
from openai import OpenAI
from .base import BaseProvider


class OpenAICompatibleProvider(BaseProvider):
    """OpenAI 兼容格式的 Provider"""

    def check_grammar(self, text: str = "", image: str = "", check_mode: str = "general") -> dict:
        if not text and not image:
            raise ValueError("text 与 image 必须提供其中之一")

        client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

        if check_mode == "student":
            system_prompt = self.get_student_system_prompt()
            prompt = self.get_student_image_prompt() if image else self.get_student_prompt(text)
        else:
            system_prompt = self.get_system_prompt()
            prompt = self.get_image_prompt() if image else self.get_prompt(text)

        if image:
            user_content = [
                {"type": "text", "text": prompt},
                # detail=high：手写小字场景需要高清识别
                {"type": "image_url", "image_url": {"url": image, "detail": "high"}},
            ]
        else:
            user_content = prompt

        try:
            kwargs = dict(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {"role": "user", "content": user_content},
                ],
            )
            print(f"[DEBUG] thinking={self.thinking} model={self.model} json_mode={self.json_mode} image={bool(image)} check_mode={check_mode}")
            if self.thinking:
                # 思考模式：合并厂商参数，禁用 json_mode（思考模型普遍不支持）
                kwargs.update(self.thinking_params)
            else:
                # 显式传递禁用思考的参数（部分厂商需要）
                if self.thinking_disable_params:
                    kwargs.update(self.thinking_disable_params)
                if self.json_mode:
                    kwargs["response_format"] = {"type": "json_object"}
            response = client.chat.completions.create(**kwargs)

            result_text = response.choices[0].message.content or ""
            print(f"[LLM RAW] {result_text}")
            result_text = self.clean_json_response(result_text)
            print(f"[LLM CLEANED] {result_text}")

            try:
                result = json.loads(result_text)
                return {"format": "json", "data": result}
            except json.JSONDecodeError:
                return {"format": "raw", "data": result_text}

        except Exception as e:
            raise Exception(f"API 调用失败: {str(e)}")
