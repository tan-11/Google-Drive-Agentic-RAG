# Google Drive RAG

Google Drive RAG is a lightweight retrieval-augmented generation (RAG) application that indexes files from Google Drive, stores their chunks locally, and lets you chat with your documents through a simple FastAPI backend and Streamlit UI.

## What it does

- Connects to Google Drive and imports supported document types
- Splits documents into chunks and stores them locally
- Builds embeddings and indexes them for semantic retrieval
- Uses a hybrid retrieval pipeline (keyword + semantic + reranking)
- Exposes a chat-style interface for asking questions over your Drive content
- Supports tool-augmented LLM responses for Drive and web search
- References links are provided in the response in any

## Architecture

- Backend API: FastAPI
- Frontend UI: Streamlit
- Vector store: Chroma
- Local database: SQLite
- Retrieval: BM25 + embeddings + reranking
- LLM access: OpenAI-compatible endpoint

## Requirements

- Python 3.14+
- uv
- A Google Cloud project with Drive API enabled
- An LLM provider API key (for example, Agnes)
- Optional: Tavily API key for web search

## Setup

1. Clone the repository
2. Install dependencies:

   ```bash
   uv sync
   ```

3. Create a `.env` file using the templete of `.env.example` and fill in the required settings. You can change models.

    ```bash
   cp .env.example .env
   ```

4. Authenticate with Google Drive. On first run, the app will prompt for OAuth access and store credentials in the `data` folder.

## Index your Google Drive documents

For first run, run the ingestion script to crawl Drive files, chunk them, and build the local index:

```bash
uv run python -m app.drive.init_data
```

This will populate the SQLite database and Chroma index used by the retrieval pipeline.

## Sync data with google drive files

```bash
uv run python -m app.drive.sync_files
```
The data will sync every 1 minute by running this script.

## Run the application

Start the FastAPI backend:

```bash
uv run uvicorn app.fastapi:app --reload
```

In a second terminal, start the Streamlit UI:

```bash
uv run streamlit run app/streamlit.py
```

Then open the Streamlit URL shown in the terminal.

## Project structure

- [app/drive/](app/drive/) – Google Drive outhentication, ingestion and indexing
- [app/rag/](app/rag/) – chunking, embedding, and retrieval pipeline
- [app/fastapi.py](app/fastapi.py) – backend API
- [app/streamlit.py](app/streamlit.py) – chat UI
- [app/llm/agent.py](app/llm/agent.py) – agent orchestration and citation rewriting
- [llm/tools.py](llm/tools.py) – tool implementations for Drive/web search
- [eval/3_retrieval_eval.ipynb](eval/3_retrieval_eval.ipynb) - Eval results

## Notes

- The app currently targets personal Google Drive content and uses local storage for indexing.
- The ingestion flow is designed for a local development workflow rather than a production-scale deployment.
