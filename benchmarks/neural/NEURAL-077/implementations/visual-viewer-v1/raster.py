"""Deterministic standard-library RGB PNG renderer; every visible sample is drawn.

No SVG, numerical sample payload, embedded text chunk, external font or plotting
library. The font and integer line rasterizer are part of the reviewed source.
"""
from fractions import Fraction
import struct
import zlib

WIDTH, HEIGHT = 1400, 820
LEFT, RIGHT = 180, 1300
BLACK = (25, 35, 48)
GRID = (220, 225, 232)
BLUE = (20, 75, 170)
RED = (170, 35, 35)
# Five columns, seven rows, encoded as row bit masks.
FONT = {
' ': '00 00 00 00 00 00 00',
'A': '0e 11 11 1f 11 11 11', 'B':'1e 11 11 1e 11 11 1e',
'C': '0e 11 10 10 10 11 0e', 'D':'1e 11 11 11 11 11 1e',
'E': '1f 10 10 1e 10 10 1f', 'F':'1f 10 10 1e 10 10 10',
'G': '0e 11 10 17 11 11 0f', 'H':'11 11 11 1f 11 11 11',
'I': '0e 04 04 04 04 04 0e', 'J':'07 02 02 02 12 12 0c',
'K': '11 12 14 18 14 12 11', 'L':'10 10 10 10 10 10 1f',
'M': '11 1b 15 15 11 11 11', 'N':'11 19 15 13 11 11 11',
'O': '0e 11 11 11 11 11 0e', 'P':'1e 11 11 1e 10 10 10',
'Q': '0e 11 11 11 15 12 0d', 'R':'1e 11 11 1e 14 12 11',
'S': '0f 10 10 0e 01 01 1e', 'T':'1f 04 04 04 04 04 04',
'U': '11 11 11 11 11 11 0e', 'V':'11 11 11 11 11 0a 04',
'W': '11 11 11 15 15 15 0a', 'X':'11 11 0a 04 0a 11 11',
'Y': '11 11 0a 04 04 04 04', 'Z':'1f 01 02 04 08 10 1f',
'0': '0e 11 13 15 19 11 0e', '1':'04 0c 04 04 04 04 0e',
'2': '0e 11 01 02 04 08 1f', '3':'1e 01 01 0e 01 01 1e',
'4': '02 06 0a 12 1f 02 02', '5':'1f 10 10 1e 01 01 1e',
'6': '0e 10 10 1e 11 11 0e', '7':'1f 01 02 04 08 08 08',
'8': '0e 11 11 0e 11 11 0e', '9':'0e 11 11 0f 01 01 0e',
'-': '00 00 00 1f 00 00 00', '.':'00 00 00 00 00 0c 0c',
':': '00 0c 0c 00 0c 0c 00', '/':'01 02 02 04 08 08 10',
'(': '02 04 08 08 08 04 02', ')':'08 04 02 02 02 04 08',
'[': '0e 08 08 08 08 08 0e', ']':'0e 02 02 02 02 02 0e',
'=': '00 00 1f 00 1f 00 00', '+':'00 04 04 1f 04 04 00',
'_': '00 00 00 00 00 00 1f', ',':'00 00 00 00 0c 0c 08',
}
FONT = {k: tuple(int(x, 16) for x in v.split()) for k, v in FONT.items()}


class Canvas:
    def __init__(self):
        self.pixels = bytearray(b'\xff' * (WIDTH * HEIGHT * 3))

    def pixel(self, x, y, color):
        if 0 <= x < WIDTH and 0 <= y < HEIGHT:
            index = (y * WIDTH + x) * 3
            self.pixels[index:index + 3] = bytes(color)

    def line(self, x0, y0, x1, y1, color):
        # Caller clips trace ordinates before this bounded integer loop.
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        error = dx + dy
        while True:
            self.pixel(x0, y0, color)
            if x0 == x1 and y0 == y1:
                break
            twice = 2 * error
            if twice >= dy:
                error += dy
                x0 += sx
            if twice <= dx:
                error += dx
                y0 += sy

    def text(self, x, y, text, color=BLACK, scale=2):
        for char in text.upper():
            for row, bits in enumerate(FONT[char]):
                for col in range(5):
                    if bits & (1 << (4 - col)):
                        for sy in range(scale):
                            for sx in range(scale):
                                self.pixel(x + col * scale + sx, y + row * scale + sy, color)
            x += 6 * scale

    def png(self):
        def chunk(name, data):
            return struct.pack('>I', len(data)) + name + data + struct.pack('>I', zlib.crc32(name + data))
        # Stored DEFLATE blocks avoid compressor-version variability entirely.
        scan = b''.join(b'\0' + self.pixels[y * WIDTH * 3:(y + 1) * WIDTH * 3] for y in range(HEIGHT))
        compressed = bytearray(b'\x78\x01')
        for start in range(0, len(scan), 65535):
            block = scan[start:start + 65535]
            compressed.append(int(start + len(block) == len(scan)))
            compressed += struct.pack('<HH', len(block), len(block) ^ 65535) + block
        compressed += struct.pack('>I', zlib.adler32(scan))
        return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', WIDTH, HEIGHT, 8, 2, 0, 0, 0))
                + chunk(b'IDAT', compressed) + chunk(b'IEND', b''))


def sample_x(offset, start, stop):
    return LEFT + round((offset - start) * (RIGHT - LEFT) / (stop - start))


def trace_segment(canvas, x0, value0, x1, value1, gain, middle):
    """Clip the actual piecewise-linear segment, never its endpoints first.

    Fractions on boundary crossings avoid overflow for any finite input and
    preserve the subpixel crossing position before integer rasterization.
    """
    lower, upper = -3 * gain, 3 * gain
    if (value0 > upper and value1 > upper) or (value0 < lower and value1 < lower):
        return
    original0, original1 = value0, value1
    if value0 < lower or value0 > upper:
        value0 = max(lower, min(upper, value0))
        t = (Fraction(value0) - Fraction(original0)) / (Fraction(original1) - Fraction(original0))
        x0 = x0 + float(t) * (x1 - x0)
    if value1 < lower or value1 > upper:
        value1 = max(lower, min(upper, value1))
        # Interpolate from original x coordinates; x0 may already be clipped.
        # Remaining segment has the same line and a finite in-range value0.
        t = (Fraction(value1) - Fraction(value0)) / (Fraction(original1) - Fraction(value0))
        x1 = x0 + float(t) * (x1 - x0)
    canvas.line(round(x0), middle - round(value0 / gain * 30),
                round(x1), middle - round(value1 / gain * 30), BLUE)


def render(record, state, mode):
    """record is operator-only; output is raster bytes, never the data coordinates."""
    c = Canvas()
    start, stop, gain = state['start_sample'], state['stop_sample'], state['units_per_division']
    label = state['record']
    title = 'QUERY - LABEL HIDDEN' if label == 'query' else label + ' - TARGET ' + str(record['target'])
    c.text(35, 22, 'NEURAL-077 ERP VIEWER - ' + mode.upper())
    c.text(35, 54, title)
    c.text(35, 86, f'WINDOW [{start}, {stop}) SAMPLES  /  1024 HZ  /  GAIN {gain} NATIVE UNITS PER DIV')
    c.text(35, 118, 'FILTER NONE  /  CZ,PZ MINUS (P9+P10)/2  /  BASELINE [-256,-1]')
    c.text(35, 150, 'POSITIVE UP  /  ALL VISIBLE SAMPLES AND ADJACENT SEGMENTS  /  RED LINE: MARKER 0')
    channels = state['channels']
    for index, name in enumerate(channels):
        top = 205 + index * 260
        bottom, middle = top + 180, top + 90
        c.text(35, top + 10, name)
        c.text(28, middle - 7, 'NATIVE')
        for division in (-3, -2, -1, 0, 1, 2, 3):
            y = middle - division * 30
            c.line(LEFT, y, RIGHT, y, GRID if division else BLACK)
            c.text(92, y - 5, f'{division * gain:g}', scale=1)
        for tick in range(5):
            offset = start + (stop - start) * tick / 4
            x = sample_x(offset, start, stop)
            c.line(x, top, x, bottom, GRID)
            c.text(x - 30, bottom + 14, f'{offset / 1024 * 1000:.2f}', scale=1)
        c.text(570, bottom + 34, 'TIME FROM RELEASED MARKER (MS)', scale=1)
        if start <= 0 < stop:
            x = sample_x(0, start, stop)
            c.line(x, top, x, bottom, RED)
        values = record['channels'][('Cz', 'Pz').index(name)]
        previous = None
        clipped = False
        for offset in range(start, stop):
            value = values[offset + 256]
            clipped |= abs(value) > gain * 3
            # Every adjacent segment is geometrically clipped, then rasterized.
            point = sample_x(offset, start, stop), value
            if previous is not None:
                trace_segment(c, *previous, *point, gain, middle)
            elif abs(value) <= gain * 3:
                c.pixel(point[0], middle - round(value / gain * 30), BLUE)
            previous = point
        if clipped:
            c.text(1030, top - 20, 'CLIPPED: INCREASE UNITS/DIV', RED, scale=1)
    c.text(35, 750, 'NATIVE AMPLITUDE CALIBRATION AND PHYSICAL DISPLAY DELAY ARE UNRESOLVED', scale=1)
    c.text(35, 774, 'EPOCH SUPPORT: -250.000 MS TO 750.000 MS EXCLUSIVE. LAST SAMPLE: 749.0234375 MS.', scale=1)
    c.text(35, 798, 'DISPLAY ONLY. NO ADDED FILTER. SELECTED CHANNELS SHARE THE SAME AMPLITUDE SCALE.', scale=1)
    return c.png()
