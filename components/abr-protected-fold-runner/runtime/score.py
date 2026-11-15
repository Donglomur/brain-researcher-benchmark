"""All-animal private scorer; no partial metrics and no runtime sandbox claim.

The trusted evaluator must bind a reviewed manifest before candidate work and
call this only after all104 outputs (and layout outputs if supplied) are durably
committed. This pure function checks completeness; it cannot prove commitment,
fresh process/storage per fold, no cross-fold labels/models, or feedback timing.
Detailed returned reports are evaluator-private because correctness reveals labels.
"""
import math
import json
import os
from pathlib import Path
import stat
import split as split_rules


class ScoreError(ValueError):
    pass


def _need(condition, message):
    if not condition:
        raise ScoreError(message)


def _predictions(rows, animals, role):
    _need(type(rows) is list and len(rows) == 104, role + ': exactly104 prediction rows required')
    expected = {a['animal_id']: a for a in animals}; values = {}
    for row in rows:
        _need(type(row) is dict and set(row) == {'animal_id', 'outer_fold', 'p_6n'}, role + ': exact prediction keys')
        animal_id = row['animal_id']
        _need(type(animal_id) is str and animal_id in expected and animal_id not in values,
              role + ': unknown or duplicate animal ID')
        fold = row['outer_fold']
        _need(type(fold) is int and fold == expected[animal_id]['outer_fold'], role + ': wrong held-out fold')
        probability = row['p_6n']
        _need(type(probability) in (int, float) and 0 <= probability <= 1 and math.isfinite(probability),
              role + ': probability must be finite JSON number in[0,1], not Boolean')
        values[animal_id] = float(probability)
    _need(set(values) == set(expected), role + ': incomplete animal set')
    return values


def _metrics(animals, probabilities):
    tp = tn = fp = fn = 0; errors = []; positive = []; negative = []
    for animal in animals:
        p = probabilities[animal['animal_id']]; y = animal['label']; predicted = int(p >= .5)
        tp += int(y == 1 and predicted == 1); tn += int(y == 0 and predicted == 0)
        fp += int(y == 0 and predicted == 1); fn += int(y == 1 and predicted == 0)
        errors.append((p-y)**2)
        (positive if y == 1 else negative).append(p)
    # Pairwise form is exactly equivalent to average tied ranks; finite104 is
    # small. Equal scores receive half credit, with no arbitrary tie jitter.
    wins = ties = 0
    for p in positive:
        for n in negative:
            wins += int(p > n); ties += int(p == n)
    pairs = len(positive) * len(negative)
    return {'balanced_accuracy': .5 * (tp/50 + tn/54),
        'recall_6n': tp/50, 'recall_repaired': tn/54,
        'confusion': {'true_positive': tp, 'false_negative': fn, 'true_negative': tn, 'false_positive': fp},
        'accuracy': (tp+tn)/104, 'brier': math.fsum(errors)/104,
        'roc_auc': (wins + .5*ties)/pairs,
        'auc_pairs': {'positive_negative_pairs': pairs, 'wins': wins, 'ties': ties},
        'probability_cutoff_6n': .5}


def score(manifest, prediction_rows, layout_prediction_rows=None):
    """Return complete pooled metrics, optionally a paired layout comparison.

    Raises ScoreError without any report for malformed manifest or either
    incomplete submission. Validating all supplied outputs precedes all metrics.
    Probabilities and fold IDs are JSON scalars; abstention/extra fields cannot
    remove or change an animal's denominator. Class1 is the released6N group.
    """
    try:
        checked = split_rules.validate_manifest(manifest)
    except (split_rules.SplitError, TypeError, ValueError, OverflowError) as exc:
        raise ScoreError('invalid trusted manifest: ' + str(exc)) from exc
    animals = checked['animals']
    predictions = _predictions(prediction_rows, animals, 'candidate')
    layout = None if layout_prediction_rows is None else _predictions(layout_prediction_rows, animals, 'layout')
    primary = _metrics(animals, predictions)
    report = {'schema': 'abr-background-complete-score/v1', 'status': 'complete_all104_predictions',
        'manifest_sha256': split_rules.digest(checked), 'animal_count': 104,
        'class_counts': {'0': 54, '1': 50}, 'primary_metric': 'balanced_accuracy',
        'metrics': primary, 'prediction_sha256': split_rules.digest([
            {'animal_id': a['animal_id'], 'outer_fold': a['outer_fold'], 'p_6n': predictions[a['animal_id']]}
            for a in animals]),
        'output_scope': 'private_evaluator_report',
        'runtime_isolation_or_commitment_proved': False,
        'scientific_qualification': False, 'benchmark_count_delta': 0}
    if layout is not None:
        reference = _metrics(animals, layout)
        paired = {'both_correct': 0, 'candidate_only_correct': 0, 'layout_only_correct': 0, 'both_wrong': 0}
        differences = []
        for a in animals:
            animal_id = a['animal_id']; y = a['label']
            good = int(predictions[animal_id] >= .5) == y
            base_good = int(layout[animal_id] >= .5) == y
            key = ('both_correct' if base_good else 'candidate_only_correct') if good else (
                'layout_only_correct' if base_good else 'both_wrong')
            paired[key] += 1
            differences.append({'animal_id': animal_id,
                'correctness_difference': int(good)-int(base_good),
                'balanced_accuracy_contribution': (int(good)-int(base_good)) * .5 / (50 if y else 54)})
        report['layout_comparison'] = {'layout_metrics': reference, 'paired_correctness_counts': paired,
            'delta_balanced_accuracy': primary['balanced_accuracy']-reference['balanced_accuracy'],
            'per_animal_differences': differences,
            'layout_prediction_sha256': split_rules.digest([
                {'animal_id': a['animal_id'], 'outer_fold': a['outer_fold'], 'p_6n': layout[a['animal_id']]}
                for a in animals]),
            'interpretation': 'paired fixed-cohort descriptive difference; no causal or population inference'}
    return report


def _json_object(pairs):
    result = {}
    for key, value in pairs:
        _need(key not in result, 'duplicate JSON object key')
        result[key] = value
    return result


def _json_float(value):
    number = float(value)
    _need(math.isfinite(number), 'nonfinite JSON number')
    return number


def _json_constant(value):
    raise ScoreError('nonfinite JSON constant')


def load_private_json(filename, cap):
    """Bounded ordinary-file input for the trusted local CLI, not authentication.

    No manifest is selected implicitly. A runner must provide its precommitted
    evaluator-private path and enforce the external ownership/isolation policy.
    """
    path = Path(filename)
    _need(path.is_absolute() and '..' not in path.parts and
          not any(p.is_symlink() for p in (path, *path.parents)), 'ordinary absolute private JSON path')
    fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
    before = path.lstat()
    _need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= cap,
          'bounded ordinary single-link JSON input')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        opened = os.fstat(fd)
        _need(all(getattr(opened, k) == getattr(before, k) for k in fields), 'JSON input replaced before open')
        raw = bytearray()
        while len(raw) < before.st_size:
            chunk = os.read(fd, min(65536, before.st_size-len(raw)))
            _need(bool(chunk), 'JSON input premature EOF'); raw.extend(chunk)
        _need(not os.read(fd, 1), 'JSON input suffix')
        ended = os.fstat(fd); current = path.lstat()
        _need(all(getattr(before, k) == getattr(ended, k) == getattr(current, k) for k in fields)
              and not any(p.is_symlink() for p in (path, *path.parents)), 'JSON input changed')
    finally:
        os.close(fd)
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=_json_object,
                          parse_float=_json_float, parse_constant=_json_constant)
    except (UnicodeDecodeError, ValueError, RecursionError, OverflowError) as exc:
        raise ScoreError('invalid finite JSON input: ' + type(exc).__name__) from exc


def main(argv=None):
    import argparse
    import sys
    parser = argparse.ArgumentParser(description='Private complete104-animal ABR scorer; external runner isolation required.')
    parser.add_argument('--manifest', required=True, help='absolute precommitted private manifest path')
    parser.add_argument('--predictions', required=True, help='absolute complete candidate prediction JSON path')
    parser.add_argument('--layout-predictions', help='absolute complete paired layout-only prediction JSON path')
    args = parser.parse_args(argv)
    try:
        manifest = load_private_json(args.manifest, 1024*1024)
        predictions = load_private_json(args.predictions, 256*1024)
        layout = None if args.layout_predictions is None else load_private_json(args.layout_predictions, 256*1024)
        report = score(manifest, predictions, layout)
    except (ScoreError, OSError, ValueError, TypeError) as exc:
        print('Score refused: ' + str(exc), file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
