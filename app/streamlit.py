import uuid
import streamlit as st
import requests

BACKEND_URL = "http://127.0.0.1:8000"

# helper API calls
def fetch_chats():
    r = requests.get(f"{BACKEND_URL}/get_chat_ids")
    r.raise_for_status()
    return r.json() # return [{"chat_id": "", "chat_name": ""}, ...]

def fetch_chat_messages(chat_id):
    r = requests.get(f"{BACKEND_URL}/chats/{chat_id}")
    r.raise_for_status()
    return r.json()  # expect list of {role, content}


# session init
if "chat_id" not in st.session_state:
    st.session_state.chat_id = uuid.uuid4().hex
if "chats" not in st.session_state:
    st.session_state.chats = {}

# Sidebar: list + controls
with st.sidebar:
    st.header("Chats")
    backend_chats = fetch_chats()
    chat_map = {c["chat_name"]: c["chat_id"] for c in backend_chats}
    try:
        options = ["Create new chat"] + list(name for name, _ in chat_map.items())
    except Exception:
        options = ["Create new chat"] + list(st.session_state.chats.keys())

    choice = st.selectbox("Select chat", options)
    
    if st.button("Create new chat"):
        new_id = uuid.uuid4().hex
        st.session_state.chat_id = new_id
        st.session_state.chats[new_id] = []
    elif choice != "Create new chat":
        # load selected chat from backend if not already in session
        chat_id = chat_map[choice]   
        st.session_state.chat_id = chat_id
        if chat_id not in st.session_state.chats:
            try:
                msgs = fetch_chat_messages(chat_id)
                st.session_state.chats[chat_id] = msgs
            except Exception:
                st.session_state.chats[chat_id] = []

        

# show messages for current chat
for message in st.session_state.chats.get(st.session_state.chat_id, []):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# input & query (streaming)
if prompt := st.chat_input("Ask me anything..."):
    payload = {"query": prompt, "chat_id": st.session_state.chat_id}

    # append user locally and to backend/store via /query
    st.session_state.chats.setdefault(st.session_state.chat_id, []).append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    def stream():
        with requests.post(f"{BACKEND_URL}/query", json=payload, stream=True) as response:
            response.raise_for_status()

            for chunk in response.iter_content(chunk_size=1024, decode_unicode=True):
                if chunk:
                    yield chunk

    full_response = ""
    with st.chat_message("assistant"):
        placeholder = st.empty()

        for chunk in stream():
            full_response += chunk
            placeholder.markdown(full_response)
      

    st.session_state.chats[st.session_state.chat_id].append({"role": "assistant", "content": full_response})