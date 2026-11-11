"""Генерация ответа: Gemini API или офлайн-режим без LLM."""
from __future__ import annotations

import os
import re
from typing import Protocol

import httpx


class LLM(Protocol):
    def generate(self, prompt: str) -> str: ...


class GeminiLLM:
    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or os.environ["GEMINI_API_KEY"]
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    def generate(self, prompt: str) -> str:
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2},
        }
        r = httpx.post(self.URL.format(model=self.model), params={"key": self.api_key},
                       json=body, timeout=60)
        r.raise_for_status()
        parts = r.json()["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts).strip()


class ExtractiveLLM:
    """Без API-ключа: возвращает 2 самых релевантных фрагмента как ответ."""

    def __init__(self, max_fragments: int = 2) -> None:
        self.max_fragments = max_fragments

    def generate(self, prompt: str) -> str:
        context = prompt.split("Фрагменты:\n", 1)[-1].split("\n\nВопрос:", 1)[0]
        fragments = re.split(r"(?:^|\n)\[\d+\] ", context)
        fragments = [f.strip() for f in fragments if f.strip()]
        if not fragments:
            return "Не нашёл ответа в документах."
        return "\n\n".join(fragments[: self.max_fragments])


def make_llm() -> LLM:
    if os.getenv("GEMINI_API_KEY"):
        return GeminiLLM()
    return ExtractiveLLM()
