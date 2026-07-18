from __future__ import annotations

import io
import re
from dataclasses import replace
from hashlib import sha1
from pathlib import Path
from typing import Iterable

import pandas as pd
from docx import Document as DocxDocument
from pypdf import PdfReader
import tiktoken

from app.domain import DocumentChunk, ExtractedSection

_encoder = tiktoken.get_encoding("cl100k_base")

def _clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _chunk_text(
    text: str,
    max_tokens: int,
    overlap_tokens: int,
) -> list[str]:

    text = _clean_text(text)
    if not text:
        return []

    tokens = _encoder.encode(text)
    total = len(tokens)

    if total <= max_tokens:
        return [text]

    chunks: list[str] = []
    start = 0

    while start < total:
        end = min(start + max_tokens, total)

        chunk_tokens = tokens[start:end]
        chunk_text = _encoder.decode(chunk_tokens).strip()

        if chunk_text:
            chunks.append(chunk_text)

        # sliding window
        if end == total:
            break

        start += max_tokens - overlap_tokens

    return chunks


def _read_txt(content: bytes) -> list[ExtractedSection]:
    return [ExtractedSection(text=content.decode("utf-8", errors="ignore"))]


def _read_pdf(content: bytes) -> list[ExtractedSection]:
    reader = PdfReader(io.BytesIO(content))
    sections: list[ExtractedSection] = []
    for index, page in enumerate(reader.pages, start=1):
        sections.append(ExtractedSection(text=page.extract_text() or "", page_number=index))
    return sections


def _read_docx(content: bytes) -> list[ExtractedSection]:
    document = DocxDocument(io.BytesIO(content))
    sections: list[ExtractedSection] = []
    current_heading: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer, current_heading
        if buffer:
            sections.append(ExtractedSection(text="\n".join(buffer), section_heading=current_heading))
            buffer = []

    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        style = getattr(paragraph.style, "name", "") or ""
        if style.lower().startswith("heading"):
            flush()
            current_heading = text
            continue
        buffer.append(text)
    flush()
    if not sections:
        sections.append(ExtractedSection(text=""))
    return sections


def _read_xlsx(content: bytes) -> list[ExtractedSection]:
    workbook = pd.ExcelFile(io.BytesIO(content))
    sections: list[ExtractedSection] = []
    for sheet_name in workbook.sheet_names:
        frame = workbook.parse(sheet_name)
        sections.append(
            ExtractedSection(
                text=f"Sheet: {sheet_name}\n" + frame.to_csv(index=False),
                sheet_name=sheet_name,
            )
        )
    return sections


def extract_sections(file_name: str, mime_type: str, content: bytes) -> list[ExtractedSection]:
    lower_name = file_name.lower()
    if mime_type == "application/pdf" or lower_name.endswith(".pdf"):
        return _read_pdf(content)
    if (
        mime_type
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        or lower_name.endswith(".docx")
    ):
        return _read_docx(content)
    if (
        mime_type
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        or lower_name.endswith(".xlsx")
    ):
        return _read_xlsx(content)
    return _read_txt(content)

def _build_context(
    file_name: str,
    section_heading: str | None,
) -> str:
    parts = [f"Document: {file_name}"]

    if section_heading:
        parts.append(f"Section: {section_heading}")

    return "\n".join(parts)

def build_chunks(
    *,
    file_id: str,
    file_name: str,
    mime_type: str,
    source_url: str | None,
    content: bytes,
    chunk_size: int = 500,          # tokens 
    chunk_overlap: int = 80,        # tokens
) -> list[DocumentChunk]:

    sections = extract_sections(file_name=file_name, mime_type=mime_type, content=content)

    chunks: list[DocumentChunk] = []
    chunk_index = 0

    for section in sections:

        context_prefix = _build_context(
            file_name=file_name,
            section_heading=section.section_heading,
        )
        full_text = f"{context_prefix}\n\n{section.text}"
        pieces = _chunk_text(full_text, chunk_size, chunk_overlap)

        for piece in pieces:

            fingerprint = sha1(
                f"{file_id}:{chunk_index}:{piece[:120]}".encode("utf-8", errors="ignore")
            ).hexdigest()[:24]

            chunks.append(
                DocumentChunk(
                    chunk_id=f"{file_id}:{fingerprint}",
                    file_id=file_id,
                    file_name=file_name,
                    mime_type=mime_type,
                    text=piece,
                    chunk_index=chunk_index,

                    section_heading=section.section_heading,
                    page_number=section.page_number,
                    sheet_name=section.sheet_name,
                    source_url=source_url,

                    metadata={
                        k: v for k, v in {
                            "file_id": file_id,
                            "page_number": section.page_number,
                            "sheet_name": section.sheet_name,
                            "section_heading": section.section_heading,
                            "token_chunk_size": chunk_size,
                            "token_overlap": chunk_overlap,
                        }.items() if v is not None
                    },
                )
            )

            chunk_index += 1

    return chunks