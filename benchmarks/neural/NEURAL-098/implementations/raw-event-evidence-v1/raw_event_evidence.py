"""COGITATE V1 raw-event evidence for the existing NEURAL-098 preparation.

This pure metadata parser reads no files or recordings. Event code 96 is the
documented stimulus offset; 97 is the subsequent blank-offset/jitter marker.
It neither fabricates an epoch join nor authenticates an event export.
"""
from bisect import bisect_left
import math


SCHEMA = "neural098-raw-event-evidence-v1"
SEMANTICS_URL = "https://cogitate-consortium.github.io/cogitate-data/03_cogdataset/#stimulus-presentation-end"
CATEGORIES = ("face", "object", "letter", "false")
ORIENTATIONS = {101: "Center", 102: "Left", 103: "Right"}
DURATIONS = {151: 500, 152: 1000, 153: 1500}
RELEVANCE = {201: "Relevant target", 202: "Relevant non-target", 203: "Irrelevant"}
KNOWN_CODES = (set(range(1, 81)) | {0, 81, 83, 86, 96, 97, 255}
               | set(ORIENTATIONS) | set(DURATIONS) | set(RELEVANCE)
               | set(range(111, 149)) | set(range(161, 201)))


def _integer(value, name, minimum=0, maximum=10**12):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(name + " must be a bounded integer")
    return value


def _one(segment, codes, name):
    found = [row for row in segment if row[2] in codes]
    if len(found) != 1:
        raise ValueError("exactly one observed " + name + " marker required")
    return found[0]


def extract_raw_trial_evidence(events, *, run, sfreq, first_sample, n_samples):
    """Interpret one complete, operator-supplied P04-style MNE event export.

    ``events`` is a list of [raw_sample, previous_stim_value, event_code].
    ``sfreq``, ``first_sample`` and ``n_samples`` describe that same raw run,
    not a later concatenated or resampled epoch. All 1..80 stimulus onsets are
    retained, including categories/response trials the later task excludes.

    Source ownership/completeness and event/header provenance remain external.
    No generated evidence row can directly satisfy the existing binding schema:
    selection_index and epoch_event_sample require an independent epoch join.
    """
    _integer(run, "run", 1, 99)
    _integer(first_sample, "first_sample")
    _integer(n_samples, "n_samples", 1)
    if first_sample + n_samples > 10**12:
        raise ValueError("bounded raw run extent")
    if type(sfreq) not in (int, float) or not math.isfinite(sfreq) or not 1 <= sfreq <= 10000:
        raise ValueError("finite raw sampling frequency in [1,10000]")
    if type(events) is not list or not 1 <= len(events) <= 1_000_000:
        raise ValueError("bounded complete raw event list")
    checked = []
    seen = set()
    previous_sample = -1
    stop_sample = first_sample + n_samples
    for row in events:
        if type(row) not in (list, tuple) or len(row) != 3:
            raise ValueError("MNE event triple required")
        sample, previous, code = row
        _integer(sample, "event sample")
        _integer(previous, "previous stimulus value", 0, 65535)
        _integer(code, "event code", 0, 65535)
        if not first_sample <= sample < stop_sample or sample < previous_sample:
            raise ValueError("ordered events inside the raw recording extent")
        item = (sample, previous, code)
        if item in seen:
            raise ValueError("duplicate raw event")
        if code not in KNOWN_CODES:
            raise ValueError("unresolved event code; do not silently interpret an unknown scheme")
        seen.add(item)
        checked.append(item)
        previous_sample = sample

    onsets = [i for i, row in enumerate(checked) if 1 <= row[2] <= 80]
    if not onsets:
        raise ValueError("at least one documented V1 stimulus onset required")
    onset_samples = [checked[i][0] for i in onsets]
    if len(set(onset_samples)) != len(onset_samples):
        raise ValueError("ambiguous simultaneous stimulus onsets")
    buttons = [row[0] for row in checked if row[2] == 255]
    if len(set(buttons)) != len(buttons):
        raise ValueError("ambiguous duplicate button sample")

    rows = []
    for ordinal, index in enumerate(onsets):
        stop_index = onsets[ordinal + 1] if ordinal + 1 < len(onsets) else len(checked)
        onset = checked[index]
        segment = checked[index + 1:stop_index]
        offset = _one(segment, {96}, "stimulus-offset96")
        blank = _one(segment, {97}, "blank-offset97")
        if not onset[0] < offset[0] < blank[0]:
            raise ValueError("ordered onset, physical-stimulus marker96 and blank marker97")
        orientation = _one(segment, set(ORIENTATIONS), "orientation")
        duration = _one(segment, set(DURATIONS), "duration")
        relevance = _one(segment, set(RELEVANCE), "task relevance")
        trial_id = _one(segment, set(range(111, 149)), "trial ID")
        if any(not onset[0] <= row[0] < offset[0]
               for row in (orientation, duration, relevance, trial_id)):
            raise ValueError("condition markers must precede observed stimulus offset")
        duration_ms = DURATIONS[duration[2]]
        measured_duration = (offset[0] - onset[0]) / sfreq
        # Match the existing prepare.validate_binding tolerance; never replace
        # the measured offset by onset + nominal duration.
        if abs(measured_duration - duration_ms / 1000) > 1.01 / sfreq:
            raise ValueError("marker96 disagrees with nominal duration on the raw clock")
        next_onset = onset_samples[ordinal + 1] if ordinal + 1 < len(onsets) else None
        # Compare relative seconds exactly as the existing binding validator.
        # Adding a fractional sample boundary to a large absolute raw origin
        # can round away its fractional part and change half-open membership.
        end_seconds = duration_ms / 1000 + .3
        relative_seconds = lambda sample: (sample - onset[0]) / sfreq
        left = bisect_left(buttons, -.5, key=relative_seconds)
        right = bisect_left(buttons, end_seconds, key=relative_seconds)
        window_buttons = buttons[left:right]
        if len(window_buttons) > 100:
            raise ValueError("button count exceeds the existing binding schema")
        covered = ((onset[0] - first_sample) / sfreq >= .5
                   and relative_seconds(stop_sample) >= end_seconds)
        next_intrudes = (None if next_onset is None
                         else relative_seconds(next_onset) < end_seconds)
        rows.append({
            "run": run,
            "event_sample": onset[0],
            "stim_trigger": onset[2],
            "category": CATEGORIES[(onset[2] - 1) // 20],
            "orientation": ORIENTATIONS[orientation[2]],
            "duration_ms": duration_ms,
            "relevance": RELEVANCE[relevance[2]],
            "source_trial_id_trigger": trial_id[2],
            "offset_sample": offset[0],
            "offset_marker_code": 96,
            "blank_offset_sample": blank[0],
            "blank_offset_marker_code": 97,
            "next_onset_sample": next_onset,
            "button_samples": window_buttons,
            "raw_event_window_covered": covered,
            "next_stimulus_intrudes": next_intrudes,
            "event_exclusion_reasons": (
                ([] if covered else ["raw_event_window_not_covered"])
                + ([] if not window_buttons else ["button_in_exclusion_window"])
                + ([] if next_intrudes is not True else ["next_stimulus_intrusion"])
                + ([] if next_onset is not None else ["next_onset_unobserved"])),
            "selection_index": None,
            "epoch_event_sample": None,
        })
    return {
        "schema": SCHEMA,
        "run": run,
        "raw_sfreq": sfreq,
        "raw_first_sample": first_sample,
        "raw_n_samples": n_samples,
        "event_count": len(checked),
        "all_stimulus_onsets_retained": len(rows),
        "rows": rows,
        "offset_semantics_source": SEMANTICS_URL,
        "source_export_authenticated": False,
        "raw_to_epoch_join_established": False,
        "compatible_complete_preparation_binding": False,
        "scientific_readiness_promoted": False,
    }
