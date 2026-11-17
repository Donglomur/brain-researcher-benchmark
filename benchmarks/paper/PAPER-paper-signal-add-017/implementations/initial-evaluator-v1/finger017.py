"""Recorded finger-EEG construction evaluator; not an EEGNet reproduction.

Only NumPy is required. Source-aligned epoch/CAR/window routing is separated
from the explicitly prospective spectral reference and aggregation choices.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import time

import numpy as np

TASK = "PAPER-paper-signal-add-017"
SOURCE_REVISION = "c3a51c374d85f7b01e33ec4e998cf007d7da7763"
FS = 1024
WINDOW = 1024
STEP = 128
MAX_SAMPLES = 5120
KNOWN_MISSING = "S07/OnlineImagery_Sess05_3class_Base"
GATES = [
    "Authentic MAT payload import and selected source-member hashes not validated here",
    "Complete 21-retained-participant/selected-session roster requires independent admission",
    "Native TensorFlow/EEGNet training, resampling/filtering and fine-tuning not executed",
    "Protected figure-specific targets, tolerances and improvement panel remain unfrozen",
    "Cue, eye and muscle nuisance identification and authentic artifact controls remain unresolved",
    "Participant-generalization extension is separate and not implemented",
    "Recorded replay cannot reproduce human adaptation or closed-loop robotic performance",
    "Data CC BY-NC 4.0 and component-specific code rights remain applicable",
]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value, name, minimum=0):
    require(isinstance(value, (int, np.integer)) and not isinstance(value, (bool, np.bool_)),
            f"{name} must be an integer")
    require(value >= minimum, f"{name} below {minimum}")
    return int(value)


def json_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def validate_protocol(protocol):
    """Freeze a selected recording cohort; never infer full-population admission."""
    require(protocol.get("task_id") == TASK and protocol.get("schema_version") == 1,
            "wrong task/schema")
    classes = protocol.get("classes")
    require(isinstance(classes, list) and all(type(c) is int for c in classes) and
            classes in ([1, 4], [1, 2, 4]), "classes must be [1,4] or [1,2,4]")
    require(protocol.get("condition") in ("MI", "ME"), "condition must be MI or ME")
    session = integer(protocol.get("evaluation_session"), "evaluation_session", 1)
    require(session <= 5, "source has five online sessions")
    subjects = protocol.get("subjects")
    require(isinstance(subjects, list) and len(subjects) > 0 and len(set(subjects)) == len(subjects),
            "declare unique selected subjects")
    require(all(s in [f"S{i:02}" for i in range(1, 22)] for s in subjects), "invalid retained subject")
    policy = protocol.get("calibration_policy")
    require(policy in ("source_folder_selection", "prospective_equal_run_subset"),
            "declare calibration policy")
    budget = integer(protocol.get("calibration_runs_per_family"), "calibration budget", 1)
    require(budget <= 8 and (policy != "source_folder_selection" or budget == 8),
            "source folder calibration needs all eight runs per eligible family")
    rows = protocol.get("runs")
    require(isinstance(rows, list) and rows, "empty selected run roster")
    ids, source_members, source_keys = set(), set(), set()
    roles = defaultdict(set)
    calibration = defaultdict(set)
    for r in rows:
        rid, member = r.get("id"), r.get("source_member")
        require(isinstance(rid, str) and rid and rid not in ids, "duplicate/empty run ID")
        require(isinstance(member, str) and member and member not in source_members,
                "source member reused across roles")
        ids.add(rid)
        source_members.add(member)
        require(r.get("subject") in subjects and r.get("condition") == protocol["condition"],
                "subject/imagery-execution mismatch")
        s = integer(r.get("session"), "run session")
        n = integer(r.get("run_number"), "run_number", 1)
        nc = r.get("nclass")
        require(nc in (2, 3), "run nclass must be 2 or 3")
        require(r.get("stage") in ("Offline", "Base", "Finetune"), "unknown stage")
        key = (r["subject"], r["condition"], s, r["stage"], nc, n)
        require(key not in source_keys, "original run reused with another ID/path")
        source_keys.add(key)
        require((s == 0) == (r["stage"] == "Offline"), "offline/session identity mismatch")
        require(s == 0 or (s <= 5 and n <= 8), "online session/run out of source range")
        require(not (r["subject"] == "S07" and r["condition"] == "MI" and
                     s == 5 and r["stage"] == "Base" and nc == 3),
                f"known unusable missing-event family: {KNOWN_MISSING}")
        require(KNOWN_MISSING not in member, "known missing-event source member")
        role = r.get("role")
        require(role in ("train", "calibration", "test"), "invalid role")
        if role == "train":
            require(s < session, "training must use offline/prior sessions")
        elif role == "calibration":
            eligible = (2, 3) if len(classes) == 2 else (3,)
            require(s == session and r["stage"] == "Base" and nc in eligible,
                    "calibration must follow source same-day Base folder selection")
            calibration[(r["subject"], nc)].add(n)
        else:
            require(s == session and r["stage"] == "Finetune" and nc == len(classes),
                    "paired replay test must be same-day matching-class Finetune runs")
        roles[r["subject"]].add(role)
        expected = r.get("expected_class_counts")
        original_classes = (1, 4) if nc == 2 else (1, 2, 4)
        require(isinstance(expected, dict) and set(expected) == {str(c) for c in original_classes},
                "declare original run class counts before binary index exclusion")
        for count in expected.values():
            integer(count, "expected class count", 1)
    for subject in subjects:
        require(roles[subject] == {"train", "calibration", "test"}, "missing subject/role")
        for nc in ((2, 3) if len(classes) == 2 else (3,)):
            require(calibration[(subject, nc)] == set(range(1, budget + 1)),
                    "calibration coverage/budget differs between selected subjects or families")
    return protocol


def extract_trials(data, fsample, events, run):
    """Original sample-1 boundaries, half-open slicing, <=5s and CAR.

    Unknown event types are ignored. Target/TrialEnd pairs must be complete,
    ordered and non-overlapping. Invalid source values fail rather than silently
    dropping windows as the author training helper does for padded NaNs.
    """
    data = np.asarray(data)
    require(data.ndim == 2 and data.shape[0] == 128 and data.shape[1] >= WINDOW,
            "EEG must be 128 channels by samples")
    require(np.issubdtype(data.dtype, np.number) and not np.iscomplexobj(data), "real numeric EEG required")
    require(float(fsample) == FS and np.isfinite(fsample), "source sampling rate must be 1024Hz")
    require(np.isfinite(data).all(), "nonfinite EEG is an explicit admission failure")
    require(isinstance(events, list) and events, "events missing")
    trials, active, previous, index = [], None, 0, 0
    for event in events:
        require(isinstance(event, dict), "event must be a mapping")
        if event.get("type") not in ("Target", "TrialEnd"):
            continue
        sample = integer(event.get("sample"), "event sample", 1)
        require(previous <= sample <= data.shape[1] + 1, "unordered/out-of-range event sample")
        previous = sample
        if event["type"] == "Target":
            require(active is None, "nested Target without TrialEnd")
            label = integer(event.get("value"), "target label", 1)
            require(label in ((1, 4) if run["nclass"] == 2 else (1, 2, 4)), "invalid target label")
            active = (sample - 1, label)
        else:
            require(active is not None, "TrialEnd without Target")
            start, label = active
            end = min(sample - 1, start + MAX_SAMPLES)
            require(end - start >= WINDOW, "trial shorter than one second; cannot silently omit")
            x = np.asarray(data[:, start:end], dtype=np.float64)
            x = x - x.mean(axis=0, keepdims=True)
            trials.append({"id": f"{run['id']}#trial{index:04}", "run_id": run["id"],
                           "subject": run["subject"], "session": run["session"],
                           "role": run["role"], "label": label, "data": x,
                           "start": start, "end": end, "source_end": sample - 1,
                           "nclass": run["nclass"]})
            active, index = None, index + 1
    require(active is None and trials, "unclosed/empty trial sequence")
    observed = Counter(str(t["label"]) for t in trials)
    require(dict(observed) == run["expected_class_counts"], "source trial/class roster incomplete")
    return trials


def prepare(protocol, recordings):
    """Consume one authenticated numeric export per declared run, no globbing."""
    validate_protocol(protocol)
    require(set(recordings) == {r["id"] for r in protocol["runs"]}, "recording roster mismatch")
    trials, metadata, windows = [], [], []
    raw_fingerprints = set()
    dropped_index = 0
    for run in protocol["runs"]:
        raw = recordings[run["id"]]
        extracted = extract_trials(raw["data"], raw["fsample"], raw["events"], run)
        # A relabeled export file must not bypass original-recording isolation.
        # Canonicalize numeric type/order so NPZ container changes are irrelevant.
        canonical = np.ascontiguousarray(raw["data"], dtype="<f8")
        digest = hashlib.sha256(str(canonical.shape).encode())
        digest.update(memoryview(canonical).cast("B"))
        fingerprint = digest.hexdigest()
        require(fingerprint not in raw_fingerprints, "duplicated numeric EEG content across run identities")
        raw_fingerprints.add(fingerprint)
        for trial in extracted:
            if trial["label"] not in protocol["classes"]:
                dropped_index += 1
                continue
            x = trial.pop("data")
            trial["window_ids"] = []
            for offset in range(0, x.shape[1] - WINDOW + 1, STEP):
                wid = f"{trial['id']}#sample{offset:05}"
                trial["window_ids"].append(wid)
                metadata.append({"id": wid, "trial_id": trial["id"], "run_id": run["id"],
                                 "subject": run["subject"], "role": run["role"],
                                 "offset": offset})
                windows.append(x[:, offset:offset + WINDOW])
            trials.append(trial)
    require(trials and windows, "empty selected trial/window roster")
    return {"protocol": protocol, "protocol_sha256": json_hash(protocol), "trials": trials,
            "windows": metadata, "eeg": np.stack(windows),
            "binary_excluded_index_trials": dropped_index}


def public_packet(prepared, role):
    """Whitelist fields; evaluation events, labels and online outputs never pass."""
    require(role in ("train", "calibration", "test"), "unknown packet role")
    ix = [i for i, w in enumerate(prepared["windows"]) if w["role"] == role]
    trial_map = {t["id"]: t for t in prepared["trials"]}
    packet = {"schema_version": 1, "task_id": TASK, "classes": prepared["protocol"]["classes"],
              "role": role, "windows": [{k: prepared["windows"][i][k]
                  for k in ("id", "trial_id", "run_id", "subject", "offset")} for i in ix],
              "eeg": prepared["eeg"][ix].copy()}
    if role != "test":
        packet["labels"] = [trial_map[prepared["windows"][i]["trial_id"]]["label"] for i in ix]
    return packet


def spectral_features(eeg):
    """Prospective 4-band log-power reference, NOT source EEGNet preprocessing."""
    x = np.asarray(eeg, dtype=float)
    require(x.ndim == 3 and x.shape[1:] == (128, WINDOW) and np.isfinite(x).all(),
            "features require finite prepared 128x1024 windows")
    x = x - x.mean(axis=-1, keepdims=True)
    scale = x.std(axis=-1, keepdims=True)
    x = np.divide(x, scale, out=np.zeros_like(x), where=scale > 0)
    power = np.abs(np.fft.rfft(x * np.hanning(WINDOW), axis=-1)) ** 2 / WINDOW
    frequencies = np.fft.rfftfreq(WINDOW, d=1 / FS)
    bands = ((4, 8), (8, 13), (13, 30), (30, 41))
    values = [np.log(np.maximum(power[..., (frequencies >= lo) & (frequencies < hi)].mean(-1), 1e-12))
              for lo, hi in bands]
    return np.stack(values, axis=-1).reshape(len(x), -1)


class Centroid:
    """Fixed diagonal-distance reference; train-only scaling, equal trial weight."""
    def fit(self, x, labels, trial_ids, classes):
        x, labels = np.asarray(x, float), np.asarray(labels)
        require(x.ndim == 2 and len(x) == len(labels) == len(trial_ids) and len(x), "fit shape mismatch")
        require(np.isfinite(x).all() and set(labels) == set(classes), "training must support every class")
        grouped = defaultdict(set)
        for trial, label in zip(trial_ids, labels):
            grouped[trial].add(int(label))
        require(all(len(v) == 1 for v in grouped.values()), "one trial cannot carry multiple targets")
        counts = Counter(trial_ids)
        weights = np.array([1 / counts[t] for t in trial_ids])
        self.classes = list(classes)
        self.mean = np.average(x, axis=0, weights=weights)
        variance = np.average((x - self.mean) ** 2, axis=0, weights=weights)
        self.scale = np.sqrt(np.maximum(variance, 1e-12))
        z = (x - self.mean) / self.scale
        self.centers = np.stack([np.average(z[labels == c], axis=0, weights=weights[labels == c])
                                 for c in classes])
        self.prior = np.array([sum(next(iter(v)) == c for v in grouped.values()) for c in classes], float)
        self.prior /= self.prior.sum()
        return self

    def predict(self, x):
        x = np.asarray(x, float)
        require(x.ndim == 2 and x.shape[1] == len(self.mean) and np.isfinite(x).all(), "prediction feature mismatch")
        z = (x - self.mean) / self.scale
        logits = -np.mean((z[:, None, :] - self.centers[None, :, :]) ** 2, axis=-1) / 2
        logits -= logits.max(axis=1, keepdims=True)
        p = np.exp(logits)
        return p / p.sum(axis=1, keepdims=True)


def validate_predictions(prepared, predictions):
    expected = {w["id"] for w in prepared["windows"] if w["role"] == "test"}
    require(isinstance(predictions, dict) and set(predictions) == expected, "exact held-out window roster required")
    nc = len(prepared["protocol"]["classes"])
    for wid, row in predictions.items():
        p = np.asarray(row, dtype=float)
        require(p.shape == (nc,) and np.isfinite(p).all() and (p >= 0).all() and (p <= 1).all(),
                f"invalid probabilities for {wid}")
        require(abs(float(p.sum()) - 1) <= 1e-8, f"probability simplex violated for {wid}")


def score(prepared, predictions):
    """Paper hard-window majority per trial; declared class-order tie rule."""
    validate_predictions(prepared, predictions)
    classes = prepared["protocol"]["classes"]
    rows = []
    for t in prepared["trials"]:
        if t["role"] != "test":
            continue
        p = np.array([predictions[w] for w in t["window_ids"]], float)
        votes = np.bincount(np.argmax(p, axis=1), minlength=len(classes))
        predicted = classes[int(np.argmax(votes))]
        target = classes.index(t["label"])
        mean_p = p.mean(axis=0)
        rows.append({"trial_id": t["id"], "subject": t["subject"], "run_id": t["run_id"],
                     "target": t["label"], "prediction": predicted, "window_count": len(p),
                     "correct": int(predicted == t["label"]), "vote_counts": votes.tolist(),
                     "tie": bool((votes == votes.max()).sum() > 1),
                     "brier_mean_window_probability": float(np.sum((mean_p - np.eye(len(classes))[target]) ** 2))})
    by_subject = {}
    for subject in prepared["protocol"]["subjects"]:
        own = [r for r in rows if r["subject"] == subject]
        require(own, "missing held-out subject")
        confusion = np.zeros((len(classes), len(classes)), dtype=int)
        for r in own:
            confusion[classes.index(r["target"]), classes.index(r["prediction"])] += 1
        support = confusion.sum(axis=1)
        predicted_support = confusion.sum(axis=0)
        recalls = [float(confusion[i, i] / support[i]) if support[i] else None for i in range(len(classes))]
        precisions = [float(confusion[i, i] / predicted_support[i]) if predicted_support[i] else None
                      for i in range(len(classes))]
        by_subject[subject] = {"trials": len(own), "accuracy": float(np.mean([r["correct"] for r in own])),
                               "balanced_accuracy": float(np.mean(recalls)) if all(v is not None for v in recalls) else None,
                               "class_support": support.tolist(), "class_recalls": recalls,
                               "class_precision": precisions, "predicted_class_support": predicted_support.tolist(),
                               "confusion_true_by_predicted": confusion.tolist(),
                               "brier": float(np.mean([r["brier_mean_window_probability"] for r in own]))}
    bacc = [r["balanced_accuracy"] for r in by_subject.values()]
    return {"protocol_sha256": prepared.get("protocol_sha256", json_hash(prepared["protocol"])),
            "subject_macro_accuracy": float(np.mean([r["accuracy"] for r in by_subject.values()])),
            "subject_macro_balanced_accuracy": float(np.mean(bacc)) if all(v is not None for v in bacc) else None,
            "subject_macro_brier": float(np.mean([r["brier"] for r in by_subject.values()])),
            "subjects": by_subject, "trials": rows,
            "metric_semantics": "hard-window-vote trial accuracy; equal subjects; ties use declared class order"}


def paired_comparison(baseline, adapted, seed=17017, replicates=2000):
    require(baseline["protocol_sha256"] == adapted["protocol_sha256"], "paired protocol/budget mismatch")
    require(set(baseline["subjects"]) == set(adapted["subjects"]), "paired subject roster mismatch")
    before = {r["trial_id"]: (r["subject"], r["target"]) for r in baseline["trials"]}
    after = {r["trial_id"]: (r["subject"], r["target"]) for r in adapted["trials"]}
    require(before == after, "paired trial/target roster mismatch")
    integer(seed, "bootstrap seed")
    integer(replicates, "bootstrap replicates", 100)
    subjects = sorted(baseline["subjects"])
    delta = np.array([adapted["subjects"][s]["accuracy"] - baseline["subjects"][s]["accuracy"] for s in subjects])
    ci = None
    if len(subjects) >= 2:
        rng = np.random.default_rng(seed)
        draws = np.array([rng.choice(delta, len(delta), replace=True).mean() for _ in range(replicates)])
        ci = np.quantile(draws, [0.025, 0.975]).tolist()
    return {"delta_subject_macro_accuracy": float(delta.mean()), "subject_deltas": dict(zip(subjects, delta.tolist())),
            "paired_subject_bootstrap_95_percentile": ci, "bootstrap_seed": seed,
            "bootstrap_replicates": replicates if ci is not None else 0,
            "limitation": "prospective uncertainty; undefined for one selected participant; no population qualification"}


def reference_predictions(prepared, include_calibration=False, control="spectral", seed=17017):
    require(control in ("spectral", "no_neural", "within_session_label_permutation", "run_trial_alignment_shift"),
            "unknown reference/control")
    features = spectral_features(prepared["eeg"])
    trials = {t["id"]: t for t in prepared["trials"]}
    result = {}
    for subject in prepared["protocol"]["subjects"]:
        fit_roles = {"train", "calibration"} if include_calibration else {"train"}
        train_ix = [i for i, w in enumerate(prepared["windows"]) if w["subject"] == subject and w["role"] in fit_roles]
        test_ix = [i for i, w in enumerate(prepared["windows"]) if w["subject"] == subject and w["role"] == "test"]
        label_map = {t["id"]: t["label"] for t in trials.values() if t["subject"] == subject and t["role"] in fit_roles}
        if control in ("within_session_label_permutation", "run_trial_alignment_shift"):
            groups = defaultdict(list)
            for tid in label_map:
                t = trials[tid]
                key = t["run_id"] if control == "run_trial_alignment_shift" else (t["session"], t["nclass"])
                groups[key].append(tid)
            rng = np.random.default_rng(seed + int(subject[1:]))
            for tids in groups.values():
                original = [label_map[t] for t in tids]
                labels = np.roll(original, 1) if control == "run_trial_alignment_shift" else rng.permutation(original)
                label_map.update(zip(tids, map(int, labels)))
        train_ids = [prepared["windows"][i]["trial_id"] for i in train_ix]
        model = Centroid().fit(features[train_ix], [label_map[t] for t in train_ids], train_ids,
                               prepared["protocol"]["classes"])
        p = np.tile(model.prior, (len(test_ix), 1)) if control == "no_neural" else model.predict(features[test_ix])
        result.update((prepared["windows"][i]["id"], row.tolist()) for i, row in zip(test_ix, p))
    return result


def run_reference(prepared):
    start = time.perf_counter()
    baseline = score(prepared, reference_predictions(prepared))
    adapted = score(prepared, reference_predictions(prepared, include_calibration=True))
    controls = {c: score(prepared, reference_predictions(prepared, control=c))
                for c in ("no_neural", "within_session_label_permutation", "run_trial_alignment_shift")}
    return {"task_id": TASK, "implementation": "initial-evaluator-v1", "protocol_sha256": prepared["protocol_sha256"],
            "scientific_qualification": "unknown", "historical_reproduction": False,
            "reference": "prospective train-only spectral centroid; calibration augments training, not EEGNet fine-tuning",
            "baseline": baseline, "calibration_augmented": adapted,
            "paired_comparison": paired_comparison(baseline, adapted), "controls": controls,
            "coverage": {"selected_subjects": prepared["protocol"]["subjects"], "runs": len(prepared["protocol"]["runs"]),
                         "trials": len(prepared["trials"]), "windows": len(prepared["windows"]),
                         "binary_index_trials_excluded": prepared["binary_excluded_index_trials"]},
            "known_unusable_source_family": KNOWN_MISSING,
            "remaining_gates": GATES,
            "observed_evaluator_wall_seconds": time.perf_counter() - start,
            "resource_limit": "array resident reference; observed engineering cost is not authentic resource envelope"}


def load_recordings(protocol, base):
    """Safe numeric-export bridge; original MAT/MCOS ingestion is not claimed."""
    recordings, paths, hashes = {}, set(), set()
    for run in protocol["runs"]:
        path = Path(base) / run["eeg_npz"]
        require(path.resolve() not in paths, "numeric-export path reused across run identities")
        paths.add(path.resolve())
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        require(digest == run["eeg_npz_sha256"], "numeric export hash mismatch")
        require(digest not in hashes, "numeric-export bytes reused across run identities")
        hashes.add(digest)
        with np.load(path, allow_pickle=False) as archive:
            recordings[run["id"]] = {"data": archive["data"], "fsample": float(archive["fsample"].item()),
                                      "events": run["events"]}
    return recordings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("reference", "score", "packets"))
    parser.add_argument("protocol", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--predictions", type=Path)
    args = parser.parse_args(argv)
    protocol = json.loads(args.protocol.read_text())
    validate_protocol(protocol)
    prepared = prepare(protocol, load_recordings(protocol, args.protocol.parent))
    if args.command == "packets":
        args.output.mkdir(parents=True, exist_ok=False)
        for role in ("train", "calibration", "test"):
            packet = public_packet(prepared, role)
            np.savez(args.output / f"{role}.npz", eeg=packet.pop("eeg"))
            (args.output / f"{role}.json").write_text(json.dumps(packet, indent=2) + "\n")
        return
    if args.command == "score":
        require(args.predictions is not None, "score requires --predictions")
        def unique_keys(pairs):
            result = {}
            for key, value in pairs:
                require(key not in result, "duplicate prediction JSON key")
                result[key] = value
            return result
        result = score(prepared, json.loads(args.predictions.read_text(), object_pairs_hook=unique_keys))
        result = {"task_id": TASK, "protocol_sha256": prepared["protocol_sha256"],
                  "scientific_qualification": "unknown", "remaining_gates": GATES, "score": result}
    else:
        result = run_reference(prepared)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
