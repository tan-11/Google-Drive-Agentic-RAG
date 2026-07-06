from app.rag.hybrid_search import hybrid_search
from app.config import get_settings
from app.llm.llm import LLMClient
from app.domain import QueryIn, Conversation
import time
from app.db.sqlite import DB
from app.llm.agent import Agent

settings = get_settings()
llm = LLMClient()
db_client = DB()
agent = Agent()

def _store_conversation_history(chat_id: str, role: str, content: str):
    db_client.insert_conversation_history(chat_id, role, content)

def _get_history_messages(chat_id: str, window: int = 11) -> list[Conversation]:
    return db_client.get_conversation_history(chat_id=chat_id, window=window)

def _is_chat_id_exists(chat_id: str) -> bool:
    return db_client.check_chat_id_exists(chat_id)

def process_query(query: QueryIn):
    #1. get chat history
    history_msgs = _get_history_messages(chat_id=query.chat_id, window=11)

    full_response = ""
    for response in agent.run(query.query, history_msgs):
        full_response += response
        yield response

    if not _is_chat_id_exists(query.chat_id):
        first_conversation = f"user: {query.query}\nassistent: {full_response}"
        chat_name = llm.conversation_naming(first_conversation=first_conversation)
        db_client.insert_chat_session(chat_id=query.chat_id, chat_name=f"{chat_name} - {query.chat_id}")

    _store_conversation_history(chat_id=query.chat_id, role="user", content=query.query)
    _store_conversation_history(chat_id=query.chat_id, role="assistant", content=full_response)