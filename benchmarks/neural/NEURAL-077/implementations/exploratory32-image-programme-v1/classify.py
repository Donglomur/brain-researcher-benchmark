#!/usr/bin/env python3
"""Frozen four-demonstration, image-only EEG event-identity classifier.

The supplied demonstration order fixes labels (0, 1, 0, 1). Neither filenames,
trial aliases, header text, nor footer text are model inputs. This is an
uncalibrated, deliberately conservative estimate, not a physiological diagnosis.
"""
import os

# Set before importing NumPy; this programme requests one computational thread.
for _thread_variable in (
    "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS", "BLIS_NUM_THREADS",
):
    os.environ[_thread_variable] = "1"

import argparse
import json
import math
import struct
import zlib

import numpy as np


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
WIDTH = 1400
HEIGHT = 820
LABELS = np.array([0, 1, 0, 1], dtype=np.int8)


def read_png(path):
    """Decode the supplied fixed-size, noninterlaced, eight-bit PNG.

    Supports grayscale, RGB, palette, grayscale/alpha, and RGBA PNGs using
    stdlib and NumPy only. Ancillary metadata are not interpreted. No external
    process, image viewer, companion file, network, or persistent cache is used.
    """
    with open(path, "rb") as handle:
        data = handle.read(16 * 1024 * 1024 + 1)
    if len(data) > 16 * 1024 * 1024 or data[:8] != PNG_SIGNATURE:
        raise ValueError("Unsupported PNG")
    position = 8
    header = None
    palette = None
    transparency = None
    compressed = []
    ended = False
    while position + 12 <= len(data):
        length = struct.unpack_from(">I", data, position)[0]
        kind = data[position + 4:position + 8]
        finish = position + 12 + length
        if finish > len(data):
            raise ValueError("Truncated PNG")
        payload = data[position + 8:position + 8 + length]
        checksum = struct.unpack_from(">I", data, position + 8 + length)[0]
        if zlib.crc32(kind + payload) & 0xffffffff != checksum:
            raise ValueError("PNG checksum")
        if kind == b"IHDR":
            if header is not None or length != 13:
                raise ValueError("PNG header")
            header = struct.unpack(">IIBBBBB", payload)
        elif kind == b"PLTE":
            if not length or length % 3:
                raise ValueError("PNG palette")
            palette = np.frombuffer(payload, dtype=np.uint8).reshape(-1, 3)
        elif kind == b"tRNS":
            transparency = payload
        elif kind == b"IDAT":
            compressed.append(payload)
        elif kind == b"IEND":
            ended = True
            break
        elif kind[:1].isupper():
            raise ValueError("Unsupported critical PNG chunk")
        position = finish
    if header is None or not ended or not compressed:
        raise ValueError("Incomplete PNG")
    width, height, depth, color, compression, filtering, interlace = header
    if (width, height) != (WIDTH, HEIGHT):
        raise ValueError("Unexpected image geometry")
    if depth != 8 or compression or filtering or interlace:
        raise ValueError("Unsupported PNG encoding")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color)
    if channels is None:
        raise ValueError("Unsupported PNG color")
    stride = width * channels
    expected = height * (stride + 1)
    decoder = zlib.decompressobj()
    decoded = decoder.decompress(b"".join(compressed), expected + 1)
    if len(decoded) != expected or not decoder.eof or decoder.unconsumed_tail:
        raise ValueError("Unexpected PNG data length")
    raw = np.frombuffer(decoded, dtype=np.uint8).reshape(height, stride + 1)
    pixels = np.empty((height, stride), dtype=np.uint8)
    previous = bytearray(stride)
    for y in range(height):
        filter_type = int(raw[y, 0])
        current_bytes = raw[y, 1:]
        if filter_type == 0:
            row = bytearray(current_bytes.tobytes())
        elif filter_type == 1:
            # Each byte channel has an independent cumulative Sub recurrence.
            cumul = np.cumsum(
                current_bytes.reshape(width, channels), axis=0, dtype=np.uint32
            )
            row = bytearray((cumul & 255).astype(np.uint8).tobytes())
        elif filter_type == 2:
            upper = np.frombuffer(previous, dtype=np.uint8)
            row = bytearray(np.add(current_bytes, upper, dtype=np.uint8).tobytes())
        elif filter_type == 3:
            row = bytearray(current_bytes.tobytes())
            for i in range(channels):
                row[i] = (row[i] + (previous[i] >> 1)) & 255
            for i in range(channels, stride):
                row[i] = (row[i] + ((row[i - channels] + previous[i]) >> 1)) & 255
        elif filter_type == 4:
            row = bytearray(current_bytes.tobytes())
            for i in range(channels):
                row[i] = (row[i] + previous[i]) & 255
            for i in range(channels, stride):
                left = row[i - channels]
                above = previous[i]
                upper_left = previous[i - channels]
                # These common flat-background cases also avoid extra abs calls.
                if above == upper_left:
                    predictor = left
                elif left == upper_left:
                    predictor = above
                else:
                    left_distance = abs(above - upper_left)
                    above_distance = abs(left - upper_left)
                    corner_distance = abs(left + above - 2 * upper_left)
                    if left_distance <= above_distance and left_distance <= corner_distance:
                        predictor = left
                    elif above_distance <= corner_distance:
                        predictor = above
                    else:
                        predictor = upper_left
                row[i] = (row[i] + predictor) & 255
        else:
            raise ValueError("Unsupported PNG row filter")
        pixels[y] = np.frombuffer(row, dtype=np.uint8)
        previous = row
    pixels = pixels.reshape(height, width, channels)
    alpha = None
    if color == 0:
        rgb = np.repeat(pixels, 3, axis=2)
        if transparency is not None:
            if len(transparency) != 2:
                raise ValueError("PNG transparency")
            transparent_gray = struct.unpack(">H", transparency)[0]
            alpha = np.where(pixels[:, :, 0] == transparent_gray, 0, 255).astype(np.uint8)
    elif color == 2:
        rgb = pixels
        if transparency is not None:
            if len(transparency) != 6:
                raise ValueError("PNG transparency")
            transparent_rgb = np.array(struct.unpack(">HHH", transparency))
            alpha = np.where(np.all(rgb == transparent_rgb, axis=2), 0, 255).astype(np.uint8)
    elif color == 3:
        indices = pixels[:, :, 0]
        if palette is None or int(indices.max()) >= len(palette):
            raise ValueError("PNG palette index")
        rgb = palette[indices]
        if transparency is not None:
            if len(transparency) > len(palette):
                raise ValueError("PNG palette transparency")
            table = np.full(len(palette), 255, dtype=np.uint8)
            table[:len(transparency)] = np.frombuffer(transparency, dtype=np.uint8)
            alpha = table[indices]
    elif color == 4:
        rgb = np.repeat(pixels[:, :, :1], 3, axis=2)
        alpha = pixels[:, :, 1]
    else:
        rgb = pixels[:, :, :3]
        alpha = pixels[:, :, 3]
    if alpha is not None:
        # Composite onto the observed white plot background, in integer arithmetic.
        a = alpha[:, :, None].astype(np.uint16)
        rgb = ((rgb.astype(np.uint16) * a + 255 * (255 - a) + 127) // 255).astype(np.uint8)
    return rgb


def trace_features(path):
    """Extract only the two blue traces at the fixed demonstration geometry."""
    rgb = read_png(path)
    x = np.arange(1121, dtype=np.float64)
    milliseconds = -250.0 + x * (1000.0 / 1120.0)
    traces = []
    for top, zero in ((205, 295), (465, 555)):
        crop = rgb[top:top + 181, 180:1301].astype(np.int16)
        red, green, blue = crop[:, :, 0], crop[:, :, 1], crop[:, :, 2]
        # Blue chromaticity rejects gray grid/axes, black text, and the red marker.
        mask = (blue > red + 30) & (blue > green + 20) & (blue > 100)
        counts = mask.sum(axis=0)
        visible = counts > 0
        if float(visible.mean()) < 0.97:
            raise ValueError("Insufficient trace pixels")
        rows = np.arange(181, dtype=np.float64)[:, None]
        # Midpoint of the vertical blue extent estimates a rasterized line center.
        low = np.min(np.where(mask, rows, np.inf), axis=0)
        high = np.max(np.where(mask, rows, -np.inf), axis=0)
        centers = 0.5 * (low[visible] + high[visible])
        line = np.interp(x, x[visible], centers)
        # The displayed ticks are 20 native units per 30 vertical pixels.
        amplitude = (float(zero - top) - line) / 1.5
        # Remove only the residual rasterization offset in the already-baselined trace.
        amplitude -= amplitude[milliseconds < 0].mean()
        traces.append(amplitude)
    traces = np.asarray(traces)
    post = np.empty((2, 15), dtype=np.float64)
    for k in range(15):
        selection = (milliseconds >= 50.0 * k) & (milliseconds < 50.0 * (k + 1))
        post[:, k] = traces[:, selection].mean(axis=1)
    bands = []
    for start, stop in ((200.0, 400.0), (300.0, 600.0),
                        (400.0, 700.0), (200.0, 700.0)):
        selection = (milliseconds >= start) & (milliseconds < stop)
        bands.append(traces[:, selection].mean(axis=1))
    bands = np.asarray(bands)
    # Broad positive AND negative excursions are retained; event identity is not
    # equated with the presence or absence of a positive component.
    broad = 0.5 * (post[:, 3:13] + post[:, 4:14])
    extrema = np.concatenate((broad.min(axis=1), broad.max(axis=1)))
    baseline_bins = []
    for start in (-250.0, -200.0, -150.0, -100.0, -50.0):
        selection = (milliseconds >= start) & (milliseconds < start + 50.0)
        baseline_bins.append(traces[:, selection].mean(axis=1))
    baseline_rms = float(np.sqrt(np.mean(np.asarray(baseline_bins) ** 2)))
    return {"post": post, "bands": bands, "extrema": extrema,
            "baseline_rms": baseline_rms}


def distance(first, second, scale):
    """Fixed symmetric multiscale distance; no parameters are fit to the query."""
    a = first["post"]
    b = second["post"]
    forward = []
    backward = []
    for shift in (-1, 0, 1):
        forward.append(float(np.mean((a[:, 2:13] - b[:, 2 + shift:13 + shift]) ** 2)))
        backward.append(float(np.mean((b[:, 2:13] - a[:, 2 + shift:13 + shift]) ** 2)))
    # Fixed +/-50 ms tolerance accounts for modest temporal variation. The
    # symmetrization avoids assigning a special fit role to either input.
    shape = 0.5 * (min(forward) + min(backward))
    bands = float(np.mean((first["bands"] - second["bands"]) ** 2))
    extrema = float(np.mean((first["extrema"] - second["extrema"]) ** 2))
    return (0.65 * shape + 0.25 * bands + 0.10 * extrema) / (scale * scale)


def fit_demo_reference(demos):
    """Choose a label-blind bandwidth from the four demonstrations only."""
    scale = max(2.0, float(np.median([d["baseline_rms"] for d in demos])))
    pairwise = np.full((4, 4), np.inf, dtype=np.float64)
    for i in range(4):
        for j in range(i + 1, 4):
            pairwise[i, j] = pairwise[j, i] = distance(demos[i], demos[j], scale)
    nearest = np.min(pairwise, axis=1)
    # A floor prevents quantization or duplicated curves from collapsing bandwidth.
    variance = max(1.0, float(np.median(nearest)) / 3.0)
    return scale, variance


def log_average_exp(values):
    largest = float(np.max(values))
    return largest + math.log(float(np.mean(np.exp(values - largest))))


def probability(query, demos, reference):
    scale, variance = reference
    distances = np.array([distance(query, demo, scale) for demo in demos])
    if not np.isfinite(distances).all():
        raise ValueError("Nonfinite features")
    log_kernels = -distances / (2.0 * variance)
    difference = (log_average_exp(log_kernels[LABELS == 1])
                  - log_average_exp(log_kernels[LABELS == 0]))
    # Equal class reference weights are a neutral reporting convention, not an
    # estimate of the unknown natural target-event prevalence.
    difference = max(-60.0, min(60.0, difference))
    raw = 1.0 / (1.0 + math.exp(-difference))
    # Four observations cannot support calibrated extreme probabilities.
    # Shrink to 0.5, increasingly so outside all four demonstrated neighborhoods.
    support = 1.0 / (1.0 + float(np.min(distances)) / (6.0 * variance))
    result = 0.5 + 0.8 * support * (raw - 0.5)
    if not math.isfinite(result):
        raise ValueError("Nonfinite probability")
    return float(min(0.9, max(0.1, result)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trial-id", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--demos", nargs=4, required=True)
    args = parser.parse_args()
    try:
        # The reference is fully fixed before the query image is opened.
        demos = [trace_features(path) for path in args.demos]
        reference = fit_demo_reference(demos)
        query = trace_features(args.query)
        target_probability = probability(query, demos, reference)
    except Exception as exc:
        # Failures are not predictions: emit a diagnostic and no probability JSON.
        raise SystemExit("classification_failed: " + type(exc).__name__) from None
    print(json.dumps({"trial_id": args.trial_id,
                      "target_probability": target_probability},
                     allow_nan=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
