"""Загрузка документов и нарезка на фрагменты (chunks)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

SUPPORTED = {".md", ".txt", ".pdf"}


@dataclass
class Chunk:
    text: str
    source: str  # имя файла
    index: int   # номер фрагмента внутри файла


def read_file(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader  # импорт по требованию: pypdf нужен только для PDF
        return "\n\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    return path.read_text(encoding="utf-8")


def split_text(text: str, max_chars: int = 800, overlap: int = 150) -> list[str]:
    """Режет текст по абзацам, склеивая их в куски до max_chars.

    Слишком длинный абзац режется на части с перекрытием overlap,
    чтобы смысл на границе кусков не терялся.
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""
    for p in paragraphs:
        if len(p) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            step = max_chars - overlap
            chunks.extend(p[i:i + max_chars] for i in range(0, len(p), step))
            continue
        candidate = f"{current}\n\n{p}" if current else p
        if len(candidate) <= max_chars:
            current = candidate
        else:
            chunks.append(current)
            current = p
    if current:
        chunks.append(current)
    return chunks


def split_sections(text: str) -> list[str]:
    """Делит markdown по заголовкам (#, ##, ###): один раздел — одна тема."""
    return [s.strip() for s in re.split(r"\n(?=#{1,3} )", text) if s.strip()]


def load_documents(folder: str | Path, max_chars: int = 800) -> list[Chunk]:
    folder = Path(folder)
    result: list[Chunk] = []
    for path in sorted(folder.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED:
            pieces = [piece for section in split_sections(read_file(path))
                      for piece in split_text(section, max_chars=max_chars)]
            for i, piece in enumerate(pieces):
                result.append(Chunk(text=piece, source=path.name, index=i))
    return result
