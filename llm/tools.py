import json

from app.rag.hybrid_search import hybrid_search
from app.config import get_settings

from tavily import TavilyClient

settings = get_settings()


def _drive_search(query: str, k: int = 10) -> dict[str, object]:
    """
    Return structured document context plus per-chunk references.
    The agent can cite results as [0], [1], ... and the final answer
    can later be rewritten into clickable links.
    """
    retrieved_chunks = hybrid_search(query, settings=settings, k=k)

    context_parts = []
    references = []

    for chunk in retrieved_chunks:
        chunk_id = chunk.get("chunk_id", "")
        file_name = chunk.get("file_name", "")
        chunk_text = chunk.get("chunk_text", "")
        drive_link = chunk.get("drive_link", "")

        context_parts.append(
            f"[{chunk_id}] {file_name}\n{chunk_text}\n"
        )

        references.append(
            {
                "chunk_id": chunk_id,
                "file_name": file_name,
                "chunk_text": chunk_text,
                "drive_link": drive_link,
            }
        )

    return {
        "context": "\n\n".join(context_parts),
        "references": references,
    }


tavily_client = TavilyClient(api_key=settings.tavily_api_key)


def _web_search(query: str, max_results: int = 5) -> str:
    response = tavily_client.search(
        query=query,
        search_depth="advanced",
        max_results=max_results,
    )

    results = []

    for item in response["results"]:
        results.append(
            f"""
Title: {item['title']}

Content:
{item['content']}

URL:
{item['url']}
"""
        )

    return "\n\n".join(results)
