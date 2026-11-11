"""Векторизация текста: локальный TF-IDF или эмбеддинги Gemini."""
from __future__ import annotations

import os
import re
from typing import Protocol

import httpx
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


class Embedder(Protocol):
    def fit(self, texts: list[str]) -> np.ndarray: ...
    def embed(self, texts: list[str]) -> np.ndarray: ...


STOP_WORDS = {"как", "что", "где", "когда", "сколько", "есть", "ли", "это", "для", "или", "при",
              "на", "в", "во", "и", "а", "по", "за", "с", "со", "до", "от", "не", "у", "к", "о", "об"}


def stem_tokens(text: str) -> list[str]:
    """Грубый стемминг для русского: обрезаем слово до 5 букв.

    «тарифы», «тарифа», «тарифом» -> «тариф»; этого хватает для поиска без NLP-библиотек.
    """
    words = re.findall(r"[a-zа-яё0-9]+", text.lower())
    return [w[:5] for w in words if w not in STOP_WORDS and len(w) > 1]


class TfidfEmbedder:
    """Работает офлайн и без ключей — удобно для демо и тестов."""

    def __init__(self) -> None:
        self.vectorizer = TfidfVectorizer(tokenizer=stem_tokens, token_pattern=None,
                                          lowercase=False, sublinear_tf=True)

    def fit(self, texts: list[str]) -> np.ndarray:
        return self.vectorizer.fit_transform(texts).toarray()

    def embed(self, texts: list[str]) -> np.ndarray:
        return self.vectorizer.transform(texts).toarray()


class GeminiEmbedder:
    """Семантические эмбеддинги через Gemini API (есть бесплатный лимит)."""

    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or os.environ["GEMINI_API_KEY"]
        self.model = model or os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-001")

    def _call(self, texts: list[str]) -> np.ndarray:
        vectors = []
        for start in range(0, len(texts), 100):  # API принимает до 100 текстов за запрос
            batch = texts[start:start + 100]
            body = {"requests": [
                {"model": f"models/{self.model}", "content": {"parts": [{"text": t}]}} for t in batch
            ]}
            r = httpx.post(self.URL.format(model=self.model), params={"key": self.api_key},
                           json=body, timeout=60)
            r.raise_for_status()
            vectors.extend(e["values"] for e in r.json()["embeddings"])
        return np.array(vectors, dtype=np.float32)

    def fit(self, texts: list[str]) -> np.ndarray:
        return self._call(texts)

    def embed(self, texts: list[str]) -> np.ndarray:
        return self._call(texts)


def make_embedder() -> Embedder:
    if os.getenv("EMBEDDER", "tfidf").lower() == "gemini":
        return GeminiEmbedder()
    return TfidfEmbedder()
