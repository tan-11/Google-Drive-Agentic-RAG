from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.responses import StreamingResponse

from app.db.sqlite import DB
from app.domain import QueryIn
from app.worker import process_query
from app.llm.agent import Agent

app = FastAPI(title = "Google Drive RAG")
db_client = DB()
agent = Agent()

@app.post("/query")
def query(query: QueryIn):
    if not query.query:
        return {"error": "Query parameter is required."}
    return StreamingResponse(process_query(query), media_type="text/plain")

@app.get("/get_chat_ids")
def list_chats():
    return db_client.get_all_chat_ids()  # return list of chat IDs

@app.get("/chats/{chat_id}")
def get_chat(chat_id: str):
    return db_client.get_conversation_history(chat_id)  # return ordered messages