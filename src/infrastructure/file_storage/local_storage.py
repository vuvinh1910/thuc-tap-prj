"""
LocalFileStorage — saves uploaded files to the local filesystem.
Implements IFileStorage for MVP. Replace with S3FileStorage for production.
"""

import os
import uuid
from pathlib import Path

import aiofiles

from src.core.interfaces.file_storage import IFileStorage


class LocalFileStorage(IFileStorage):
    """
    Stores files in a local directory structure:
    {base_dir}/{uuid}_{original_filename}
    """

    def __init__(self, base_dir: str = "./uploads") -> None:
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)

    async def save(self, filename: str, content: bytes) -> str:
        """Save file with a UUID prefix to avoid name collisions."""
        safe_filename = f"{uuid.uuid4().hex}_{filename}"
        file_path = self._base_dir / safe_filename

        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

        return str(file_path)

    async def read(self, file_path: str) -> bytes:
        async with aiofiles.open(file_path, "rb") as f:
            return await f.read()

    async def delete(self, file_path: str) -> None:
        path = Path(file_path)
        if path.exists():
            os.remove(path)

    async def exists(self, file_path: str) -> bool:
        return Path(file_path).exists()
