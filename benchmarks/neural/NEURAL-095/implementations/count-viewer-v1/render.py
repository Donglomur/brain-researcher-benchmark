"""Exact integer count table; no inferred spike times, features or filtering."""
import struct
import zlib


def layout(metadata, counts, units):
    """Return literal displayed strings/positions, independently testable before drawing."""
    rows = [(30, 20, 'NEURAL-095  RESTRICTED COUNT VIEWER  ' + metadata['view'].upper(), 2),
            (30, 49, metadata['split'].upper() + '  ' + metadata['case_id'].upper(), 2),
            (30, 78, 'CONDITION ' + str(metadata['condition']) + '  CONTEXT ' + str(metadata['context']) +
             '  NOMINAL ' + repr(metadata['nominal_ts_ms']) + ' MS', 2),
            (30, 107, 'ELAPSED CLOCK ' + repr(metadata['clock_seconds']) + ' S', 2)]
    if metadata['split'] == 'train':
        rows.append((30, 136, 'TRAIN TP ' + repr(metadata['tp_ms']) + ' MS  FOLD ' + str(metadata['fold']), 2))
    else:
        rows.append((30, 136, 'QUERY TP HIDDEN - PREDICT RELEASED TP IN MILLISECONDS', 2))
    if counts is None:
        rows.extend([(30, 210, 'CUE-ONLY VIEW: NO SPIKE COUNTS', 2),
                     (30, 246, 'ALL 748 TRAINING CASES AND 258 QUERY CASES AVAILABLE', 2)])
        return rows
    if len(units) != 40 or len(counts) != 4 or any(len(row) != 40 for row in counts):
        raise ValueError('Complete 4-bin by 40-unit table required')
    rows.append((30, 175, 'UNIT ID', 2))
    for b, label in enumerate(('[-200,-150)', '[-150,-100)', '[-100,-50)', '[-50,0)')):
        rows.append((210 + b * 270, 175, label + ' MS', 2))
    for u, unit in enumerate(units):
        if type(unit) is not int or not 0 <= unit <= 9999999999:
            raise ValueError('Bounded original integer unit ID required')
        rows.append((30, 201 + u * 15, str(unit), 2))
        for b in range(4):
            value = counts[b][u]
            if type(value) is not int or not 0 <= value <= 4294967295:
                raise ValueError('Exact uint32 count required')
            rows.append((210 + b * 270, 201 + u * 15, str(value), 2))
    rows.append((30, 810, 'EXACT COUNTS. HALF-OPEN BINS RELATIVE TO SET. SET EXCLUDED. NO RAW WAVEFORMS OR SPIKE TIMESTAMPS.', 1))
    return rows


def render(metadata, counts, units, raster):
    canvas = raster.Canvas()
    for x, y, text, scale in layout(metadata, counts, units):
        if any(c not in raster.FONT for c in text.upper()) or x + 6 * scale * len(text) > raster.WIDTH or y + 7 * scale > raster.HEIGHT:
            raise ValueError('Display string outside fixed exact table')
        canvas.text(x, y, text, scale=scale)
    # Compress the exact RGB bytes, with no change to geometry or samples.
    scan = b''.join(b'\0' + canvas.pixels[y * raster.WIDTH * 3:(y + 1) * raster.WIDTH * 3]
                    for y in range(raster.HEIGHT))
    def chunk(name, body):
        return struct.pack('>I', len(body)) + name + body + struct.pack('>I', zlib.crc32(name + body))
    image = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', raster.WIDTH, raster.HEIGHT, 8, 2, 0, 0, 0)) +
             chunk(b'IDAT', zlib.compress(scan, level=6)) + chunk(b'IEND', b''))
    return image, bytes(canvas.pixels)
