"""Чат в терминале: python cli.py"""
from dotenv import load_dotenv

load_dotenv()

from rag.pipeline import RAGPipeline  # noqa: E402

if __name__ == "__main__":
    rag = RAGPipeline("data")
    print("RAG Docs Assistant. Задайте вопрос (пустая строка — выход).")
    while True:
        q = input("\n> ").strip()
        if not q:
            break
        a = rag.ask(q)
        print(a.text)
        if a.sources:
            print("Источники:", ", ".join(a.sources))
