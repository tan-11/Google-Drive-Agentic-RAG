from app.llm.agent import (
    _index_tool_context,
    _replace_reference_indices,
    _replace_reference_indices_with_ids,
)
from app.rag.citation import build_citation_label, build_redirect_target


def test_build_citation_label_includes_page():
    assert build_citation_label("Report.pdf", 4) == "Report.pdf · p. 4"


def test_build_citation_label_without_page():
    assert build_citation_label("Report.pdf", None) == "Report.pdf"


def test_build_redirect_target_appends_page_fragment():
    assert (
        build_redirect_target("https://drive.google.com/file/d/abc/view", 4)
        == "https://drive.google.com/file/d/abc/view#page=4"
    )


def test_replace_reference_indices_rewrites_chunk_ids():
    content = "First line [id1]."
    references = {
        "id1": {
            "url": "https://example.com/a",
            "file_name": "Report.pdf",
            "page_number": 4,
            "drive_link": "https://drive.google.com/a",
        }
    }

    result = _replace_reference_indices(content, references)

    assert "[Report.pdf · p. 4](https://example.com/a)" in result


def test_replace_reference_indices_with_ids_uses_index_map():
    content = "First line [3]. Second line [4]."
    index_to_chunk_id = {"3": "chunk-a", "4": "chunk-b"}

    assert _replace_reference_indices_with_ids(content, index_to_chunk_id) == (
        "First line [chunk-a]. Second line [chunk-b]."
    )


def test_index_tool_context_keeps_indices_unique_across_search_calls():
    first_context, first_map, next_index = _index_tool_context(
        "[chunk-a] A\n[chunk-b] B",
        [{"chunk_id": "chunk-a"}, {"chunk_id": "chunk-b"}],
        0,
    )
    second_context, second_map, next_index = _index_tool_context(
        "[chunk-c] C",
        [{"chunk_id": "chunk-c"}],
        next_index,
    )

    assert first_context == "[0] A\n[1] B"
    assert second_context == "[2] C"
    assert first_map == {"0": "chunk-a", "1": "chunk-b"}
    assert second_map == {"2": "chunk-c"}
    assert next_index == 3


def test_replace_reference_indices_preserves_markdown_newlines():
    content = """### PowerDockerLab
*   **Programming Languages:** Python, Bash/Shell.

### SQL Agent Project
*   **Programming Languages:** Python, JavaScript.

Sources: [chunk-a], [chunk-b]"""
    references = {
        "chunk-a": {
            "url": "https://example.com/a",
            "file_name": "PowerDockerLab.md",
            "drive_link": "https://drive.google.com/a",
        },
        "chunk-b": {
            "url": "https://example.com/b",
            "file_name": "SQL Agent.md",
            "drive_link": "https://drive.google.com/b",
        },
    }

    result = _replace_reference_indices(content, references)

    assert "### PowerDockerLab\n*   **Programming Languages:**" in result
    assert "\n\n### SQL Agent Project\n" in result
    assert "[PowerDockerLab.md](https://example.com/a)" in result
    assert "[SQL Agent.md](https://example.com/b)" in result
