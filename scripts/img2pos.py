#!/usr/bin/env python

from PIL import Image


def png_to_raster_escpos(path, max_width=576):
    img = Image.open(path).convert("L")  # grayscale
    w, h = img.size

    # resize to printer width
    if w > max_width:
        new_h = int(h * (max_width / w))
        img = img.resize((max_width, new_h), Image.LANCZOS)

    # dither
    img = img.convert("1", dither=Image.FLOYDSTEINBERG)

    width, height = img.size
    bytes_per_row = (width + 7) // 8

    out = bytearray()

    # GS v 0: raster bit image
    out += b'\x1D\x76\x30\x00'  # GS v 0 m=0
    out += bytes([bytes_per_row & 0xFF, bytes_per_row >> 8])
    out += bytes([height & 0xFF, height >> 8])

    for y in range(height):
        for x in range(0, width, 8):
            byte = 0
            for b in range(8):
                if x + b < width:
                    if img.getpixel((x + b, y)) == 0:  # black
                        byte |= 1 << (7 - b)
            out.append(byte)

    return bytes(out)


# usage:
data = png_to_raster_escpos("logo.png")
with open('qe-logo.raw', 'wb') as f:
    f.write(data)

#with open("/dev/usb/lp0", "wb") as f:
#    f.write(data)
#    f.write(b"\x1Bd\x02")  # feed paper
#    f.write(b'\n' * 5)
#    f.write(b"\x1d\x56\x00")  # cut
