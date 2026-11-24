#!/usr/bin/env python3
"""Private operator-only complete released-output rescore; no model inference.

This route deliberately does not instantiate the four-arm candidate contract.
Source calculate_metric is imported unchanged, with its positional traversal
constructed by the maintained source_alignment helper. Native-index identity
is checked without inventing a join to actual NSD/COCO stimuli.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import sys
import stat
import types

SUBJECTS = ('S1', 'S2', 'S5', 'S7')
GROUP_COUNTS = {'All': 2419, 'Salient': 1343, 'Salient Creatures': 700,
                'Salient Objects': 643, 'Inconspicuous': 1076}
PUBLISHED = {'S1': 18.93, 'S2': 18.27, 'S5': 18.19, 'S7': 16.74}
THRESHOLDS = (0.3, 0.5, 0.7)
MAX_FILE_BYTES = 2 * 1024**2


def require(ok, message):
    if not ok:
        raise ValueError(message)


def pairs(rows):
    out = {}
    for key, value in rows:
        require(key not in out, 'duplicate JSON key')
        out[key] = value
    return out


def finite(value):
    raise ValueError('nonfinite JSON constant')


def pinned_bytes(pin):
    require(isinstance(pin, dict) and set(pin) == {'path', 'bytes', 'sha256'}, 'exact file pin required')
    require(type(pin['bytes']) is int and 0 <= pin['bytes'] <= MAX_FILE_BYTES, 'file byte bound')
    path = Path(pin['path'])
    require(path.is_absolute() and path.resolve(strict=True) == path, 'absolute resolved input path required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode), 'ordinary non-symlink input required')
        body = stream.read(pin['bytes'] + 1)
        after = os.fstat(stream.fileno())
    final = path.lstat()
    identity = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    require(identity(before) == identity(after) == identity(final), 'input changed while reading')
    require(len(body) == pin['bytes'] and hashlib.sha256(body).hexdigest() == pin['sha256'], 'input pin mismatch')
    return body


def pinned_json(pin):
    return json.loads(pinned_bytes(pin), object_pairs_hook=pairs, parse_constant=finite)


def load_module(name, pin):
    body = pinned_bytes(pin)
    module = types.ModuleType(name)
    module.__file__ = pin['path']
    sys.modules[name] = module
    exec(compile(body, pin['path'], 'exec'), module.__dict__)
    return module


def validate_annotation(annotations, g, *, paper=True):
    require(isinstance(annotations, dict) and bool(annotations), 'annotation object required')
    require(set(annotations) == {str(i) for i in range(len(annotations))}, 'contiguous native index membership required')
    targets, boxes_count = {}, 0
    for image in sorted(annotations, key=int):
        values = annotations[image]
        require(isinstance(values, dict), 'annotation category object required')
        for category, boxes in values.items():
            require(category in g.GROUPS['All'] and isinstance(boxes, list) and bool(boxes), 'annotation category/box representation rejected')
            checked = [g.box(box, reference=True) for box in boxes]
            targets[(image, category)] = checked[0]
            boxes_count += len(boxes)
    counts = {name: sum(category in categories for _, category in targets)
              for name, categories in g.GROUPS.items()}
    if paper:
        require(len(annotations) == 982 and boxes_count == 5829 and counts == GROUP_COUNTS,
                'complete original annotation population differs')
    require(bool(targets), 'empty annotation queries')
    return targets, {'images': len(annotations), 'boxes': boxes_count,
                     'queries': len(targets), 'group_counts': counts,
                     'native_index_join_only': True, 'NSD_COCO_stimulus_join_authenticated': False}


def validate_response_membership(responses, annotations):
    require(isinstance(responses, dict) and set(responses) <= set(annotations), 'unknown response image membership')
    for image, values in responses.items():
        require(isinstance(values, dict) and set(values) <= set(annotations[image]),
                'unknown response category membership')
    # Missing image/category answers remain in the fixed keyed denominator.
    # Original source traversal is kept separate, without padding or repairs.


def source_lists(annotations, responses, categories, alignment):
    # Exact source CLI assertion: bbox_gt and bbox_pd have one list per image.
    # It does not assert equality of flattened category-list lengths.
    require(len(annotations) == len(responses), 'source image-list length assertion failed')
    expected = alignment.traversal(annotations, categories)
    actual = alignment.traversal(responses, categories)
    targets = [annotations[image][category][0] for image, category in expected]
    predictions = [None if len(responses[image][category]) == 0 else responses[image][category][0][0]
                   for image, category in actual]
    return predictions, targets


def safe_result(result):
    require(isinstance(result, dict) and set(result) == {'accuracy', 'iou', 'target_failed', 'failed'},
            'author metric schema differs')
    require(all(type(result[k]) in (int, float) and math.isfinite(result[k]) for k in result),
            'author metric nonfinite')
    return result


def rescore(manifest, *, source_only=False):
    require(manifest['schema'] == 'umbrae-released-reference-inputs/v1', 'wrong manifest schema')
    require(set(manifest['responses']) == set(SUBJECTS), 'exact four subjects required')
    g = load_module('umbrae_complete_grounding', manifest['sources']['grounding'])
    alignment = load_module('umbrae_complete_alignment', manifest['sources']['source_alignment'])
    annotations = pinned_json(manifest['annotation'])
    groups = alignment.validate_categories(pinned_json(manifest['category_groups']))
    targets, population = validate_annotation(annotations, g)
    responses = {s: pinned_json(manifest['responses'][s]) for s in SUBJECTS}
    for response in responses.values():
        validate_response_membership(response, annotations)
    audits = {s: alignment.audit_subject(annotations, responses[s], groups) for s in SUBJECTS}
    result = {'schema': 'umbrae-complete-released-reference-rescore/v1', 'population': population,
              'source_traversal': audits, 'subject_order': list(SUBJECTS),
              'subjects': list(SUBJECTS), 'hash_seed': os.environ.get('PYTHONHASHSEED'),
              'expected_scalar_metric_cells': 80, 'query_count_per_subject': population['queries'],
              'group_query_counts': population['group_counts'],
              'runtime': {'python': platform.python_version(), 'hash_seed_environment': os.environ.get('PYTHONHASHSEED'),
                          'ignore_environment': bool(sys.flags.ignore_environment),
                          'hash_randomization': bool(sys.flags.hash_randomization)},
              'input_pins': manifest, 'native_inference_runs': 0, 'candidate_streams': 0,
              'scientific_scope': 'Released author-output scoring qualification only; no independent fMRI reproduction, improvement, source-producing lineage or benchmark readiness.'}
    result['mode'] = 'source_only' if source_only else 'source_and_keyed'
    author = load_module('umbrae_unchanged_author_evaluator', manifest['sources']['author_evaluator'])
    require(str(author.torch.get_default_dtype()) == 'torch.float32', 'original default float32 required')
    require(str(author.torch.get_default_device()) == 'cpu', 'CPU default device required')
    author.torch.set_num_threads(1)
    author.torch.set_num_interop_threads(1)
    result['runtime'].update(torch=author.torch.__version__, torch_threads=author.torch.get_num_threads(),
                             default_dtype=str(author.torch.get_default_dtype()),
                             torch_interop_threads=author.torch.get_num_interop_threads(), default_device=str(author.torch.get_default_device()))
    result['author_source'] = {}
    if not source_only:
        result['keyed_float64'], result['diagnostics'] = {}, {}
    complete_cells = 0
    for subject in SUBJECTS:
        response = responses[subject]
        result['author_source'][subject] = {}
        if not source_only:
            rows = g.score_subject(targets, set(annotations), response)
            result['keyed_float64'][subject] = g.summarize(rows)
            result['diagnostics'][subject] = {}
        for source_name, local_name in alignment.GROUP_NAMES.items():
            group_result = {}
            try:
                preds, expected = source_lists(annotations, response, groups[source_name], alignment)
                for threshold in THRESHOLDS:
                    group_result[str(threshold)] = safe_result(author.calculate_metric(preds, expected, threshold))
                require(len({group_result[str(t)]['iou'] for t in THRESHOLDS}) == 1,
                        'mean IoU changed between threshold calls')
                complete_cells += 4
                result['author_source'][subject][local_name] = {'status': 'scored', 'query_count': len(expected),
                     'accuracy': {str(t): group_result[str(t)]['accuracy'] for t in THRESHOLDS},
                     'mean_iou': group_result['0.5']['iou'],
                     'failed': group_result['0.5']['failed'], 'target_failed': group_result['0.5']['target_failed']}
            except (ValueError, TypeError, IndexError, KeyError, RuntimeError, ZeroDivisionError) as exc:
                result['author_source'][subject][local_name] = {'status': 'source_rejected',
                     'exception_type': type(exc).__name__, 'completed_threshold_calls': len(group_result)}
            if source_only:
                continue
            chosen = [row for row in rows if row['category'] in g.GROUPS[local_name]]
            # Native first-box float32 check uses identical source box_iou and
            # scale, but aligns identity explicitly to isolate precision from
            # positional pairing. Invalid first boxes remain zero as in g.
            pred_boxes = []
            target_boxes = []
            for row in chosen:
                image, category = row['image_id'], row['category']
                value = response.get(image, {}).get(category)
                predicted, status = g._prediction(value)
                pred_boxes.append([0., 0., 0., 0.] if predicted is None else list(predicted))
                target_boxes.append(list(targets[(image, category)]))
            with author.torch.no_grad():
                a, b = author.torch.tensor(pred_boxes), author.torch.tensor(target_boxes)
                require(a.device.type == b.device.type == 'cpu' and a.dtype == b.dtype == author.torch.float32,
                        'keyed diagnostic CPU float32 tensors required')
                diagonal = author.box_iou(a * 1000, b * 1000).diagonal()
                require(bool(author.torch.isfinite(diagonal).all()), 'keyed float32 nonfinite IoU')
                values32 = diagonal.tolist()
                values64 = [row['iou'] for row in chosen]
                result['diagnostics'][subject][local_name] = {
                    'source_positional_pairing_compatible': audits[subject]['groups'][local_name]['source_pairing_compatible_in_this_process'],
                    'keyed_float32_mean_iou': diagonal.mean().item(),
                    'keyed_float32_accuracy': {str(t): (diagonal > t).sum().item() / len(chosen) for t in THRESHOLDS},
                    'max_abs_iou_float32_minus_float64': max(abs(a - b) for a, b in zip(values32, values64)),
                    'threshold_decision_disagreements_float32_vs_float64': {
                        str(t): sum(bool(a) != (b > t) for a, b in zip((diagonal > t).tolist(), values64)) for t in THRESHOLDS},
                    'keyed_prediction_status_counts': dict(Counter(row['prediction_status'] for row in chosen))}
    result['scored_cells'] = complete_cells
    result['status'] = 'complete_source_panel_scored' if complete_cells == 80 else 'complete_inputs_source_scoring_rejections'
    result['published_v2_all_accuracy_percent'] = PUBLISHED
    result['source_all_accuracy_percent'] = {s: None if result['author_source'][s]['All']['status'] != 'scored'
          else 100 * result['author_source'][s]['All']['accuracy']['0.5'] for s in SUBJECTS}
    result['source_minus_published_percentage_points'] = {s: None if result['source_all_accuracy_percent'][s] is None
          else result['source_all_accuracy_percent'][s] - PUBLISHED[s] for s in SUBJECTS}
    result['paper_table_match_is_not_inference_attestation'] = True
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--manifest-bytes', type=int, required=True)
    p.add_argument('--manifest-sha256', required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--source-only', action='store_true')
    args = p.parse_args()
    manifest = pinned_json({'path': str(args.manifest), 'bytes': args.manifest_bytes, 'sha256': args.manifest_sha256})
    result = rescore(manifest, source_only=args.source_only)
    body = (json.dumps(result, indent=2, allow_nan=False) + '\n').encode()
    require(len(body) <= 1024**2, 'aggregate output exceeded 1 MiB')
    with args.output.open('xb') as stream:
        stream.write(body)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, TypeError, KeyError, IndexError, RuntimeError, OSError, UnicodeError, RecursionError, ZeroDivisionError) as exc:
        # Keep protected body contents out of logs and the operator context.
        print('rescore_rejected: ' + type(exc).__name__, file=sys.stderr)
        raise SystemExit(2)
