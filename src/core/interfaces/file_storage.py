"""
IFileStorage — abstract contract for persisting uploaded files.

Implementations: LocalFileStorage
Future: S3FileStorage, MinIOFileStorage
"""

from abc import ABC, abstractmethod


class IFileStorage(ABC):
    """
    Interface for reading and writing raw file bytes.
    Decouples business logic from the underlying storage backend.
    """

    @abstractmethod
    async def save(self, filename: str, content: bytes) -> str:
        """
        Persist file bytes and return the storage path/key.

        Args:
            filename: Original filename (used for extension/naming).
            content: Raw file bytes.

        Returns:
            A string path or key that can be used to read the file later.
        """
        ...

    @abstractmethod
    async def read(self, file_path: str) -> bytes:
        """
        Read raw file bytes from a storage path/key.

        Args:
            file_path: The path or key returned by save().

        Returns:
            Raw file bytes.
        """
        ...

    @abstractmethod
    async def delete(self, file_path: str) -> None:
        """
        Remove a stored file.

        Args:
            file_path: The path or key returned by save().
        """
        ...

    @abstractmethod
    async def exists(self, file_path: str) -> bool:
        """Check if a file exists at the given path/key."""
        ...
