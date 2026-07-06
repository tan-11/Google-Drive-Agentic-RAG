from dataclasses import dataclass, field
from typing import Any

@dataclass(slots=True)
class DocumentChunk:
    chunk_id : str
    file_id: str
    file_name: str
    mime_type: str
    text : str
    chunk_index: int
    section_heading: str | None = ""
    page_number: int | None = ""
    sheet_name: str | None = ""
    source_url: str | None = ""
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(slots=True)
class ExtractedSection:
    text: str
    section_heading: str | None = ""
    page_number: int | None = ""
    sheet_name: str | None = ""

@dataclass(slots=True)
class Conversation:
    id: str
    role: str
    content: str

@dataclass(slots=True)
class QueryIn:
    query: str
    chat_id: str