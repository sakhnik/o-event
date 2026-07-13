#!/usr/bin/env python

import asyncio
from aop.ble_transport import BleTransport
from aop.shell_protocol import ShellProtocol


async def main():
    async with BleTransport("AOP 1", "hci1") as transport:
        # transport = SerialTransport("/dev/ttyUSB0")
        shell = ShellProtocol(transport)

        print(await shell.execute("info"))
        print(await shell.execute("stats"))
        print(await shell.execute("card-readout"))

        async for notification in shell.notifications():
            print(notification)


if __name__ == "__main__":
    asyncio.run(main())
