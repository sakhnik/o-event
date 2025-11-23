#!/usr/bin/env python3

import sys

with open("/dev/usb/lp0", "wb") as f:
    f.write(b"\033@")
    f.write(b"\x1c\x2e\x1b\x52\x00\x1bt\x17")
    for line in sys.stdin:
        f.write(line.encode('cp1251'))
        f.write(b'\n')
    f.write(b"\x1Bd\x02")  # feed paper
    f.write(b'\n' * 5)
    f.write(b"\x1d\x56\x00")  # cut
