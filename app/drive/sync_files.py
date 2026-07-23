from app.db.sqlite import DB
from app.drive.init_data import generate_hash, read_byte
from app.rag.chunking import build_chunks
from app.rag.embedding import embed_text
from app.drive.google_auth import build_drive_service, bootstrap_google_oauth
from app.config import get_settings, Settings
from app.db.chroma import Chroma

import time
import traceback

def delete_file(file_id, db_client: DB, chroma_client: Chroma):
    db_client.delete_file_n_chunk(file_id=file_id)
    chroma_client.delete_rows_by_fileid(file_id=file_id)
    

def create_file(file, drive_service, chroma_client: Chroma, db_client: DB, settings: Settings):
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
    if file['mimeType'] in documentToRead:
        byte_content = read_byte(mimeType=file['mimeType'], 
                                 file_id=file['id'], 
                                 drive_service=drive_service)
        chunks = build_chunks(file_id=file['id'], 
                              file_name=file['name'], 
                              mime_type=file['mimeType'], 
                              source_url=None, 
                              content=byte_content)
        if not chunks:
            print("No chunks generated")
            return

        if not chunks[0].text.strip():
            print("No content")
            return
        db_client.upsert_file(file)
        for i , chunk in enumerate(chunks):
            hash_value = generate_hash(chunk.text)
            inserted = db_client.insert_chunk(chunk = chunk, 
                                              hash_value = hash_value, 
                                              index = i+1, 
                                              file_id = file['id'])
            
            # Only upsert to Chroma if successfully inserted in SQLite
            if inserted:
                try:
                    embeddings = embed_text(chunk.text, settings)
                    chroma_client.upsert(
                        ids=[chunk.chunk_id],
                        documents=[chunk.text],
                        embeddings=embeddings,
                        metadatas=[chunk.metadata],
                    ) 
                except:
                    # if failed to insert embedding, delete also the chunk
                    db_client.delete_chunk(chunk_id=chunk.chunk_id)
                
    else:
        print(
            f"Skipping unsupported file type: "
            f"{file['mimeType']}"
        )

def update_file(file, db_client: DB, chroma_client: Chroma, drive_service, settings: Settings):
    delete_file(file_id=file['id'], db_client=db_client, chroma_client=chroma_client)
    create_file(file=file, drive_service=drive_service, chroma_client=chroma_client, db_client=db_client, settings=settings)


def process_changes(page_token, db_client: DB, chroma_client: Chroma, drive_service, settings: Settings):
    while True:
        response = drive_service.changes().list(
            pageToken=page_token,
            fields=(
                "nextPageToken,"
                "newStartPageToken,"
                "changes("
                    "fileId,"
                    "removed,"
                    "file("
                        "id,"
                        "name,"
                        "mimeType,"
                        "modifiedTime,"
                        "webViewLink,"
                        "trashed"
                    ")"
                ")"
            )
        ).execute()

        changes = response.get('changes', [])
        # process changes
        for change in changes:

            file_id = change["fileId"]
            file = change.get("file")

            existing_file = db_client.get_file(file_id)
            if change.get("removed") or (file and file.get("trashed")):
                delete_file(file_id=file_id, 
                            db_client=db_client, 
                            chroma_client=chroma_client)
                print("Deleted file: ", file_id)

            elif not existing_file:
                create_file(file=file, 
                            drive_service=drive_service, 
                            chroma_client=chroma_client,
                            db_client=db_client,
                            settings=settings)
                print("Created file: ", file['name'])

            elif existing_file[0]['modified_time'] != file.get("modifiedTime"):
                update_file(file, 
                            db_client=db_client, 
                            chroma_client=chroma_client, 
                            drive_service=drive_service,
                            settings=settings)
                print("Updated file: ", file['name'])
        # check end
        next_page_token = response.get("nextPageToken")

        if not next_page_token:
            return response.get('newStartPageToken')

        page_token = next_page_token


if __name__ == "__main__":
    settings = get_settings()

    drive_service = build_drive_service(settings)
    if drive_service is None:
        creds = bootstrap_google_oauth(settings)
        drive_service = build_drive_service(settings)

    db_client = DB()
    chroma_client = Chroma()

    while True:
        start_page_token = db_client.get_app_state("start_page_token")
        try:
            newStartPageToken = process_changes(page_token=start_page_token, 
                            db_client=db_client, 
                            chroma_client=chroma_client, 
                            drive_service=drive_service,
                            settings=settings)
            if newStartPageToken:
                db_client.update_page_token(
                    page_token=newStartPageToken
                )
                print("Token Updated...")
        except Exception as e:
            traceback.print_exc()
        print("Sleep 1 minute...")
        time.sleep(60)
