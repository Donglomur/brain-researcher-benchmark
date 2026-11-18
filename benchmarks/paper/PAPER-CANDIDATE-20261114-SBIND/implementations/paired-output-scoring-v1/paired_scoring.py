"""Owner-side paired scoring of complete prospective WFCI1 predictions.

No candidate code, fitting, source selection, mask selection or paper-win rule.
The caller independently freezes binding bytes; hashes do not prove provenance.
Streams and Python modules are trusted owner objects, not an isolation boundary.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json

import endpoint_kernels as kernels
import trial_inference as inference

TASK = inference.trials.TASK
META_LIMIT = 2 * 1024 * 1024


class ScoringError(ValueError):
    """Operand does not match the owner's complete paired evaluation contract."""


def _require(ok, message):
    if not ok:
        raise ScoringError(message)


def _hash(value):
    inference._hash(value)
    return value


def _integer(value, low=0):
    return inference._integer(value, low)


def _keys(value, keys):
    inference._keys(value, keys)


def _same(value, expected):
    # Reject Python's otherwise equal bool/int and int/float identities.
    if type(value) is not type(expected):
        return False
    if type(expected) is dict:
        return set(value) == set(expected) and all(_same(value[k], v) for k, v in expected.items())
    if type(expected) is list:
        return len(value) == len(expected) and all(_same(v, e) for v, e in zip(value, expected))
    return value == expected


def _expect(value, expected, name):
    _require(_same(value, expected), name + ' differs from frozen plan')


def _metadata(raw, digest):
    _hash(digest)
    _require(type(raw) is bytes and 0 < len(raw) <= META_LIMIT, 'bounded metadata bytes required')
    _require(hashlib.sha256(raw).hexdigest() == digest, 'metadata hash mismatch')
    return inference._decode(raw)


def _stream_receipt(value, records):
    _keys(value, ('bytes', 'sha256', 'records'))
    _integer(value['bytes'], 1)
    _hash(value['sha256'])
    _expect(value['records'], records, 'record count')


def _normalization(raw, binding, assay, fold):
    value = _metadata(raw, binding['normalization_receipt_sha256'])
    _keys(value, ('schema', 'task_id', 'assay_id', 'fold', 'normalization',
                  'normalization_sha256', 'participant_streams', 'owner_targets',
                  'complete_selected_fold_frames', 'historical_reproduction_qualified',
                  'runtime_isolation_qualified', 'durable_publication_qualified',
                  'whole_grid_execution_qualified'))
    expected = {'schema': 'sbind-owner-normalization-result-v1', 'task_id': TASK,
                'assay_id': 'WFCI1', 'fold': binding['fold'],
                'normalization_sha256': binding['normalization_sha256'],
                'historical_reproduction_qualified': False, 'runtime_isolation_qualified': False,
                'durable_publication_qualified': False, 'whole_grid_execution_qualified': False}
    _expect({k: value[k] for k in expected}, expected, 'normalization receipt')
    counts = {role: sum(s.length for s in getattr(fold, role))
              for role in ('train', 'validation', 'test')}
    _expect(value['complete_selected_fold_frames'], counts, 'complete fold frame counts')
    _keys(value['participant_streams'], counts)
    for role, count in counts.items():
        _stream_receipt(value['participant_streams'][role], count + 1)
    _stream_receipt(value['owner_targets'], counts['validation'] + counts['test'] + 1)
    stats = value['normalization']
    _keys(stats, ('policy', 'training_frames', 'neural_mean', 'neural_sd',
                  'behavior_mean', 'behavior_sd'))
    _expect(stats['policy'], inference.POLICY, 'normalization policy')
    _expect(stats['training_frames'], counts['train'], 'training frame count')
    for key, width in (('neural_mean', 16384), ('behavior_mean', len(assay.channels)),
                       ('behavior_sd', len(assay.channels))):
        for item in inference._sequence(stats[key], width):
            number = inference._number(item)
            if key.endswith('_sd'):
                _require(number > 0, 'normalization scales must be positive')
    _require(inference._number(stats['neural_sd']) > 0, 'neural scale must be positive')
    _require(hashlib.sha256(inference._encode(stats)).hexdigest() == binding['normalization_sha256'],
             'normalization statistics identity mismatch')
    return value


def _receipt(raw, digest, binding, source, spans):
    value = _metadata(raw, digest)
    _keys(value, ('schema', 'task_id', 'assay_id', 'fold', 'role', 'input_sha256', 'input_bytes',
                  'output_sha256', 'output_bytes', 'output_records', 'trials', 'frames',
                  'model_calls', 'reset_true_calls', 'historical_reproduction_qualified',
                  'runtime_isolation_qualified'))
    _hash(value['output_sha256'])
    _integer(value['output_bytes'], 1)
    frames = sum(s.length for s in spans)
    expected = {'schema': 'sbind-prospective-wfci1-inference-receipt-v1', 'task_id': TASK,
                'assay_id': 'WFCI1', 'fold': binding['fold'], 'role': binding['role'],
                'input_sha256': source['sha256'], 'input_bytes': source['bytes'],
                'output_sha256': value['output_sha256'], 'output_bytes': value['output_bytes'],
                'output_records': frames + 1, 'trials': len(spans), 'frames': frames,
                'model_calls': len(spans), 'reset_true_calls': len(spans),
                'historical_reproduction_qualified': False, 'runtime_isolation_qualified': False}
    _expect(value, expected, 'inference receipt')
    return value


def _identity(span, offset, role):
    return {'role': role, 'trial_id': span.trial_id,
            'source_index': span.source_start + offset, 'trial_offset': offset}


def _sample_id(identity, fold):
    return json.dumps(['WFCI1', fold, identity['role'], identity['trial_id'],
                       identity['source_index'], identity['trial_offset']],
                      ensure_ascii=True, separators=(',', ':'))


def _flatten(field):
    return tuple(x for row in inference._field(field)[0] for x in row)


def _start(stream, extent):
    stream.seek(0)
    _require(stream.tell() == 0, 'seekable binary owner stream required')
    return inference._Reader(stream, extent)


def _prediction(stream, receipt, binding, header, spans):
    reader = _start(stream, receipt['output_bytes'])
    expected = {'schema': 'sbind-prospective-wfci1-predictions-v1', 'task_id': TASK,
                'assay_id': 'WFCI1', 'fold': binding['fold'], 'role': binding['role'],
                'input_sha256': receipt['input_sha256'],
                'census_sha256': binding['census_sha256'], 'split_sha256': binding['split_sha256'],
                'normalization_sha256': binding['normalization_sha256'],
                'representations_sha256': binding['representations_sha256'],
                'behavior_channels': header['behavior_channels'], 'model_call_policy': inference.CALL_POLICY,
                'record': 'header', 'historical_reproduction_qualified': False}
    _expect(reader.line()[1], expected, 'prediction header')
    neural, behavior = [], []
    for span in spans:
        for offset in range(span.length):
            row = reader.line()[1]
            identity = _identity(span, offset, binding['role'])
            _keys(row, (*identity, 'record', 'neural', 'behavior'))
            _expect({k: row[k] for k in (*identity, 'record')},
                    dict(identity, record='prediction'), 'prediction support')
            sample = _sample_id(identity, binding['fold'])
            neural.append((sample, _flatten(row['neural'])))
            behavior.append((sample, tuple(inference._number(x) for x in
                                           inference._sequence(row['behavior'], 14))))
    reader.finish(receipt['output_sha256'])
    return neural, behavior


def _source(stream, receipt, header, spans):
    neural = []
    for reader, span, fields, _ in inference._walk(stream, receipt['bytes'], header, spans):
        for offset, field in enumerate(fields):
            sample = _sample_id(_identity(span, offset, header['role']), header['fold'])
            neural.append((sample, _flatten(field)))
    reader.finish(receipt['sha256'])
    return neural


def _targets(stream, receipt, header, fold):
    reader = _start(stream, receipt['bytes'])
    _expect(reader.line()[1], dict(header, role='owner-held-targets', includes_behavior=True),
            'owner targets header')
    behavior = []
    for role in ('validation', 'test'):
        for span in getattr(fold, role):
            for offset in range(span.length):
                row = reader.line()[1]
                identity = _identity(span, offset, role)
                _keys(row, (*identity, 'record', 'reset', 'behavior'))
                expected = dict(identity, record='target', reset=offset == 0)
                _expect({k: row[k] for k in expected}, expected, 'owner target support')
                values = tuple(inference._number(x) for x in inference._sequence(row['behavior'], 14))
                if role == header['role']:
                    behavior.append((_sample_id(identity, header['fold']), values))
    reader.finish(receipt['sha256'])
    return behavior


def score_pair(owner_binding_bytes, *, owner_binding_sha256, census_bytes, split_bytes,
               normalization_receipt_bytes, candidate_receipt_bytes, comparator_receipt_bytes,
               mask_bytes, source_stream, owner_targets_stream, candidate_stream, comparator_stream,
               max_total_stream_bytes, max_role_frames):
    """Return two unchanged endpoint vectors for the same complete held role.

    The owner precommits every digest and method label outside participant code.
    All prediction outputs are authenticated before private behavior is read.
    Both held target roles authenticate, but only the selected role is scored.
    Values are materialized: frame/serialized-byte ceilings bound inputs, not
    resident memory. A native memory envelope requires separate qualification.
    Failure returns no result; no partial result is published or score trusted.
    """
    binding = _metadata(owner_binding_bytes, owner_binding_sha256)
    pins = ('census_sha256', 'split_sha256', 'representations_sha256', 'normalization_sha256',
            'normalization_receipt_sha256', 'candidate_receipt_sha256',
            'comparator_receipt_sha256', 'mask_sha256')
    _keys(binding, ('schema', 'task_id', 'assay_id', 'fold', 'role',
                    'candidate_method_id', 'comparator_method_id', *pins))
    _expect(binding['schema'], 'sbind-owner-paired-evaluation-v1', 'binding schema')
    _expect(binding['task_id'], TASK, 'binding task')
    _expect(binding['assay_id'], 'WFCI1', 'binding assay')
    for pin in pins:
        _hash(binding[pin])
    for name in ('candidate_method_id', 'comparator_method_id'):
        _require(type(binding[name]) is str and 0 < len(binding[name]) <= 1024,
                 'bounded nonempty owner method identity required')
    _integer(max_total_stream_bytes, 1)
    _integer(max_role_frames, 1)
    # Pinned producer planning enforces complete census, ten folds and held role.
    header, spans = inference._plan(census_bytes, split_bytes,
        census_sha256=binding['census_sha256'], split_sha256=binding['split_sha256'],
        representations_sha256=binding['representations_sha256'],
        normalization_sha256=binding['normalization_sha256'], role=binding['role'],
        fold=binding['fold'], max_trial_frames=max_role_frames)
    frames = sum(s.length for s in spans)
    _require(frames <= max_role_frames, 'complete role exceeds owner frame envelope')
    protocol = inference.trials.compile_protocol(census_bytes, split_bytes,
        census_sha256=binding['census_sha256'], split_sha256=binding['split_sha256'])
    assay = protocol.assays[0]
    fold = assay.folds[binding['fold']]
    norm = _normalization(normalization_receipt_bytes, binding, assay, fold)
    source = norm['participant_streams'][binding['role']]
    targets = norm['owner_targets']
    mask = _metadata(mask_bytes, binding['mask_sha256'])
    _keys(mask, ('schema', 'task_id', 'assay_id', 'source_sha256', 'representation_sha256',
                 'pixel_indices'))
    expected = {'schema': 'sbind-owner-brain-pixel-selection-v1', 'task_id': TASK,
                'assay_id': 'WFCI1', 'source_sha256': assay.source_sha256,
                'representation_sha256': assay.representation_sha256}
    _expect({k: mask[k] for k in expected}, expected, 'owner mask source')
    pixels = mask['pixel_indices']
    _require(type(pixels) is list and bool(pixels) and
             all(type(p) is int and 0 <= p < 16384 for p in pixels) and
             len(set(pixels)) == len(pixels), 'explicit distinct brain pixel indices required')
    receipts = {name: _receipt(raw, binding[name + '_receipt_sha256'], binding, source, spans)
                for name, raw in (('candidate', candidate_receipt_bytes),
                                  ('comparator', comparator_receipt_bytes))}
    total = source['bytes'] + targets['bytes'] + sum(r['output_bytes'] for r in receipts.values())
    _require(total <= max_total_stream_bytes, 'complete stream inputs exceed owner byte envelope')
    # Parse once and retain authenticated operands; no post-authentication reread.
    predictions = {name: _prediction(stream, receipts[name], binding, header, spans)
                   for name, stream in (('candidate', candidate_stream), ('comparator', comparator_stream))}
    neural = _source(source_stream, source, header, spans)
    behavior = _targets(owner_targets_stream, targets, header, fold)
    support = tuple(_sample_id(_identity(span, offset, binding['role']), binding['fold'])
                    for span in spans for offset in range(span.length))
    scores = {}
    for name, (predicted_neural, predicted_behavior) in predictions.items():
        scores[name] = {'method_id': binding[name + '_method_id'],
            'receipt_sha256': binding[name + '_receipt_sha256'],
            'output_sha256': receipts[name]['output_sha256'],
            'behavior': asdict(kernels.wfci1_behavior_mse(support, behavior, predicted_behavior,
                                                       channel_ids=header['behavior_channels'])),
            'neural': asdict(kernels.neural_mse(support, neural, predicted_neural,
                                              brain_pixel_indices=pixels))}
    return {'schema': 'sbind-owner-paired-metrics-v1', 'task_id': TASK, 'assay_id': 'WFCI1',
            'fold': binding['fold'], 'role': binding['role'], 'frames': frames,
            'binding_sha256': owner_binding_sha256, 'census_sha256': binding['census_sha256'],
            'split_sha256': binding['split_sha256'],
            'representations_sha256': binding['representations_sha256'],
            'normalization_sha256': binding['normalization_sha256'],
            'normalization_receipt_sha256': binding['normalization_receipt_sha256'],
            'source_sha256': source['sha256'], 'owner_targets_sha256': targets['sha256'],
            'mask_sha256': binding['mask_sha256'], 'scores': scores,
            'historical_reproduction_qualified': False, 'comparator_competence_qualified': False,
            'runtime_isolation_qualified': False, 'authentic_execution_qualified': False,
            'paper_win_qualified': False}
