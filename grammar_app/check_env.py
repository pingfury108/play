#!/usr/bin/env python
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(BASE_DIR, ".env")

print(f"检查 {env_path} 是否存在...")
if os.path.exists(env_path):
    with open(env_path) as f:
        content = f.read()
        if "your_deepseek_api_key_here" in content:
            print("❌ .env 文件中的 API Key 未设置")
            print(f"请编辑 {env_path}，设置你的 DeepSeek API Key")
            sys.exit(1)
        else:
            print("✅ .env 文件配置正确")
else:
    print("❌ .env 文件不存在")
    print(f"请复制 .env.example 为 .env 并配置 API Key")
    sys.exit(1)

print("\n🚀 你可以启动服务了：")
print(f"   cd {BASE_DIR}")
print("   python grammar_app.py")
print("\n然后访问 http://localhost:5002")
