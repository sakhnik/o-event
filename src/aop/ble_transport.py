import asyncio

from aop.transport import Transport
from bleak import BleakClient, BleakScanner

SERVICE_UUID = "16404bac-eab0-422c-955f-fb13799c00fa"
STDIN_UUID = "16404bac-eab1-422c-955f-fb13799c00fa"
STDOUT_UUID = "16404bac-eab2-422c-955f-fb13799c00fa"


class BleTransport(Transport):
    def __init__(self, device: str, adapter: str | None = None):
        self._device = device
        self._adapter = adapter

        self._client: BleakClient | None = None
        self._rx = bytearray()
        self._lines: asyncio.Queue[bytes] = asyncio.Queue()

    async def open(self):
        device = await BleakScanner.find_device_by_filter(
            lambda d, adv: (
                (d.name == self._device or d.address == self._device) and SERVICE_UUID.lower() in [u.lower() for u in (adv.service_uuids or [])]
            ),
            adapter=self._adapter,
        )

        if device is None:
            raise RuntimeError(f'Device "{self._device}" not found')

        self._client = BleakClient(device, adapter=self._adapter)
        await self._client.connect()

        await self._client.start_notify(
            STDOUT_UUID,
            self._notification,
        )

    async def close(self):
        if self._client:
            await self._client.disconnect()

    async def write(self, data: bytes):
        await self._client.write_gatt_char(STDIN_UUID, data)

    async def readline(self) -> bytes:
        return await self._lines.get()

    def _notification(self, _, data: bytearray):
        self._rx.extend(data)

        while True:
            try:
                i = self._rx.index(ord("\n"))
            except ValueError:
                break

            line = bytes(self._rx[: i + 1])
            del self._rx[: i + 1]

            self._lines.put_nowait(line)
