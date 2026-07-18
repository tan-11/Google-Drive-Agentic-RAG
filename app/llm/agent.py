import json
import re
import time

from openai import OpenAI

from app.config import get_settings
from app.domain import Conversation

from app.llm.tool_registry import TOOL_DEFINITIONS, TOOL_FUNCTIONS

settings = get_settings()
client = OpenAI(api_key=settings.agnes_api_key, base_url=settings.agnes_url)

def _history_to_messages(history_msgs: list[Conversation]) -> list[dict[str, str]]:
    return [{"role": msg.role, "content": msg.content} for msg in history_msgs]


import re


def _replace_reference_indices(
    content: str,
    references: dict[str, tuple[str, str]]
) -> str:
    print("reference\n", references)

    if not references:
        return content

    sentences = re.split(r"(?<=[.!?])\s+", content)
    rewritten_sentences = []

    for sentence in sentences:
        seen_references: set[tuple[str, str]] = set()

        def _replace(match: re.Match[str]) -> str:
            reference_key = match.group(1).strip()

            reference = references.get(reference_key)
            if not reference:
                return match.group(0)

            url, file_name = reference

            if not url:
                return match.group(0)

            dedupe_key = (url, file_name)

            if dedupe_key in seen_references:
                return ""

            seen_references.add(dedupe_key)

            return f"[{file_name}]({url})"

        rewritten_sentence = re.sub(
            r"\[([^\]]+)\]",
            _replace,
            sentence,
        )

        rewritten_sentence = re.sub(
            r"\b(and|or)\s+(?:and|or)\b",
            r"\1",
            rewritten_sentence,
        )

        rewritten_sentence = re.sub(
            r"\s{2,}",
            " ",
            rewritten_sentence,
        ).strip()

        rewritten_sentences.append(rewritten_sentence)

    return "\n".join(
        part for part in rewritten_sentences
        if part
    )


class Agent:
    def stream_completion(self, messages):
        system_message = [
            {
                "role": "system",
                "content": """
## Role
You are a personal AI assistant belong to the user.

## Intruction
- You may use tools when needed.
- Any personal information can find from drive search.
- Any external information can perform web search to get knowledge.
- You can call multiple tools if necessary.
- Only answer when you have enough information.
- **Must** contain citations if you are reference to any references.
- When citing internal documents, cites it as a bracketed id.
    For example:
    user ask: 'I am boy or girl?'
    The returned information from drive search: 
    '''
    [1NrJanasjfoTsxIVfT_CgXc4Gis7D0Xu:f8b776c20d38cea59a0f1042] Aboutme.pdf
    I am a boy.
    '''
    Your answer with citation:
    '''
    You are a boy.[1NrJanasjfoTsxIVfT_CgXc4Gis7D0Xu:f8b776c20d38cea59a0f1042]
    '''
- Note that a single bracket only for a chunk citation, not combine multiple id in single bracket.
""",
            }
        ]

        for attempt in range(3):
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

        reference_map: dict[str, tuple[str, str]] = {}

        while True:
            content, tool_calls = self.stream_completion(messages)

            if not tool_calls:
                print("ori response: ", content)
                final_content = _replace_reference_indices(content, reference_map)
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
                result = TOOL_FUNCTIONS[tc["name"]](**args)
                print(f"calling {tc["name"]}...")
                print(f"arguments: {args}")

                if isinstance(result, dict):
                    references = result.get("references", [])
                    for reference in references:
                        chunk_id = reference.get("chunk_id")
                        drive_link = reference.get("drive_link", "")
                        file_name = reference.get("file_name", "")
                        if chunk_id is not None and drive_link:
                            reference_map[chunk_id] = (drive_link, file_name)
                    
                    tool_content = result.get("context", "")
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