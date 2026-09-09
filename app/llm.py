"""Chat completion behind one interface, so the pipeline does not care who generates.

auto: Groq if a key is set, else a local Ollama server, else no generator at all
(the caller then quotes the retrieved text instead of writing an answer).
"""
import re
import time

import httpx

from . import config

THINK_BLOCK = re.compile(r"<think>.*?</think>\s*", re.S | re.I)
_probe = {"at": 0.0, "ok": False}
PROBE_TTL = 30.0


class NoGenerator(Exception):
    """No LLM is reachable, the caller should fall back to extractive answers."""


def ollama_up() -> bool:
    now = time.time()
    if now - _probe["at"] < PROBE_TTL:
        return _probe["ok"]
    try:
        httpx.get(f"{config.OLLAMA_HOST}/api/tags", timeout=2.0).raise_for_status()
        _probe["ok"] = True
    except Exception:
        _probe["ok"] = False
    _probe["at"] = now
    return _probe["ok"]


def provider() -> str:
    choice = config.LLM_PROVIDER.lower()
    if choice != "auto":
        return choice
    if config.GROQ_API_KEY:
        return "groq"
    return "ollama" if ollama_up() else "none"


def model_name(name: str = None) -> str:
    name = name or provider()
    return {"groq": config.GROQ_MODEL, "ollama": config.OLLAMA_MODEL}.get(name, "")


def describe() -> str:
    name = provider()
    if name == "none":
        return "extractive (no generator: set GROQ_API_KEY or start Ollama)"
    return f"{name}:{model_name(name)}"


class Timeout(Exception):
    """The generator did not answer inside the interactive budget."""


def complete(messages, temperature: float = 0.2, max_tokens: int = 400, timeout: float = None) -> str:
    name = provider()
    if name == "groq":
        return _groq(messages, temperature, max_tokens, timeout)
    if name == "ollama":
        return _ollama(messages, temperature, max_tokens, timeout)
    raise NoGenerator("no generator configured")


def _groq(messages, temperature, max_tokens, timeout) -> str:
    from groq import Groq
    client = Groq(api_key=config.GROQ_API_KEY, timeout=timeout or config.GEN_TIMEOUT)
    try:
        response = client.chat.completions.create(
            model=config.GROQ_MODEL, messages=messages,
            temperature=temperature, max_tokens=max_tokens,
        )
    except Exception as exc:
        raise _as_timeout(exc) from exc
    return clean(response.choices[0].message.content)


def _ollama(messages, temperature, max_tokens, timeout) -> str:
    payload = {
        "model": config.OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "think": False,                       # ignored by models that do not reason
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    try:
        response = httpx.post(f"{config.OLLAMA_HOST}/api/chat", json=payload,
                              timeout=timeout or config.OLLAMA_TIMEOUT)
        response.raise_for_status()
    except Exception as exc:
        raise _as_timeout(exc) from exc
    return clean(response.json().get("message", {}).get("content", ""))


def _as_timeout(exc: Exception) -> Exception:
    """A slow generator and a broken one need different words in the widget."""
    if isinstance(exc, httpx.TimeoutException) or "timed out" in str(exc).lower():
        return Timeout(f"{provider()} did not answer in time")
    return exc


def clean(text: str) -> str:
    """Reasoning models emit a <think> block before the answer. Drop it."""
    return THINK_BLOCK.sub("", text or "").strip()
