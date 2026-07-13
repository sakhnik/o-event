#!/usr/bin/env python

import asyncio
from aop.ble_transport import BleTransport


async def main():
    async with BleTransport("AOP 1", "hci1") as transport:
        # transport = SerialTransport("/dev/ttyUSB0")

        await transport.write(b"info\n")

        while True:
            line = await transport.readline()
            print(line.decode(), end="")


if __name__ == "__main__":
    asyncio.run(main())
