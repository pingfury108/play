import os
import sys
import traceback
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from openai import OpenAI

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(BASE_DIR, ".env")
load_dotenv(env_path)

app = Flask(__name__)
CORS(app)

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

print(f"[DEBUG] .env 文件路径: {env_path}")
print(f"[DEBUG] .env 文件存在: {os.path.exists(env_path)}")
print(f"[DEBUG] DEEPSEEK_API_KEY: {'已设置' if DEEPSEEK_API_KEY else '未设置'}")
print(f"[DEBUG] DEEPSEEK_BASE_URL: {DEEPSEEK_BASE_URL}")


def check_grammar(text):
    """使用 DeepSeek 检查语法语义"""
    if not DEEPSEEK_API_KEY:
        raise Exception("DeepSeek API Key 未设置")

    client = OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
    )

    prompt = f"""你是一个专业的语法语义检查助手。请仔细检查以下文本的语法、语义和词汇拼写错误。

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

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": "你是一个专业的语法语义检查助手，擅长中英文文本的语法、语义和拼写检查。必须仔细检查文本，找出所有可能的错误，不要遗漏任何一处。",
                },
                {"role": "user", "content": prompt},
            ],
        )

        result_text = response.choices[0].message.content or ""

        import json
        import re

        # 清理 markdown 代码块标记
        result_text = result_text.strip()
        if result_text.startswith("```json"):
            result_text = result_text[7:]  # 去掉 ```json
        elif result_text.startswith("```"):
            result_text = result_text[3:]  # 去掉 ```
        if result_text.endswith("```"):
            result_text = result_text[:-3]  # 去掉末尾 ```
        result_text = result_text.strip()

        try:
            result = json.loads(result_text)
            return {"format": "json", "data": result}
        except json.JSONDecodeError:
            # 如果解析失败，返回原始文本
            return {"format": "raw", "data": result_text}

    except Exception as e:
        raise Exception(f"DeepSeek API 调用失败: {str(e)}")


@app.route("/")
def index():
    return render_template("grammar.html")


@app.route("/check", methods=["POST"])
def check():
    """语法语义检查 API"""
    data = request.get_json()
    if not data or "text" not in data:
        return jsonify({"error": "缺少 text 参数"}), 400

    text = data["text"].strip()
    if not text:
        return jsonify({"error": "文本不能为空"}), 400

    if len(text) > 5000:
        return jsonify({"error": "文本长度超过限制（最大 5000 字符）"}), 400

    try:
        result = check_grammar(text)
        return jsonify({"success": True, "result": result})

    except Exception as e:
        error_detail = traceback.format_exc()
        print(f"[CHECK ERROR] {error_detail}")
        return jsonify(
            {
                "error": str(e),
                "error_type": type(e).__name__,
                "detail": error_detail,
            }
        ), 500


if __name__ == "__main__":
    port = 5002
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"错误: 无效的端口号 '{sys.argv[1]}'，使用默认端口 5002")

    print(f"启动语法语义检查服务，访问 http://localhost:{port}")
    app.run(debug=True, host="0.0.0.0", port=port)
