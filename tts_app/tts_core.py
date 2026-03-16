"""
讯飞 TTS 核心功能模块
"""

import os
import base64
import hashlib
import hmac
import json
import io
import wave
import asyncio
from urllib.parse import urlencode
from datetime import datetime
from time import mktime
from wsgiref.handlers import format_date_time

import websockets
from dotenv import load_dotenv

# 加载环境变量
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(BASE_DIR, ".env")
load_dotenv(env_path)

IFLYTEK_APPID = os.environ.get("IFLYTEK_APPID", "")
IFLYTEK_API_KEY = os.environ.get("IFLYTEK_API_KEY", "")
IFLYTEK_API_SECRET = os.environ.get("IFLYTEK_API_SECRET", "")


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
    return url + "?" + urlencode(v)


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
    if not text or not text.strip():
        return None

    text = text.strip()
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
            await websocket.send(json.dumps(request_data))

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

    except Exception as e:
        error_msg = f"WebSocket 错误: {str(e)}"

    if error_msg:
        print(f"[TTS ERROR] {error_msg}")
        return None

    return bytes(audio_data)


def text_to_speech(text, vcn="x4_yezi"):
    """同步包装异步函数，返回带 WAV 头的音频数据"""
    pcm_data = asyncio.run(text_to_speech_async(text, vcn))
    if pcm_data:
        # 添加 WAV 头部，返回 WAV 格式的字节数据
        wav_buffer = pcm_to_wav(pcm_data)
        wav_buffer.seek(0)
        return wav_buffer.read()
    return None
