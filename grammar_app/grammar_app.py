import os
import sys
import traceback
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from providers.factory import create_provider, get_available_providers, get_provider_models

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(BASE_DIR, ".env")
load_dotenv(env_path)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB，给图片上传留足空间
CORS(app)


@app.route("/")
def index():
    return render_template("grammar.html")


@app.route("/providers", methods=["GET"])
def providers():
    """获取可用的 AI 提供商列表"""
    available = get_available_providers()
    return jsonify({"providers": available})


@app.route("/models/<provider_name>", methods=["GET"])
def models(provider_name):
    """获取指定提供商支持的模型列表"""
    model_list = get_provider_models(provider_name)
    return jsonify({"models": model_list})


@app.route("/check", methods=["POST"])
def check():
    """语法语义检查 API"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "请求体为空"}), 400

    mode = data.get("mode", "text")
    provider_name = data.get("provider")
    model = data.get("model")
    thinking = bool(data.get("thinking", False))
    check_mode = data.get("check_mode", "general")
    if check_mode not in ("general", "student", "student_typo"):
        return jsonify({"error": f"不支持的检查模式: {check_mode}"}), 400

    text = ""
    image = ""

    if mode == "image":
        image = (data.get("image") or "").strip()
        if not image:
            return jsonify({"error": "缺少 image 参数"}), 400
        if not image.startswith("data:image/"):
            return jsonify({"error": "image 必须是 data:image/... 形式的 data URL"}), 400
        # base64 字符长度上限 ~8MB（对应原图约 5MB）
        if len(image) > 8 * 1024 * 1024:
            return jsonify({"error": "图片过大，请压缩后重试（建议 < 5MB）"}), 400
    else:
        text = (data.get("text") or "").strip()
        if not text:
            return jsonify({"error": "文本不能为空"}), 400
        if len(text) > 5000:
            return jsonify({"error": "文本长度超过限制（最大 5000 字符）"}), 400

    try:
        provider = create_provider(provider_name, model, thinking=thinking)
        result = provider.check_grammar(text=text, image=image, check_mode=check_mode)
        return jsonify({"success": True, "result": result})

    except Exception as e:
        error_detail = traceback.format_exc()
        print(f"[CHECK ERROR] {error_detail}")
        return jsonify(
            {
                "error": str(e),
                "error_type": type(e).__name__,
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
