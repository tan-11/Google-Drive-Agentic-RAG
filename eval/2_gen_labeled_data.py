from eval.llm import get_response
import sqlite3
import json
# prompt for llm to return question and ground truth
prompt = """
Given this document chunk:

{chunk}

Generate:
1. One factual question
2. Ground truth answer

Instruction:
1. Refer to the document chunk provided.
2. Based on the chunk information, generate a factual question, and a ground truth answer for the question.
3. The question can not too broad.
4. Too broad means the answer can probably find from others document chunk.
5. Return in JSON format.

Output JSON:
{{
    "question": "The question",
    "ground_truth": "Ground truth answer",
}}
"""

# get all chunks from test db
test_conn = sqlite3.connect("eval/data/test_chunks.db")
test_cur = test_conn.cursor()

test_cur.execute(
    """
    SELECT chunk_id, chunk_text
    FROM chunks
    """
)

rows = test_cur.fetchall()

test_data = []

for chunk_id, chunk_text in rows:
    response = get_response(prompt=prompt.format(chunk=chunk_text))
    print(response)
    test_data.append({"question": response["question"], "ground_truth": response["ground_truth"], "reference_chunk_id": chunk_id})

with open("eval/test_data_labeled.json", "w", encoding="utf-8") as file:
    json.dump(test_data, file, indent=4)

test_conn.close()