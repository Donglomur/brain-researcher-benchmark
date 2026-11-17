"""Four-tone prediction scoring on an operator-supplied, frozen source panel.

This module performs no fitting, split selection, target loading, or inference.
It computes the ordered decoder endpoint, not a reward for the paper's null.
"""
from dataclasses import dataclass
from itertools import product

import numpy as np


CONDITIONS = ("random", "midminus", "midplus", "ordered")
PIPELINES = ("replication", "empirical_null")
PARTICIPANTS = (
    '19830114RFTM', '19921111BRHC', '19930630MNSU', '19930118IMSH',
    '19861231ANSR', '19851130EIFI', '19930524GNTA', '19871229CRBC',
    '19940403HIEC', '19900606KTAD', '19880328AGSG', '19950326IIQI',
    '19750430PNRK', '19950212BTKC', '19930423EEHB', '19960418GBSH',
    '11920812IONP', '19950604LLZM', '19800616MRGU', '19950905MCSH',
    '19891222GBHL', '19940930SZDT', '19960304SBPE', '19821223KRHR',
    '19920804CRLE', '19810726GDZN', '19960708HLHY', '19810918SLBR',
    '19940601IGSH', '19961118BRSH', '19901026KRKE', '19930621ATLI',
    '19910823SSLD',
)


class ScoreError(ValueError):
    """A supplied score panel has invalid or incomplete support."""


def _require(condition, message):
    if not condition:
        raise ScoreError(message)


def _ids(values):
    _require(type(values) is tuple and bool(values), "nonempty tuple of trial identities required")
    _require(all(type(x) is str and x for x in values), "trial identities must be nonempty strings")
    _require(len(set(values)) == len(values), "duplicate trial identity")
    return values


def _axis(values):
    values = np.asarray(values)
    _require(values.ndim == 1 and values.size > 0 and values.dtype.kind in "ifu",
             "nonempty numeric time axis required")
    _require(np.isfinite(values).all() and (np.diff(values.astype(np.float64)) > 0).all(),
             "time axis must be finite and strictly increasing")
    return values


@dataclass(frozen=True, order=True)
class FoldKey:
    participant: str
    pipeline: str
    condition: str
    fold: int


@dataclass(frozen=True)
class Targets:
    """Operator-owned tone identities (omitted tone for the omission route).

    This is never a decoder feature interface.
    """
    trial_ids: tuple
    labels: object


@dataclass(frozen=True)
class Predictions:
    trial_ids: tuple
    train_times: object
    test_times: object
    labels: object  # trial, training time, testing time; class codes 1..4


@dataclass(frozen=True)
class FoldScore:
    correct: object
    tested: int
    confusion_counts: object  # training time, testing time, actual, predicted


@dataclass(frozen=True)
class SourceFold:
    fold: int
    train_ids: tuple
    test_ids: tuple
    boundary_excluded_ids: tuple


def pinned_sound_folds(ordered_event_ids):
    """Literal a454439 sound KFold(5) plus its asymmetric test-edge removal.

    Input is the source's already matched ordered event list. This is before
    MNE epoch rejection, which still needs observed retained-event identities.
    The held-out boundary events remain excluded from training too. This exact
    current-source rule is not the paper's described stratified five-fold rule
    and must never be relabelled publication-vintage recovery.
    """
    ids = _ids(ordered_event_ids)
    _require(len(ids) >= 5, "KFold(5) needs at least five source events")
    width, remainder = divmod(len(ids), 5)
    start = 0
    result = []
    for fold in range(5):
        stop = start + width + (fold < remainder)
        raw_test = tuple(range(start, stop))
        if start == 0:
            retained = raw_test[:-1]
        elif stop == len(ids):
            retained = raw_test[2:]
        else:
            retained = raw_test[2:-1]
        _require(bool(retained), "source boundary trimming emptied a held-out fold")
        result.append(SourceFold(fold,
            ids[:start] + ids[stop:],
            tuple(ids[i] for i in retained),
            tuple(ids[i] for i in raw_test if i not in retained)))
        start = stop
    return tuple(result)


def score_fold(targets, predictions, *, train_times, test_times):
    """Count correct tones; neither class balancing nor nominal chance scoring.

    Trial order and both observed time axes must exactly match the frozen source
    support. A fold missing a tone class is valid for the pinned KFold producer;
    its confusion row has zero support, not an invented normalized row.
    """
    ids = _ids(targets.trial_ids)
    _require(_ids(predictions.trial_ids) == ids, "prediction trial order differs from frozen targets")
    train_times, test_times = _axis(train_times), _axis(test_times)
    _require(np.array_equal(_axis(predictions.train_times), train_times) and
             np.array_equal(_axis(predictions.test_times), test_times),
             "prediction time axes differ from frozen source axes")
    truth, guessed = np.asarray(targets.labels), np.asarray(predictions.labels)
    _require(truth.shape == (len(ids),) and truth.dtype.kind in "iu" and
             np.isin(truth, (1, 2, 3, 4)).all(), "actual tone labels must be integer codes 1..4")
    _require(guessed.shape == (len(ids), len(train_times), len(test_times)) and
             guessed.dtype.kind in "iu" and np.isin(guessed, (1, 2, 3, 4)).all(),
             "predictions require exact trial/train/test shape and integer tone codes 1..4")
    # Work one training-time plane at a time; never expand a trial x time x
    # time x class one-hot tensor. Counts use a signed wide integer dtype.
    counts = np.empty((len(train_times), len(test_times), 4, 4), dtype=np.int64)
    correct = np.empty((len(train_times), len(test_times)), dtype=np.int64)
    for i in range(len(train_times)):
        plane = guessed[:, i, :]
        correct[i] = (plane == truth[:, None]).sum(axis=0, dtype=np.int64)
        for actual in range(1, 5):
            selected = plane[truth == actual]
            for predicted in range(1, 5):
                counts[i, :, actual - 1, predicted - 1] = (selected == predicted).sum(axis=0, dtype=np.int64)
    return FoldScore(correct, len(ids), counts)


def compare_panel(cases, *, stimulus, train_times, test_times, fold_ids, frozen_trials):
    """Stream paired source/candidate predictions into complete participant maps.

    Each case is (FoldKey, Targets, author Predictions, candidate Predictions).
    frozen_trials independently lists the operator-selected ordered trial IDs for
    every FoldKey. Cases cannot silently shorten those denominators.
    The caller supplies the frozen publication-aligned fold IDs and actual time
    axes; this scorer does not choose between discrepant historical versions.
    Both original and reordered controls and all 33 declared participants are
    required. Sound and omission are separate invocations and separate results.

    Accuracy is mean_folds(correct/tested), then mean_participants, at each
    condition/train/test cell. Unequal folds are deliberately not pooled. No
    reduction across conditions or temporal cells, inferential test, selected
    interval, scalar victory, or claim of authenticated author execution occurs.
    """
    _require(stimulus in ("sound", "omission"), "sound and omission must be scored separately")
    train_times, test_times = _axis(train_times), _axis(test_times)
    _require(type(fold_ids) is tuple and bool(fold_ids) and
             all(type(i) is int and i >= 0 for i in fold_ids) and
             len(set(fold_ids)) == len(fold_ids), "exact frozen fold identities required")
    # Source sound decoding uses five folds. Omission fold provenance is supplied
    # explicitly because the legacy corrected profile uses a different route.
    _require(stimulus != "sound" or len(fold_ids) == 5, "source sound panel requires five folds")
    expected = {FoldKey(*key) for key in product(PARTICIPANTS, PIPELINES, CONDITIONS, fold_ids)}
    _require(type(frozen_trials) is dict and set(frozen_trials) == expected,
             "frozen trial manifest must cover the complete panel")
    for key, ids in frozen_trials.items():
        _require(type(key) is FoldKey and type(key.fold) is int, "typed frozen fold identities required")
        _ids(ids)
    shape = (len(PARTICIPANTS), len(PIPELINES), len(CONDITIONS), len(train_times), len(test_times))
    author = np.zeros(shape, dtype=np.float64)
    candidate = np.zeros(shape, dtype=np.float64)
    denominators = np.zeros(shape[:3] + (len(fold_ids),), dtype=np.int64)
    seen = set()
    trial_sets = {}
    for key, targets, author_predictions, candidate_predictions in cases:
        _require(type(key) is FoldKey and type(key.fold) is int and key in expected and key not in seen,
                 "unexpected or duplicate participant/pipeline/condition/fold")
        slot = (PARTICIPANTS.index(key.participant), PIPELINES.index(key.pipeline), CONDITIONS.index(key.condition))
        ids = _ids(targets.trial_ids)
        _require(ids == frozen_trials[key], "case trial support differs from frozen trial manifest")
        previous = trial_sets.setdefault(slot, set())
        _require(not previous.intersection(ids), "test trial appears in more than one fold")
        previous.update(ids)
        a = score_fold(targets, author_predictions, train_times=train_times, test_times=test_times)
        c = score_fold(targets, candidate_predictions, train_times=train_times, test_times=test_times)
        author[slot] += 100.0 * a.correct / a.tested / len(fold_ids)
        candidate[slot] += 100.0 * c.correct / c.tested / len(fold_ids)
        denominators[slot + (fold_ids.index(key.fold),)] = a.tested
        seen.add(key)
    _require(seen == expected, "incomplete full participant/condition/control/fold panel")
    delta = candidate - author
    return {
        "stimulus": stimulus,
        "participants": PARTICIPANTS,
        "pipelines": PIPELINES,
        "conditions": CONDITIONS,
        "fold_ids": fold_ids,
        "train_times": train_times.copy(),
        "test_times": test_times.copy(),
        "fold_test_counts": denominators,
        "author_accuracy_percent": author,
        "candidate_accuracy_percent": candidate,
        "participant_gain_percentage_points": delta,
        "participant_reconstruction_absolute_error_percentage_points": np.abs(delta),
        "group_author_accuracy_percent": author.mean(axis=0),
        "group_candidate_accuracy_percent": candidate.mean(axis=0),
        "group_gain_percentage_points": delta.mean(axis=0),
        "group_mean_reconstruction_absolute_error_percentage_points": np.abs(delta).mean(axis=0),
        "aggregation": "equal fold accuracy, then equal participants; retain pipeline/condition/time axes",
        "qualified_reward": None,
        "outcomes": "reproduction error and signed improvement are separate; neither is a preactivation inference",
        "historical_publication_parity": "requires independent source/fold/input qualification",
        "inference": "not performed; participant-level uncertainty and full-panel decision remain unfrozen",
    }
