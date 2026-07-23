import json
import re
import time

from openai import OpenAI

from app.config import get_settings
from app.domain import Conversation
from app.llm.tool_registry import TOOL_DEFINITIONS, TOOL_FUNCTIONS
from app.rag.citation import (
    build_citation_endpoint_url,
    build_citation_label,
    normalize_page_number,
)

settings = get_settings()
client = OpenAI(api_key=settings.agnes_api_key, base_url=settings.agnes_url)


def _history_to_messages(history_msgs: list[Conversation]) -> list[dict[str, str]]:
    return [{"role": msg.role, "content": msg.content} for msg in history_msgs]


def _replace_reference_indices(
    content: str,
    references: dict[str, dict[str, object]],
) -> str:
    if not references:
        return content

    sentences = re.split(r"(?<=[.!?])[ \t]+", content)
    rewritten_sentences = []

    for sentence in sentences:
        seen_references: set[tuple[str, object]] = set()

        def _replace(match: re.Match[str]) -> str:
            reference_key = match.group(1).strip()

            reference = references.get(reference_key)
            if not reference:
                return match.group(0)

            url = str(reference.get("url", ""))
            file_name = str(reference.get("file_name", ""))
            page_number = normalize_page_number(reference.get("page_number"))
            drive_link = str(reference.get("drive_link", ""))

            if not url:
                return match.group(0)

            dedupe_key = (drive_link or file_name, page_number)
            if dedupe_key in seen_references:
                return ""

            seen_references.add(dedupe_key)
            return f"[{build_citation_label(file_name, page_number)}]({url})"

        rewritten_sentence = re.sub(r"\[([^\]]+)\]", _replace, sentence)
        rewritten_sentences.append(rewritten_sentence)

    return "\n".join(part for part in rewritten_sentences if part)


def _replace_reference_indices_with_ids(
    content: str,
    index_to_chunk_id: dict[str, str],
) -> str:
    """Replace the citation indices emitted by the LLM with chunk IDs."""
    if not index_to_chunk_id:
        return content

    def _replace(match: re.Match[str]) -> str:
        index = match.group(1).strip()
        chunk_id = index_to_chunk_id.get(index)
        return f"[{chunk_id}]" if chunk_id else match.group(0)

    return re.sub(r"\[([^\]]+)\]", _replace, content)


def _index_tool_context(
    context: str,
    references: list[dict[str, object]],
    next_index: int,
) -> tuple[str, dict[str, str], int]:
    """Give each result in a tool response a globally unique citation index."""
    index_to_chunk_id: dict[str, str] = {}
    indexed_context = context

    for reference in references:
        chunk_id = str(reference.get("chunk_id", ""))
        if not chunk_id:
            continue

        index = str(next_index)
        next_index += 1
        index_to_chunk_id[index] = chunk_id
        indexed_context = indexed_context.replace(
            f"[{chunk_id}]", f"[{index}]", 1
        )

    return indexed_context, index_to_chunk_id, next_index


class Agent:
    def stream_completion(self, messages):
        system_message = [
            {
                "role": "system",
                "content": """
## Role
You are a personal AI assistant belong to the user named Tan Peng Rong (Ron).

## Tools
- You can call multiple tools if necessary.
### drive_search
- ALWAYS call drive search before answer user personal questions.
- Any personal information can find from drive search.
- Alway refine the user query to more informative in seaarching.
    For example:
        user: "what is my current working company?"
        query parameter: "tan peng rong working company 2026."
### web_search
- Any external information can perform web search to get knowledge.

## Instruction
- **Must** contain citations if you are reference to any references.
- When citing internal documents, cite the result index in square brackets and an **optional** section in round brackets beside it.
    For example:
        user ask: 'I am boy or girl?'
        The returned information from drive search:
        '''
        [0] Aboutme.docx
        Section: About me
        I am a boy.
        '''
        Your answer with citation:
        '''
        You are a boy.[0] (Section: About me)
        '''
- ALWAYS cite the result index exactly as it appears in the retrieved context.
- Result indices are globally unique across all drive_search calls in this conversation.
- The Section only available where "Section: ..." is provided in the chunk text.
- Follow strictly the RULES to plan the steps to answer.

## Rules (IMPORTANT)
- You must answer ONLY using the retrieved context for user internal information.
- DO NOT answer when you have not the full of truth.
- DO NOT asnwer when you have not confirm the truth.
- For any question related to the user's personal information, files, documents, projects, company information, or internal knowledge, ALWAYS call drive_search first.
    **Do not answer from memory.**
    **Do not say you don't know before performing drive_search.**
- **Do not infer.**
- **Do not guess.**
- Note that a single bracket pair only for a chunk citation, not combine multiple id in single bracket.
- Citation never cite for header, only cite for content.
- Only provide the Section where the document chunk includes the Section information.
""",
            }
        ]

        for attempt in range(3):
            print("msg: ", messages)
            try:
                stream = client.chat.completions.create(
                    model=settings.agnes_model_name,
                    messages=system_message + messages,
                    tools=TOOL_DEFINITIONS,
                    stream=True,
                )
                break
            except Exception as e:
                print(
                    f"LLM call failed "
                    f"(attempt {attempt + 1}/3): {type(e).__name__}: {e}"
                )

                if attempt == 2:
                    raise

                time.sleep(2 ** attempt)

        content = ""
        tool_calls = {}

        for chunk in stream:
            if chunk.choices:
                delta = chunk.choices[0].delta

                if delta.content:
                    content += delta.content

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        index = tc.index

                        if index not in tool_calls:
                            tool_calls[index] = {
                                "id": "",
                                "name": "",
                                "arguments": "",
                            }

                        if tc.id:
                            tool_calls[index]["id"] = tc.id

                        if tc.function:
                            if tc.function.name:
                                tool_calls[index]["name"] = tc.function.name

                            if tc.function.arguments:
                                tool_calls[index]["arguments"] += tc.function.arguments

        return content, list(tool_calls.values())

    def run(self, user_query: str, chat_history=None):
        if chat_history:
            messages = [
                *_history_to_messages(chat_history),
                {"role": "user", "content": user_query},
            ]
        else:
            messages = [{"role": "user", "content": user_query}]

        reference_map: dict[str, dict[str, object]] = {}
        index_to_chunk_id: dict[str, str] = {}
        next_reference_index = 0

        while True:
            content, tool_calls = self.stream_completion(messages)

            if not tool_calls:
                print("ori response: ", content)
                content_with_ids = _replace_reference_indices_with_ids(
                    content, index_to_chunk_id
                )
                final_content = _replace_reference_indices(
                    content_with_ids, reference_map
                )
                yield final_content
                return

            messages.append(
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": tc["arguments"],
                            },
                        }
                        for tc in tool_calls
                    ],
                }
            )

            for tc in tool_calls:
                args = json.loads(tc["arguments"])
                print(f"calling {tc['name']}...")
                print(f"arguments: {args}")
                result = TOOL_FUNCTIONS[tc["name"]](**args)

                if isinstance(result, dict):
                    references = result.get("references", [])
                    tool_content = result.get("context", "")
                    (
                        tool_content,
                        call_index_map,
                        next_reference_index,
                    ) = _index_tool_context(
                        tool_content,
                        references,
                        next_reference_index,
                    )
                    index_to_chunk_id.update(call_index_map)

                    for reference in references:
                        chunk_id = reference.get("chunk_id")
                        drive_link = reference.get("drive_link", "")
                        file_name = reference.get("file_name", "")
                        page_number = normalize_page_number(reference.get("page_number"))

                        if chunk_id is not None and drive_link:
                            reference_map[str(chunk_id)] = {
                                "url": build_citation_endpoint_url(
                                    str(chunk_id),
                                    backend_url=settings.backend_url,
                                ),
                                "file_name": file_name,
                                "page_number": page_number,
                                "drive_link": drive_link,
                            }

                    print("tool_content: ", tool_content)
                else:
                    tool_content = str(result)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": tool_content,
                    }
                )
