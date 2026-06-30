import os
import sys
import re
import traceback
import base64
from io import BytesIO

from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(BASE_DIR, ".env")
load_dotenv(env_path)

app = Flask(__name__)
CORS(app)

# 配置（无前缀，简洁命名）
API_KEY = os.environ.get("API_KEY", "")
BASE_URL = os.environ.get("BASE_URL", "https://www.dmxapi.com/v1")
MODEL = os.environ.get("MODEL", "gpt-image-2")

# 固化提示词模板
# 中文说明：根据英文例句创作一幅鲜艳卡通/动画风格插画，画面需体现单词释义，
#          图片中绝对不能出现任何文字、字母、数字或字幕，纯视觉画面表达。
PROMPT_TEMPLATE = (
    'Create a vibrant cartoon/animation style illustration depicting the scene from '
    'this English sentence: "{english_sentence}". '
    'The scene should visually express: {meaning}. '
    'Do not include any text, words, letters, numbers, or captions in the image. '
    'Pure visual storytelling in colorful animation style. High quality, detailed.'
)


def parse_word_input(text: str) -> dict:
    """
    解析用户输入的单词+例句格式。

    预期格式: 单词 词性.释义;英文例句中文翻译
    例: abandon v.放弃(信念、信仰或看法);By 1930 he had abandoned his Marxist principles.1930 年时他已放弃了马克思主义信念。

    返回: {"word", "pos_meaning", "english_sentence", "chinese_translation"}
    """
    result = {
        "word": "",
        "pos_meaning": "",
        "english_sentence": "",
        "chinese_translation": "",
    }

    text = text.strip()
    if not text:
        return result

    # 1. 用分号把 "单词 释义" 和 "例句" 分开
    parts = [p.strip() for p in text.split(";", 1)]

    # 2. 前半部分: 单词 + 词性释义
    if parts:
        first = parts[0]
        # 第一个空格分单词和释义
        space_idx = first.find(" ")
        if space_idx > 0:
            result["word"] = first[:space_idx].strip()
            result["pos_meaning"] = first[space_idx + 1 :].strip()
        else:
            result["word"] = first

    # 3. 后半部分: 例句
    if len(parts) > 1:
        sentence_text = parts[1]
        # 找到第一个中文字符的位置，把英文例句和中文翻译分开
        match = re.search(r"[\u4e00-\u9fff]", sentence_text)
        if match:
            result["english_sentence"] = sentence_text[: match.start()].strip(
                " ."
            ) + "."
            result["chinese_translation"] = sentence_text[match.start() :].strip()
        else:
            result["english_sentence"] = sentence_text

    return result


def build_image_prompt(parsed: dict) -> str:
    """根据解析结果构建图像生成提示词。"""
    english_sentence = parsed.get("english_sentence", "").strip()
    meaning = parsed.get("pos_meaning", "").strip()

    # 如果没有解析出英文例句，直接用原始输入兜底
    if not english_sentence:
        english_sentence = parsed.get("word", "")
    if not meaning:
        meaning = "the given concept"

    return PROMPT_TEMPLATE.format(english_sentence=english_sentence, meaning=meaning)


def convert_to_jpg(image_data: bytes) -> bytes:
    """将图片字节流转为 JPG 格式。"""
    img = Image.open(BytesIO(image_data))
    # 去掉透明通道（JPG 不支持透明）
    if img.mode in ("RGBA", "P"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[3])  # 使用 alpha 通道作为 mask
        img = background
    else:
        img = img.convert("RGB")

    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=92)
    buffer.seek(0)
    return buffer.getvalue()


def bytes_to_jpg_data_url(image_bytes: bytes) -> str:
    """将图片字节流转为 JPG 的 base64 data URL。"""
    jpg_bytes = convert_to_jpg(image_bytes)
    b64 = base64.b64encode(jpg_bytes).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


def generate_image(prompt: str) -> dict:
    """调用图像模型生成图片，返回包含 image data URL 和 prompt 的字典。"""
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    response = client.images.generate(
        model=MODEL,
        prompt=prompt,
        n=1,
    )

    image_item = response.data[0]

    # 获取图片原始字节
    if image_item.b64_json:
        raw_bytes = base64.b64decode(image_item.b64_json)
    elif image_item.url:
        import urllib.request

        req = urllib.request.Request(
            image_item.url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw_bytes = resp.read()
    else:
        raise Exception("模型未返回图片数据")

    # 转为 JPG
    jpg_data_url = bytes_to_jpg_data_url(raw_bytes)
    print(f"[DEBUG] 成功生成 JPG，data URL 长度: {len(jpg_data_url)}")

    return {"image": jpg_data_url, "prompt": prompt}


@app.route("/")
def index():
    return render_template("image_gen.html")


@app.route("/general")
def general_index():
    return render_template("general_gen.html")


@app.route("/generate", methods=["POST"])
def generate():
    """单词学习图片生成 API（使用默认提示词模板）"""
    if not API_KEY:
        return jsonify({"error": "API Key 未设置，请检查 .env 文件"}), 500

    data = request.get_json()
    if not data:
        return jsonify({"error": "请求体为空"}), 400

    raw_input = (data.get("prompt") or "").strip()
    if not raw_input:
        return jsonify({"error": "输入不能为空"}), 400

    # 解析用户输入
    parsed = parse_word_input(raw_input)
    image_prompt = build_image_prompt(parsed)

    print(f"[DEBUG] 单词: {parsed['word']}, 模型: {MODEL}")
    print(f"[DEBUG] 图像提示词: {image_prompt}")

    try:
        result = generate_image(image_prompt)
        return jsonify(
            {
                "success": True,
                "image": result["image"],
                "word": parsed["word"],
                "prompt": result["prompt"],
            }
        )

    except Exception as e:
        error_detail = traceback.format_exc()
        print(f"[GENERATE ERROR] {error_detail}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "detail": error_detail,
                }
            ),
            500,
        )


@app.route("/generate-general", methods=["POST"])
def generate_general():
    """通用提示词图片生成 API（直接使用用户输入，不套用模板）"""
    if not API_KEY:
        return jsonify({"error": "API Key 未设置，请检查 .env 文件"}), 500

    data = request.get_json()
    if not data:
        return jsonify({"error": "请求体为空"}), 400

    prompt = (data.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"error": "提示词不能为空"}), 400

    print(f"[DEBUG] 通用生成, 模型: {MODEL}")
    print(f"[DEBUG] 图像提示词: {prompt}")

    try:
        result = generate_image(prompt)
        return jsonify(
            {
                "success": True,
                "image": result["image"],
                "prompt": result["prompt"],
            }
        )

    except Exception as e:
        error_detail = traceback.format_exc()
        print(f"[GENERATE GENERAL ERROR] {error_detail}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "detail": error_detail,
                }
            ),
            500,
        )


@app.route("/download", methods=["POST"])
def download():
    """下载生成的 JPG 图片"""
    data = request.get_json()
    if not data or "image" not in data:
        return jsonify({"error": "缺少图片数据"}), 400

    image_data = data["image"]
    filename = data.get("filename", "word_card.jpg")

    try:
        if image_data.startswith("data:image/jpeg;base64,"):
            encoded = image_data.split(",", 1)[1]
            image_bytes = base64.b64decode(encoded)
        elif image_data.startswith("data:image/"):
            # 兜底：任何 data URL 都重新转一次 JPG
            header, encoded = image_data.split(",", 1)
            raw_bytes = base64.b64decode(encoded)
            image_bytes = convert_to_jpg(raw_bytes)
        elif image_data.startswith("http"):
            return jsonify({"error": "暂不支持直接下载远程 URL，请右键保存图片"}), 400
        else:
            image_bytes = base64.b64decode(image_data)

        buffer = BytesIO(image_bytes)
        return send_file(
            buffer,
            mimetype="image/jpeg",
            as_attachment=True,
            download_name=filename,
        )

    except Exception as e:
        error_detail = traceback.format_exc()
        print(f"[DOWNLOAD ERROR] {error_detail}")
        return jsonify({"error": str(e), "detail": error_detail}), 500


if __name__ == "__main__":
    port = 5004
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"错误: 无效的端口号 '{sys.argv[1]}'，使用默认端口 5004")

    print(f"启动 AI 图像生成服务，访问 http://localhost:{port}")
    app.run(debug=True, host="0.0.0.0", port=port)
