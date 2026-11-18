"""Operator-private full-plan to original MindBridge Table2 metadata join.

No archive parser, image reader, model, metric calculation or execution attestation.
The supplied plan/receipts are trusted operator inputs, not proof of real execution.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import types

TASK = 'PAPER-paper-method-033'
SUBJECTS = (1, 2, 5, 7)
BUDGETS = (500, 1500, 4000)
COUNTS = {'train': 8559, 'val': 300, 'test': 982}
FIELDS = ('jpg', 'nsdgeneral.npy', 'coco73k.npy')
METRICS = ('pixcorr', 'ssim', 'alexnet2', 'alexnet5', 'inception', 'clip', 'effnet_b', 'swav')
MODE_ARM = {'scratch': 'vanilla', 'reset': 'mindbridge'}
DEPENDENCY_MANIFEST_SHA = '34a291380bb982a3af8db9954982b46d0ebe618f024ef236467d4841e6ddac1e'
HEX = re.compile('[a-f0-9]{64}')
KEY = re.compile('sample[0-9]+')
GENERATION_FILES = ('INPUT_MANIFEST.json', 'COHORT.json', 'CODE_PROVENANCE.json',
                    'binding.py', 'prepare.py', 'protocol.py', 'provision.py',
                    'delivery_io.py', 'array_io.py', 'native_bridge.py', 'native_predict.py')


class CompositionError(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise CompositionError(message)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=True, allow_nan=False) + '\n').encode('ascii')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def exact(value, fields, name):
    need(type(value) is dict and set(value) == set(fields), name + ': exact fields')


def identities(values, count, name, sha=False):
    need(type(values) is list and len(values) == count and
         all(type(x) is str and x and (not sha or HEX.fullmatch(x)) for x in values),
         name + ': full identity count/type')
    need(len(set(values)) == count, name + ': duplicate identities')


def validate_preparation(plan, receipt, deps):
    """Check full metadata support before selecting a single target7 condition.

    This checks the structure and agreement of already sealed operator inputs.
    It does not authenticate an archive or replay prepare.index's array checks.
    """
    io = deps['io']
    rows = deps['provision'].designated_records(deps['manifest'])
    expected = {r['path']: {k: r[k] for k in ('bytes', 'sha256')} for r in rows}
    exact(receipt, ('source_files_verified', 'source_bytes',
                    'native_decoded_schema_verified', 'models_executed'), 'provision receipt')
    need(receipt['native_decoded_schema_verified'] is False and receipt['models_executed'] is False,
         'original provision receipt is metadata custody only')
    observed = receipt['source_files_verified']
    need(type(observed) is list and len(observed) == 88, 'all88 provision records required')
    got = {}
    for record in observed:
        exact(record, ('path', 'bytes', 'sha256'), 'source record')
        path = record['path']
        need(type(path) is str and path in expected and path not in got, 'unique designated source path')
        got[path] = {k: record[k] for k in ('bytes', 'sha256')}
        io.check_pin(got[path], expected[path]['bytes'])
    need(got == expected and type(receipt['source_bytes']) is int and
         receipt['source_bytes'] == sum(r['bytes'] for r in rows), 'complete exact source pins/extent')
    exact(plan, ('generation', 'cases', 'private_source_rows', 'selection', 'runtime_verified'), 'full plan')
    need(plan['generation'] == deps['generation'] and plan['runtime_verified'] is False,
         'current original generation; runtime remains unverified')
    need(plan['selection'] == 'first lexicographically sorted K training keys;300validation separate',
         'original train-only selection declaration')
    source = plan['private_source_rows']
    need(type(source) is dict and (set(source) == {str(s) for s in SUBJECTS} or
         set(source) == set(SUBJECTS)), 'all four complete subject inventories')
    need(all(type(s) is str for s in source) or all(type(s) is int for s in source),
         'canonical subject dictionary key types')
    source = {s: source[str(s)] if str(s) in source else source[s] for s in SUBJECTS}
    image_sets = {}
    for subject in SUBJECTS:
        exact(source[subject], COUNTS, 'subject split inventory')
        image_sets[subject] = {}
        for split, count in COUNTS.items():
            records = source[subject][split]
            need(type(records) is list and len(records) == count, 'complete source split support')
            keys, images = [], []
            for record in records:
                exact(record, ('key', 'image_id', 'files'), 'source sample')
                key, image = record['key'], record['image_id']
                need(type(key) is str and KEY.fullmatch(key), 'original sample key')
                need(type(image) is int and 0 <= image < 73000, 'original image identifier range')
                exact(record['files'], FIELDS, 'complete source sample modalities')
                for ext, descriptor in record['files'].items():
                    exact(descriptor, ('path', 'bytes', 'sha256'), 'source payload descriptor')
                    need(descriptor['path'] == f'webdataset_avg_split/{split}/subj{subject:02d}/{key}.{ext}',
                         'payload path must bind exact sample/subject/split')
                    io.check_pin({k: descriptor[k] for k in ('bytes', 'sha256')}, 10000000)
                keys.append(key); images.append(image)
            identities(keys, count, 'split sample keys')
            need(keys == sorted(keys) and len(set(images)) == count, 'ordered unique sample/image identities')
            image_sets[subject][split] = set(images)
        groups = image_sets[subject]
        need(not (groups['train'] & groups['val'] or groups['train'] & groups['test'] or
                  groups['val'] & groups['test']), 'within-subject image split overlap')
    common = image_sets[7]['test']
    need(all(image_sets[s]['test'] == common for s in SUBJECTS), 'same complete982 images across subjects')
    need(all(not common & image_sets[s][split] for s in SUBJECTS for split in ('train', 'val')),
         'test images cannot occur in any source/target training or validation')
    cases = plan['cases']
    expected_cases = deps['protocol'].cases()
    need(type(cases) is list and len(cases) == len(expected_cases) == 32, 'complete32-case indexed plan')
    by_case = {}
    base_fields = set(expected_cases[0])
    for case in cases:
        exact(case, base_fields | {'query_ids', 'train_keys', 'validation_keys'}, 'indexed case')
        cid = case['case_id']
        need(type(cid) is str and cid not in by_case, 'unique indexed case')
        by_case[cid] = case
    need(set(by_case) == {c['case_id'] for c in expected_cases}, 'no changed/missing/extra indexed cases')
    for expected_case in expected_cases:
        case = by_case[expected_case['case_id']]
        need(all(type(case[k]) is type(v) and case[k] == v for k, v in expected_case.items()),
             'source case population/mode/exposure/budget')
        # List element types matter: bool and float must not alias integer subjects.
        need(all(type(s) is int for s in case['source_subjects']), 'integer source subjects')
        records = source[case['subject']]
        need(case['train_keys'] == [r['key'] for r in records['train'][:case['budget']]] and
             case['validation_keys'] == [r['key'] for r in records['val']], 'full original case prefix and validation')
        identities(case['query_ids'], 982, 'opaque case query IDs', sha=True)
    # All private conditions have case-specific opaque IDs. A shared token cannot
    # silently join two conditions with different image ordering.
    all_queries = [q for c in cases for q in c['query_ids']]
    need(len(set(all_queries)) == len(all_queries), 'case-specific query identities')
    filenames = (f"{r['key']}.{ext}" for r in source[7]['train'] for ext in FIELDS)
    prefixes = deps['source_protocol'].calibration_memberships(filenames)
    need(all(list(prefixes[k]) == [r['key'] for r in source[7]['train'][:k]] for k in BUDGETS),
         'reused source calibration membership rule')
    return source, by_case, prefixes


def compose_panel(plan, receipt, bundle, deps, *, input_pins):
    """Join six complete frozen-descriptor conditions onto one full source gallery.

    Query records may arrive in any order; their opaque case IDs map through the
    complete original index order. No true target feature or pixel is opened.
    """
    source, cases, prefixes = validate_preparation(plan, receipt, deps)
    exact(input_pins, ('plan', 'receipt', 'bundle'), 'operator input pins')
    for pin in input_pins.values():
        deps['io'].check_pin(pin, 134217728)
    exact(bundle, ('source_kind', 'information_condition', 'skimage_version', 'feature_pipeline_sha256',
                   'image_prior_sha256', 'conditions'), 'condition descriptor bundle')
    need(bundle['information_condition'] in ('paper_data', 'paper_data_author_code'),
         'explicit paper access condition, separate from source method arm')
    conditions = bundle['conditions']
    need(type(conditions) is list and len(conditions) == 6, 'six target7 conditions required')
    by_condition = {}
    selected = [(f'adapt_{mode}_s07_k{k:04d}', arm, k)
                for k in BUDGETS for mode, arm in MODE_ARM.items()]
    for condition in conditions:
        exact(condition, ('case_id', 'freeze_receipt_sha256',
                          'generation_frozen_before_target_selection', 'images'), 'condition')
        cid = condition['case_id']
        need(type(cid) is str and cid not in by_condition, 'unique condition case')
        by_condition[cid] = condition
    need(set(by_condition) == {cid for cid, _, _ in selected}, 'exact target7 scratch/reset conditions')
    gallery = [f"nsd73k:{r['image_id']:05d}" for r in source[7]['test']]
    calibration = {str(k): list(prefixes[k]) for k in BUDGETS}
    output_rows, joins = [], []
    for cid, arm, budget in selected:
        condition, case = by_condition[cid], cases[cid]
        images = condition['images']
        need(type(images) is list and len(images) == 982, 'complete982 condition descriptors')
        by_query = {}
        for item in images:
            exact(item, ('query_id', 'target', 'candidates'), 'opaque query payload')
            q = item['query_id']
            need(type(q) is str and q not in by_query, 'unique payload query identity')
            by_query[q] = item
        need(set(by_query) == set(case['query_ids']), 'no missing/extra/cross-case query descriptors')
        output_rows.append({'arm': arm, 'budget': budget,
            'freeze_receipt_sha256': condition['freeze_receipt_sha256'],
            'generation_frozen_before_target_selection': condition['generation_frozen_before_target_selection'],
            'images': [{'image_id': ident, 'target': by_query[q]['target'],
                        'candidates': by_query[q]['candidates']}
                       for q, ident in zip(case['query_ids'], gallery)]})
        people = [7] if arm == 'vanilla' else list(SUBJECTS)
        joins.append({'case_id': cid, 'arm': arm, 'budget': budget,
            'query_order_sha256': digest(case['query_ids']), 'gallery_order_sha256': digest(gallery),
            'adaptation': [{'subject': s, 'train_count': budget, 'validation_count': 300,
                'train_keys_sha256': digest([r['key'] for r in source[s]['train'][:budget]]),
                'validation_keys_sha256': digest([r['key'] for r in source[s]['val']])} for s in people],
            'pretraining': [{'subject': s, 'train_count': 8559, 'validation_count': 300,
                'train_keys_sha256': digest([r['key'] for r in source[s]['train']]),
                'validation_keys_sha256': digest([r['key'] for r in source[s]['val']])}
                for s in ([1, 2, 5] if arm == 'mindbridge' else [])]})
    packet = {'schema': 'mindbridge-original-panel/v1', 'task_id': TASK,
        'source_kind': bundle['source_kind'], 'target_subject': 7, 'source_subjects': [1, 2, 5],
        'information_condition': bundle['information_condition'],
        'test_image_ids': gallery, 'calibration': calibration, 'rows': output_rows,
        'skimage_version': bundle['skimage_version'],
        'feature_pipeline_sha256': bundle['feature_pipeline_sha256'],
        'image_prior_sha256': bundle['image_prior_sha256'],
        'preparation_composition': {'schema': 'mindbridge-target7-composition/v1',
            'operator_private': True, 'generation': plan['generation'], 'input_pins': input_pins,
            'source_file_count': 88, 'source_tar_count': 84,
            'indexed_case_count': 32, 'selected_condition_count': 6,
            'metrics': list(METRICS), 'finding_count': 48, 'conditions': joins,
            'gallery_source_binding': [{'image_id': ident, 'source_key': r['key'],
                'coco73k_image_id': r['image_id']} for r, ident in zip(source[7]['test'], gallery)],
            'calibration_source_binding': [{'source_key': r['key'], 'coco73k_image_id': r['image_id']}
                                           for r in source[7]['train'][:max(BUDGETS)]],
            'calibration_identity_rule': 'exact source-sorted train keys; separate private coco73k binding; validation excluded',
            'payloads_opened': False, 'original_membership_authenticated': False,
            'freeze_chronology_authenticated': False, 'runtime_qualified': False,
            'scientific_qualification': False, 'reproduction': 'unknown', 'improvement': 'unknown'}}
    need(tuple(deps['panel'].METRICS) == METRICS, 'unchanged original eight metric names')
    deps['panel'].validate_packet(packet)
    return packet


def _module(name, body, filename):
    module = types.ModuleType(name)
    module.__file__ = str(filename)
    sys.modules[name] = module
    try:
        exec(compile(body, str(filename), 'exec'), module.__dict__)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def load_dependencies(operator_root, implementations_root):
    """Load only exact retained helper bytes; no implicit legacy absolute path.

    The initial small dependency reads have a fixed total bound from the pin file.
    The CLI's separate cumulative budget covers the three supplied metadata inputs.
    """
    pin_path = Path(__file__).with_name('dependency_pins.json')
    need(not any(p.is_symlink() for p in (pin_path, *pin_path.parents)), 'no linked dependency pin manifest')
    with pin_path.open('rb') as stream:
        raw = stream.read(16385)
    need(len(raw) <= 16384 and hashlib.sha256(raw).hexdigest() == DEPENDENCY_MANIFEST_SHA,
         'bounded exact dependency pin manifest')
    pins = json.loads(raw)
    need(set(pins) == {'operator_files', 'implementation_files'} and
         set(pins['operator_files']) == set(GENERATION_FILES) and
         set(pins['implementation_files']) == {'source-protocol-v2/source_protocol.py', 'original-panel-v1/panel.py'},
         'complete fixed dependency topology')
    roots = {'operator_files': Path(operator_root), 'implementation_files': Path(implementations_root)}
    bodies = {}
    for group, entries in pins.items():
        for name, expected in entries.items():
            path = roots[group] / name
            need(not any(p.is_symlink() for p in (path, *path.parents)), 'no linked source dependency')
            with path.open('rb') as stream:
                body = stream.read(expected['bytes'] + 1)
            need(len(body) == expected['bytes'] and hashlib.sha256(body).hexdigest() == expected['sha256'],
                 'exact source dependency: ' + name)
            bodies[name] = body
    # Legacy generation additionally requires the existing public/private alias.
    alias = roots['operator_files'].parent / 'public/protocol.py'
    need(not any(p.is_symlink() for p in (alias, *alias.parents)), 'no linked protocol alias')
    with alias.open('rb') as stream:
        body = stream.read(len(bodies['protocol.py']) + 1)
    need(body == bodies['protocol.py'], 'original protocol alias')
    temporary = {name: sys.modules.get(name) for name in ('delivery_io', 'protocol', 'provision')}
    try:
        io = _module('delivery_io', bodies['delivery_io.py'], roots['operator_files'] / 'delivery_io.py')
        protocol = _module('protocol', bodies['protocol.py'], roots['operator_files'] / 'protocol.py')
        provision = _module('provision', bodies['provision.py'], roots['operator_files'] / 'provision.py')
    finally:
        for name, previous in temporary.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous
    sp = _module('_mindbridge_composition_source_protocol', bodies['source-protocol-v2/source_protocol.py'],
                 roots['implementation_files'] / 'source-protocol-v2/source_protocol.py')
    panel = _module('_mindbridge_composition_panel', bodies['original-panel-v1/panel.py'],
                    roots['implementation_files'] / 'original-panel-v1/panel.py')
    generation = hashlib.sha256(b''.join(name.encode() + b'\0' + bodies[name] + b'\0'
                                        for name in GENERATION_FILES)).hexdigest()
    return {'io': io, 'protocol': protocol, 'provision': provision,
            'manifest': io.decode(bodies['INPUT_MANIFEST.json']), 'generation': generation,
            'source_protocol': sp, 'panel': panel,
            'dependency_read_ceiling_bytes': sum(r['bytes'] + 1 for g in pins.values() for r in g.values())
                + len(bodies['protocol.py']) + 1 + 16385}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operator-root', required=True)
    parser.add_argument('--implementations-root', required=True)
    for name in ('plan', 'receipt', 'bundle'):
        parser.add_argument('--' + name, required=True)
        parser.add_argument('--' + name + '-bytes', type=int, required=True)
        parser.add_argument('--' + name + '-sha256', required=True)
    parser.add_argument('--max-read-bytes', type=int, required=True)
    parser.add_argument('--max-output-bytes', type=int, required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    caps = {'plan': 60000000, 'receipt': 1000000, 'bundle': 134217728}
    pins = {}
    for name, cap in caps.items():
        size, sha = getattr(args, name + '_bytes'), getattr(args, name + '_sha256')
        need(type(size) is int and 0 < size <= cap and HEX.fullmatch(sha), 'bounded exact input pin')
        pins[name] = {'bytes': size, 'sha256': sha}
    need(args.max_read_bytes >= sum(p['bytes'] + 1 for p in pins.values()),
         'reserve every input and one EOF probe before any metadata open')
    need(0 < args.max_output_bytes <= 134217728, 'explicit bounded output allowance')
    deps = load_dependencies(args.operator_root, args.implementations_root)
    values = {name: deps['io'].decode(deps['panel'].stable_bytes(
                  getattr(args, name), pins[name], pins[name]['bytes'])) for name in caps}
    packet = compose_panel(values['plan'], values['receipt'], values['bundle'], deps, input_pins=pins)
    deps['io'].put(args.output, packet, args.max_output_bytes)


if __name__ == '__main__':
    main()
