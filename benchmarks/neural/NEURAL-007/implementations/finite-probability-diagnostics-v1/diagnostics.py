"""Finite sleep probability endpoints, preserving the frozen primary scorer.

Operator API only: candidate and both reference files are fully validated before
the one trusted target-loader call. No model, target discovery or input crop.
"""
import hashlib
import importlib.util
import math
import os
from pathlib import Path
import stat
import sys

HERE = Path(__file__).resolve().parent
ADAPTER = HERE.parent / 'finite-attempt-audit/vendor/candidate_adapter.py'
ADAPTER_PIN = (14326, 'fc8363b28a86cd1f5083b4cc5d24fb1a5a4abd1d490d9163a305f85f1fbe4d23')
CASES = (('development-001', 2780), ('development-002', 2670))
COMPARATORS = ('YASA', 'RF')
BIN_EDGES = tuple(i / 10 for i in range(11))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_adapter():
    """Execute only the retained exact predecessor bytes; no new numeric code."""
    path = ADAPTER.absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)),
            'Pinned adapter and ancestors must not be linked')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                and before.st_size == ADAPTER_PIN[0], 'Pinned ordinary adapter size')
        body = bytearray()
        while len(body) < ADAPTER_PIN[0]:
            block = os.read(fd, ADAPTER_PIN[0] - len(body))
            require(bool(block), 'Complete pinned adapter')
            body.extend(block)
        after = os.fstat(fd)
        fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_nlink')
        require(not os.read(fd, 1) and all(getattr(before, k) == getattr(after, k) for k in fields),
                'Stable pinned adapter capture')
    finally:
        os.close(fd)
    require(hashlib.sha256(body).hexdigest() == ADAPTER_PIN[1], 'Pinned adapter digest')
    name = '_neural007_probability_adapter_' + ADAPTER_PIN[1]
    spec = importlib.util.spec_from_file_location(name, path)
    adapter = importlib.util.module_from_spec(spec)
    sys.modules[name] = adapter
    try:
        exec(compile(bytes(body), str(path), 'exec'), adapter.__dict__)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return adapter


def _diagnostics(probability, truth):
    """Checked eligible rows only. Natural logs, unscaled Brier, fixed bins."""
    n = len(truth)
    require(n > 0 and len(probability) == n, 'Every person requires eligible probability rows')
    log_terms, brier_terms = [], []
    zero_count = 0
    bins = [{'count': 0, 'correct': 0, 'confidence_terms': []} for _ in range(10)]
    for row, stage in zip(probability, truth):
        p = [float(x) for x in row]
        stage = int(stage)
        actual = p[stage]
        if actual == 0:
            zero_count += 1
        else:
            log_terms.append(-math.log(actual))
        brier_terms.append(math.fsum((x - int(k == stage)) ** 2 for k, x in enumerate(p)))
        predicted = max(range(5), key=lambda k: (p[k], -k))
        confidence = p[predicted]
        # Compare with declared edges, so an exact edge belongs to its upper bin.
        index = sum(confidence >= edge for edge in BIN_EDGES[1:-1])
        item = bins[index]
        item['count'] += 1
        item['correct'] += int(predicted == stage)
        item['confidence_terms'].append(confidence)
    calibration, deviations = [], []
    for index, item in enumerate(bins):
        count, correct = item['count'], item['correct']
        confidence_sum = math.fsum(item['confidence_terms'])
        deviations.append(abs(correct - confidence_sum))
        calibration.append({'lower_inclusive': BIN_EDGES[index],
                            'upper': BIN_EDGES[index + 1], 'upper_inclusive': index == 9,
                            'count': count, 'correct': correct,
                            'mean_confidence': confidence_sum / count if count else None,
                            'accuracy': correct / count if count else None})
    finite_sum = math.fsum(log_terms)
    return {'scored_epochs': n,
            'mean_log_loss': None if zero_count else finite_sum / n,
            'log_loss_is_infinite': bool(zero_count),
            'zero_true_probability_epochs': zero_count,
            'finite_log_loss_sum': finite_sum,
            'mean_multiclass_brier': math.fsum(brier_terms) / n,
            'top_label_ece_10': math.fsum(deviations) / n,
            'calibration_bins': calibration}


def _score(validated, targets, spec):
    rows = []
    for case in spec.cases:
        truth, mask = targets[case.case_id]
        probability = validated['people'][case.case_id]['probabilities']
        rows.append({'person_id': case.case_id, 'full_epochs': case.epochs,
                     **_diagnostics(probability[mask], truth)})
    infinite = any(row['log_loss_is_infinite'] for row in rows)
    return {'per_person': rows,
            'person_mean_log_loss': None if infinite else math.fsum(row['mean_log_loss'] for row in rows) / len(rows),
            'log_loss_is_infinite': infinite,
            'person_mean_multiclass_brier': math.fsum(row['mean_multiclass_brier'] for row in rows) / len(rows),
            'person_mean_top_label_ece_10': math.fsum(row['top_label_ece_10'] for row in rows) / len(rows)}


def _log_difference(a, b, key):
    if a['log_loss_is_infinite'] and b['log_loss_is_infinite']:
        return {'value': None, 'status': 'undefined_both_infinite'}
    if a['log_loss_is_infinite']:
        return {'value': None, 'status': 'positive_infinity'}
    if b['log_loss_is_infinite']:
        return {'value': None, 'status': 'negative_infinity'}
    return {'value': a[key] - b[key], 'status': 'finite'}


def _difference(candidate, comparator):
    rows = []
    for a, b in zip(candidate['per_person'], comparator['per_person']):
        require((a['person_id'], a['scored_epochs']) == (b['person_id'], b['scored_epochs']),
                'Same people and eligible support for probability contrast')
        rows.append({'person_id': a['person_id'],
                     'mean_log_loss_delta': _log_difference(a, b, 'mean_log_loss'),
                     'mean_multiclass_brier_delta': a['mean_multiclass_brier'] - b['mean_multiclass_brier'],
                     'top_label_ece_10_delta': a['top_label_ece_10'] - b['top_label_ece_10']})
    return {'direction': 'candidate_minus_comparator', 'lower_is_better': True,
            'per_person': rows,
            'person_mean_log_loss_delta': _log_difference(candidate, comparator, 'person_mean_log_loss'),
            'person_mean_multiclass_brier_delta': candidate['person_mean_multiclass_brier'] - comparator['person_mean_multiclass_brier'],
            'person_mean_top_label_ece_10_delta': candidate['person_mean_top_label_ece_10'] - comparator['person_mean_top_label_ece_10']}


def evaluate(submission_path, submission_lock, target_loader, comparators):
    """Score the complete 5,450-epoch finite panel; target_loader is trusted.

    Locks are operator-retained {bytes, sha256} objects. comparators maps YASA/RF
    to (path, lock). This API must run in the operator scoring realm; it supplies
    no sandbox, candidate provenance or permission to discover target files.
    """
    adapter = load_adapter()
    spec = adapter.Specification(tuple(adapter.Case(*case) for case in CASES), COMPARATORS)
    require(type(comparators) is dict and set(comparators) == set(COMPARATORS),
            'Both frozen finite comparators required')
    candidate = adapter.validate_submission(submission_path, submission_lock, spec)
    references = {}
    for name in COMPARATORS:
        item = comparators[name]
        require(type(item) is tuple and len(item) == 2, 'Comparator path/freeze pair')
        references[name] = adapter.validate_submission(item[0], item[1], spec)
    # No callback or private filesystem access precedes complete public validation.
    targets = adapter._checked_targets(target_loader(), spec)
    primary = adapter._score(candidate, targets, spec)
    primary_references = {name: adapter._score(value, targets, spec) for name, value in references.items()}
    candidate_scores = _score(candidate, targets, spec)
    reference_scores = {name: _score(value, targets, spec) for name, value in references.items()}
    return {'schema': 'neural007_finite_probability_diagnostics_v1',
            'status': 'valid_descriptive_probability_diagnostics',
            'people': 2, 'full_epochs': 5450, 'class_order': list(adapter.CLASS_ORDER),
            'primary': {'candidate': primary, 'comparators': primary_references,
                        'signed_comparator_differences': {name: adapter._difference(primary, value)
                                                         for name, value in primary_references.items()}},
            'diagnostics': {'candidate': candidate_scores, 'comparators': reference_scores,
                            'signed_comparator_differences': {name: _difference(candidate_scores, value)
                                                             for name, value in reference_scores.items()}},
            'input_freezes': {'candidate': candidate['file'],
                             'comparators': {name: value['file'] for name, value in references.items()}},
            'definitions': {'aggregation': 'equal_person_after_private_mask',
                            'logarithm': 'natural', 'brier_scale': 'sum_over_five_classes_not_divided_by_five',
                            'calibration': 'top_label_10_fixed_equal_width_bins_first_index_ties',
                            'normalization_clipping_or_epsilon': False,
                            'infinite_log_loss_encoding': 'null_mean_with_explicit_true_infinite_flag'},
            'scope': 'two_previously_exposed_development_people',
            'population_inference': False, 'confidence_interval': None,
            'scientific_qualification': False, 'native_direct_understanding_tested': False}
