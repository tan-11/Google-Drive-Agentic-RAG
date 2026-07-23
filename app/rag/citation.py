from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlsplit, urlunsplit

from app.config import get_settings
from app.db.chroma import Chroma
from app.db.sqlite import DB


def normalize_page_number(value: object) -> int | None:
    if value is None or value == "":
        return None

    try:
        page_number = int(value)
    except (TypeError, ValueError):
        return None

    if page_number <= 0:
        return None

    return page_number


def build_citation_endpoint_url(
    chunk_id: str,
    backend_url: str | None = None,
) -> str:
    base_url = (backend_url or get_settings().backend_url).rstrip("/")
    return f"{base_url}/cite/{chunk_id}"


def build_citation_label(file_name: str, page_number: object | None = None) -> str:
    normalized_page = normalize_page_number(page_number)
    if normalized_page is None:
        return file_name

    return f"{file_name} · p. {normalized_page}"


def build_redirect_target(
    drive_link: str,
    page_number: object | None = None,
) -> str:
    normalized_page = normalize_page_number(page_number)
    if normalized_page is None:
        return drive_link

    parts = urlsplit(drive_link)
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            parts.query,
            f"page={normalized_page}",
        )
    )


@lru_cache(maxsize=1)
def _get_clients() -> tuple[DB, Chroma]:
    return DB(), Chroma()


def resolve_chunk_citation(chunk_id: str) -> dict[str, object] | None:
    db_client, chroma_client = _get_clients()

    file_rows = db_client.get_chunks_by_ids([chunk_id])
    if not file_rows:
        return None

    file_row = file_rows[0]
    metadata_rows = chroma_client.get_chunks_by_ids([chunk_id])
    metadata = metadata_rows[0].get("metadata", {}) if metadata_rows else {}
    page_number = normalize_page_number(metadata.get("page_number"))

    return {
        "chunk_id": chunk_id,
        "file_name": file_row["name"],
        "drive_link": file_row["drive_link"],
        "page_number": page_number,
        "redirect_url": build_redirect_target(file_row["drive_link"], page_number),
    }
