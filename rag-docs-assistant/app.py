"""REST API: uvicorn app:app --reload"""
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel, Field

load_dotenv()

from rag.pipeline import RAGPipeline  # noqa: E402

app = FastAPI(title="RAG Docs Assistant", version="1.0.0")
rag = RAGPipeline(os.getenv("DOCS_DIR", "data"))


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class AnswerOut(BaseModel):
    answer: str
    sources: list[str]


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "chunks": len(rag.index.chunks)}


@app.post("/ask", response_model=AnswerOut)
def ask(q: Question) -> AnswerOut:
    a = rag.ask(q.question)
    return AnswerOut(answer=a.text, sources=a.sources)


@app.post("/reindex")
def reindex() -> dict:
    return {"chunks": rag.reindex()}
