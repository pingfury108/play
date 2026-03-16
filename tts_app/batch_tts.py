"""讯飞 TTS 批量处理脚本

功能：
1. 读取两个 Excel 文件（核心词汇表和词汇性释义例句表）
2. 生成音频文件：
   - 核心词汇表：英音（Amanda）、美音（Gavin）
   - 例句表：例句音频（Catherine）
3. 按固定目录结构组织文件
4. 打包为压缩包

目录结构：
/profile/vocabulary/{word}/core/audio/{word}1.mp3  - 英音
/profile/vocabulary/{word}/core/audio/{word}2.mp3  - 美音
/profile/vocabulary/{word}/definition/examples/audio/{id}.mp3  - 例句
"""

import os
import sys
import base64
import hashlib
import hmac
import json
import io
import wave
import asyncio
import zipfile
import shutil
from urllib.parse import urlencode
from datetime import datetime
from time import mktime
from wsgiref.handlers import format_date_time
from pathlib import Path

import websockets
import pandas as pd
from dotenv import load_dotenv

# 加载环境变量
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(BASE_DIR, ".env")
load_dotenv(env_path)

IFLYTEK_APPID = os.environ.get("IFLYTEK_APPID", "")
IFLYTEK_API_KEY = os.environ.get("IFLYTEK_API_KEY", "")
IFLYTEK_API_SECRET = os.environ.get("IFLYTEK_API_SECRET", "")

# 发音人配置
VOICE_AMANDA = "x4_enuk_amanda_education"  # 英音女声
VOICE_GAVIN = "x4_enus_gavin_assist"  # 美音男声
VOICE_CATHERINE = "x4_enus_catherine_profnews"  # 例句女声


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


def pcm_to_mp3_bytes(pcm_data, sample_rate=16000):
    """将 PCM 数据转换为 MP3 格式（使用 lame 编码）"""
    # 先转换为 WAV
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)

    wav_data = wav_buffer.getvalue()

    # 使用 pydub 转换为 MP3
    try:
        from pydub import AudioSegment

        audio = AudioSegment.from_wav(io.BytesIO(wav_data))
        mp3_buffer = io.BytesIO()
        audio.export(mp3_buffer, format="mp3", bitrate="128k")
        return mp3_buffer.getvalue()
    except ImportError:
        # 如果没有 pydub，返回 WAV 数据
        return wav_data


async def text_to_speech_async(text, vcn=VOICE_GAVIN):
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
            "aue": "lame",  # 使用 MP3 格式
            "sfl": 1,  # 开启流式返回
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


def text_to_speech(text, vcn=VOICE_GAVIN):
    """同步包装异步函数"""
    return asyncio.run(text_to_speech_async(text, vcn))


def process_vocabulary_table(excel_path, output_base_dir):
    """处理核心词汇表

    Excel 格式：
    A列: 单词, B列: 英音音标, C列: 美音音标, D列: 英音音频路径, E列: 美音音频路径
    """
    print(f"[INFO] 处理核心词汇表: {excel_path}")

    df = pd.read_excel(excel_path)
    results = []

    for idx, row in df.iterrows():
        word = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else None
        if not word:
            continue

        print(f"[INFO] 处理单词: {word}")

        # 生成英音音频 (Amanda)
        uk_audio_path = f"vocabulary/{word}/core/audio/{word}1.mp3"
        uk_audio_data = text_to_speech(word, VOICE_AMANDA)

        # 生成美音音频 (Gavin)
        us_audio_path = f"vocabulary/{word}/core/audio/{word}2.mp3"
        us_audio_data = text_to_speech(word, VOICE_GAVIN)

        # 保存音频文件
        if uk_audio_data:
            uk_file_path = os.path.join(output_base_dir, uk_audio_path)
            os.makedirs(os.path.dirname(uk_file_path), exist_ok=True)
            with open(uk_file_path, "wb") as f:
                f.write(uk_audio_data)
            print(f"  [OK] 英音: {uk_file_path}")

        if us_audio_data:
            us_file_path = os.path.join(output_base_dir, us_audio_path)
            os.makedirs(os.path.dirname(us_file_path), exist_ok=True)
            with open(us_file_path, "wb") as f:
                f.write(us_audio_data)
            print(f"  [OK] 美音: {us_file_path}")

        results.append(
            {
                "word": word,
                "uk_audio": uk_audio_path if uk_audio_data else None,
                "us_audio": us_audio_path if us_audio_data else None,
            }
        )

    return results


def process_examples_table(excel_path, output_base_dir):
    """处理词汇性释义例句表

    Excel 格式：
    A列: 编号, B列: 单词, C列: 例句, D列: 翻译, E列: 音频路径
    """
    print(f"[INFO] 处理例句表: {excel_path}")

    df = pd.read_excel(excel_path)
    results = []

    for idx, row in df.iterrows():
        example_id = str(row.iloc[0]) if pd.notna(row.iloc[0]) else None
        word = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else None
        sentence = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else None

        if not all([example_id, word, sentence]):
            continue

        print(f"[INFO] 处理例句 #{example_id}: {sentence[:50]}...")

        # 生成例句音频 (Catherine)
        audio_data = text_to_speech(sentence, VOICE_CATHERINE)

        if audio_data:
            audio_path = f"vocabulary/{word}/definition/examples/audio/{example_id}.mp3"
            file_path = os.path.join(output_base_dir, audio_path)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(audio_data)
            print(f"  [OK] 例句音频: {file_path}")

            results.append(
                {
                    "id": example_id,
                    "word": word,
                    "sentence": sentence,
                    "audio_path": audio_path,
                }
            )

    return results


def create_zip_package(source_dir, output_path):
    """将生成的文件打包为 zip"""
    print(f"[INFO] 打包文件: {output_path}")

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                file_path = os.path.join(root, file)
                # 跳过 zip 文件本身
                if file_path == output_path:
                    continue
                arcname = os.path.relpath(file_path, source_dir)
                zipf.write(file_path, arcname)

    print(f"[OK] 打包完成: {output_path}")


def main():
    """主函数"""
    # 检查环境变量
    if not all([IFLYTEK_APPID, IFLYTEK_API_KEY, IFLYTEK_API_SECRET]):
        print("[ERROR] 讯飞 API 配置未设置，请检查 .env 文件")
        sys.exit(1)

    # 检查命令行参数
    if len(sys.argv) < 3:
        print(
            "用法: python batch_tts.py <核心词汇表.xlsx> <词汇性释义例句.xlsx> [输出目录]"
        )
        sys.exit(1)

    vocab_file = sys.argv[1]
    examples_file = sys.argv[2]
    output_dir = sys.argv[3] if len(sys.argv) > 3 else "./output"

    # 检查文件是否存在
    if not os.path.exists(vocab_file):
        print(f"[ERROR] 文件不存在: {vocab_file}")
        sys.exit(1)

    if not os.path.exists(examples_file):
        print(f"[ERROR] 文件不存在: {examples_file}")
        sys.exit(1)

    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print("讯飞 TTS 批量处理")
    print("=" * 60)

    # 处理核心词汇表
    vocab_results = process_vocabulary_table(vocab_file, output_dir)

    print("\n" + "=" * 60)

    # 处理例句表
    examples_results = process_examples_table(examples_file, output_dir)

    print("\n" + "=" * 60)

    # 打包
    zip_path = os.path.join(output_dir, "vocabulary_audio.zip")
    create_zip_package(output_dir, zip_path)

    # 统计
    print("\n" + "=" * 60)
    print("处理统计:")
    print(f"  核心词汇: {len(vocab_results)} 个")
    print(f"  例句: {len(examples_results)} 条")
    print(f"  输出目录: {output_dir}")
    print(f"  压缩包: {zip_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
