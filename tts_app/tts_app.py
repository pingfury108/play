import os
import sys
import base64
import hashlib
import hmac
import json
import io
import wave
import tempfile
import asyncio
import traceback
from urllib.parse import urlencode
from datetime import datetime
from time import mktime
from wsgiref.handlers import format_date_time

import websockets
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from dotenv import load_dotenv

# 获取当前文件所在目录，确保能正确加载 .env
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(BASE_DIR, ".env")
load_dotenv(env_path)

app = Flask(__name__)
CORS(app)

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


if __name__ == "__main__":
    port = 5001
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"错误: 无效的端口号 '{sys.argv[1]}'，使用默认端口 5001")

    print(f"启动讯飞 TTS 服务，访问 http://localhost:{port}")
    app.run(debug=True, host="0.0.0.0", port=port)
