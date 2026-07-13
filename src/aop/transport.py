from __future__ import annotations

from abc import ABC, abstractmethod


class Transport(ABC):
    @abstractmethod
    async def open(self) -> None:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...

    @abstractmethod
    async def write(self, data: bytes) -> None:
        """
        Send bytes to the device.
        """
        ...

    @abstractmethod
    async def readline(self) -> bytes:
        """
        Return one complete line, including the trailing newline if present.
        """
        ...

    async def __aenter__(self):
        await self.open()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()
