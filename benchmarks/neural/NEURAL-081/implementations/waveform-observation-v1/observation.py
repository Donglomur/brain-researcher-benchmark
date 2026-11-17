"""Fixed waveform images for NEURAL-081; no data acquisition or provider calls.

Inputs are already prepared, authorized single-query NPY windows. This module
does not establish their source eligibility, isolate a process, or score a model.
Only PNG pixels and public fixed geometry leave the observation object.
"""
from __future__ import annotations

import ast
import base64
import hashlib
import math
import re
import struct
import zlib
from dataclasses import dataclass

CHANNELS = (
    'Fp1','AF7','AF3','F1','F3','F5','F7','FT7','FC5','FC3','FC1','C1','C3','C5','T7','TP7',
    'CP5','CP3','CP1','P1','P3','P5','P7','P9','PO7','PO3','O1','Iz','Oz','POz','Pz','CPz',
    'Fpz','Fp2','AF8','AF4','AFz','Fz','F2','F4','F6','F8','FT8','FC6','FC4','FC2','FCz','Cz',
    'C2','C4','C6','T8','TP8','CP6','CP4','CP2','P2','P4','P6','P8','P10','PO8','PO4','O2',
)
CLASS_IDS = (1,2,3,4,11,12,13,14,21,22,23,24)
WIDTH, HEIGHT = 1168, 1080
LEFT, TOP, ROW_HEIGHT = 120, 100, 56
PIXELS_PER_SAMPLE, HALF_RANGE_UV, HALF_RANGE_PIXELS = 2, 100, 22
BACKGROUND, GRID, INK, TRACE, CLIPPED = (
    (255,255,255), (224,229,235), (30,40,52), (17,74,132), (190,30,45)
)

# Tiny fixed bitmap font keeps image creation portable and font-independent.
_FONT_ROWS = {
    'A':('01110','10001','10001','11111','10001','10001','10001'),
    'B':('11110','10001','10001','11110','10001','10001','11110'),
    'C':('01111','10000','10000','10000','10000','10000','01111'),
    'D':('11110','10001','10001','10001','10001','10001','11110'),
    'E':('11111','10000','10000','11110','10000','10000','11111'),
    'F':('11111','10000','10000','11110','10000','10000','10000'),
    'G':('01111','10000','10000','10111','10001','10001','01111'),
    'H':('10001','10001','10001','11111','10001','10001','10001'),
    'I':('11111','00100','00100','00100','00100','00100','11111'),
    'J':('00111','00010','00010','00010','10010','10010','01100'),
    'K':('10001','10010','10100','11000','10100','10010','10001'),
    'L':('10000','10000','10000','10000','10000','10000','11111'),
    'M':('10001','11011','10101','10101','10001','10001','10001'),
    'N':('10001','11001','10101','10011','10001','10001','10001'),
    'O':('01110','10001','10001','10001','10001','10001','01110'),
    'P':('11110','10001','10001','11110','10000','10000','10000'),
    'Q':('01110','10001','10001','10001','10101','10010','01101'),
    'R':('11110','10001','10001','11110','10100','10010','10001'),
    'S':('01111','10000','10000','01110','00001','00001','11110'),
    'T':('11111','00100','00100','00100','00100','00100','00100'),
    'U':('10001','10001','10001','10001','10001','10001','01110'),
    'V':('10001','10001','10001','10001','10001','01010','00100'),
    'W':('10001','10001','10001','10101','10101','11011','10001'),
    'X':('10001','10001','01010','00100','01010','10001','10001'),
    'Y':('10001','10001','01010','00100','00100','00100','00100'),
    'Z':('11111','00001','00010','00100','01000','10000','11111'),
    '0':('01110','10001','10011','10101','11001','10001','01110'),
    '1':('00100','01100','00100','00100','00100','00100','01110'),
    '2':('01110','10001','00001','00010','00100','01000','11111'),
    '3':('11110','00001','00001','01110','00001','00001','11110'),
    '4':('00010','00110','01010','10010','11111','00010','00010'),
    '5':('11111','10000','10000','11110','00001','00001','11110'),
    '6':('01110','10000','10000','11110','10001','10001','01110'),
    '7':('11111','00001','00010','00100','01000','01000','01000'),
    '8':('01110','10001','10001','01110','10001','10001','01110'),
    '9':('01110','10001','10001','01111','00001','00001','01110'),
    '-':('00000','00000','00000','11111','00000','00000','00000'),
    '+':('00000','00100','00100','11111','00100','00100','00000'),
    '/':('00001','00001','00010','00100','01000','10000','10000'),
    '.':('00000','00000','00000','00000','00000','00110','00110'),
    ':':('00000','00110','00110','00000','00110','00110','00000'),
    ' ':('00000',)*7,
}


def _window(payload: bytes, view: str) -> tuple[float, ...]:
    """Strict primitive NPY decoder; never invokes pickle or imports NumPy."""
    if type(payload) is not bytes or len(payload) > 135180:
        raise ValueError('One bounded ordinary NPY byte payload is required')
    if view not in ('EEG', 'ZERO'):
        raise ValueError('The view is EEG or ZERO')
    if len(payload) < 10 or payload[:6] != b'\x93NUMPY':
        raise ValueError('NPY input required')
    version = payload[6:8]
    if version == b'\x01\x00':
        offset, header_size = 10, struct.unpack('<H', payload[8:10])[0]
    elif version == b'\x02\x00' and len(payload) >= 12:
        offset, header_size = 12, struct.unpack('<I', payload[8:12])[0]
    else:
        raise ValueError('Only primitive NPY versions 1 and 2 are supported')
    if not 1 <= header_size <= 4096 or len(payload) != offset + header_size + 131072:
        raise ValueError('Exact complete 64 by 512 float32 extent required')
    header_bytes = payload[offset:offset + header_size]
    if not header_bytes.endswith(b'\n'):
        raise ValueError('NPY header must end with newline')
    try:
        header = ast.literal_eval(header_bytes.decode('ascii').strip())
    except (ValueError, SyntaxError, UnicodeError, RecursionError) as exc:
        raise ValueError('Invalid primitive NPY header') from exc
    if (type(header) is not dict or set(header) != {'descr','fortran_order','shape'}
            or header['descr'] != '<f4' or header['fortran_order'] is not False
            or type(header['shape']) is not tuple or header['shape'] != (64,512)
            or any(type(n) is not int for n in header['shape'])):
        raise ValueError('C-ordered little-endian float32 shape (64,512) required')
    body = payload[offset + header_size:]
    if view == 'ZERO' and body != b'\0' * 131072:
        raise ValueError('ZERO input must contain only positive float32 zero')
    values = struct.unpack('<32768f', body)
    if not all(math.isfinite(v) for v in values):
        raise ValueError('Every prepared sample must be finite')
    return values


def _pixel(canvas: bytearray, x: int, y: int, color: tuple[int,int,int]) -> None:
    if 0 <= x < WIDTH and 0 <= y < HEIGHT:
        start = 3 * (y * WIDTH + x)
        canvas[start:start+3] = bytes(color)


def _line(canvas: bytearray, x0: int, y0: int, x1: int, y1: int,
          color: tuple[int,int,int]) -> None:
    dx, dy = abs(x1-x0), -abs(y1-y0)
    sx, sy = (1 if x0<x1 else -1), (1 if y0<y1 else -1)
    error = dx + dy
    while True:
        _pixel(canvas, x0, y0, color)
        if x0 == x1 and y0 == y1:
            return
        twice = 2 * error
        if twice >= dy:
            error += dy
            x0 += sx
        if twice <= dx:
            error += dx
            y0 += sy


def _text(canvas: bytearray, x: int, y: int, value: str, scale: int = 2) -> None:
    for char in value.upper():
        for row, bits in enumerate(_FONT_ROWS[char]):
            for column, bit in enumerate(bits):
                if bit == '1':
                    for dx in range(scale):
                        for dy in range(scale):
                            _pixel(canvas, x + column*scale + dx, y + row*scale + dy, INK)
        x += 6 * scale


def _chunk(kind: bytes, body: bytes) -> bytes:
    return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind+body))


def _png(canvas: bytearray) -> bytes:
    scanlines = b''.join(b'\0'+canvas[y*WIDTH*3:(y+1)*WIDTH*3] for y in range(HEIGHT))
    return (b'\x89PNG\r\n\x1a\n' + _chunk(b'IHDR', struct.pack('>IIBBBBB', WIDTH, HEIGHT, 8, 2, 0, 0, 0))
            + _chunk(b'IDAT', zlib.compress(scanlines, 6)) + _chunk(b'IEND', b''))


def _render(values: tuple[float, ...], page: int, view: str) -> bytes:
    canvas = bytearray(bytes(BACKGROUND) * WIDTH * HEIGHT)
    _text(canvas, 20, 14, f'NEURAL-081   {view}   PAGE {page+1}/4')
    _text(canvas, 20, 38, 'ALL SAMPLES AT 128 HZ. FIXED SCALE: -100 TO +100 UV PER ROW.', 1)
    _text(canvas, 20, 55, 'RED TICKS MARK VALUES OUTSIDE SCALE. NO AUTO SCALING.', 1)
    for second in range(5):
        x = LEFT + second * 128 * PIXELS_PER_SAMPLE
        _line(canvas, x, TOP-25, x, TOP+15*ROW_HEIGHT+25, GRID)
        _text(canvas, x-4, TOP+16*ROW_HEIGHT, str(second), 1)
    _text(canvas, LEFT+370, TOP+16*ROW_HEIGHT+20, 'TIME FROM WINDOW START / S', 1)
    _text(canvas, 20, HEIGHT-30, 'WINDOW: SOURCE ONSET +0.5 S TO +4.5 S. VOLTS DISPLAYED AS MICROVOLTS.', 1)
    for local_channel in range(16):
        channel = page*16 + local_channel
        middle = TOP + local_channel*ROW_HEIGHT
        _text(canvas, 20, middle-6, CHANNELS[channel])
        _line(canvas, LEFT, middle, LEFT+1024, middle, GRID)
        coordinates = []
        for sample in range(512):
            uv = values[channel*512+sample] * 1_000_000
            clipped = abs(uv) > HALF_RANGE_UV
            displayed = max(-HALF_RANGE_UV, min(HALF_RANGE_UV, uv))
            y = middle - round(displayed*HALF_RANGE_PIXELS/HALF_RANGE_UV)
            coordinates.append((LEFT+sample*PIXELS_PER_SAMPLE, y, clipped))
        for first, second in zip(coordinates, coordinates[1:]):
            _line(canvas, first[0], first[1], second[0], second[1], TRACE)
        for x, y, clipped in coordinates:
            if clipped:
                _line(canvas, x, y-2, x, y+2, CLIPPED)
    return _png(canvas)


@dataclass(frozen=True)
class Observation:
    """A query-bound PNG projection. This object contains no waveform arrays."""
    context_alias: str
    view: str
    _frames: tuple[bytes, ...]

    def metadata(self) -> dict:
        return {
            'schema': 'neural081_waveform_observation_v1', 'task_id': 'NEURAL-081',
            'context_alias': self.context_alias, 'view': self.view,
            'class_ids': list(CLASS_IDS), 'pages': 4, 'channels_per_page': 16,
            'sample_rate_hz': 128, 'samples_per_channel': 512,
            'duration_seconds': 4, 'display_units': 'microvolts',
            'display_half_range_microvolts': HALF_RANGE_UV,
            'clipping': 'saturated at fixed scale; out-of-scale samples have red ticks',
            'response': 'twelve probabilities in class_ids order; no feedback',
        }

    def page(self, action: dict) -> dict:
        if (type(action) is not dict or set(action) != {'action','page'}
                or action['action'] != 'view_page' or type(action['page']) is not int
                or not 0 <= action['page'] < 4):
            raise ValueError('Only view_page with integer page 0..3 is permitted')
        page = action['page']
        image = self._frames[page]
        return {
            'context_alias': self.context_alias, 'view': self.view, 'page': page,
            'channels': list(CHANNELS[page*16:page*16+16]),
            'mime_type': 'image/png', 'width': WIDTH, 'height': HEIGHT,
            'sha256': hashlib.sha256(image).hexdigest(),
            'image_base64': base64.b64encode(image).decode('ascii'),
        }

    def direct(self) -> dict:
        """All four fixed pages; no channel or time selection by the participant."""
        return {'metadata': self.metadata(), 'images': [
            self.page({'action':'view_page','page':page}) for page in range(4)
        ]}


def prepare_observation(npy_payload: bytes, *, context_alias: str, view: str) -> Observation:
    """Render an already prepared authorized query; never inspect source labels.

    ZERO requires its own zero input. It does not open/derive from EEG in a ZERO
    role. The host must enforce source eligibility, unique aliases, and custody.
    """
    if type(context_alias) is not str or re.fullmatch('[0-9a-f]{32}', context_alias) is None:
        raise ValueError('One opaque lowercase 32-hex context alias is required')
    values = _window(npy_payload, view)
    return Observation(context_alias, view, tuple(_render(values, page, view) for page in range(4)))
