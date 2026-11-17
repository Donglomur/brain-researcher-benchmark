"""Fixed full-native-frame PNG; only plotting, never prediction or filtering."""
import math
import struct
import zlib

WIDTH, HEIGHT = 960, 384


def trace(means, counts):
    if len(means) not in (200, 240) or len(counts) != len(means):
        raise ValueError('Complete original frame grid')
    if not all(math.isfinite(float(v)) for v in means) or not all(type(v) is int and 0 <= v <= 50 for v in counts):
        raise ValueError('Finite original means and trial counts')
    pixels = bytearray([255]) * (WIDTH * HEIGHT * 3)

    def point(x, y, color):
        if 0 <= x < WIDTH and 0 <= y < HEIGHT:
            index = (y * WIDTH + x) * 3
            pixels[index:index + 3] = bytes(color)

    def line(x0, y0, x1, y1, color):
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        error = dx + dy
        while True:
            point(x0, y0, color)
            if x0 == x1 and y0 == y1:
                break
            twice = 2 * error
            if twice >= dy:
                error += dy; x0 += sx
            if twice <= dx:
                error += dx; y0 += sy

    seen = [float(value) for value, count in zip(means, counts) if count > 0]
    low, high = (min(seen), max(seen)) if seen else (0.0, 0.0)
    magnitude = max(abs(low), abs(high), 1.0)
    bottom, top = low / magnitude, high / magnitude
    if bottom == top:
        bottom -= 0.5; top += 0.5
    x = lambda i: 24 + round(i * (WIDTH - 49) / (len(means) - 1))
    y = lambda v: 270 - round((float(v) / magnitude - bottom) / (top - bottom) * 246)
    for index in (0, len(means) // 4, len(means) // 2, 3 * len(means) // 4, len(means) - 1):
        line(x(index), 24, x(index), 360, (235, 235, 235))
    line(24, 270, WIDTH - 25, 270, (120, 120, 120))
    line(24, 360, WIDTH - 25, 360, (120, 120, 120))
    for i, (value, count) in enumerate(zip(means, counts)):
        if count:
            point(x(i), y(value), (24, 63, 130))
            if i and counts[i - 1]:
                line(x(i - 1), y(means[i - 1]), x(i), y(value), (24, 63, 130))
        else:
            line(x(i), 274, x(i), 279, (180, 60, 60))
        if i:
            line(x(i - 1), 360 - counts[i - 1], x(i), 360 - count, (20, 130, 80))
    raw = b''.join(b'\x00' + pixels[i * WIDTH * 3:(i + 1) * WIDTH * 3] for i in range(HEIGHT))

    def chunk(kind, body):
        return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body))

    png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', WIDTH, HEIGHT, 8, 2, 0, 0, 0))
    png += chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b'')
    return png, {'width': WIDTH, 'height': HEIGHT, 'frame_indices': [0, len(means) - 1],
        'observed_mean_min': low if seen else None, 'observed_mean_max': high if seen else None,
        'mean_panel_y_pixels': [24, 270], 'count_panel_y_pixels': [310, 360],
        'count_range': [0, 50], 'mean_color': 'blue', 'count_color': 'green',
        'unavailable_marker': 'red ticks; no mean curve across zero-count frames',
        'units': 'unchanged source numeric units; physical convention unknown',
        'clock': 'native frame index only; no physical onset/timestamps',
        'visual_line_segments_are_not_resampled_source_values': True}
