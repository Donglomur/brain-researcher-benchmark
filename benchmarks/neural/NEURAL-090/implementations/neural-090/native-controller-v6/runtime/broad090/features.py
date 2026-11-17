"""Deferred source feature transformations for the prospective Broad protocol.

This file is source, not a scientific execution or a qualification certificate.
NumPy/SciPy are imported only inside numerical functions. Importing this module
does not import them, read source data, fit anything, or construct a model.

The source compiler/qualified owner must enforce role admission, authentic
clocks, canonical recording aliases, and physical actor separation. The seal
references below are required metadata, NOT an authority mechanism: this module
neither verifies nor issues seals. Protected neural/shift/timing predictions must
already be sealed before any acoustic/transcript diagnostic execution. These
diagnostics expose the stimulus; transcript masking is not batch privacy.

No implicit download, missing-file skip, channel inference, clock estimation,
fractional-phase rounding, downmixing, PCM decoding, or dependency install exists.
"""

from dataclasses import dataclass
from fractions import Fraction
from math import gcd
from typing import Any, Iterable, Protocol, Sequence


class FeatureContractError(ValueError):
    """The declared source/role/layout contract was not met."""


class UnsupportedFeatureSource(FeatureContractError):
    """A whole case needs unavailable source/clock qualification; do not skip it."""


@dataclass(frozen=True)
class TrainInterval:
    """Half-open continuous-sample bounds, in a canonical recording clock."""

    recording_id: str
    clock_id: str
    start: int
    stop: int
    role: str


class ChannelIntervalReader(Protocol):
    """Only this declared channel order and exact requested interval may be read.

    Implementations must expose channels x samples, without channel inference,
    sample interpolation, reading a whole recording, or padding missing samples.
    The external owner must verify this promise and canonical recording aliases.
    """

    channel_order: Sequence[str]

    def read_interval(self, recording_id: str, start: int, stop: int) -> Any:
        ...


@dataclass(frozen=True)
class FrozenChannelMoments:
    mean: Any
    std: Any
    channel_order: tuple[str, ...]
    sample_count: int
    admitted_intervals: tuple[TrainInterval, ...]
    admission_ref: str
    fit_role: str = "TRAIN"
    variance_convention: str = "population_ddof_0_unique_continuous_samples"


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FeatureContractError(f"{name} must be a nonempty explicit string")
    return value


def _integer(value: Any, name: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise FeatureContractError(f"{name} must be an integer >= {minimum}")
    return value


def _rational(value: Any, name: str) -> Fraction:
    # Floats are deliberately refused: Fraction(float) would enshrine an
    # unauthenticated binary approximation as apparent exact clock evidence.
    if isinstance(value, bool) or not isinstance(value, (Fraction, int)):
        raise FeatureContractError(f"{name} must be an exact Fraction or integer")
    return Fraction(value)


def unique_train_intervals(
    intervals: Iterable[TrainInterval],
) -> tuple[TrainInterval, ...]:
    """Union admitted TRAIN intervals without reading signals or filling gaps.

    Overlap and adjacency are merged within a canonical recording/clock only.
    Input role admission is the caller's obligation; no supplied non-TRAIN
    interval is accepted. This does not discover overlap with unsupplied roles.
    """
    declared = list(intervals)
    if not declared:
        raise FeatureContractError("TRAIN interval support is empty")
    clocks: dict[str, str] = {}
    for interval in declared:
        if not isinstance(interval, TrainInterval) or interval.role != "TRAIN":
            raise FeatureContractError("only explicit TrainInterval(role='TRAIN') is admitted")
        _text(interval.recording_id, "recording_id")
        _text(interval.clock_id, "clock_id")
        _integer(interval.start, "start")
        _integer(interval.stop, "stop", 1)
        if interval.stop <= interval.start:
            raise FeatureContractError("TRAIN intervals must have positive length")
        if clocks.setdefault(interval.recording_id, interval.clock_id) != interval.clock_id:
            raise FeatureContractError("one recording was assigned incompatible sample clocks")
    declared.sort(key=lambda item: (item.recording_id, item.start, item.stop))
    merged: list[TrainInterval] = []
    for interval in declared:
        if merged and merged[-1].recording_id == interval.recording_id and interval.start <= merged[-1].stop:
            previous = merged[-1]
            merged[-1] = TrainInterval(previous.recording_id, previous.clock_id,
                                       previous.start, max(previous.stop, interval.stop), "TRAIN")
        else:
            merged.append(interval)
    return tuple(merged)


def fit_train_channel_moments(
    reader: ChannelIntervalReader,
    intervals: Iterable[TrainInterval],
    *,
    channel_order: Sequence[str],
    admission_ref: str,
    max_chunk_samples: int = 65536,
) -> FrozenChannelMoments:
    """Fit per-channel population moments on the unique admitted TRAIN samples.

    Neural callers supply all 306 channels in the selected exact source order.
    A separately qualified feature reader may supply the 80 acoustic channels;
    it must define its TRAIN feature support explicitly. Raw-audio moments are
    not interchangeable with log-mel moments. Inner and final refit call this
    separately. TUNE/CAL/query cannot update the returned frozen moments.
    """
    import numpy as np

    _text(admission_ref, "admission_ref")
    _integer(max_chunk_samples, "max_chunk_samples", 1)
    channels = tuple(channel_order)
    if not channels or any(not isinstance(item, str) or not item for item in channels):
        raise FeatureContractError("channel_order must name every channel")
    if len(set(channels)) != len(channels):
        raise FeatureContractError("channel_order contains duplicates")
    if tuple(reader.channel_order) != channels:
        raise FeatureContractError("reader and declared channel order disagree")
    merged = unique_train_intervals(intervals)
    count = 0
    mean = np.zeros(len(channels), dtype=np.float64)
    m2 = np.zeros(len(channels), dtype=np.float64)
    for interval in merged:
        start = interval.start
        while start < interval.stop:
            stop = min(start + max_chunk_samples, interval.stop)
            raw = np.asarray(reader.read_interval(interval.recording_id, start, stop))
            if raw.ndim != 2 or raw.shape != (len(channels), stop - start):
                raise UnsupportedFeatureSource("reader must return exactly channels x requested samples")
            if raw.dtype.kind not in "fiu" or np.iscomplexobj(raw):
                raise UnsupportedFeatureSource("channel reader must return real numeric samples")
            block = np.asarray(raw, dtype=np.float64)
            if not np.isfinite(block).all():
                raise UnsupportedFeatureSource("nonfinite TRAIN samples are not silently dropped")
            block_count = block.shape[1]
            block_mean = block.mean(axis=1, dtype=np.float64)
            centered = block - block_mean[:, None]
            block_m2 = np.sum(centered * centered, axis=1, dtype=np.float64)
            total = count + block_count
            delta = block_mean - mean
            m2 += block_m2 + delta * delta * (count * block_count / total)
            mean += delta * (block_count / total)
            count = total
            start = stop
    variance = m2 / count
    if not np.isfinite(mean).all() or not np.isfinite(variance).all() or np.any(variance <= 0):
        raise UnsupportedFeatureSource("nonfinite or zero-variance TRAIN channels fail the whole case")
    std = np.sqrt(variance)
    mean.setflags(write=False)
    std.setflags(write=False)
    return FrozenChannelMoments(mean, std, channels, count, merged, admission_ref)


def apply_frozen_channel_moments(
    values: Any,
    moments: FrozenChannelMoments,
    *,
    channel_order: Sequence[str],
) -> Any:
    """Normalize channels x samples using supplied frozen moments; clip at ±10.

    This operation never fits moments and does not infer or reorder channels.
    A batch dimension is deliberately unsupported: apply to each admitted view.
    """
    import numpy as np

    if not isinstance(moments, FrozenChannelMoments) or moments.fit_role != "TRAIN":
        raise FeatureContractError("explicit frozen TRAIN moments are required")
    if tuple(channel_order) != moments.channel_order:
        raise FeatureContractError("normalization channel order mismatch")
    raw = np.asarray(values)
    if raw.ndim != 2 or raw.shape[0] != len(moments.channel_order):
        raise UnsupportedFeatureSource("normalization requires channels x samples")
    if raw.dtype.kind not in "fiu" or np.iscomplexobj(raw):
        raise UnsupportedFeatureSource("normalization requires real numeric samples")
    array = np.asarray(raw, dtype=np.float64)
    mean = np.asarray(moments.mean, dtype=np.float64)
    std = np.asarray(moments.std, dtype=np.float64)
    if mean.shape != (array.shape[0],) or std.shape != mean.shape:
        raise FeatureContractError("frozen moment dimensions disagree")
    if not np.isfinite(array).all() or not np.isfinite(mean).all() or not np.isfinite(std).all() or np.any(std <= 0):
        raise UnsupportedFeatureSource("nonfinite samples or invalid frozen moments")
    normalized = (array - mean[:, None]) / std[:, None]
    if not np.isfinite(normalized).all():
        raise UnsupportedFeatureSource("normalization overflow is not silently clipped")
    return np.clip(normalized, -10.0, 10.0)


@dataclass(frozen=True)
class DiagnosticRelease:
    """Private references to externally verified release evidence, not authority."""

    scope_id: str
    release_evidence_ref: str
    protected_seal_refs: tuple[tuple[str, str], ...]


def _require_diagnostic_release(release: DiagnosticRelease) -> None:
    if not isinstance(release, DiagnosticRelease):
        raise FeatureContractError("an externally qualified diagnostic release record is required")
    _text(release.scope_id, "diagnostic scope_id")
    _text(release.release_evidence_ref, "release_evidence_ref")
    pairs = release.protected_seal_refs
    if len(pairs) != 3 or {arm for arm, _ in pairs} != {"neural", "time_shifted_neural", "timing"}:
        raise FeatureContractError("all three protected-arm seal references must precede diagnostics")
    for _, reference in pairs:
        _text(reference, "protected seal reference")
    # Deliberately no fabricated issuer, seal verification, or qualification.


@dataclass(frozen=True)
class AudioClockEvidence:
    """Caller-supplied PRIVATE clock/decode metadata requiring external proof.

    Source sample zero has the given exact MEG time. Only a unit-rate affine
    mapping (seconds_per_source_sample == 1/source_rate_hz) is supported. Source
    recording coordinates must start at zero; offsets for a crop must instead be
    resolved by the source compiler. Authentication is not inferred from these
    strings. Mono floating-point decoding/amplitude conventions must be pinned.
    """

    source_id: str
    source_rate_hz: int
    source_sample_count: int
    source_sample_zero_meg_seconds: Fraction
    meg_seconds_per_source_sample: Fraction
    clock_evidence_ref: str
    decode_convention_ref: str
    amplitude_convention_ref: str
    source_layout: str = "mono_float_recording_samples_from_zero"


class MonoAudioReader(Protocol):
    """Read only the exact admitted half-open source-audio interval as 1-D mono."""

    def read_interval(self, source_id: str, start: int, stop: int) -> Any:
        ...


@dataclass(frozen=True)
class AcousticFeatures:
    logmel: Any
    private_audit: dict[str, Any]
    exposure: str = "stimulus_exposed_acoustic_diagnostic"


@dataclass(frozen=True)
class AcousticTrainView:
    """One admitted source-row feature view, retaining donor row multiplicity.

    view_id is the private admitted source-row identity, NOT the cross-person
    stimulus-event group. Distinct people hearing the same event remain distinct
    admitted views; repeated optimization must not add the same view twice.
    """

    view_id: str
    role: str
    features: AcousticFeatures


def fit_train_acoustic_moments(
    training_views: Iterable[AcousticTrainView],
    *,
    admission_ref: str,
    diagnostic_release: DiagnosticRelease,
) -> FrozenChannelMoments:
    """Root-selected TRAIN-only event-local feature weighting.

    Fit 80 log-mel moments, pooling each admitted TRAIN view's 125 frames once.

    These are event-local FEATURE moments, not raw-audio sample moments. Segment
    zero boundaries make overlapping event-local features nonidentical, so they
    cannot use neural continuous-sample coordinates for de-duplication. This
    explicit view-weighting recipe was selected before source or outcome execution.
    """
    _require_diagnostic_release(diagnostic_release)
    _text(admission_ref, "acoustic admission_ref")
    channels = tuple(f"mel_{index:02d}" for index in range(80))
    by_view: dict[str, AcousticFeatures] = {}
    intervals: list[TrainInterval] = []
    for view in training_views:
        if not isinstance(view, AcousticTrainView) or view.role != "TRAIN":
            raise FeatureContractError("acoustic moments accept only explicit TRAIN views")
        _text(view.view_id, "private admitted view_id")
        if view.view_id in by_view:
            raise FeatureContractError("duplicate acoustic TRAIN view would change normalization weight")
        if not isinstance(view.features, AcousticFeatures) or getattr(view.features.logmel, "shape", None) != (80, 125):
            raise UnsupportedFeatureSource("each acoustic TRAIN view must contain the fixed 80 x 125 log-mel output")
        by_view[view.view_id] = view.features
        intervals.append(TrainInterval(view.view_id, "event_local_logmel_frame_0_to_124", 0, 125, "TRAIN"))

    class FeatureReader:
        channel_order = channels

        def read_interval(self, recording_id: str, start: int, stop: int) -> Any:
            return by_view[recording_id].logmel[:, start:stop]

    return fit_train_channel_moments(FeatureReader(), intervals,
                                     channel_order=channels, admission_ref=admission_ref)


def _audio_segment_bounds(clock: AudioClockEvidence, event_onset_meg_seconds: Fraction) -> tuple[int, int, int, int, int]:
    if not isinstance(clock, AudioClockEvidence):
        raise FeatureContractError("explicit AudioClockEvidence is required")
    for name in ("source_id", "clock_evidence_ref", "decode_convention_ref", "amplitude_convention_ref"):
        _text(getattr(clock, name), name)
    rate = _integer(clock.source_rate_hz, "source_rate_hz", 1)
    count = _integer(clock.source_sample_count, "source_sample_count", 1)
    if clock.source_layout != "mono_float_recording_samples_from_zero":
        raise UnsupportedFeatureSource("stereo, interleaved, cropped-origin, or encoded PCM layouts need qualification")
    origin = _rational(clock.source_sample_zero_meg_seconds, "source sample-zero time")
    step = _rational(clock.meg_seconds_per_source_sample, "source-to-MEG sample step")
    onset = _rational(event_onset_meg_seconds, "event onset")
    if step != Fraction(1, rate):
        raise UnsupportedFeatureSource("clock drift/non-unit-rate mapping is not guessed or corrected")
    source_start = (onset - origin) / step
    output_start = (onset - origin) * 16000
    if source_start.denominator != 1:
        raise UnsupportedFeatureSource("fractional source-grid onset requires an unselected phase/quantization convention")
    source_length = Fraction(rate, 2)
    if source_length.denominator != 1:
        raise UnsupportedFeatureSource("the half-second source interval must contain an exact integer number of samples")
    start = source_start.numerator
    stop = start + source_length.numerator
    if start < 0 or stop > count:
        raise UnsupportedFeatureSource("the full source 0..0.5-second event interval is unavailable")
    factor = gcd(rate, 16000)
    return start, stop, 16000 // factor, rate // factor, output_start


def _acoustic_segment_transform(
    segment: Any,
    *,
    clock: AudioClockEvidence,
    event_onset_meg_seconds: Fraction,
    bounds: tuple[int, int, int, int, int],
) -> AcousticFeatures:
    """Private numerical worker; exposed diagnostic callers must gate execution."""
    import numpy as np
    import scipy
    from scipy.signal import resample_poly

    start, stop, up, down, global_output_start = bounds
    raw = np.asarray(segment)
    if raw.ndim != 1 or raw.shape != (stop - start,) or raw.dtype.kind != "f":
        raise UnsupportedFeatureSource("audio must already be decoded mono floating-point samples at the exact admitted bounds")
    source = np.asarray(raw, dtype=np.float64)
    if not np.isfinite(source).all():
        raise UnsupportedFeatureSource("nonfinite audio samples fail the whole case")
    # SEGMENT FIRST: no adjacent source sample enters the FIR. Resetting its
    # origin is permitted only after exact source-grid alignment above; the event-local output origin is zero.
    # SciPy's centered/zero-phase output convention and version require native
    # qualification; no estimated delay correction or trim is introduced here.
    audio = resample_poly(source, up, down, axis=0, window=("kaiser", 5.0),
                          padtype="constant", cval=0.0)
    if audio.shape != (8000,) or not np.isfinite(audio).all():
        raise UnsupportedFeatureSource("resampling did not produce exactly 8000 finite event samples")
    centers = 64 * np.arange(125, dtype=np.int64)
    offsets = np.arange(-200, 200, dtype=np.int64)
    indices = centers[:, None] + offsets[None, :]
    admitted = (indices >= 0) & (indices < 8000)
    frames = np.zeros((125, 400), dtype=np.float64)
    frames[admitted] = audio[indices[admitted]]
    # Explicit symmetric Hann: h[n]=0.5-0.5*cos(2*pi*n/399), n=0..399.
    # This is a selected implementation convention, not an unstated default.
    hann = np.hanning(400)
    spectrum = np.fft.rfft(frames * hann[None, :], n=512, axis=1)
    power = spectrum.real * spectrum.real + spectrum.imag * spectrum.imag
    frequencies = np.fft.rfftfreq(512, d=1.0 / 16000.0)
    # HTK mel mapping; exact-frequency triangles; no area normalization,
    # no integer FFT-bin rounding, and no normalization of |rFFT|^2 power.
    top_mel = 2595.0 * np.log10(1.0 + 8000.0 / 700.0)
    mel_edges = np.linspace(0.0, top_mel, 82, dtype=np.float64)
    hz_edges = 700.0 * (np.power(10.0, mel_edges / 2595.0) - 1.0)
    hz_edges[0], hz_edges[-1] = 0.0, 8000.0
    rising = (frequencies[None, :] - hz_edges[:-2, None]) / (hz_edges[1:-1, None] - hz_edges[:-2, None])
    falling = (hz_edges[2:, None] - frequencies[None, :]) / (hz_edges[2:, None] - hz_edges[1:-1, None])
    filters = np.maximum(0.0, np.minimum(rising, falling))
    logmel = np.log1p(filters @ power.T)
    if logmel.shape != (80, 125) or not np.isfinite(logmel).all():
        raise UnsupportedFeatureSource("log-mel transform did not produce finite 80 x 125 features")
    left_padding = np.sum(indices < 0, axis=1)
    right_padding = np.sum(indices >= 8000, axis=1)
    audit = {
        "source_id": clock.source_id,
        "clock_evidence_ref": clock.clock_evidence_ref,
        "decode_convention_ref": clock.decode_convention_ref,
        "amplitude_convention_ref": clock.amplitude_convention_ref,
        "source_sample_bounds_half_open": (start, stop),
        "source_rate_hz": clock.source_rate_hz,
        "event_onset_meg_seconds_rational": str(_rational(event_onset_meg_seconds, "event onset")),
        "source_sample_zero_meg_seconds_rational": str(clock.source_sample_zero_meg_seconds),
        "resample_up": up,
        "resample_down": down,
        "resample_phase_remainder": (start * up) % down,
        "global_output_start_sample_rational": str(global_output_start),
        "segment_local_output_sample_origin": 0,
        "resample_scope": "event_segment_only_before_resampling",
        "resample_window": ("kaiser", 5.0),
        "resample_boundary": "constant_zero_no_adjacent_samples",
        "resample_fir_extension_count": "implementation_defined_by_pinned_scipy; not a read of authentic samples",
        "output_samples": 8000,
        "frame_centers": tuple(int(item) for item in centers),
        "frame_left_zero_padding_counts": tuple(int(item) for item in left_padding),
        "frame_right_zero_padding_counts": tuple(int(item) for item in right_padding),
        "fft_zero_padding_samples_per_frame": 112,
        "hann": "symmetric_400_endpoints_zero",
        "mel": "HTK_80_exact_frequency_triangles_no_area_normalization_0_to_8000_Hz",
        "power": "unnormalized_abs_rfft_squared_512",
        "compression": "log1p",
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "qualification": "caller_metadata_only_no_authority_issued",
    }
    return AcousticFeatures(logmel, audit)


def acoustic_features_from_reader(
    reader: MonoAudioReader,
    *,
    clock: AudioClockEvidence,
    event_onset_meg_seconds: Fraction,
    diagnostic_release: DiagnosticRelease,
) -> AcousticFeatures:
    """Read only the verified event segment; produce exposed 80 x 125 features."""
    _require_diagnostic_release(diagnostic_release)
    bounds = _audio_segment_bounds(clock, event_onset_meg_seconds)
    segment = reader.read_interval(clock.source_id, bounds[0], bounds[1])
    return _acoustic_segment_transform(segment, clock=clock,
                                       event_onset_meg_seconds=event_onset_meg_seconds,
                                       bounds=bounds)


def acoustic_features_from_array(
    source_audio: Any,
    *,
    clock: AudioClockEvidence,
    event_onset_meg_seconds: Fraction,
    diagnostic_release: DiagnosticRelease,
) -> AcousticFeatures:
    """Array adapter; only the admitted segment is sampled by this transform.

    The caller already owns the full authenticated array. Prefer the interval
    reader when source custody must prove no whole-recording signal read. This
    adapter performs no full-recording finite-value pass or implicit conversion.
    """
    _require_diagnostic_release(diagnostic_release)
    bounds = _audio_segment_bounds(clock, event_onset_meg_seconds)
    if getattr(source_audio, "ndim", None) != 1 or getattr(source_audio, "shape", None) != (clock.source_sample_count,):
        raise UnsupportedFeatureSource("array must preserve the declared full mono recording origin/length")
    segment = source_audio[bounds[0]:bounds[1]]
    return _acoustic_segment_transform(segment, clock=clock,
                                       event_onset_meg_seconds=event_onset_meg_seconds,
                                       bounds=bounds)


@dataclass(frozen=True)
class WordSpan:
    """Private source metadata. Neither word_id nor exact times are actor fields."""

    word_id: str
    text: str
    start: Fraction
    end: Fraction


@dataclass(frozen=True)
class TranscriptTrainView:
    role: str
    event_onset: Fraction
    words: tuple[WordSpan, ...]


@dataclass(frozen=True)
class TranscriptVocabulary:
    """Only admitted TRAIN feature words, with exact case/spelling preserved."""

    tokens: tuple[str, ...]
    training_view_count: int
    admission_ref: str
    fit_role: str = "TRAIN"
    pad_id: int = 0
    unk_id: int = 1
    exposure: str = "stimulus_transcript_exposed_oracle_context_diagnostic"


@dataclass(frozen=True)
class EncodedTranscript:
    token_ids: tuple[int, ...]
    attention_mask: tuple[int, ...]
    length: int
    exposure: str = "stimulus_transcript_exposed_oracle_context_diagnostic"


def _completed_words(words: Iterable[WordSpan], event_onset: Fraction) -> tuple[str, ...]:
    """Select last 256 completed words, with end strictly less than onset.

    This per-row rule DOES NOT protect earlier query targets from later rows.
    Word spelling is exposed by design; direct/indirect recoverability and
    across-row overlap must be audited by the private source compiler.
    """
    onset = _rational(event_onset, "event onset")
    completed: list[WordSpan] = []
    seen: set[str] = set()
    for word in words:
        if not isinstance(word, WordSpan):
            raise FeatureContractError("word annotations must be explicit WordSpan records")
        start = _rational(word.start, "word start")
        end = _rational(word.end, "word end")
        if end <= start:
            raise UnsupportedFeatureSource("word intervals require positive exact-clock duration")
        if end >= onset:
            continue  # equality, current overlap and future words are omitted
        _text(word.word_id, "private word_id")
        if word.word_id in seen:
            raise UnsupportedFeatureSource("duplicate canonical words must be resolved privately, not duplicated in context")
        seen.add(word.word_id)
        if not isinstance(word.text, str) or not word.text or word.text.strip() != word.text or any(char.isspace() for char in word.text):
            raise UnsupportedFeatureSource("one explicit word token per annotation is required; no implicit tokenizer")
        if word.text in ("<PAD>", "<UNK>"):
            raise UnsupportedFeatureSource("source spelling collides with reserved vocabulary tokens")
        completed.append(word)
    completed.sort(key=lambda word: (word.start, word.end, word.word_id))
    for previous, following in zip(completed, completed[1:]):
        if following.start < previous.end:
            raise UnsupportedFeatureSource("overlapping/multispeaker word streams require a selected ordering convention")
    return tuple(word.text for word in completed[-256:])


def completed_word_tokens(
    words: Iterable[WordSpan],
    event_onset: Fraction,
    *,
    diagnostic_release: DiagnosticRelease,
) -> tuple[str, ...]:
    """Exposed diagnostic tokens only; no source IDs or times are returned."""
    _require_diagnostic_release(diagnostic_release)
    return _completed_words(words, event_onset)


def fit_transcript_vocabulary(
    training_views: Iterable[TranscriptTrainView],
    *,
    admission_ref: str,
    diagnostic_release: DiagnosticRelease,
) -> TranscriptVocabulary:
    """Fit vocabulary only from admitted TRAIN views, never CAL/TUNE/query.

    Use separate calls for inner source TRAIN and final source-refit TRAIN.
    Tokens outside that frozen vocabulary map to UNK, including during CAL.
    """
    _require_diagnostic_release(diagnostic_release)
    _text(admission_ref, "transcript admission_ref")
    tokens: set[str] = set()
    count = 0
    for view in training_views:
        if not isinstance(view, TranscriptTrainView) or view.role != "TRAIN":
            raise FeatureContractError("transcript vocabulary accepts only explicit TRAIN views")
        tokens.update(_completed_words(view.words, view.event_onset))
        count += 1
    if count == 0:
        raise FeatureContractError("transcript TRAIN view support is empty")
    return TranscriptVocabulary(("<PAD>", "<UNK>", *sorted(tokens)), count, admission_ref)


def encode_transcript(
    words: Iterable[WordSpan],
    event_onset: Fraction,
    vocabulary: TranscriptVocabulary,
    *,
    diagnostic_release: DiagnosticRelease,
) -> EncodedTranscript:
    """Return exactly 256 left-padded token IDs and a matching attention mask.

    The model must honor the mask/length. Empty context is all PAD, with length
    zero. No IDs, original chronology, exact clocks, or strings enter this view.
    These encoded tokens still constitute a stimulus-exposed diagnostic.
    """
    _require_diagnostic_release(diagnostic_release)
    if not isinstance(vocabulary, TranscriptVocabulary) or vocabulary.fit_role != "TRAIN":
        raise FeatureContractError("a frozen TRAIN transcript vocabulary is required")
    if vocabulary.tokens[:2] != ("<PAD>", "<UNK>") or vocabulary.pad_id != 0 or vocabulary.unk_id != 1 or len(set(vocabulary.tokens)) != len(vocabulary.tokens):
        raise FeatureContractError("invalid frozen PAD/UNK vocabulary")
    index = {token: position for position, token in enumerate(vocabulary.tokens)}
    tokens = _completed_words(words, event_onset)
    encoded = tuple(index.get(token, vocabulary.unk_id) for token in tokens)
    padding = 256 - len(encoded)
    return EncodedTranscript((vocabulary.pad_id,) * padding + encoded,
                             (0,) * padding + (1,) * len(encoded), len(encoded))


def timing_one_hot(progress_bin: int, previous_distinct_onset_gap_bin: int) -> tuple[float, ...]:
    """Encode declared 16-bin progress and 9-bin gap as exactly 25 features.

    Bin boundaries and clocks are supplied by the separately selected source
    compiler. This function neither invents bin thresholds nor consumes exact
    time. The nuisance classifier's intercept is separate from these 25 fields.
    """
    progress = _integer(progress_bin, "progress_bin")
    gap = _integer(previous_distinct_onset_gap_bin, "gap_bin")
    if progress >= 16 or gap >= 9:
        raise FeatureContractError("timing bins must be 0..15 and 0..8")
    values = [0.0] * 25
    values[progress] = 1.0
    values[16 + gap] = 1.0
    return tuple(values)
