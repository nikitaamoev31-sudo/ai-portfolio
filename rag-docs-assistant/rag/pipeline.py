"""RAG-пайплайн: поиск релевантных фрагментов + генерация ответа по ним."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .embeddings import Embedder, make_embedder
from .index import VectorIndex
from .llm import LLM, make_llm
from .loader import load_documents

NO_ANSWER = "В документах нет ответа на этот вопрос. Уточните у менеджера."

PROMPT = """Ты — ассистент поддержки компании. Отвечай ТОЛЬКО на основе фрагментов документов ниже.
Если ответа во фрагментах нет — ответь ровно: "{no_answer}"
Не выдумывай цены, сроки и условия. Отвечай кратко, по-русски. В конце укажи номера фрагментов, например [1], [3].

Фрагменты:
{context}

Вопрос: {question}
Ответ:"""


@dataclass
class Answer:
    text: str
    sources: list[str] = field(default_factory=list)


class RAGPipeline:
    def __init__(self, docs_dir: str | Path, embedder: Embedder | None = None,
                 llm: LLM | None = None, top_k: int = 4) -> None:
        self.docs_dir = Path(docs_dir)
        self.index = VectorIndex(embedder or make_embedder())
        self.llm = llm or make_llm()
        self.top_k = top_k
        self.reindex()

    def reindex(self) -> int:
        chunks = load_documents(self.docs_dir)
        self.index.build(chunks)
        return len(chunks)

    def build_prompt(self, question: str, results) -> str:
        context = "\n".join(f"[{i}] {r.chunk.text}" for i, r in enumerate(results, start=1))
        return PROMPT.format(no_answer=NO_ANSWER, context=context, question=question)

    def ask(self, question: str) -> Answer:
        question = question.strip()
        if not question:
            return Answer(NO_ANSWER)
        results = self.index.search(question, top_k=self.top_k)
        if not results:
            return Answer(NO_ANSWER)
        text = self.llm.generate(self.build_prompt(question, results))
        sources = sorted({f"{r.chunk.source}#{r.chunk.index}" for r in results})
        return Answer(text=text or NO_ANSWER, sources=sources)
