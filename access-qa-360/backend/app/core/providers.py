"""
AI providers other than Anthropic, for organisations that bring their own key.

Every one of them is reached through the same "chat completions" request shape
that OpenAI defined and the others copy, so one small adapter covers them all.
The adapter takes the request the app already makes for Claude and hands back a
reply shaped like Claude's, so no feature has to know which provider answered.

Model names change often. The defaults below are starting points; an
organisation can type the exact model it wants, and the key and model are
tried with a real call before they are saved.
"""
from __future__ import annotations

from types import SimpleNamespace

import httpx

PROVIDERS: dict[str, dict] = {
    "anthropic": {"name": "Claude (Anthropic)", "base": None, "fast": "claude-haiku-4-5", "best": "claude-sonnet-4-5", "embeddings": None},
    "openai": {"name": "ChatGPT (OpenAI)", "base": "https://api.openai.com/v1", "fast": "gpt-4o-mini", "best": "gpt-4o", "embeddings": "text-embedding-3-small"},
    "gemini": {"name": "Gemini (Google)", "base": "https://generativelanguage.googleapis.com/v1beta/openai", "fast": "gemini-2.0-flash", "best": "gemini-2.5-pro", "embeddings": "text-embedding-004"},
    "grok": {"name": "Grok (xAI)", "base": "https://api.x.ai/v1", "fast": "grok-3-mini", "best": "grok-3", "embeddings": None},
    "mistral": {"name": "Mistral", "base": "https://api.mistral.ai/v1", "fast": "mistral-small-latest", "best": "mistral-large-latest", "embeddings": "mistral-embed"},
    "deepseek": {"name": "DeepSeek", "base": "https://api.deepseek.com/v1", "fast": "deepseek-chat", "best": "deepseek-reasoner", "embeddings": None},
    "groq": {"name": "Groq", "base": "https://api.groq.com/openai/v1", "fast": "llama-3.1-8b-instant", "best": "llama-3.3-70b-versatile", "embeddings": None},
    "openrouter": {"name": "OpenRouter", "base": "https://openrouter.ai/api/v1", "fast": "openai/gpt-4o-mini", "best": "openai/gpt-4o", "embeddings": None},
    # Any other service that speaks the same request shape, at an address the organisation gives.
    "custom": {"name": "Another OpenAI-compatible API", "base": None, "fast": None, "best": None, "embeddings": None},
}


class ProviderError(Exception):
    pass


def base_url(provider: str, custom_base: str | None) -> str:
    return (custom_base if provider == "custom" else PROVIDERS[provider]["base"] or "").rstrip("/")


def model_for(provider: str, asked: str, quality: str | None, override: str | None) -> str:
    """Which model to call: the organisation's own choice, else the provider's fast or best one."""
    if override:
        return override
    info = PROVIDERS[provider]
    tier = quality if quality in ("fast", "best") else ("fast" if "haiku" in asked else "best")
    return info[tier] or asked


def _text(content) -> str:
    """Claude accepts a list of blocks as content; the others want plain text."""
    if isinstance(content, str):
        return content
    return "\n".join(str(block.get("text", "")) for block in content if isinstance(block, dict) and block.get("type", "text") == "text")


async def _post(url: str, key: str, body: dict, timeout: float) -> dict:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(url, json=body, headers={"Authorization": f"Bearer {key}"})
    except httpx.HTTPError:
        raise ProviderError("The AI provider could not be reached")
    if r.status_code in (401, 403):
        raise ProviderError("The AI provider did not accept the key")
    if r.status_code == 404:
        raise ProviderError("The AI provider does not know that model or address")
    if r.status_code == 429:
        raise ProviderError("The AI provider says the key is out of quota or sending too fast")
    if r.status_code >= 400:
        raise ProviderError(f"The AI provider refused the request (status {r.status_code})")
    try:
        return r.json()
    except ValueError:
        raise ProviderError("The AI provider sent an answer that could not be read")


async def chat(provider: str, custom_base: str | None, key: str, model: str, *, messages: list[dict], max_tokens: int = 1024,
               system: str | None = None, timeout: float = 120, **_ignored):
    """One chat call. Returns an object with `.content[0].text` and `.usage`, like Claude's reply."""
    sent = ([{"role": "system", "content": system}] if system else []) + [{"role": m["role"], "content": _text(m["content"])} for m in messages]
    # OpenAI's newer models only take max_completion_tokens; the others only take max_tokens.
    limit = {"max_completion_tokens": max_tokens} if provider == "openai" else {"max_tokens": max_tokens}
    data = await _post(f"{base_url(provider, custom_base)}/chat/completions", key, {"model": model, "messages": sent, **limit}, timeout)
    try:
        text = data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        raise ProviderError("The AI provider sent an answer that could not be read")
    usage = data.get("usage") or {}
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)], model=model,
                           usage=SimpleNamespace(input_tokens=usage.get("prompt_tokens", 0), output_tokens=usage.get("completion_tokens", 0)))


async def embed(base: str, key: str, model: str, texts: list[str]) -> list[list[float]]:
    """Turn each text into a list of numbers that is close to those of texts with a similar meaning."""
    data = await _post(f"{base.rstrip('/')}/embeddings", key, {"model": model, "input": texts}, 60)
    try:
        rows = sorted(data["data"], key=lambda row: row.get("index", 0))
        vectors = [row["embedding"] for row in rows]
    except (KeyError, TypeError):
        raise ProviderError("The AI provider sent an answer that could not be read")
    if len(vectors) != len(texts):
        raise ProviderError("The AI provider sent an answer that could not be read")
    return vectors
