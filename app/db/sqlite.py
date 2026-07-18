

import sqlite3
from datetime import datetime
from pathlib import Path

from app.domain import Conversation


class DB:
    def __init__(self, db_path: str | None = "data/rag.db"):
        self.db_path = Path(db_path).expanduser() if db_path else Path(__file__).resolve().parent.parent.parent / "data" / "rag.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self._connect() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS files (
                file_id TEXT PRIMARY KEY,
                name TEXT,
                mime_type TEXT,
                drive_link TEXT,
                modified_time TEXT,
                last_synced_at TEXT
            );

            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                chunk_text TEXT NOT NULL,
                content_hash TEXT NOT NULL UNIQUE
            );
                               
            CREATE TABLE IF NOT EXISTS chat_sessions (
                chat_id TEXT PRIMARY KEY,
                chat_name TEXT
            );

            CREATE TABLE IF NOT EXISTS conversation_history (
                chat_id TEXT REFERENCES chat_sessions(chat_id),
                role TEXT,
                content TEXT
            );

            CREATE TABLE IF NOT EXISTS app_state (
                key TEXT PRIMARY KEY,
                value TEXT                   
            );
            
            CREATE INDEX IF NOT EXISTS idx_chunks_file_id
            ON chunks(file_id);
                               
            CREATE UNIQUE INDEX IF NOT EXISTS idx_chunk_hash
            ON chunks(content_hash);
            """)

    def upsert_file(self, file):
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO files (file_id, name, mime_type, drive_link, modified_time, last_synced_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_id) DO UPDATE SET
                    name = excluded.name,
                    mime_type = excluded.mime_type,
                    drive_link = excluded.drive_link,
                    modified_time = excluded.modified_time,
                    last_synced_at = excluded.last_synced_at
                """,
                (
                    file["id"],
                    file["name"],
                    file["mimeType"],
                    file["webViewLink"],
                    file["modifiedTime"],
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )

    def insert_chunk(self, chunk, hash_value, file_id, index):
        with self._connect() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO chunks (chunk_id, file_id, chunk_index, chunk_text, content_hash)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        chunk.chunk_id,
                        file_id,
                        index,
                        chunk.text,
                        hash_value,
                    ),
                )
                return True
            except sqlite3.IntegrityError as e:
                # Log duplicate content hash or chunk ID
                print(f"[DEBUG] Skipping duplicate chunk: {chunk.chunk_id} - {str(e)}")
                return False
        
    def update_page_token(self, page_token: str):
        query = "REPLACE INTO app_state (value, key) VALUES (?,?)"
        with self._connect() as conn:
            conn.execute(query, (page_token, 'start_page_token'))
            
    def check_id_exists(self, table_name, record_id):
        query = f"SELECT EXISTS(SELECT 1 FROM {table_name} WHERE file_id = ?)"
        with self._connect() as conn:
            cursor = conn.execute(query, (record_id,))
            exists = cursor.fetchone()[0] == 1
        return exists

    def get_file(self, file_id):
        query = "SELECT * FROM files WHERE file_id = ?"
        with self._connect() as conn:
            cursor = conn.execute(query, (file_id,))
            result = [dict(row) for row in cursor.fetchall()]
        return result

    def get_all_chunks(self):
        query = "SELECT chunk_id, chunk_text FROM chunks"
        with self._connect() as conn:
            cursor = conn.execute(query)
            result = [dict(row) for row in cursor.fetchall()]
        return result

    def get_chunks_by_ids(self, chunk_ids: list[str]):
        if not chunk_ids:
            return []

        placeholders = ", ".join("?" for _ in chunk_ids)
        query = f"""SELECT c.chunk_id, c.chunk_text, f.name, f.drive_link 
        FROM chunks c
        JOIN files f
        ON c.file_id == f.file_id
        WHERE c.chunk_id IN ({placeholders})"""
        with self._connect() as conn:
            cursor = conn.execute(query, chunk_ids)
            result = [dict(row) for row in cursor.fetchall()]

        return result

    def get_app_state(self, key: str):
        query = "SELECT value FROM app_state WHERE key = ?"
        with self._connect() as conn:
            cursor = conn.execute(query, (key, ))
            result = cursor.fetchone()
        
        if result:
            return result[0]
        return None

    def delete_file_n_chunk(self, file_id):
        query_table = "DELETE FROM files WHERE file_id = ?"
        query_chunk = "DELETE FROM chunks WHERE file_id = ?"
        with self._connect() as conn:
            conn.execute(query_chunk, (file_id, ))
            conn.execute(query_table, (file_id, ))

    def delete_chunk(self, chunk_id):
        query = "DELETE FROM chunks WHERE chunk_id = ?"
        with self._connect() as conn:
            conn.execute(query, (chunk_id, ))
            
    # ======================= LLM conversation ========================

    def check_chat_id_exists(self, chat_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT EXISTS(SELECT 1 FROM chat_sessions WHERE chat_id = ?)",
                (chat_id,),
            )
            exists = cursor.fetchone()[0] == 1
        return exists

    def insert_chat_session(self, chat_id: str, chat_name: str):
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO chat_sessions (chat_id, chat_name)
                VALUES (?, ?)
                """,
                (chat_id, chat_name),
            )

    def insert_conversation_history(self, chat_id: str, role: str, content: str):
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO conversation_history (chat_id, role, content)
                VALUES (?, ?, ?)
                """,
                (chat_id, role, content),
            )

    def get_conversation_history(self, chat_id: str, window: int = 11) -> list[Conversation]:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT role, content FROM conversation_history
                WHERE chat_id = ?
                ORDER BY rowid DESC
                LIMIT ?
                """,
                (chat_id, window),
            )
            result = [Conversation(id=chat_id, role=row["role"], content=row["content"]) for row in cursor.fetchall()]
            result.reverse()
        return result

    def get_all_chat_ids(self) -> list[dict]:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT DISTINCT chat_id, chat_name FROM chat_sessions
                """
            )
            result = [{"chat_id": row["chat_id"], "chat_name": row["chat_name"]} for row in cursor.fetchall()]
        return result