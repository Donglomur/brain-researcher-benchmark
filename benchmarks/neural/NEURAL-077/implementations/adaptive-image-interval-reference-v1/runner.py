"""Operator-only full6400 adaptive image reference collection and target-last seam.

No observer capture, raw packet, target path, subset, model/provider or sandbox.
Caller supplies an already captured, committed complete observation tree.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
import stat
import time
from pathlib import Path
import signal
import sys
import types

HERE = Path(__file__).resolve().parent
PREFIX = 'benchmarks/neural/NEURAL-077/implementations/'
METHOD = 'erp-adaptive-image-interval-reference-v1'
EXTERNAL = {'observer': PREFIX + 'adaptive-gain-observation-v1/observation.py',
            'endpoint': PREFIX + 'full32-paired-benchmark-v1/evaluator.py',
            'ordering': PREFIX + 'full32-image-uncertainty-v1/adapter.py'}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def load(name, path, body):
    module = types.ModuleType(name)
    module.__file__ = str(path)
    exec(compile(body, str(path), 'exec'), module.__dict__)
    return module


class SourceMeter:
    def __init__(self, read_limit, seconds):
        need(type(read_limit) is int and read_limit > 0 and type(seconds) is int and
             0 < seconds <= 86400, 'Explicit bounded source-read/deadline envelope')
        self.read_limit, self.read = read_limit, 0
        self.deadline = time.monotonic() + seconds

    def input(self, amount):
        self.read += amount
        need(self.read <= self.read_limit and time.monotonic() < self.deadline,
             'Source loading read cap or deadline')


def source_read(path, cap, meter):
    need(path.is_absolute() and all(not p.is_symlink() for p in (path, *path.parents)), 'Ordinary source path')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap,
             'Bounded single-link source')
        meter.input(before.st_size + 1)
        body = stream.read(before.st_size + 1)
        after = os.fstat(stream.fileno())
    identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
    need(identity(before) == identity(after) == identity(path.lstat()) and len(body) == before.st_size,
         'Source changed during read')
    return body


def dependencies(root, meter=None):
    """Authenticate the complete reused closure before executing its source."""
    root = Path(root).absolute()
    meter = meter or SourceMeter(4 * 1024**2, 30)
    manifest_path = HERE / 'SOURCE_BINDINGS.json'
    binding_body = source_read(manifest_path, 65536, meter)
    bindings = json.loads(binding_body)
    own = {'reference.py', 'runner.py'}
    need(set(bindings) == {'schema', 'own', 'external'} and
         bindings['schema'] == METHOD + '-sources' and set(bindings['own']) == own and
         set(bindings['external']) == set(EXTERNAL.values()) |
         {PREFIX + 'adaptive-gain-observation-v1/SOURCE_BINDINGS.json'}, 'Exact source closure')
    sources = {}
    for name, descriptor in {**{str(HERE / p): v for p, v in bindings['own'].items()},
                             **{str(root / p): v for p, v in bindings['external'].items()}}.items():
        path = Path(name)
        body = source_read(path, 131072, meter)
        need(pin(body) == descriptor, 'Source bytes differ')
        sources[str(path)] = body
    observer = load('adaptive_reference_observer', root / EXTERNAL['observer'],
                    sources[str(root / EXTERNAL['observer'])])
    # Its loader authenticates viewer/raster/codec/consumer/actions before use.
    modules = observer.dependencies(root, meter)
    modules.update(observer=observer,
        reference=load('adaptive_reference_method', HERE / 'reference.py', sources[str(HERE / 'reference.py')]),
        endpoint=load('adaptive_reference_endpoint', root / EXTERNAL['endpoint'], sources[str(root / EXTERNAL['endpoint'])]),
        ordering=load('adaptive_reference_ordering', root / EXTERNAL['ordering'], sources[str(root / EXTERNAL['ordering'])]),
        reference_binding=pin(binding_body))
    return modules


def capture_inventory(capture, expected, modules, budget):
    a = modules['observer']
    capture = a.ordinary(capture)
    value = a.decode(a.read(capture / 'COMPLETE.json', 4 * 1024**2, expected, budget))
    a.validate_inventory(value)
    intent = a.decode(a.read(capture / 'INTENT.json', 65536, value['intent'], budget))
    need(intent == {'schema': 'erp-adaptive-observation-intent-v1', 'policy': a.POLICY,
                    'source_bindings': modules['binding'], 'public_manifest': a.MANIFEST}, 'Frozen original observation')
    names = {'COMPLETE.json', 'INTENT.json'} | {f'demo-{i}' for i in range(4)} | {f'query-{i:04d}' for i in range(a.COUNT)}
    need(set(p.name for p in capture.iterdir()) == names, 'Complete capture inventory only')
    return value


def projected_features(directory, row, demonstration, modules, budget):
    a = modules['observer']
    projection = a.participant_projection(directory, row['record'], row['trial_id'], demonstration, modules, budget)
    selected = projection['attempts'][projection['selected_index']]
    descriptor = {k: selected['image'][k] for k in ('bytes', 'sha256')}
    image = a.read(directory / selected['image']['file'], 4 * 1024**2, descriptor, budget)
    # All features originate here: selected audited pixels and allowed gain only.
    features = modules['reference'].extract(modules['codec'].scanlines(image), projection['selected_gain'])
    provenance = {'record': row['record'], 'projection': a.pin(a.encode(projection)),
                  'trial_id': projection['trial_id'], 'selected_gain': projection['selected_gain'],
                  'selected_index': projection['selected_index'], 'outcome': projection['outcome'],
                  'attempted_images': len(projection['attempts']),
                  'attempts': projection['attempts']}
    return features, provenance


def response(identifier, features, model, provenance, modules):
    probability, quality = modules['reference'].predict(features, model)
    return {'trial_id': identifier, 'target_probability': probability, 'quality': quality,
            'observation': provenance}


def collect(capture, capture_pin, output, modules, budget):
    a, method = modules['observer'], modules['reference']
    capture, output = a.ordinary(capture), a.ordinary(output)
    need(not output.exists() and not output.is_relative_to(capture) and
         not capture.is_relative_to(output), 'Fresh disjoint reference output')
    inventory = capture_inventory(capture, capture_pin, modules, budget)
    output.mkdir(mode=0o700)
    rows, predictions = [], []
    intent = {'schema': METHOD + '-intent', 'config': method.CONFIG,
              'source_bindings': modules['reference_binding'], 'observation': capture_pin,
              'query_ids': [r['trial_id'] for r in inventory['queries']],
              'demonstrations': inventory['demos']}
    intent_pin = a.write(output / 'INTENT.json', a.encode(intent), budget)
    try:
        pairs = [projected_features(capture / f'demo-{i}', row, i, modules, budget)
                 for i, row in enumerate(inventory['demos'])]
        model = method.fit([f for f, _ in pairs], [p for _, p in pairs])
        method.validate_model(model)
        # Immutable persisted model and source/method/provenance BEFORE any query.
        model_pin = a.write(output / 'MODEL.json', a.encode(model), budget)
        for row in inventory['queries']:
            i = row['ordinal']
            features, provenance = projected_features(capture / f'query-{i:04d}', row, None, modules, budget)
            result = response(row['trial_id'], features, model, provenance, modules)
            pred = {'trial_id': result['trial_id'], 'target_probability': result['target_probability']}
            # Existing schema admission checks every first response immediately.
            modules['endpoint'].parse_prediction_rows(a.encode(pred), [row['trial_id']])
            committed = a.write(output / f'RESPONSE-{i:04d}.json', a.encode(result), budget)
            rows.append({'ordinal': i, 'trial_id': row['trial_id'], 'response': committed})
            predictions.append(a.encode(pred))
        body = b''.join(predictions)
        modules['endpoint'].parse_prediction_rows(body, intent['query_ids'])
        prediction_pin = a.write(output / 'predictions.jsonl', body, budget)
        receipt = {'schema': METHOD + '-complete', 'status': 'complete_unscored_reference',
                   'condition': a.CONDITION, 'method': METHOD, 'intent': intent_pin,
                   'model': model_pin, 'predictions': prediction_pin, 'rows': rows,
                   'private_target_reads': 0, 'scoring_performed': False,
                   'scientific_qualification': False, 'isolation_qualified': False}
        return a.write(output / 'COMPLETE.json', a.encode(receipt), budget)
    except BaseException as exc:
        a.write(output / 'FAILED.json', a.encode({'status': 'incomplete_reference', 'method': METHOD,
            'completed_queries': len(rows), 'uncompleted_queries': a.COUNT - len(rows),
            'first_outputs_retained': True, 'automatic_retry': False,
            'error_type': type(exc).__name__, 'message': str(exc)[:512]}), budget, failure=True)
        raise


def admit(output, expected, modules, budget):
    """Admit ALL6400 frozen first outputs before a target loader can run.

    Expected COMPLETE pin is supplied by the trusted operator. Pins authenticate
    custody, not the truth of an adversarial producer or participant isolation.
    """
    a, method = modules['observer'], modules['reference']
    output = a.ordinary(output)
    receipt = a.decode(a.read(output / 'COMPLETE.json', 4 * 1024**2, expected, budget))
    need(type(receipt) is dict and set(receipt) == {'schema', 'status', 'condition', 'method', 'intent',
         'model', 'predictions', 'rows', 'private_target_reads', 'scoring_performed',
         'scientific_qualification', 'isolation_qualified'} and
         receipt['schema'] == METHOD + '-complete' and receipt['status'] == 'complete_unscored_reference' and
         receipt['condition'] == a.CONDITION and receipt['method'] == METHOD and
         type(receipt['private_target_reads']) is int and receipt['private_target_reads'] == 0 and
         all(receipt[k] is False for k in ('scoring_performed', 'scientific_qualification', 'isolation_qualified')),
         'Complete separate adaptive condition required')
    intent = a.decode(a.read(output / 'INTENT.json', 2 * 1024**2, receipt['intent'], budget))
    need(type(intent) is dict and set(intent) == {'schema', 'config', 'source_bindings', 'observation', 'query_ids', 'demonstrations'} and
         intent['schema'] == METHOD + '-intent' and intent['config'] == method.CONFIG and
         intent['source_bindings'] == modules['reference_binding'], 'Frozen method/source intent')
    a.roster(tuple(intent['query_ids']))
    a.descriptor(intent['observation'], 4 * 1024**2)
    need(type(intent['demonstrations']) is list and len(intent['demonstrations']) == 4, 'Four demonstration commitments')
    model = a.decode(a.read(output / 'MODEL.json', 2 * 1024**2, receipt['model'], budget))
    method.validate_model(model)
    for i, provenance in enumerate(model['provenance']):
        row = intent['demonstrations'][i]
        validate_provenance(provenance, i, modules)
        need(model['demos'][i]['gain'] == provenance['selected_gain'], 'Demo feature gain provenance')
        need(set(row) == {'ordinal', 'trial_id', 'record'} and type(row['ordinal']) is int and row['ordinal'] == i and
             provenance['trial_id'] == row['trial_id'] and provenance['record'] == row['record'], 'Demo/model identity')
    need(type(receipt['rows']) is list and len(receipt['rows']) == a.COUNT, 'All6400 first outputs required')
    body = a.read(output / 'predictions.jsonl', 2 * 1024**2, receipt['predictions'], budget)
    predictions = modules['endpoint'].parse_prediction_rows(body, intent['query_ids'])
    names = {'INTENT.json', 'MODEL.json', 'COMPLETE.json', 'predictions.jsonl'}
    for i, row in enumerate(receipt['rows']):
        need(type(row) is dict and set(row) == {'ordinal', 'trial_id', 'response'} and
             type(row['ordinal']) is int and row['ordinal'] == i and row['trial_id'] == intent['query_ids'][i], 'Exact response order')
        name = f'RESPONSE-{i:04d}.json'; names.add(name)
        result = a.decode(a.read(output / name, 65536, row['response'], budget))
        validate_response(result, row['trial_id'], predictions[row['trial_id']], modules)
    need(set(p.name for p in output.iterdir()) == names, 'No omitted/extra/incomplete output')
    return predictions


def validate_response(result, identifier, probability, modules):
    need(type(result) is dict and set(result) == {'trial_id', 'target_probability', 'quality', 'observation'} and
         result['trial_id'] == identifier and result['target_probability'] == probability, 'First response binding')
    need(type(result['target_probability']) in (int, float) and math.isfinite(result['target_probability']) and
         0 <= result['target_probability'] <= 1, 'Finite nonboolean first probability')
    validate_provenance(result['observation'], None, modules)
    need(result['observation']['trial_id'] == identifier, 'Query provenance identity')
    validate_quality(result['quality'], probability)
    need(result['quality']['native_units_per_vertical_pixel'] == result['observation']['selected_gain'] / 30,
         'Query resolution must match observed gain')


def validate_provenance(value, demonstration, modules):
    a = modules['observer']
    need(type(value) is dict and set(value) == {'record', 'projection', 'trial_id', 'selected_gain',
         'selected_index', 'outcome', 'attempted_images', 'attempts'}, 'Exact projection provenance')
    a.descriptor(value['record'], 65536); a.descriptor(value['projection'], 131072)
    need(type(value['attempts']) is list and type(value['attempted_images']) is int and
         1 <= len(value['attempts']) == value['attempted_images'] <= 6 and
         type(value['selected_index']) is int and value['selected_index'] == len(value['attempts']) - 1 and
         type(value['selected_gain']) is int and value['selected_gain'] == a.GAINS[value['selected_index']],
         'Complete ordered gain prefix')
    state = modules['viewer'].initial_state()
    for i, attempt in enumerate(value['attempts']):
        action = a.action_at(i, demonstration)
        state = modules['viewer'].transition(state, action, 'four_demo')
        label = {} if demonstration is None else {'target': a.DEMO_LABELS[demonstration]}
        need(type(attempt) is dict and set(attempt) == {'action', 'state', 'image', 'display', 'warning_evidence', 'resolution'} and
             attempt['action'] == action and attempt['state'] == state and
             attempt['display'] == modules['viewer'].display_metadata(state, label) and
             attempt['resolution'] == a.resolution(a.GAINS[i]), 'Exact projected action/display/resolution')
        image = attempt['image']
        need(type(image) is dict and set(image) == {'file', 'bytes', 'sha256'} and image['file'] == f'FRAME-{i}.png',
             'Projected frame identity')
        a.descriptor({k: image[k] for k in ('bytes', 'sha256')}, 4 * 1024**2)
        evidence = attempt['warning_evidence']
        need(type(evidence) is dict and set(evidence) == {'schema', 'template_rgb', 'scanlines', 'channels', 'both_channels_unclipped'} and
             evidence['schema'] == 'erp-rendered-warning-evidence-v1' and type(evidence['channels']) is list and
             len(evidence['channels']) == 2, 'Exact projected warning evidence')
        a.descriptor(evidence['template_rgb'], 65536); a.descriptor(evidence['scanlines'], 4 * 1024**2)
        for c, (name, top) in zip(evidence['channels'], (('Cz', 185), ('Pz', 445))):
            need(type(c) is dict and set(c) == {'channel', 'roi_xyxy', 'pixels', 'clipped'} and c['channel'] == name and
                 c['roi_xyxy'] == [1030, top, 1030 + len(a.WARNING) * 6, top + 7] and type(c['clipped']) is bool,
                 'Exact channel warning provenance')
            a.descriptor(c['pixels'], 65536)
        unclipped = all(not c['clipped'] for c in evidence['channels'])
        need(evidence['both_channels_unclipped'] is unclipped and
             (not unclipped or i == len(value['attempts']) - 1), 'First both-channel-unclipped policy')
    need((unclipped or len(value['attempts']) == 6) and
         value['outcome'] == ('unclipped' if unclipped else 'cap_clipped'), 'Retained cap-clipped outcome')
    projection = {k: value[k] for k in ('trial_id', 'attempts', 'selected_index', 'selected_gain', 'outcome')}
    projection.update(condition=a.CONDITION, demonstration=demonstration)
    need(a.pin(a.encode(projection)) == value['projection'], 'Complete attempted projection pin')


def validate_quality(q, probability):
    need(type(q) is dict and set(q) == {'shared_support_fraction', 'shared_weights', 'baseline_coverage',
         'no_shared_support', 'interval_distances', 'query_feature_widths_native',
         'native_units_per_vertical_pixel', 'in_range_sample_placement_rounding_bound_native',
         'raw_sample_recovery', 'calibrated_probability'}, 'Exact quality diagnostics')
    finite = lambda v: type(v) in (int, float) and math.isfinite(v)
    for field, length in (('shared_weights', 30), ('baseline_coverage', 2)):
        need(type(q[field]) is list and len(q[field]) == length and
             all(finite(v) and 0 <= v <= 1 for v in q[field]), 'Complete finite support')
    need(q['shared_support_fraction'] == sum(q['shared_weights']) / 30 and
         q['no_shared_support'] is (sum(q['shared_weights']) == 0) and
         (not q['no_shared_support'] or probability == .5), 'Zero-support policy')
    need(type(q['interval_distances']) is list and len(q['interval_distances']) == 2 and
         all(finite(v) and v >= 0 for v in q['interval_distances']), 'Finite distances')
    need(type(q['query_feature_widths_native']) is list and len(q['query_feature_widths_native']) == 30 and
         all((w == 0 and v is None) or (w > 0 and finite(v) and v >= 0)
             for w, v in zip(q['shared_weights'], q['query_feature_widths_native'])), 'Explicit missing widths')
    need(q['native_units_per_vertical_pixel'] in [g / 30 for g in (20, 50, 100, 200, 500, 1000)] and
         q['in_range_sample_placement_rounding_bound_native'] == q['native_units_per_vertical_pixel'] / 2 and
         q['raw_sample_recovery'] is False and q['calibrated_probability'] is False, 'Honest resolution diagnostics')


def evaluate_complete(output, expected, modules, budget, private_loader):
    """Existing full32 join and metric endpoint, with public admission first.

    private_loader is an operator callback, invoked only after complete admission.
    It must use existing evaluator.load_private_people and the authorized original
    private commitment. No paired/native/model interpretation is implied.
    """
    return modules['ordering'].ordered_metrics(lambda: admit(output, expected, modules, budget),
                                               private_loader, modules['endpoint'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository-root', required=True)
    parser.add_argument('--capture', required=True)
    parser.add_argument('--capture-bytes', type=int, required=True)
    parser.add_argument('--capture-sha256', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--read-bytes', type=int, required=True)
    parser.add_argument('--write-bytes', type=int, required=True)
    parser.add_argument('--work-seconds', type=int, required=True)
    args = parser.parse_args(argv)
    meter = SourceMeter(args.read_bytes, args.work_seconds)
    def alarm(*_):
        raise TimeoutError('Whole reference deadline')
    old = signal.signal(signal.SIGALRM, alarm)
    signal.setitimer(signal.ITIMER_REAL, args.work_seconds + 5)
    try:
        modules = dependencies(args.repository_root, meter)
        a = modules['observer']; budget = a.Budget(args.read_bytes, args.write_bytes, args.work_seconds)
        budget.read, budget.deadline = meter.read, meter.deadline
        expected = {'bytes': args.capture_bytes, 'sha256': args.capture_sha256}
        a.descriptor(expected, 4 * 1024**2)
        receipt = collect(args.capture, expected, args.output, modules, budget)
        print(json.dumps({'status': 'complete_unscored_reference', 'receipt': receipt,
                          'named_read_bytes': budget.read, 'artifact_bytes': budget.written}))
        return 0
    except (Exception, KeyboardInterrupt) as error:
        print(json.dumps({'status': 'refused_or_incomplete', 'error': str(error)[:512]}), file=sys.stderr)
        return 2
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


if __name__ == '__main__':
    raise SystemExit(main())
