#!/usr/bin/env python3

import asyncio

from aop.ble_transport import BleTransport, SerialTransport
from aop.shell_protocol import ShellProtocol


USE_BLE = False
SERIAL_DEVICE = "/dev/ttyUSB0"
HCI_DEVICE = "hci1"
AOP = "AOP 1"


async def stdin_task(shell: ShellProtocol):
    loop = asyncio.get_running_loop()

    while True:
        try:
            line = await loop.run_in_executor(None, input, f"{AOP}> ")
        except EOFError:
            break

        if not line:
            continue

        if line in ("quit", "exit"):
            break

        try:
            response = await shell.execute(line)
            print(response, end="" if response.endswith("\n") else "\n")
        except Exception as e:
            print(f"Error: {e}")

    raise asyncio.CancelledError()


async def notification_task(shell: ShellProtocol):
    async for notification in shell.notifications():
        print(notification, end="" if notification.endswith("\n") else "\n")


def get_transport():
    if USE_BLE:
        return BleTransport(AOP, HCI_DEVICE)
    return SerialTransport(SERIAL_DEVICE)


async def main():
    async with get_transport() as transport:
        shell = ShellProtocol(transport)

        stdin = asyncio.create_task(stdin_task(shell))
        notifications = asyncio.create_task(notification_task(shell))

        done, pending = await asyncio.wait(
            {stdin, notifications},
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()

        await asyncio.gather(*pending, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())
