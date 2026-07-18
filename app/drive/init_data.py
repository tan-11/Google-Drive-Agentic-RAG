import app.drive.google_auth as google_auth
from app.config import Settings, get_settings
import app.rag.chunking as chunking
from app.db.chroma import Chroma
from app.rag.embedding import embed_text
from app.db.sqlite import DB

import hashlib
import re

def generate_hash(text):
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    text = text.strip()

    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()

def _get_files_recursive(service, folder_id="root"):
    page_token = None

    while True:
        results = service.files().list(
            q=f"'{folder_id}' in parents",
            pageSize=1000,
            fields="nextPageToken, files(id, name, mimeType, modifiedTime, webViewLink, trashed)",
            pageToken = page_token
        ).execute()
        files = results.get("files", [])

        for f in files:
            mime = f["mimeType"]
            if mime == "application/vnd.google-apps.folder":
                yield from _get_files_recursive(service, f["id"])
            else:
                yield f

        page_token = results.get("nextPageToken")
        if not page_token:
            break

def read_byte(mimeType: str, file_id: str, drive_service) -> str:
    if mimeType == "application/vnd.google-apps.document":
        content = drive_service.files().export_media(
            fileId=file_id,
            mimeType="text/plain"
        ).execute()

    elif mimeType == "application/vnd.google-apps.spreadsheet":
        content = drive_service.files().export_media(
            fileId=file_id,
            mimeType="text/csv"
        ).execute()

    elif mimeType == "application/vnd.google-apps.presentation":
        content = drive_service.files().export_media(
            fileId=file_id,
            mimeType="application/pdf"
        ).execute()
    else:
        content = drive_service.files().get_media(
            fileId=file_id
        ).execute()

    return content

def db_init(settings: Settings, db_client: DB, documentToRead: list["str"]):
    drive_service = google_auth.build_drive_service(settings)
    if drive_service is None:
        creds = google_auth.bootstrap_google_oauth(settings)
        drive_service = google_auth.build_drive_service(settings)

    chroma_client = Chroma()

    for file in _get_files_recursive(drive_service):
        
        file_id = file['id']
        mimeType = file['mimeType']
        name = file['name']
        webViewLink = file['webViewLink']
        modifiedTime = file['modifiedTime']
        trashed = file['trashed']
        chunks = None

        print("type:", mimeType, "\nname: ", name, "webViewLink: ", webViewLink)

        # pass the files exist in table
        if db_client.check_id_exists(table_name = "files", record_id = file_id):
            if db_client.get_file(file_id)[0].get("modified_time") == modifiedTime:
                print("skip")
                continue
        
        if trashed == True : 
            print("skip") 
            continue

        if mimeType in documentToRead:
            
            byte_content = read_byte(mimeType=mimeType, file_id=file_id, drive_service=drive_service)
            
                
            chunks = chunking.build_chunks(file_id=file_id, file_name = name, mime_type = mimeType, content = byte_content, source_url=None)
            
            if not chunks[0].text or not chunks[0].text.strip():
                print("no content, skip")
                continue

            db_client.upsert_file(file)
            for i , chunk in enumerate(chunks):
                hash_value = generate_hash(chunk.text)
                inserted = db_client.insert_chunk(chunk = chunk, hash_value = hash_value, index = i+1, file_id = file_id)
                
                # Only upsert to Chroma if successfully inserted in SQLite
                if inserted:
                    embeddings = embed_text(chunk.text, settings)
                    chroma_client.upsert(
                        ids=[chunk.chunk_id],
                        documents=[chunk.text],
                        embeddings=embeddings,
                        metadatas=[chunk.metadata],
                    )

    print("End of drive file...")
    startPageToken = drive_service.changes().getStartPageToken().execute()
    return startPageToken

if __name__ == "__main__":
    settings = get_settings()
    db_client = DB()
    documentToRead = [
        # PDF
        "application/pdf",

        # Microsoft Office
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # DOCX
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",        # XLSX
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",# PPTX

        # Google Workspace
        "application/vnd.google-apps.document",
        "application/vnd.google-apps.spreadsheet",
        "application/vnd.google-apps.presentation",

        # Plain text documents
        "text/plain",
    ]
    startPageToken = db_init(settings, db_client, documentToRead)
    db_client.update_page_token(startPageToken['startPageToken'])
    print(f"Completed all... Start Page Token saved ({startPageToken['startPageToken']})...")