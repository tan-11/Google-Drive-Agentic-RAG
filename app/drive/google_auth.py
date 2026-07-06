from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow

from app.config import Settings

def load_credential(settings: Settings) -> Credentials | None:
    token_file = Path(settings.google_token_file)
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), settings.google_scope_list)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_file.write_text(creds.to_json(), encoding="utf-8")
        return creds
    return None

def build_drive_service(settings: Settings):
    creds = load_credential(settings)
    if not creds:
        return None
    return build("drive", "v3", credentials=creds, cache_discovery=False)

def bootstrap_google_oauth(settings: Settings):
    creds_file = Path(settings.google_credentials_file)
    if not creds_file.exists():
        raise FileNotFoundError(
            f"Google client secrets file not found: {settings.google_credentials_file}"
        )
    flow = InstalledAppFlow.from_client_secrets_file(
        str(creds_file),
        settings.google_scope_list
    )
    creds = flow.run_local_server(port=0)

    token_file = Path(settings.google_token_file)
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.touch(exist_ok=True)
    token_file.write_text(creds.to_json(), encoding="utf-8")
    return creds