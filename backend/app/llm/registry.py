from app.llm.anthropic import AnthropicProvider
from app.llm.base import LLMProvider
from app.llm.ollama import OllamaProvider
from app.llm.openai_provider import OpenAIProvider

_providers: dict[str, type[LLMProvider]] = {
    "claude": AnthropicProvider,
    "openai": OpenAIProvider,
    "ollama": OllamaProvider,
}

_instances: dict[str, LLMProvider] = {}


def get_provider(name: str) -> LLMProvider:
    if name not in _instances:
        provider_cls = _providers.get(name)
        if not provider_cls:
            raise ValueError(f"Unknown LLM provider: {name}. Available: {list(_providers.keys())}")
        _instances[name] = provider_cls()
    return _instances[name]
