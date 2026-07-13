from __future__ import annotations

import asyncio


class ShellProtocol:
    def __init__(self, transport):
        self._transport = transport

        self._notifications = asyncio.Queue()
        self._pending = None

        self._reader_task = asyncio.create_task(self._reader())

    async def close(self):
        self._reader_task.cancel()
        try:
            await self._reader_task
        except asyncio.CancelledError:
            pass

    async def execute(self, command: str) -> str:
        if self._pending is not None:
            raise RuntimeError("Another command is executing")

        loop = asyncio.get_running_loop()
        future = loop.create_future()

        self._pending = future

        await self._transport.write((command + "\n").encode())

        try:
            return await future
        finally:
            self._pending = None

    async def notification(self) -> str:
        return await self._notifications.get()

    async def notifications(self):
        while True:
            yield await self.notification()

    async def _reader(self):
        lines = []

        while True:
            line = await self._transport.readline()

            if line in (b"\n", b"\r\n"):
                if not lines:
                    continue

                message = b"".join(lines).decode()
                lines.clear()

                if self._pending is None:
                    await self._notifications.put(message)
                else:
                    self._pending.set_result(message)
            else:
                lines.append(line)
