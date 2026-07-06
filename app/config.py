from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file = ".env",
        env_file_encoding = "utf-8",
    )

    google_credentials_file : str = "data/google_credentials.json"
    google_token_file : str = "data/google_token.json"
    google_scope_list : list[str] = [
        "https://www.googleapis.com/auth/drive.readonly"
    ]

    openrouter_api_key: str = ""
    agnes_api_key: str = ""
    tavily_api_key: str = ""

    agnes_url: str = "https://apihub.agnes-ai.com/v1"

    agnes_model_name: str = "agnes-2.0-flash"
    hf_token: str = ""

def get_settings() -> Settings:
    return Settings()