import serial_asyncio
from transport import Transport


class SerialTransport(Transport):
    def __init__(self, port: str, baudrate: int = 115200):
        self._port = port
        self._baudrate = baudrate

        self._reader = None
        self._writer = None

    async def open(self):
        self._reader, self._writer = await serial_asyncio.open_serial_connection(
            url=self._port,
            baudrate=self._baudrate,
        )

    async def close(self):
        self._writer.close()
        await self._writer.wait_closed()

    async def write(self, data: bytes):
        self._writer.write(data)
        await self._writer.drain()

    async def readline(self) -> bytes:
        return await self._reader.readline()
