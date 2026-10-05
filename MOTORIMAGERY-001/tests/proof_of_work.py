"""Source-bound held-run predictions and conditional original-pair swaps.

All statistics are recomputed from full receipts. There is no performance,
significance, nonconstant-output or prose-recognition acceptance gate.
"""
from __future__ import annotations
import csv
import json
from pathlib import Path
import numpy as np
from scipy.stats import ttest_1samp

PIPELINE_ID = "eegbci-paired-null-held-run-csp-v3"
SUBJECTS = tuple(range(1, 11))
RUNS = (6, 10, 14)
N_PERM = 200
SCORE_ATOL, SCORE_RTOL = 1e-7, 1e-5
STAT_ATOL = STAT_RTOL = 1e-6
EVENT_FIELDS = ("subject", "run", "event_index", "event_sample", "source_class", "retained", "drop_reason")
PRED_FIELDS = ("subject", "run", "event_index", "event_sample", "replicate", "source_class", "target_class", "predicted_class", "decision_score")
FOLD_FIELDS = ("subject", "replicate", "test_run", "n_train", "n_test", "n_train_class0", "n_train_class1", "n_test_class0", "n_test_class1", "accuracy")
SUBJECT_FIELDS = ("subject", "n_epochs", "n_runs", "accuracy", "kappa", "perm_p", "holm_p", "null_mean", "null_sd", "n_null_ge_observed")
FILES = ("source_epochs.csv", "oof_predictions.csv", "fold_receipts.csv", "per_subject.csv", "decoding_results.json", "run_metadata.json", "findings.md")


def finite(value, name):
    assert not isinstance(value, (bool, np.bool_)), f"{name}: boolean is not a number"
    try: result = float(value)
    except (ValueError, TypeError, OverflowError) as exc: raise AssertionError(f"{name}: expected finite number") from exc
    assert np.isfinite(result), f"{name}: expected finite number"
    return result


def integer(value, name):
    value = finite(value, name)
    assert value.is_integer(), f"{name}: expected exact integer"
    return int(value)


def boolean(value, name):
    if isinstance(value, (bool, np.bool_)): return bool(value)
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "1.0"}: return True
    if normalized in {"false", "0", "0.0"}: return False
    raise AssertionError(f"{name}: expected true/false or 1/0")


def load_json(path):
    try: result = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (ValueError, OSError) as exc: raise AssertionError(f"cannot read {path}") from exc
    assert isinstance(result, dict), f"{path}: expected object"
    return result


def csv_rows(path, fields):
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        assert reader.fieldnames is not None, "missing CSV header"
        reader.fieldnames = [name.strip() for name in reader.fieldnames]
        assert len(reader.fieldnames) == len(set(reader.fieldnames)), "duplicate CSV column"
        assert set(fields) <= set(reader.fieldnames), f"missing required columns in {Path(path).name}"
        for row in reader:
            if any(str(value or "").strip() for value in row.values()): yield row


def event_key(row):
    return tuple(integer(row[name], name) for name in ("subject", "run", "event_index"))


def canonical_reason(value):
    parts = [part.strip().lower() for part in str(value or "").split(";") if part.strip()]
    assert len(parts) == len(set(parts)) and set(parts) <= {"annotation", "out_of_bounds"}, "unknown/duplicate drop_reason"
    return ";".join(sorted(parts))


def parse_source_rows(rows):
    parsed = {}
    for row in rows:
        key = event_key(row)
        assert key not in parsed, "duplicate source event"
        sample = integer(row["event_sample"], "event_sample")
        label = integer(row["source_class"], "source_class")
        keep = boolean(row["retained"], "retained")
        reason = canonical_reason(row["drop_reason"])
        assert sample >= 0 and key[2] >= 0 and label in (0, 1), "invalid source sample/index/class"
        assert (keep and not reason) or (not keep and reason), "drop reason inconsistent with retained status"
        parsed[key] = dict(subject=key[0], run=key[1], event_index=key[2], event_sample=sample,
                           source_class=label, retained=keep, drop_reason=reason)
    return parsed


def permutation_targets(subject, runs, labels, event_index, n_permutations=N_PERM):
    """Original balanced-pair swaps; singleton/dropped-pair survivors stay fixed."""
    subject, runs, labels, event_index = map(np.asarray, (subject, runs, labels, event_index))
    result = np.tile(labels, (n_permutations+1, 1)).astype(np.int8)
    for current in sorted(np.unique(subject)):
        rng = np.random.RandomState(0)
        for replicate in range(1, n_permutations+1):
            for run in RUNS:
                for pair in range(7):
                    indices = np.flatnonzero((subject == current) & (runs == run) & (event_index//2 == pair))
                    assert len(indices) <= 2, "duplicate original pair member"
                    indices = indices[np.argsort(event_index[indices])]
                    if len(indices) == 2:
                        assert set(event_index[indices]) == {2*pair, 2*pair+1}
                        assert set(labels[indices]) == {0, 1}, "source original pair must be balanced"
                        result[replicate, indices] = rng.permutation(labels[indices])
    return result


def holm_adjust(p):
    p = np.asarray(p, float)
    assert p.ndim == 1 and len(p) and np.isfinite(p).all() and np.all((p >= 0) & (p <= 1))
    order = np.argsort(p, kind="stable")
    sorted_adjusted = np.maximum.accumulate(p[order]*(len(p)-np.arange(len(p))))
    result = np.empty_like(p); result[order] = np.minimum(1., sorted_adjusted)
    return result


def kappa_score(actual, predicted):
    counts = np.bincount(np.asarray(actual)*2+np.asarray(predicted), minlength=4).reshape(2, 2)
    n = counts.sum(); accuracy = np.trace(counts)/n
    expected = np.dot(counts.sum(axis=0), counts.sum(axis=1))/float(n*n)
    assert expected < 1, "kappa undefined for a degenerate source class set"
    return float((accuracy-expected)/(1-expected))


def statistics_from_predictions(subject, runs, targets, predictions):
    """Pooled epoch accuracy for both observed and every null replicate."""
    subject, runs = np.asarray(subject), np.asarray(runs)
    b = targets.shape[0]-1
    assert b > 0 and targets.shape == predictions.shape
    subjects, folds = [], {}
    for current in sorted(np.unique(subject)):
        mask = subject == current; n = int(mask.sum())
        correct = np.sum(targets[:, mask] == predictions[:, mask], axis=1)
        accuracy = correct/n
        ge = int(np.count_nonzero(correct[1:] >= correct[0]))
        subjects.append(dict(subject=int(current), n_epochs=n, n_runs=len(np.unique(runs[mask])),
            accuracy=float(accuracy[0]), kappa=kappa_score(targets[0, mask], predictions[0, mask]),
            perm_p=(1+ge)/(b+1), null_mean=float(np.mean(accuracy[1:])),
            null_sd=float(np.std(accuracy[1:], ddof=0)), n_null_ge_observed=ge))
        for rep in range(b+1):
            for run in RUNS:
                test = mask & (runs == run); train = mask & (runs != run)
                assert test.any() and train.any(), "empty held-run fold"
                test_y, train_y = targets[rep, test], targets[rep, train]
                folds[(int(current), rep, run)] = dict(subject=int(current), replicate=rep, test_run=run,
                    n_train=int(train.sum()), n_test=int(test.sum()), n_train_class0=int(np.sum(train_y == 0)),
                    n_train_class1=int(np.sum(train_y == 1)), n_test_class0=int(np.sum(test_y == 0)),
                    n_test_class1=int(np.sum(test_y == 1)), accuracy=float(np.mean(predictions[rep, test] == test_y)))
    adjusted = holm_adjust([row["perm_p"] for row in subjects])
    for row, value in zip(subjects, adjusted): row["holm_p"] = float(value)
    acc = np.array([row["accuracy"] for row in subjects])
    if len(acc) < 2 or np.all(acc == acc[0]):
        group_t = group_p = None
    else:
        test = ttest_1samp(acc, .5, alternative="two-sided")
        group_t, group_p = float(test.statistic), float(test.pvalue)
    result = dict(status="ok", pipeline_id=PIPELINE_ID, n_subjects=len(subjects), n_epochs_total=len(subject),
        n_classes=2, chance_level=.5, accuracy=float(acc.mean()),
        cohen_kappa=float(np.mean([row["kappa"] for row in subjects])),
        finite_sample_null_sd=float(np.mean([row["null_sd"] for row in subjects])),
        group_t_vs_chance=group_t, group_p_vs_chance=group_p,
        n_subjects_significant_perm_p05=int(np.sum(np.array([row["perm_p"] for row in subjects]) < .05)),
        n_subjects_significant_holm_p05=int(np.sum(adjusted < .05)),
        n_subjects_below_chance=int(np.sum(acc < .5)), n_subjects_above_half_nominal=int(np.sum(acc > .5)),
        permutation_p_resolution=1/(b+1))
    return subjects, folds, result


def match_values(actual, expected, name="value"):
    for key, value in expected.items():
        assert key in actual, f"{name}: missing {key}"
        if value is None: assert actual[key] is None, f"{name}.{key}: expected null"
        elif isinstance(value, str): assert actual[key] == value, f"{name}.{key}: mismatch"
        elif isinstance(value, int): assert integer(actual[key], key) == value, f"{name}.{key}: count/ID mismatch"
        else: assert np.isclose(finite(actual[key], key), value, atol=STAT_ATOL, rtol=STAT_RTOL), f"{name}.{key}: not recomputed from submitted predictions"


def match_contract(actual, expected, name="metadata"):
    if isinstance(expected, dict):
        assert isinstance(actual, dict), f"{name}: expected object"
        if name.endswith("source_sha256"):
            assert actual == expected, f"{name}: source hash set mismatch"
            return
        for key, value in expected.items():
            assert key in actual, f"{name}: missing {key}"
            match_contract(actual[key], value, name+"."+key)
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(actual) == len(expected), f"{name}: list mismatch"
        for index, value in enumerate(expected): match_contract(actual[index], value, f"{name}[{index}]")
    elif expected is None or isinstance(expected, (bool, str)):
        assert type(actual) is type(expected) and actual == expected, f"{name}: recipe mismatch"
    else: assert abs(finite(actual, name)-expected) <= 1e-12*abs(expected), f"{name}: recipe mismatch"


def inventory(events):
    rows = list(events.values()); result = []
    for subject, run in sorted({(row["subject"], row["run"]) for row in rows}):
        selected = [row for row in rows if row["subject"] == subject and row["run"] == run]
        kept = sum(row["retained"] for row in selected)
        result.append(dict(subject=subject, run=run, n_source_events=len(selected), n_retained=kept, n_dropped=len(selected)-kept))
    return result


def validate_reference(reference):
    stats = reference["stats"]
    assert stats["pipeline_id"] == PIPELINE_ID, "obsolete reference pipeline"
    assert stats["metadata_contract"]["source_sha256"] == stats["source_sha256"]
    events = parse_source_rows(reference["source_rows"])
    assert {key[0] for key in events} == set(SUBJECTS)
    assert {(key[0], key[1]) for key in events} == {(s, r) for s in SUBJECTS for r in RUNS}
    for s in SUBJECTS:
        for r in RUNS:
            keys = sorted(key for key in events if key[:2] == (s, r))
            assert [key[2] for key in keys] == list(range(15)), "incomplete original 15-event source run"
            for pair in range(7):
                assert {events[(s, r, 2*pair)]["source_class"], events[(s, r, 2*pair+1)]["source_class"]} == {0, 1}, "unbalanced original source pair"
            samples = [events[key]["event_sample"] for key in keys]
            assert samples == sorted(samples), "source event order mismatch"
    retained = [events[key] for key in sorted(events) if events[key]["retained"]]
    for key in ("subject", "run", "event_index", "event_sample", "source_class"):
        assert np.array_equal(reference[key], [row[key] for row in retained]), "retained source identity mismatch"
    expected = permutation_targets(reference["subject"], reference["run"], reference["source_class"], reference["event_index"], N_PERM)
    assert reference["targets"].shape == reference["scores"].shape == reference["predictions"].shape == (N_PERM+1, len(retained))
    assert np.array_equal(reference["targets"], expected), "reference permutation stream mismatch"
    assert np.isfinite(reference["scores"]).all()
    assert np.array_equal(reference["predictions"], (reference["scores"] > 0).astype(int)), "reference score/sign mismatch"
    reference["events"] = events
    reference["index"] = {(row["subject"], row["run"], row["event_index"]): i for i, row in enumerate(retained)}
    return reference


def load_reference(path=None):
    path = Path(path) if path else Path(__file__).with_name("reference.npz")
    try:
        with np.load(path, allow_pickle=False) as bank:
            arrays = {key: bank["ref_source_"+key] for key in EVENT_FIELDS}
            rows = [{key: value[i].item() for key, value in arrays.items()} for i in range(len(arrays["subject"]))]
            reference = dict(source_rows=rows, stats=json.loads(str(bank["ref_stats"].item())),
                **{key: bank["ref_"+key] for key in ("subject", "run", "event_index", "event_sample", "source_class")},
                targets=bank["ref_target_class"], scores=bank["ref_decision_score"], predictions=bank["ref_predicted_class"])
    except (OSError, ValueError, KeyError) as exc: raise AssertionError("missing, corrupt or obsolete source-derived bank") from exc
    return validate_reference(reference)


def require_files(output):
    for filename in FILES: assert (Path(output)/filename).is_file(), f"missing required output {filename}"
    assert (Path(output)/"findings.md").read_text(encoding="utf-8-sig").strip(), "empty findings.md"


def validate_source_ledger(path, reference):
    assert parse_source_rows(csv_rows(path, EVENT_FIELDS)) == reference["events"], "source epoch ledger differs from pinned annotations/retention"


def load_predictions(path, reference):
    shape = reference["scores"].shape
    seen = np.zeros(shape, bool); scores = np.empty(shape); predictions = np.empty(shape, np.int8)
    for row in csv_rows(path, PRED_FIELDS):
        key = event_key(row)
        assert key in reference["index"], "prediction event outside retained source epochs"
        index = reference["index"][key]; rep = integer(row["replicate"], "replicate")
        assert 0 <= rep <= N_PERM and not seen[rep, index], "invalid/duplicate replicate-event prediction"
        assert integer(row["event_sample"], "event_sample") == reference["event_sample"][index], "prediction source sample mismatch"
        assert integer(row["source_class"], "source_class") == reference["source_class"][index], "prediction source class mismatch"
        assert integer(row["target_class"], "target_class") == reference["targets"][rep, index], "original-pair conditional permutation target mismatch"
        pred = integer(row["predicted_class"], "predicted_class"); score = finite(row["decision_score"], "decision_score")
        assert pred in (0, 1) and pred == int(score > 0), "prediction must follow decision-score sign (tie=0)"
        seen[rep, index] = True; scores[rep, index] = score; predictions[rep, index] = pred
    assert seen.all(), "OOF table must contain every retained event in every replicate0..200"
    assert np.allclose(scores, reference["scores"], atol=SCORE_ATOL, rtol=SCORE_RTOL), "decision scores differ from source-bound held-run model"
    return scores, predictions


def validate_folds(path, expected):
    seen = set()
    for row in csv_rows(path, FOLD_FIELDS):
        key = tuple(integer(row[name], name) for name in ("subject", "replicate", "test_run"))
        assert key in expected and key not in seen, "unknown/duplicate fold receipt"
        match_values(row, expected[key], "fold"); seen.add(key)
    assert seen == set(expected), "missing held-run fold receipts"


def validate_subjects(path, expected):
    lookup = {row["subject"]: row for row in expected}; seen = set()
    for row in csv_rows(path, SUBJECT_FIELDS):
        subject = integer(row["subject"], "subject")
        assert subject in lookup and subject not in seen, "unknown/duplicate per-subject row"
        match_values(row, lookup[subject], "subject"); seen.add(subject)
    assert seen == set(lookup), "missing per-subject results"


def validate_metadata(path, reference):
    metadata = load_json(path); match_contract(metadata, reference["stats"]["metadata_contract"])
    assert metadata.get("status") == "ok"
    n = len(reference["subject"]); total = len(reference["events"])
    match_values(metadata, dict(n_subjects=len(SUBJECTS), n_epochs_total=n,
                               n_source_events=total, n_dropped_epochs=total-n), "metadata")
    expected = {(row["subject"], row["run"]): row for row in inventory(reference["events"])}
    actual = metadata.get("n_epochs_by_run"); assert isinstance(actual, list)
    seen = set()
    for row in actual:
        key = (integer(row.get("subject"), "subject"), integer(row.get("run"), "run"))
        assert key in expected and key not in seen, "unknown/duplicate run inventory"
        match_values(row, expected[key], "metadata run inventory"); seen.add(key)
    assert seen == set(expected), "incomplete run inventory"
    assert metadata.get("channels") == reference["stats"]["metadata_contract"]["channels"]
    assert finite(metadata.get("sfreq"), "sfreq") == 160


def validate_output_directory(output, reference):
    output = Path(output); require_files(output)
    validate_source_ledger(output/"source_epochs.csv", reference)
    scores, predicted = load_predictions(output/"oof_predictions.csv", reference)
    subjects, folds, result = statistics_from_predictions(reference["subject"], reference["run"], reference["targets"], predicted)
    validate_folds(output/"fold_receipts.csv", folds); validate_subjects(output/"per_subject.csv", subjects)
    match_values(load_json(output/"decoding_results.json"), result, "group")
    validate_metadata(output/"run_metadata.json", reference)
    return scores, predicted
