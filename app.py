import os
import sys
import base64
import traceback
from io import BytesIO
from flask import Flask, render_template, request, jsonify
from zai import ZhipuAiClient
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max file size

# 从环境变量获取 API Key
API_KEY = os.environ.get("ZHIPU_API_KEY", "")


def image_to_base64(image_file):
    """将上传的图片文件转换为 base64 编码"""
    image_file.seek(0)
    image_data = image_file.read()
    base64_encoded = base64.b64encode(image_data).decode("utf-8")
    return base64_encoded


def get_image_mime_type(filename):
    """根据文件名获取 MIME 类型"""
    ext = filename.lower().split(".")[-1] if "." in filename else ""
    mime_types = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "bmp": "image/bmp",
        "webp": "image/webp",
    }
    return mime_types.get(ext, "image/jpeg")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/ocr", methods=["POST"])
def ocr():
    if "image" not in request.files:
        return jsonify({"error": "没有上传图片"}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "没有选择文件"}), 400

    try:
        # 转换为 base64
        base64_data = image_to_base64(file)
        mime_type = get_image_mime_type(file.filename)
        base64_url = f"data:{mime_type};base64,{base64_data}"

        # 调用智谱 AI OCR
        client = ZhipuAiClient(api_key=API_KEY)
        response = client.layout_parsing.create(model="glm-ocr", file=base64_url)

        # 将响应对象转换为字典
        result_dict = (
            response.model_dump()
            if hasattr(response, "model_dump")
            else response.dict()
        )

        return jsonify({"success": True, "result": result_dict})

    except Exception as e:
        import traceback

        error_detail = traceback.format_exc()
        print(f"[OCR ERROR] {error_detail}")
        return jsonify(
            {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "detail": error_detail,
            }
        ), 500


if __name__ == "__main__":
    # 从命令行参数获取端口，默认为 5000
    port = 5000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"错误: 无效的端口号 '{sys.argv[1]}'，使用默认端口 5000")

    app.run(debug=True, host="0.0.0.0", port=port)
