"""
Provider 工厂
根据配置创建对应的 Provider 实例
"""

import os
from .openai_compatible import OpenAICompatibleProvider

# 厂家配置映射
PROVIDER_CONFIG = {
    "dashscope": {
        "api_key_env": "DASHSCOPE_API_KEY",
        "base_url_env": "DASHSCOPE_BASE_URL",
        "default_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model_env": "DASHSCOPE_MODEL",
        "json_mode": True,
        # 思考模式：extra_body 传 enable_thinking，不切换模型
        "thinking_model": None,
        "thinking_params": {"extra_body": {"enable_thinking": True}},
        "thinking_disable_params": {"extra_body": {"enable_thinking": False}},
        "provider_class": OpenAICompatibleProvider,
    },
    "ark": {
        "api_key_env": "ARK_API_KEY",
        "base_url_env": "ARK_BASE_URL",
        "default_base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model_env": "ARK_MODEL",
        "json_mode": False,
        # 思考模式：extra_body 传 thinking.type=enabled
        "thinking_model": None,
        "thinking_params": {"extra_body": {"thinking": {"type": "enabled"}, "reasoning_effort": "medium"}},
        "thinking_disable_params": {"extra_body": {"thinking": {"type": "disabled"}}},
        "provider_class": OpenAICompatibleProvider,
    },
}

# 各厂家可选模型列表（供前端展示）
PROVIDER_MODELS = {
    "dashscope": [
        {"id": "qwen3.5-flash", "name": "qwen3.5-flash"},
    ],
    "ark": [
        {"id": "ep-20260709234540-p6n46", "name": "ep-20260709234540-p6n46"},
    ],
}


def get_available_providers():
    """获取所有已配置 API Key 的厂家列表，默认厂商排在首位"""
    available = []
    for provider_name, config in PROVIDER_CONFIG.items():
        api_key = os.environ.get(config["api_key_env"], "")
        if api_key and not api_key.startswith("your_"):
            available.append(provider_name)
    default = os.environ.get("DEFAULT_PROVIDER", "ark")
    if default in available:
        available.remove(default)
        available.insert(0, default)
    return available


def get_provider_models(provider_name: str):
    """获取指定厂家支持的模型列表，若环境变量中配置了模型则标记为默认"""
    models = list(PROVIDER_MODELS.get(provider_name, []))
    config = PROVIDER_CONFIG.get(provider_name)
    if not config:
        return models

    env_model = os.environ.get(config["model_env"], "")
    if not env_model:
        return models

    # 将环境变量配置的模型排到最前面（若列表中已有则移动，否则插入）
    models = [m for m in models if m["id"] != env_model]
    models.insert(0, {"id": env_model, "name": f"{env_model} (默认)"})
    return models


def create_provider(provider_name: str = None, model: str = None, thinking: bool = False):
    """
    创建 Provider 实例

    Args:
        provider_name: 厂家名称，默认读取 DEFAULT_PROVIDER 环境变量
        model: 模型名称，默认读取各厂家 {PROVIDER}_MODEL 环境变量
        thinking: 是否开启思考模式

    Returns:
        BaseProvider 实例
    """
    if provider_name is None:
        provider_name = os.environ.get("DEFAULT_PROVIDER", "ark")

    if provider_name not in PROVIDER_CONFIG:
        raise ValueError(f"不支持的厂家: {provider_name}")

    config = PROVIDER_CONFIG[provider_name]

    api_key = os.environ.get(config["api_key_env"], "")
    if not api_key:
        raise ValueError(f"{provider_name} 的 API Key 未设置（{config['api_key_env']}）")

    base_url = os.environ.get(config["base_url_env"], "") or config["default_base_url"]

    if not model:
        model = os.environ.get(config["model_env"], "")
    if not model:
        raise ValueError(
            f"{provider_name} 的模型未配置，请设置环境变量 {config['model_env']}"
        )

    # 思考模式：若该提供商需要切换模型，则覆盖 model
    if thinking and config.get("thinking_model"):
        model = config["thinking_model"]

    return config["provider_class"](
        api_key=api_key,
        base_url=base_url,
        model=model,
        json_mode=config.get("json_mode", False),
        thinking=thinking,
        thinking_params=config.get("thinking_params", {}),
        thinking_disable_params=config.get("thinking_disable_params", {}),
    )
