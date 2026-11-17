"""Prospective native-1024-Hz causal filter and fixed window, source only.

A verified raw/event/clock producer is still absent. These functions do not certify it.
No author-cleaned epoch, response-locked data, resampling or query fit is supported.
"""
from dataclasses import dataclass
import math

HZ = 1024
CHANNEL_COUNT = 32
FIRST_OFFSET = -204
STOP_OFFSET = 103
SAMPLES = STOP_OFFSET - FIRST_OFFSET
ALPHA = 0.125
WARMUP = HZ
CHUNK = HZ

@dataclass(frozen=True)
class Schedule:
    session_start: int
    onset: int
    start: int
    stop: int
    deadline_numerator: int
    deadline_denominator: int

def schedule(session_start, onset):
    if type(session_start) is not int or type(onset) is not int or session_start < 0:
        raise ValueError("integer native sample coordinates required")
    start, stop = onset + FIRST_OFFSET, onset + STOP_OFFSET
    if start < session_start + WARMUP:
        raise ValueError("insufficient predeclared acquisition-start history")
    # Absolute deadline is onset + 1024/10 samples. The last included sample is +102.
    return Schedule(session_start, onset, start, stop, 10 * onset + HZ, 10)

def response_at_or_before_deadline(first_response_sample, plan):
    if type(plan) is not Schedule or type(first_response_sample) is not int:
        raise ValueError("verified original response sample required")
    if first_response_sample < plan.onset:
        raise ValueError("response pairing precedes its stimulus")
    return 10 * first_response_sample <= plan.deadline_numerator

def advance(state, row):
    """Arithmetic kernel, also inspectable using symbolic engineering operands.

    Instantaneous common-average reference, then a fixed forward one-pole smoother.
    Every output depends only on this row and the preceding state. This is not
    the paper's 40-Hz zero-phase filter.
    """
    if len(state) != CHANNEL_COUNT or len(row) != CHANNEL_COUNT:
        raise ValueError("32 EEG channels")
    common = sum(row) / CHANNEL_COUNT
    return tuple((1.0 - ALPHA) * old + ALPHA * (value - common)
                 for old, value in zip(state, row))

def produce_prefix(raw, eeg_indices, plan, max_native_samples):
    """Consume a future admitted MNE Raw object via its real get_data interface.

    raw must already be the unfiltered original acquisition with independently
    validated channel/time identity. This is a downstream component, not that
    missing admission/decoder/event producer. A native reader may read physical
    blocks beyond logical slices; physical I/O and timing remain qualification.
    """
    if type(plan) is not Schedule or plan != schedule(plan.session_start, plan.onset):
        raise ValueError("exact fixed schedule")
    if type(max_native_samples) is not int or max_native_samples < 0:
        raise ValueError("prospective history budget")
    required = plan.stop - plan.session_start
    if required > max_native_samples:
        raise ValueError("history budget before native capture")
    eeg_indices = tuple(eeg_indices)
    if (len(eeg_indices) != CHANNEL_COUNT or len(set(eeg_indices)) != CHANNEL_COUNT
            or any(type(i) is not int or i < 0 for i in eeg_indices)):
        raise ValueError("verified ordered EEG-only channel indices required")
    if float(raw.info["sfreq"]) != HZ:
        raise ValueError("native1024 only; neither saved512 nor suggested100")
    state = (0.0,) * CHANNEL_COUNT
    captured = []
    attempted = 0
    for begin in range(plan.session_start, plan.stop, CHUNK):
        end = min(begin + CHUNK, plan.stop)
        attempted += (end - begin) * CHANNEL_COUNT
        # Charge before the call; preserve the actual first native exception.
        try:
            block = raw.get_data(picks=list(eeg_indices), start=begin, stop=end)
        except BaseException as error:
            try:
                error.add_note("N003 attempted logical scalar reads=" + str(attempted)
                               + "; physical I/O and completion unknown")
            except BaseException as diagnostic_error:
                # Best-effort secondary custody must never replace the first read error.
                try:
                    BaseException.__setattr__(error, "_n003_annotation_failure", diagnostic_error)
                except BaseException:
                    # Even an unavailable diagnostic sink must preserve the outward first error.
                    pass
            raise
        if tuple(block.shape) != (CHANNEL_COUNT, end - begin):
            raise ValueError("native slice shape")
        for j in range(end - begin):
            row = tuple(float(block[c, j]) for c in range(CHANNEL_COUNT))
            if any(not math.isfinite(v) for v in row):
                raise ValueError("nonfinite predeadline sample; never postdeadline rejection")
            state = advance(state, row)
            if begin + j >= plan.start:
                captured.append(state)
    if len(captured) != SAMPLES:
        raise ValueError("fixed complete window required")
    return tuple(captured)

def fixed_features(prefix):
    """96 fixed bin/channel means; no parameters fitted from held-out people."""
    if len(prefix) != SAMPLES or any(len(row) != CHANNEL_COUNT for row in prefix):
        raise ValueError("complete fixed prefix")
    # Three fixed native-grid bins: [-204,-102), [-102,0), [0,103).
    bounds = ((0, 102), (102, 204), (204, 307))
    return tuple(sum(prefix[t][c] for t in range(a, b)) / (b - a)
                 for a, b in bounds for c in range(CHANNEL_COUNT))
