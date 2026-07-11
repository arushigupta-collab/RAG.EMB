"""OpenRouter chat + multimodal client (generation, OCR, classification, Text-to-SQL).

Isolated here so the OpenRouter -> Vertex AI swap (scope §11) is a one-file change:
the rest of the app only calls chat()/chat_stream()/vision().
"""

from __future__ import annotations

import json
from typing import AsyncIterator, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.config import settings


def _is_retryable(exc: Exception) -> bool:
    """Retry on rate limits (429) and transient server/network errors."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return isinstance(exc, (httpx.TransportError, httpx.TimeoutException))


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "HTTP-Referer": settings.openrouter_app_url,
        "X-Title": settings.openrouter_app_title,
        "Content-Type": "application/json",
    }


@retry(
    retry=retry_if_exception(_is_retryable),
    wait=wait_exponential_jitter(initial=1, max=30),
    stop=stop_after_attempt(6),
    reraise=True,
)
async def chat(
    messages: list[dict],
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 1024,
    response_format: Optional[dict] = None,
) -> str:
    """Non-streaming completion. Returns the assistant message content."""
    payload = {
        "model": model or settings.model_fast,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format:
        payload["response_format"] = response_format
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            f"{settings.openrouter_base_url}/chat/completions",
            headers=_headers(),
            json=payload,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


async def chat_json(messages: list[dict], model: Optional[str] = None) -> dict:
    """Completion constrained to a JSON object (used for classification/SQL)."""
    raw = await chat(
        messages,
        model=model,
        response_format={"type": "json_object"},
    )
    return json.loads(raw)


async def chat_stream(
    messages: list[dict],
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 2048,
) -> AsyncIterator[str]:
    """Stream assistant content token deltas (scope §8 TTFT)."""
    payload = {
        "model": model or settings.model_generation,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream(
            "POST",
            f"{settings.openrouter_base_url}/chat/completions",
            headers=_headers(),
            json=payload,
        ) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data = line[len("data: "):]
                if data == "[DONE]":
                    break
                try:
                    delta = json.loads(data)["choices"][0]["delta"].get("content")
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
                if delta:
                    yield delta


async def vision(
    prompt: str,
    image_b64: str,
    mime: str = "image/png",
    response_format: Optional[dict] = None,
) -> str:
    """Single multimodal OCR call over one rasterised page/image (scope §3).

    Pass response_format={"type": "json_object"} to force clean, fence-free JSON.
    """
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{image_b64}"},
                },
            ],
        }
    ]
    return await chat(
        messages,
        model=settings.model_ocr,
        max_tokens=4096,
        response_format=response_format,
    )
