#!/usr/bin/env python

import asyncio
import contextlib
from dataclasses import dataclass
import traceback

from aop.ble_transport import BleTransport, SerialTransport
from aop.shell_protocol import ShellProtocol
from o_event.card_processor import PunchReadout, PunchItem, CardProcessor
from o_event.printer import PrinterMux
from o_event.db import SessionLocal


USE_BLE = False
SERIAL_DEVICE = "/dev/ttyUSB0"
HCI_DEVICE = "hci1"
STATION_NUMBER = 1
AOP = f"AOP {STATION_NUMBER}"
KEEPALIVE_INTERVAL = 60

CLEAR_STATION = 0
CHECK_STATION = 1
START_STATION = 10
FINISH_STATION = 255


@dataclass
class RawPunch:
    station: int
    timestamp: int


def parse_punch_readout(lines: list[str], station_number: int) -> PunchReadout:
    values: dict[str, str] = {}
    punches: list[RawPunch] = []

    it = iter(lines)
    for line in it:
        if line.startswith("punches="):
            count = int(line.split("=", 1)[1])
            for _ in range(count):
                station, timestamp = map(int, next(it).split())
                punches.append(RawPunch(station, timestamp))
        elif "=" in line:
            key, value = line.split("=", 1)
            values[key] = value

    card_number = int(values["card"])

    start_idx = 0
    check_time = None

    if punches[start_idx].station == CHECK_STATION:
        check_time = punches[start_idx].timestamp
        start_idx += 1

    start_time = None
    while start_idx < len(punches) and punches[start_idx].station == START_STATION:
        start_time = punches[start_idx].timestamp
        if start_idx == 0:
            check_time = start_time
        start_idx += 1

    if start_time is None:
        raise ValueError("No START punch")

    finish_idx = len(punches) - 1
    if punches[finish_idx].station != FINISH_STATION:
        raise ValueError("No FINISH punch")

    finish_time = punches[finish_idx].timestamp
    finish_idx -= 1

    return PunchReadout(
        stationNumber=station_number,
        cardNumber=card_number,
        startTime=start_time,
        finishTime=finish_time,
        checkTime=check_time,
        punches=[
            PunchItem(
                cardNumber=card_number,
                code=p.station,
                time=p.timestamp,
            )
            for p in punches[start_idx:finish_idx + 1]
        ],
    )


def get_transport():
    if USE_BLE:
        return BleTransport(AOP, HCI_DEVICE)
    return SerialTransport(SERIAL_DEVICE)


async def keep_alive(shell):
    await asyncio.sleep(KEEPALIVE_INTERVAL)
    while True:
        try:
            await shell.execute("id")
            await asyncio.sleep(KEEPALIVE_INTERVAL)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"Keep-alive failed: {e}")


async def main():
    async with get_transport() as transport:
        shell = ShellProtocol(transport)
        keepalive_task = asyncio.create_task(keep_alive(shell))

        try:
            print(await shell.execute("card-readout"))

            async for notification in shell.notifications():
                db = SessionLocal()
                try:
                    data = parse_punch_readout(notification.split(), STATION_NUMBER)
                    with PrinterMux() as printer:
                        result = CardProcessor().handle_readout(db, data, printer)
                        print('\n'.join(printer.get_output()))
                        print(result)
                        return result

                except Exception as e:
                    print("Exception:", e)
                    db.rollback()
                    traceback.print_exc()

                finally:
                    db.close()

        finally:
            keepalive_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await keepalive_task


if __name__ == "__main__":
    asyncio.run(main())
