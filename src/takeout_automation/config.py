import os
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Download and execution parameters
    download_path: Path = Path("./takeout-downloads")

    # Browser automation parameters
    executable_path: str | None = None
    user_data_dir: Path = Path("./takeout-profile")

    # Authentication parameters
    google_pass: str | None = None

    @field_validator("executable_path")
    @classmethod
    def validate_executable_path(cls, v: str | None) -> str | None:
        if v is not None and not os.path.isfile(v):
            raise ValueError(f"executable_path '{v}' does not exist or is not a file")
        return v


settings = Settings()
