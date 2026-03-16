# 讯飞语音合成 TTS Web 应用

## 功能
- 输入文本，转换为语音
- 支持在线播放和下载音频

## 配置
1. 复制 `.env.example` 为 `.env`
2. 填写讯飞开放平台申请的 APPID、APIKey、APISecret

## 运行
```bash
# 安装依赖
pip install flask python-dotenv websocket-client

# 运行
python tts_app.py
```

## 访问
打开浏览器访问 http://localhost:5001
