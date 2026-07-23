from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.responses import RedirectResponse, StreamingResponse

from app.db.sqlite import DB
from app.domain import QueryIn
from app.rag.citation import resolve_chunk_citation
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


@app.get("/cite/{chunk_id}")
def cite_chunk(chunk_id: str):
    citation = resolve_chunk_citation(chunk_id)
    if not citation:
        raise HTTPException(status_code=404, detail="Citation not found.")

    return RedirectResponse(url=str(citation["redirect_url"]), status_code=302)
