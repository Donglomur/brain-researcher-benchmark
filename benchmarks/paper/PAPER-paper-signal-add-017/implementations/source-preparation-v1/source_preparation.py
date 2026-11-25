"""Operator-side source MAT/trial/EEGNet-input preparation, without model fitting.

This implements the pinned author training preprocessing, not the missing
figure-specific five-fold evaluation. Raw source class 3 (middle finger) must
be counted before the binary/ternary training class selection.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re

import numpy as np
from scipy.io import loadmat
from scipy.signal import butter, lfilter, resample
from scipy.stats import zscore

SOURCE_REVISION = "c3a51c374d85f7b01e33ec4e998cf007d7da7763"
FS, CHANNELS, WINDOW, STEP, MAX_SAMPLES = 1024, 128, 1024, 128, 5120


def require(condition, message):
    if not condition:
        raise ValueError(message)


def source_integer(value, name, minimum=0):
    """MATLAB stores source sample indices as doubles; require exact integers."""
    require(isinstance(value, (int, float, np.integer, np.floating))
            and not isinstance(value, (bool, np.bool_)), f"invalid {name}")
    require(np.isfinite(value) and value == int(value) and value >= minimum,
            f"invalid {name}")
    return int(value)


@dataclass(frozen=True)
class Run:
    member: str
    subject: str
    condition: str
    session: int
    stage: str
    nclass: int
    number: int

    @property
    def source_classes(self):
        return (1, 2, 3, 4) if self.stage == "Offline" else ((1, 4) if self.nclass == 2 else (1, 2, 4))


def parse_member(member):
    """Accept the documented ordinary-session layout, never invent aliases."""
    require(isinstance(member, str), "source member must be text")
    match = re.fullmatch(
        r"(S\d{2})/(Offline(?:Imagery|Movement)|Online(?:Imagery|Movement)_Sess\d{2}_[23]class_(?:Base|Finetune))/\1_\2_R(\d{2})\.mat",
        member,
    )
    require(match is not None, "unsupported or inconsistent source member")
    subject, folder, number = match.groups()
    require(1 <= int(subject[1:]) <= 21, "subject outside retained cohort")
    number = int(number)
    condition = "MI" if "Imagery" in folder else "ME"
    if folder.startswith("Offline"):
        require(1 <= number <= 32, "offline run outside source range")
        return Run(member, subject, condition, 0, "Offline", 4, number)
    _, sess, nclass, stage = folder.split("_")
    session, nclass = int(sess[4:]), int(nclass[0])
    require(1 <= session <= 5 and 1 <= number <= 8, "online session/run outside source range")
    require(not (subject == "S07" and condition == "MI" and session == 5
                 and nclass == 3 and stage == "Base"), "known missing-event source family")
    return Run(member, subject, condition, session, stage, nclass, number)


@dataclass(frozen=True)
class Trial:
    id: str
    run: Run
    source_label: int
    start_sample_zero_based: int
    end_sample_exclusive: int
    source_end_sample_exclusive: int
    eeg: np.ndarray


def extract_trials(data, fsample, events, run, expected_class_counts):
    """Validate the whole original run, then CAR each <=5-second trial.

    Sample indices are converted once from MATLAB's 1-based coordinates. No
    volts/microvolts conversion is justified by the inspected data dictionary.
    Nonfinite raw values and <1-second trials fail; source NaN padding is only
    represented implicitly by later omission of incomplete windows.
    """
    require(isinstance(run, Run) and parse_member(run.member) == run, "unverified run identity")
    data = np.asarray(data)
    require(data.ndim == 2 and data.shape[0] == CHANNELS and data.shape[1] >= WINDOW,
            "EEG must have 128 channels and at least 1024 samples")
    require(np.issubdtype(data.dtype, np.number) and not np.iscomplexobj(data)
            and np.isfinite(data).all(), "EEG must be real and finite")
    require(source_integer(fsample, "sampling rate", 1) == FS, "source rate must be 1024 Hz")
    require(isinstance(expected_class_counts, dict)
            and set(expected_class_counts) == {str(c) for c in run.source_classes},
            "declare every original source class, including offline middle finger")
    for count in expected_class_counts.values():
        require(type(count) is int and count > 0, "source counts must be positive integers")
    require(isinstance(events, list) and events, "source events missing")
    trials, active, previous = [], None, 0
    for event in events:
        require(isinstance(event, dict), "malformed source event")
        if event.get("type") not in ("Target", "TrialEnd"):
            continue
        sample = source_integer(event.get("sample"), "event sample", 1)
        require(previous <= sample <= data.shape[1] + 1, "event order/range violation")
        previous = sample
        if event["type"] == "Target":
            require(active is None, "Target without preceding TrialEnd")
            label = source_integer(event.get("value"), "source class", 1)
            require(label in run.source_classes, "class outside original source run")
            active = (sample - 1, label)
        else:
            require(active is not None, "TrialEnd without Target")
            start, label = active
            end = min(sample - 1, start + MAX_SAMPLES)
            require(end - start >= WINDOW, "trial has no complete source window")
            eeg = np.array(data[:, start:end], dtype=np.float64, copy=True)
            eeg -= eeg.mean(axis=0, keepdims=True)
            trials.append(Trial(f"{run.member}#trial{len(trials):04d}", run, label,
                                start, end, sample - 1, eeg))
            active = None
    require(active is None and trials, "incomplete/empty source event sequence")
    require(dict(Counter(str(t.source_label) for t in trials)) == expected_class_counts,
            "observed original class counts differ from declared source roster")
    return trials


def read_mat(path, member, expected_sha256, expected_class_counts):
    """Read a preauthorized original MAT file using a required content pin.

    Returns operator-private trials only. Online outputs, channel metadata and
    arbitrary extra variables are never returned as decoder input. This does
    not authenticate that a local digest was obtained from the public archive.
    """
    run = parse_member(member)
    require(isinstance(expected_sha256, str) and re.fullmatch(r"[0-9a-f]{64}", expected_sha256),
            "require source MAT SHA256")
    path = Path(path)
    digest = hashlib.sha256()
    # Keep the same descriptor and require stable metadata across both passes.
    # A retained descriptor prevents pathname replacement, but not writes to
    # that same open inode while the authenticated MAT is being decoded.
    with path.open("rb") as handle:
        def identity():
            state = os.fstat(handle.fileno())
            return (state.st_dev, state.st_ino, state.st_size,
                    state.st_mtime_ns, state.st_ctime_ns)

        original_identity = identity()
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
        require(digest.hexdigest() == expected_sha256, "source MAT checksum mismatch")
        require(identity() == original_identity, "source MAT changed during authentication")
        handle.seek(0)
        mat = loadmat(handle, variable_names=["eeg", "event"], simplify_cells=True)
        require(identity() == original_identity, "source MAT changed during decoding")
    require(isinstance(mat.get("eeg"), dict), "missing source eeg structure")
    eeg = mat["eeg"]
    require({"data", "fsample", "nChans", "nSamples"} <= set(eeg), "incomplete source eeg structure")
    shape = np.shape(eeg["data"])
    require(len(shape) == 2 and source_integer(eeg["nChans"], "nChans", 1) == shape[0]
            and source_integer(eeg["nSamples"], "nSamples", 1) == shape[1], "source dimension metadata disagree")
    events = mat.get("event")
    if isinstance(events, dict):
        events = [events]
    require(isinstance(events, (list, np.ndarray)), "missing source event structure")
    return extract_trials(eeg["data"], eeg["fsample"], list(events), run, expected_class_counts)


def source_transform(windows):
    """Exact author Fourier-resample -> causal-filter -> channel-zscore path."""
    windows = np.asarray(windows)
    require(windows.ndim == 3 and windows.shape[1:] == (CHANNELS, WINDOW)
            and len(windows) and not np.iscomplexobj(windows)
            and np.isfinite(windows).all(), "expected finite CAR windows, N x 128 x 1024")
    result = resample(windows, 100, axis=2, window=None, domain="time")
    result = np.pad(result, ((0, 0), (0, 0), (100, 100)), mode="constant")
    b, a = butter(4, [4, 40], btype="bandpass", fs=100)
    result = lfilter(b, a, result, axis=-1)[:, :, 100:-100]
    result = zscore(result, axis=2, nan_policy="omit")
    require(np.isfinite(result).all(), "source preprocessing produced nonfinite channel/window")
    return result[..., np.newaxis]


def segment_trials(trials, classes):
    """Author offset-major order with permanent original trial/window IDs."""
    require(classes in ([1, 4], [1, 2, 4]), "only source binary/ternary classes supported")
    require(trials and len({t.id for t in trials}) == len(trials), "empty/duplicate trial roster")
    require(all(t.source_label in classes for t in trials), "select source classes before segmentation")
    windows, metadata, labels = [], [], []
    for offset in range(0, MAX_SAMPLES - WINDOW + 1, STEP):
        for trial in trials:
            if offset + WINDOW <= trial.eeg.shape[1]:
                windows.append(trial.eeg[:, offset:offset + WINDOW])
                labels.append(classes.index(trial.source_label))
                metadata.append({"id": f"{trial.id}#sample{offset:05d}", "trial_id": trial.id,
                                 "offset_samples": offset,
                                 "start_sample_zero_based": trial.start_sample_zero_based + offset})
    require(windows, "no complete source windows")
    return {"eeg": source_transform(np.stack(windows)), "labels_zero_based": np.asarray(labels),
            "windows": metadata, "trial_ids": [t.id for t in trials]}


def prepare_training(trials, classes, permutation, *, subject, condition, session, model_type):
    """Replay a frozen author 80/20 trial split; never draw or guess its seed.

    The caller supplies trials in the pinned author's folder/file/event order
    and a permutation of selected-trial indices. This API does not recover the
    original random split or Fig. 6's different five-fold CV.
    """
    require(classes in ([1, 4], [1, 2, 4]), "only source binary/ternary classes supported")
    require(condition in ("MI", "ME") and model_type in ("Orig", "Finetune"), "invalid source route")
    require(type(session) is int and 1 <= session <= 5, "invalid source session")
    require(trials and len({t.id for t in trials}) == len(trials), "empty/duplicate original trial roster")
    # The source sorts folders within each chronological session and files in
    # each folder. Refuse a changed ordering before interpreting permutation.
    order = [(t.run.session, t.run.member, t.start_sample_zero_based) for t in trials]
    require(order == sorted(order), "trials must retain original folder/file/event order")
    for trial in trials:
        run = trial.run
        require(run.subject == subject and run.condition == condition, "mixed participant/task source")
        if model_type == "Orig":
            require(run.session < session, "future/current-session training leak")
        else:
            families = (2, 3) if len(classes) == 2 else (3,)
            require(run.session == session and run.stage == "Base" and run.nclass in families,
                    "fine-tuning requires same-day source Base families")
    selected = [t for t in trials if t.source_label in classes]
    require(len(selected) >= 2, "not enough selected trials for 80/20 split")
    require(isinstance(permutation, (list, tuple)) and all(type(i) is int for i in permutation)
            and sorted(permutation) == list(range(len(selected))), "invalid frozen trial permutation")
    cut = int(0.8 * len(selected))
    train_indices = permutation[:cut]
    # np.setdiff1d in the source sorts validation indices into original order.
    validation_indices = sorted(set(permutation) - set(train_indices))
    return {
        "training": segment_trials([selected[i] for i in train_indices], classes),
        "validation": segment_trials([selected[i] for i in validation_indices], classes),
        "classes": list(classes), "permutation": list(permutation),
        "excluded_source_class_counts": dict(Counter(str(t.source_label) for t in trials
                                                      if t.source_label not in classes)),
        "input_signal_units": "unspecified_in_inspected_source_no_amplitude_conversion",
        "output_units": "per_window_per_channel_zscore",
        "output_axes": ["window", "channel", "sample_at_100_Hz", "kernel"],
    }
