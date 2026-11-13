"""Local file storage for uploaded builds and generated reports."""
import os

from app.core.config import settings


def storage_path(kind: str, filename: str) -> str:
    """Absolute path for a file under STORAGE_DIR/<kind>/, creating the folder if needed."""
    folder = os.path.abspath(os.path.join(settings.STORAGE_DIR, kind))
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, filename)
