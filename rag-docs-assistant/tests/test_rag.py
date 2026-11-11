from pathlib import Path

import pytest

from rag.embeddings import TfidfEmbedder
from rag.llm import ExtractiveLLM
from rag.loader import split_text
from rag.pipeline import NO_ANSWER, RAGPipeline

DATA = Path(__file__).resolve().parent.parent / "data"


class FakeLLM:
    """Запоминает промпт, чтобы проверить, что в него попал нужный контекст."""

    def __init__(self):
        self.last_prompt = ""

    def generate(self, prompt: str) -> str:
        self.last_prompt = prompt
        return "ok [1]"


@pytest.fixture
def rag():
    return RAGPipeline(DATA, embedder=TfidfEmbedder(), llm=ExtractiveLLM())


def test_split_respects_max_chars():
    text = "\n\n".join(["абзац " * 30] * 10)
    chunks = split_text(text, max_chars=400)
    assert len(chunks) > 1
    assert all(len(c) <= 400 for c in chunks)


def test_long_paragraph_is_split_with_overlap():
    chunks = split_text("x" * 2000, max_chars=800, overlap=100)
    assert len(chunks) == 3
    assert all(len(c) <= 800 for c in chunks)


def test_finds_price(rag):
    answer = rag.ask("Сколько стоит тариф Бизнес?")
    assert "2 490" in answer.text
    assert any(s.startswith("tarify.md") for s in answer.sources)


def test_finds_refund_rules(rag):
    answer = rag.ask("Как вернуть деньги?")
    assert "14 дней" in answer.text


def test_context_goes_into_prompt():
    llm = FakeLLM()
    rag = RAGPipeline(DATA, embedder=TfidfEmbedder(), llm=llm)
    rag.ask("Когда работает поддержка?")
    assert "9:00 до 21:00" in llm.last_prompt
    assert "ТОЛЬКО на основе фрагментов" in llm.last_prompt


def test_empty_question(rag):
    assert rag.ask("   ").text == NO_ANSWER


def test_off_topic_question_is_rejected(rag):
    assert rag.ask("Какая погода в Москве?").text == NO_ANSWER
