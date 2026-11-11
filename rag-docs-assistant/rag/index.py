"""Простое векторное хранилище на numpy с косинусным поиском."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .embeddings import Embedder
from .loader import Chunk


@dataclass
class SearchResult:
    chunk: Chunk
    score: float


def _normalize(m: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return m / norms


class VectorIndex:
    def __init__(self, embedder: Embedder) -> None:
        self.embedder = embedder
        self.chunks: list[Chunk] = []
        self.matrix: np.ndarray | None = None

    def build(self, chunks: list[Chunk]) -> None:
        if not chunks:
            raise ValueError("Нет документов для индексации")
        self.chunks = chunks
        self.matrix = _normalize(self.embedder.fit([c.text for c in chunks]))

    def search(self, query: str, top_k: int = 4, min_score: float = 0.05) -> list[SearchResult]:
        if self.matrix is None:
            raise RuntimeError("Индекс не построен: вызовите build()")
        q = _normalize(self.embedder.embed([query]))[0]
        scores = self.matrix @ q
        order = np.argsort(-scores)[:top_k]
        return [SearchResult(self.chunks[i], float(scores[i])) for i in order if scores[i] >= min_score]
