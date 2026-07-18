from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow

from app.config import Settings

def load_credential(settings: Settings) -> Credentials | None:
    token_file = Path(settings.google_token_file)
    creds = None
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), settings.google_scope_list)

    if creds and creds.valid:
        return creds
    
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            token_file.write_text(creds.to_json(), encoding="utf-8")
            return creds
        
        except Exception:
            print("Refresh token invalid, recreating credentials")
            creds = None
    if creds is None:
        return bootstrap_google_oauth(settings)
    

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
    creds = flow.run_local_server(
        port=0,
        access_type="offline",
        prompt="consent"
    )

    token_file = Path(settings.google_token_file)
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.touch(exist_ok=True)
    token_file.write_text(creds.to_json(), encoding="utf-8")
    return creds