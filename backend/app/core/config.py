from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "eBon Reader"
    db_path: str = "ebon_reader.db"
    upload_dir: str = "uploads"
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "tauri://localhost",
        "http://tauri.localhost",
        "https://tauri.localhost",
    ]

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.db_path}"

    @property
    def upload_path(self) -> Path:
        path = Path(self.upload_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    model_config = {"env_prefix": "EBON_"}


settings = Settings()
