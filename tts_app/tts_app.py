import os
import sys
import tempfile
import traceback
from datetime import datetime

from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from dotenv import load_dotenv

# 获取当前文件所在目录，确保能正确加载 .env
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(BASE_DIR, ".env")
load_dotenv(env_path)

app = Flask(__name__)
CORS(app)

# 导入 TTS 核心功能
from tts_core import (
    text_to_speech,
    pcm_to_wav,
    IFLYTEK_APPID,
    IFLYTEK_API_KEY,
    IFLYTEK_API_SECRET,
)

# 导入批量处理模块
from batch_processor import (
    create_task,
    get_task_status,
    start_task,
    process_next_batch,
    pause_task,
    resume_task,
    get_partial_zip,
    get_final_zip,
)

IFLYTEK_APPID = os.environ.get("IFLYTEK_APPID", "")
IFLYTEK_API_KEY = os.environ.get("IFLYTEK_API_KEY", "")
IFLYTEK_API_SECRET = os.environ.get("IFLYTEK_API_SECRET", "")

# Debug: 打印环境变量读取情况
print(f"[DEBUG] .env 文件路径: {env_path}")
print(f"[DEBUG] .env 文件存在: {os.path.exists(env_path)}")
print(
    f"[DEBUG] IFLYTEK_APPID: {'已设置' if IFLYTEK_APPID else '未设置'} (长度: {len(IFLYTEK_APPID)})"
)
print(
    f"[DEBUG] IFLYTEK_API_KEY: {'已设置' if IFLYTEK_API_KEY else '未设置'} (长度: {len(IFLYTEK_API_KEY)})"
)
print(
    f"[DEBUG] IFLYTEK_API_SECRET: {'已设置' if IFLYTEK_API_SECRET else '未设置'} (长度: {len(IFLYTEK_API_SECRET)})"
)


def create_auth_url():
    """生成讯飞 WebSocket 鉴权 URL"""
    url = "wss://tts-api.xfyun.cn/v2/tts"
    now = datetime.now()
    date = format_date_time(mktime(now.timetuple()))

    signature_origin = "host: " + "tts-api.xfyun.cn" + "\n"
    signature_origin += "date: " + date + "\n"
    signature_origin += "GET " + "/v2/tts " + "HTTP/1.1"

    signature_sha = hmac.new(
        IFLYTEK_API_SECRET.encode("utf-8"),
        signature_origin.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    signature_sha = base64.b64encode(signature_sha).decode(encoding="utf-8")

    authorization_origin = (
        'api_key="%s", algorithm="%s", headers="%s", signature="%s"'
        % (IFLYTEK_API_KEY, "hmac-sha256", "host date request-line", signature_sha)
    )
    authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode(
        encoding="utf-8"
    )

    v = {"authorization": authorization, "date": date, "host": "tts-api.xfyun.cn"}
    final_url = url + "?" + urlencode(v)

    # Debug: 打印鉴权信息
    print(f"[DEBUG] signature_origin:\n{signature_origin}")
    print(f"[DEBUG] authorization_origin: {authorization_origin}")
    print(f"[DEBUG] final_url: {final_url[:100]}...")

    return final_url


def pcm_to_wav(pcm_data, sample_rate=16000, channels=1, sample_width=2):
    """将 PCM 数据转换为 WAV 格式"""
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)
    wav_buffer.seek(0)
    return wav_buffer


async def text_to_speech_async(text, vcn="x4_yezi"):
    """使用 websockets 库调用讯飞 TTS API 合成语音"""
    ws_url = create_auth_url()
    audio_data = bytearray()
    error_msg = None

    request_data = {
        "common": {"app_id": IFLYTEK_APPID},
        "business": {
            "aue": "raw",
            "auf": "audio/L16;rate=16000",
            "vcn": vcn,
            "tte": "utf8",
        },
        "data": {
            "status": 2,
            "text": base64.b64encode(text.encode("utf-8")).decode("utf-8"),
        },
    }

    try:
        async with websockets.connect(ws_url) as websocket:
            # 发送请求
            await websocket.send(json.dumps(request_data))

            # 接收响应
            async for message in websocket:
                try:
                    response = json.loads(message)
                    code = response.get("code")
                    sid = response.get("sid")

                    if code != 0:
                        err_msg = response.get("message", "未知错误")
                        error_msg = f"sid:{sid} call error:{err_msg} code is:{code}"
                        break

                    audio = response.get("data", {}).get("audio")
                    if audio:
                        audio_bytes = base64.b64decode(audio)
                        audio_data.extend(audio_bytes)

                    status = response.get("data", {}).get("status")
                    if status == 2:
                        break

                except Exception as e:
                    error_msg = f"解析消息异常: {str(e)}"
                    break

    except websockets.exceptions.InvalidStatusCode as e:
        error_msg = f"WebSocket 连接失败: HTTP {e.status_code}"
    except Exception as e:
        error_msg = f"WebSocket 错误: {str(e)}"

    if error_msg:
        raise Exception(error_msg)

    return bytes(audio_data)


def text_to_speech(text, vcn="x4_yezi"):
    """同步包装异步函数"""
    return asyncio.run(text_to_speech_async(text, vcn))


@app.route("/")
def index():
    return render_template("tts.html")


@app.route("/batch")
def batch_page():
    return render_template("batch.html")


@app.route("/tts", methods=["POST"])
def tts():
    """TTS API 接口"""
    if not all([IFLYTEK_APPID, IFLYTEK_API_KEY, IFLYTEK_API_SECRET]):
        return jsonify({"error": "讯飞 API 配置未设置，请检查环境变量"}), 500

    data = request.get_json()
    if not data or "text" not in data:
        return jsonify({"error": "缺少 text 参数"}), 400

    text = data["text"].strip()
    if not text:
        return jsonify({"error": "文本不能为空"}), 400

    if len(text) > 2000:
        return jsonify({"error": "文本长度超过限制（最大 2000 字符）"}), 400

    vcn = data.get("vcn", "x4_yezi")

    try:
        pcm_data = text_to_speech(text, vcn)
        if not pcm_data:
            return jsonify({"error": "语音合成失败，未获取到音频数据"}), 500

        wav_buffer = pcm_to_wav(pcm_data)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
            tmp_file.write(wav_buffer.getvalue())
            tmp_path = tmp_file.name

        return send_file(
            tmp_path,
            mimetype="audio/wav",
            as_attachment=True,
            download_name="tts_output.wav",
        )

    except Exception as e:
        error_detail = traceback.format_exc()
        print(f"[TTS ERROR] {error_detail}")
        return jsonify({"error": str(e), "detail": error_detail}), 500


# ========== 批量处理 API ==========


@app.route("/batch/create", methods=["POST"])
def batch_create():
    """创建批量处理任务"""
    if "vocab_file" not in request.files or "examples_file" not in request.files:
        return jsonify({"success": False, "error": "请上传两个 Excel 文件"}), 400

    vocab_file = request.files["vocab_file"]
    examples_file = request.files["examples_file"]
    limit = request.form.get("limit", "")
    limit = int(limit) if limit.strip() else None

    if vocab_file.filename == "" or examples_file.filename == "":
        return jsonify({"success": False, "error": "文件不能为空"}), 400

    try:
        # 保存上传的文件
        upload_dir = os.path.join(BASE_DIR, "uploads")
        os.makedirs(upload_dir, exist_ok=True)

        vocab_path = os.path.join(upload_dir, vocab_file.filename)
        examples_path = os.path.join(upload_dir, examples_file.filename)

        vocab_file.save(vocab_path)
        examples_file.save(examples_path)

        # 创建输出目录
        output_dir = os.path.join(
            BASE_DIR, "output", datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        os.makedirs(output_dir, exist_ok=True)

        # 创建任务
        task_id = create_task(vocab_path, examples_path, output_dir, limit)

        return jsonify({"success": True, "task_id": task_id})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/batch/start/<task_id>", methods=["POST"])
def batch_start(task_id):
    """启动自动处理"""
    if start_task(task_id):
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "任务不存在"}), 404


@app.route("/batch/process/<task_id>", methods=["POST"])
def batch_process(task_id):
    """处理下一批（手动模式）"""
    status = process_next_batch(task_id)
    if status:
        return jsonify({"success": True, "status": status})
    return jsonify({"success": False, "error": "任务不存在"}), 404


@app.route("/batch/status/<task_id>")
def batch_status(task_id):
    """获取任务状态"""
    status = get_task_status(task_id)
    if status:
        return jsonify(status)
    return jsonify({"error": "任务不存在"}), 404


@app.route("/batch/pause/<task_id>", methods=["POST"])
def batch_pause(task_id):
    """暂停任务"""
    if pause_task(task_id):
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "任务不存在"}), 404


@app.route("/batch/resume/<task_id>", methods=["POST"])
def batch_resume(task_id):
    """恢复任务"""
    if resume_task(task_id):
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "任务不存在"}), 404


@app.route("/batch/download/<task_id>")
def batch_download(task_id):
    """下载结果"""
    # 先尝试获取最终压缩包
    zip_path = get_final_zip(task_id)

    if not zip_path or not os.path.exists(zip_path):
        # 如果没有最终包，获取部分包
        zip_path = get_partial_zip(task_id)

    if zip_path and os.path.exists(zip_path):
        return send_file(
            zip_path,
            mimetype="application/zip",
            as_attachment=True,
            download_name="vocabulary_audio.zip",
        )

    return jsonify({"error": "文件不存在"}), 404


if __name__ == "__main__":
    port = 5001
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"错误: 无效的端口号 '{sys.argv[1]}'，使用默认端口 5001")

    print(f"启动讯飞 TTS 服务，访问 http://localhost:{port}")
    app.run(debug=True, host="0.0.0.0", port=port)
