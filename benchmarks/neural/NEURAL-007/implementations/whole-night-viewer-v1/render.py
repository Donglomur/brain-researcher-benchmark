"""Image-only sleep traces using the authenticated, unchanged EEG raster module.

No file reads, signal preparation, filtering, resampling, targets or model calls.
Inputs are one explicitly selected original-clock window of calibrated volts.
The parent retains full-precision clock metadata and authenticates this module
and the raster dependency before calling it.
"""
from __future__ import annotations

import math
import re
import struct
import zlib


CHANNELS = ('EEG Fpz-Cz', 'EEG Pz-Oz', 'EOG horizontal')
GAINS_UV = (10, 20, 50, 100, 200, 500, 1000)
SAMPLE_RATE_HZ = 100
EPOCH_SAMPLES = 3000
MIN_WINDOW_SAMPLES = 100
MAX_WINDOW_SAMPLES = 6000
MAX_SAMPLE = (1 << 53) - 1
PLOT_TOPS = (195, 395, 595)
EPOCH_PATTERN = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,95}\Z')
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
SCAN_BYTES = (1400 * 3 + 1) * 820
COMPRESSION_LEVEL = 9
COMPRESSION_MEMORY_LEVEL = 8


def require(condition, message):
    if not condition:
        raise ValueError(message)


def finite_number(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def seconds_text(sample):
    """Exact decimal hundredths for integer 100-Hz absolute sample offsets."""
    whole, hundredths = divmod(sample, SAMPLE_RATE_HZ)
    return f'{whole}.{hundredths:02d}'


def sample_x(sample, start, stop, raster):
    """Nearest pixel; subtract original-clock integers before any division."""
    return raster.LEFT + round((sample - start) * (raster.RIGHT - raster.LEFT) / (stop - start))


def compress_png(body):
    """Losslessly re-encode the unchanged raster's exact RGB scanline bytes.

    Only the three-chunk, noninterlaced 1400x820 RGB8 source format is accepted.
    Full pixel resolution and the original zero scanline filters are retained.
    Compression settings are fixed, but compressed-byte replay additionally
    requires the same recorded zlib build/runtime; pixels are checked separately.
    """
    require(type(body) is bytes and 8 < len(body) <= SCAN_BYTES + 65536
            and body[:8] == PNG_SIGNATURE, 'Bounded source PNG bytes required')
    offset, chunks = 8, []
    while offset < len(body):
        require(len(chunks) < 3 and offset + 12 <= len(body), 'Exactly three complete PNG chunks required')
        size = struct.unpack('>I', body[offset:offset + 4])[0]
        require(size <= SCAN_BYTES + 65536 and offset + size + 12 <= len(body), 'Bounded complete PNG chunk')
        name = body[offset + 4:offset + 8]
        data = body[offset + 8:offset + 8 + size]
        crc = struct.unpack('>I', body[offset + 8 + size:offset + 12 + size])[0]
        require(crc == zlib.crc32(name + data), 'Source PNG chunk CRC mismatch')
        chunks.append((name, data))
        offset += size + 12
    require(offset == len(body) and [item[0] for item in chunks] == [b'IHDR', b'IDAT', b'IEND']
            and chunks[-1][1] == b'', 'Exact metadata-free source PNG chunks required')
    expected_header = struct.pack('>IIBBBBB', 1400, 820, 8, 2, 0, 0, 0)
    require(chunks[0][1] == expected_header, 'Original RGB8 dimensions/mode required')
    decoder = zlib.decompressobj(wbits=15)
    try:
        scan = decoder.decompress(chunks[1][1], SCAN_BYTES + 1)
    except zlib.error as error:
        raise ValueError('Invalid source PNG compression') from error
    require(len(scan) == SCAN_BYTES and decoder.eof and not decoder.unused_data
            and not decoder.unconsumed_tail, 'Exactly one bounded complete PNG scanline stream required')
    require(all(scan[row * (1400 * 3 + 1)] == 0 for row in range(820)),
            'Original zero scanline filters required')
    encoder = zlib.compressobj(level=COMPRESSION_LEVEL, method=zlib.DEFLATED,
                               wbits=15, memLevel=COMPRESSION_MEMORY_LEVEL,
                               strategy=zlib.Z_DEFAULT_STRATEGY)
    compressed = encoder.compress(scan) + encoder.flush(zlib.Z_FINISH)
    def chunk(name, data):
        return struct.pack('>I', len(data)) + name + data + struct.pack('>I', zlib.crc32(name + data))
    return PNG_SIGNATURE + chunk(b'IHDR', expected_header) + chunk(b'IDAT', compressed) + chunk(b'IEND', b'')


def validate(epoch_id, start_sample, channel_names, channel_values_volts,
             gain_uv, clock_features, target_start_sample):
    require(type(epoch_id) is str and EPOCH_PATTERN.fullmatch(epoch_id) is not None,
            'Bounded ASCII opaque epoch identity required')
    require(type(start_sample) is int and 0 <= start_sample <= MAX_SAMPLE - MAX_WINDOW_SAMPLES,
            'Nonnegative bounded integer original-clock start sample required')
    require(type(target_start_sample) is int and 0 <= target_start_sample <= MAX_SAMPLE - EPOCH_SAMPLES
            and target_start_sample % EPOCH_SAMPLES == 0,
            'Target must start on the original 3000-sample epoch grid')
    require(type(channel_names) is list and 1 <= len(channel_names) <= len(CHANNELS)
            and all(type(name) is str and name in CHANNELS for name in channel_names)
            and channel_names == [name for name in CHANNELS if name in channel_names],
            'Canonical ordered unique nonempty channel selection required')
    require(type(channel_values_volts) is list and len(channel_values_volts) == len(channel_names)
            and all(type(row) is list for row in channel_values_volts),
            'One list of original volts for each selected channel required')
    width = len(channel_values_volts[0])
    require(MIN_WINDOW_SAMPLES <= width <= MAX_WINDOW_SAMPLES
            and all(len(row) == width for row in channel_values_volts),
            'Aligned complete window of 100 through 6000 samples required')
    require(all(finite_number(value) for row in channel_values_volts for value in row),
            'Finite numerical source volts required; booleans are not samples')
    require(type(gain_uv) is int and gain_uv in GAINS_UV,
            'Declared integer microvolts-per-division gain required')
    require(type(clock_features) is dict
            and set(clock_features) == {'elapsed_hours', 'wall_clock_sin', 'wall_clock_cos'}
            and all(finite_number(v) for v in clock_features.values()),
            'Exactly three finite declared target clock features required')
    # Source admission binds the original stored clock values. Do not invent a
    # precision/equality rule here: an upstream float32-derived phase may not lie
    # on the unit circle to a new float64 tolerance.
    return width


def render(epoch_id, start_sample, channel_names, channel_values_volts,
           gain_uv, clock_features, raster, *, target_start_sample):
    """Return deterministic RGB PNG bytes; emit no numerical trace payload.

    Each row contains the requested half-open window only, in canonical channel
    order. The target remains the same 30-second epoch while the participant may
    navigate elsewhere in the same recording. Parent source admission bounds the
    requested window to that recording; this renderer has no full-night extent.

    The unchanged raster helper clips in source volts with gain_uv / 1e6. This
    is the identical display conversion to microvolts, without multiplying a
    finite extreme source value by one million and overflowing it first.
    """
    width = validate(epoch_id, start_sample, channel_names, channel_values_volts,
                     gain_uv, clock_features, target_start_sample)
    require((raster.WIDTH, raster.HEIGHT, raster.LEFT, raster.RIGHT) == (1400, 820, 180, 1300),
            'Expected authenticated raster geometry required')
    stop_sample = start_sample + width
    target_stop = target_start_sample + EPOCH_SAMPLES
    gain_volts = gain_uv / 1_000_000
    canvas = raster.Canvas()
    canvas.text(35, 18, 'NEURAL-007 SLEEP TRACE VIEWER')
    canvas.text(35, 48, 'TARGET ' + epoch_id + ' - LABEL HIDDEN', scale=1)
    canvas.text(35, 66,
                f'TARGET [{seconds_text(target_start_sample)}, {seconds_text(target_stop)}) S  /  30-SECOND EPOCH',
                scale=1)
    canvas.text(35, 84,
                f'VIEW [{seconds_text(start_sample)}, {seconds_text(stop_sample)}) S  /  '
                f'LAST SAMPLE {seconds_text(stop_sample - 1)} S', scale=1)
    canvas.text(35, 102,
                f'100 HZ  /  {width} ORIGINAL SAMPLES PER CHANNEL  /  {gain_uv} UV PER DIV  /  POSITIVE UP',
                scale=1)
    canvas.text(35, 120,
                'FILTER NONE  /  NO RESAMPLING  /  ALL VISIBLE SAMPLES AND ADJACENT SEGMENTS', scale=1)
    canvas.text(35, 138,
                'TARGET CLOCK ROUNDED TO 6 SIGNIFICANT DIGITS: '
                f'H={clock_features["elapsed_hours"]:.6g}  '
                f'SIN={clock_features["wall_clock_sin"]:.6g}  '
                f'COS={clock_features["wall_clock_cos"]:.6g}', scale=1)
    canvas.text(35, 156,
                'RED BRACKET: VISIBLE TARGET INTERVAL  /  NO STAGE ANSWERS, DEMONSTRATIONS OR FEEDBACK', scale=1)

    visible_start = max(start_sample, target_start_sample)
    visible_stop = min(stop_sample, target_stop)
    for index, (name, values) in enumerate(zip(channel_names, channel_values_volts, strict=True)):
        top = PLOT_TOPS[index]
        middle, bottom = top + 90, top + 180
        canvas.text(28, top + 12, name, scale=1)
        canvas.text(35, middle - 7, 'UV', scale=1)
        for division in (-3, -2, -1, 0, 1, 2, 3):
            y = middle - division * 30
            canvas.line(raster.LEFT, y, raster.RIGHT, y, raster.GRID if division else raster.BLACK)
            canvas.text(115, y - 4, str(division * gain_uv), scale=1)
        for tick in range(5):
            sample = start_sample + width * tick // 4
            x = sample_x(sample, start_sample, stop_sample, raster)
            canvas.line(x, top, x, bottom, raster.GRID)
            label = seconds_text(sample)
            canvas.text(x - len(label) * 3, bottom + 6, label, scale=1)
        if visible_start < visible_stop:
            left = sample_x(visible_start, start_sample, stop_sample, raster)
            right = sample_x(visible_stop, start_sample, stop_sample, raster)
            canvas.line(left, top + 3, right, top + 3, raster.RED)
            # Window edges are not represented as original target boundaries.
            for boundary in (target_start_sample, target_stop):
                if start_sample <= boundary <= stop_sample:
                    x = sample_x(boundary, start_sample, stop_sample, raster)
                    canvas.line(x, top, x, bottom, raster.RED)
        previous = None
        clipped = False
        for offset, value in enumerate(values):
            clipped |= abs(value) > 3 * gain_volts
            point = sample_x(start_sample + offset, start_sample, stop_sample, raster), value
            if previous is not None:
                raster.trace_segment(canvas, *previous, *point, gain_volts, middle)
            elif abs(value) <= 3 * gain_volts:
                canvas.pixel(point[0], middle - round(value / gain_volts * 30), raster.BLUE)
            previous = point
        if clipped:
            canvas.text(1030, top - 12, 'CLIPPED: INCREASE UV/DIV', raster.RED, scale=1)
    canvas.text(390, 806, 'TIME SINCE RECORDING START (S)  /  SAMPLE CLOCK NEVER WRAPS', scale=1)
    return compress_png(canvas.png())
