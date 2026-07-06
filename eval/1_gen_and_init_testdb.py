import sqlite3
from eval.utils.chroma import Chroma
from app.rag.embedding import embed_text
from app.config import get_settings
from pathlib import Path

live_conn = sqlite3.connect("data/rag.db")
live_cur = live_conn.cursor()

test_db_path = Path("eval/data/test_chunks.db")
test_db_path.parent.mkdir(parents=True, exist_ok=True)
test_conn = sqlite3.connect(test_db_path)
test_cur = test_conn.cursor()

# Create table in test first
test_cur.execute("""
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    file_id TEXT NOT NULL,
    chunk_text TEXT NOT NULL
);
""")

# Get first 100 rows
live_cur.execute("""
SELECT chunk_id, file_id, chunk_text
FROM chunks
LIMIT 100
""")

rows = live_cur.fetchall()

# Insert into test sqlite
test_cur.executemany("""
INSERT INTO chunks (chunk_id, file_id, chunk_text)
VALUES (?, ?, ?)
""", rows)
test_conn.commit()

#embedding chunk test and store into test chroma
chroma_client = Chroma()
for id, _, chunk_text in rows:
    embedding = embed_text(chunk_text, get_settings())
    chroma_client.add([id], [embedding])

live_conn.close()
test_conn.close()