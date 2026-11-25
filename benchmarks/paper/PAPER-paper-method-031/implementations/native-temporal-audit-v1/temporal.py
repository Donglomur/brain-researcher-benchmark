"""Independent arithmetic oracle for the pinned FAST CLI and GUI temporal paths.

No model, target, TIFF reader, training, or scientific scorer is included. Source
mean reduction is represented algebraically, not as a bitwise PyTorch emulation.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from fractions import Fraction
import json
import math
from pathlib import Path

TASK_ID = "PAPER-paper-method-031"
SOURCE_COMMIT = "6f92663f7a36589507cac57c8d24cfd8adbce7b1"


class TemporalError(ValueError):
    """The supplied sequence does not have the selected source route's support."""


def _integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise TemporalError(f"{name} must be an integer >= {minimum}")
    return value


def _finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TemporalError(f"{name} must be a finite number")
    try:
        result = float(value)
    except OverflowError as exc:
        raise TemporalError(f"{name} exceeds floating-point range") from exc
    if not math.isfinite(result):
        raise TemporalError(f"{name} must be finite")
    return result


@dataclass(frozen=True)
class TemporalPlan:
    """Temporal semantics only; valid dimensions do not qualify a FAST model."""

    frames: int
    channels: int
    route: str

    def __post_init__(self):
        _integer(self.frames, "frames", 1)
        _integer(self.channels, "channels", 1)
        if self.route not in ("cli", "gui"):
            raise TemporalError("route must be explicitly cli or gui")
        if self.channels > self.frames:
            raise TemporalError("author inference requires channels <= original frames")
        if self.route == "gui" and self.channels - 1 > self.tail_frames:
            raise TemporalError("GUI last window exceeds the source's reflected tail")

    @property
    def tail_frames(self):
        return min(self.frames, 100)

    @property
    def window_count(self):
        return self.frames - self.channels + 1 if self.route == "cli" else self.frames

    def source_frame(self, augmented_index):
        """Map a dataset tensor index to the original frame, including reflection."""
        _integer(augmented_index, "augmented_index")
        if augmented_index >= self.frames + self.tail_frames:
            raise TemporalError("index is outside the author-augmented stack")
        return (augmented_index if augmented_index < self.frames else
                2 * self.frames - 1 - augmented_index)

    def window_frames(self, start):
        _integer(start, "window start")
        if start >= self.window_count:
            raise TemporalError("window start is outside the selected route")
        return tuple(self.source_frame(start + offset) for offset in range(self.channels))

    def contributions(self, frame):
        """Exact weights of window output channels in one saved original frame.

        First two contributions have the same weight. Subsequent contributions
        have increasing powers of two. These are not equal overlap averages.
        """
        _integer(frame, "frame")
        if frame >= self.frames:
            raise TemporalError("only original output frames may be inspected")
        first = max(0, frame - self.channels + 1)
        last = min(frame, self.window_count - 1)
        count = last - first + 1
        rows = []
        for index, start in enumerate(range(first, last + 1)):
            exponent = count - 1 if index == 0 else count - index
            rows.append((start, frame - start, Fraction(1, 2 ** exponent)))
        return tuple(rows)

    def frame_report(self, frame):
        rows = self.contributions(frame)
        support = sorted({source for start, _, _ in rows for source in self.window_frames(start)})
        return {
            "original_frame": frame,
            "contributions": [
                {"window_start": start, "output_channel": channel,
                 "weight_numerator": weight.numerator, "weight_denominator": weight.denominator}
                for start, channel, weight in rows
            ],
            "network_window_original_frame_support": support,
            "network_window_lookahead_frames": max(support) - frame,
            "centering_requires_last_original_frame": self.frames - 1,
        }

    def summary(self):
        return {
            "task_id": TASK_ID, "source_commit": SOURCE_COMMIT, "route": self.route,
            "original_frames": self.frames, "saved_output_frames": self.frames,
            "channels": self.channels, "window_count": self.window_count,
            "augmented_frames": self.frames + self.tail_frames,
            "reflected_tail_frames": self.tail_frames,
            "reflected_tail_used_by_network": self.route == "gui" and self.channels > 1,
            "centering": {
                "scope": "all spatial pixels of original plus reflected tail",
                "single_weight_frame_interval": [0, self.frames - self.tail_frames],
                "double_weight_frame_interval": [self.frames - self.tail_frames, self.frames],
                "frame_weight_denominator": self.frames + self.tail_frames,
                "requires_last_original_frame": self.frames - 1,
            },
            "qualification": "source_arithmetic_component_only",
            "not_established": ["paper route identity", "original pixel roster and synchronization",
                                "native float32 parity", "author denoising quality", "measured latency"],
        }


def augmented_mean(frame_sums, pixels_per_frame):
    """Mean of the whole augmented movie from full-spatial frame sums.

    The sums must cover *all* pixels, not the selected diagnostic trace pixels.
    This float64 oracle must not replace the source's float32 torch.mean in a
    claimed native replay; its numerical reduction order is different.
    """
    _integer(pixels_per_frame, "pixels_per_frame", 1)
    sums = [_finite(value, "frame sum") for value in frame_sums]
    if not sums:
        raise TemporalError("full original frame sums are required")
    tail = min(len(sums), 100)
    divisor = (len(sums) + tail) * pixels_per_frame
    try:
        mean = math.fsum(sums + sums[-tail:]) / divisor
    except OverflowError:
        # Finite frame sums can overflow an intermediate reduction even though
        # their weighted mean is representable. Preserve the original operands
        # exactly in this exceptional algebraic-oracle path.
        total = sum((Fraction(value) for value in sums + sums[-tail:]), Fraction())
        mean = float(total / divisor)
    return _finite(mean, "augmented mean")


def _half_average(left, right):
    """Keep ordinary rounding, avoiding overflow of a finite half-sum."""
    total = left + right
    return 0.5 * total if math.isfinite(total) else left / 2.0 + right / 2.0


def reconstruct_traces(plan, windows, source_mean):
    """Replay sequential half averaging on logged fixed-coordinate window outputs.

    ``windows`` yields (start, values) in source invocation order. ``values`` has
    channels rows and the same nonzero number of diagnostic pixels per row.
    Values are centered network outputs before source_mean restoration. This
    routine neither chooses the pixel roster nor estimates the mean from traces.
    It returns original-frame float traces and source clip/truncate uint16 values.
    Python arithmetic is an independent oracle, not bitwise framework parity.
    """
    if not isinstance(plan, TemporalPlan):
        raise TemporalError("a validated temporal plan is required")
    mean = _finite(source_mean, "source_mean")
    original = [None] * plan.frames
    width = None
    received = 0
    for received, item in enumerate(windows, 1):
        if received > plan.window_count:
            raise TemporalError("extra native window")
        try:
            start, values = item
        except (ValueError, TypeError) as exc:
            raise TemporalError("window must contain start and output rows") from exc
        _integer(start, "window start")
        if start != received - 1:
            raise TemporalError("missing, repeated, or reordered native window")
        try:
            rows = [list(row) for row in values]
        except TypeError as exc:
            raise TemporalError("window output must contain channel-by-pixel rows") from exc
        if len(rows) != plan.channels:
            raise TemporalError("window output channel count differs from source")
        if width is None:
            width = len(rows[0])
        if not width or any(len(row) != width for row in rows):
            raise TemporalError("diagnostic pixel roster width differs or is empty")
        rows = [[_finite(value, "window value") for value in row] for row in rows]
        for channel, row in enumerate(rows):
            frame = start + channel
            if frame >= plan.frames:
                continue  # GUI writes augmented output but saves original support only.
            previous = original[frame]
            if previous is None:
                original[frame] = row
            else:
                original[frame] = [_finite(_half_average(old, new), "overlap result")
                                   for old, new in zip(previous, row)]
    if received != plan.window_count or any(row is None for row in original):
        raise TemporalError("incomplete native window stream")
    restored = [[_finite(value + mean, "restored trace") for value in row] for row in original]
    quantized = [[int(min(65535.0, max(0.0, value))) for value in row] for row in restored]
    return {"float_traces": restored, "uint16_traces": quantized,
            "original_frame_ids": list(range(plan.frames)), "plan": plan.summary()}


def acquisition_bounds(plan, input_available_s, output_available_s=None):
    """Check the literal offline route's necessary acquisition ordering.

    Full-stack centering precedes every forward call. This bound includes no
    training, transfers, compute, I/O or scheduling time, and is not a real-time
    performance result. It applies only to the pinned CLI/GUI implementation.
    """
    if not isinstance(plan, TemporalPlan):
        raise TemporalError("a validated temporal plan is required")
    arrivals = [_finite(value, "input time") for value in input_available_s]
    if len(arrivals) != plan.frames or any(a > b for a, b in zip(arrivals, arrivals[1:])):
        raise TemporalError("input times must cover all original frames in acquisition order")
    earliest = [arrivals[-1]] * plan.frames
    if output_available_s is not None:
        outputs = [_finite(value, "output time") for value in output_available_s]
        if len(outputs) != plan.frames:
            raise TemporalError("output times must cover all original frames")
        if any(value < arrivals[-1] for value in outputs):
            raise TemporalError("output precedes required whole-stack centering input")
    return {"earliest_output_s": earliest,
            "minimum_acquisition_delay_s": [_finite(arrivals[-1] - value, "acquisition delay")
                                            for value in arrivals],
            "scope": "necessary_bound_only_not_measured_latency"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, required=True)
    parser.add_argument("--channels", type=int, required=True)
    parser.add_argument("--route", choices=("cli", "gui"), required=True)
    parser.add_argument("--inspect-frame", type=int, action="append", default=[])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        plan = TemporalPlan(args.frames, args.channels, args.route)
        report = plan.summary()
        report["inspected_frames"] = [plan.frame_report(frame) for frame in args.inspect_frame]
        encoded = json.dumps(report, indent=2, allow_nan=False) + "\n"
        if args.output is None:
            print(encoded, end="")
        else:
            # Source reports are immutable once written; avoid replacing evidence.
            with args.output.open("x", encoding="utf-8") as handle:
                handle.write(encoded)
    except (TemporalError, OSError) as exc:
        parser.exit(2, f"temporal audit refused: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
