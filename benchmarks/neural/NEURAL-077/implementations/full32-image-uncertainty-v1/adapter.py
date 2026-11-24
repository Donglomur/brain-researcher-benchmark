"""Complete fixed-view full32 image reference; single arm, target-last scoring.

Production has no reduced-cohort switch. Generated controls exercise pure seams
and the actual child transport without granting authentic execution authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import struct
import sys
import time
import types

HERE = Path(__file__).resolve().parent
PREFIX = 'benchmarks/neural/NEURAL-077/implementations/'
COUNT, PEOPLE = 6400, 32
CONDITION = 'fixed_initial_image_four_demo_uncertainty_reference'
PROFILE = 'erp-full32-visual-v1'
IMAGE_PROFILE = 'neural077-initial-cz-pz-gain20-v1'
ALGORITHM = {'bytes': 16220, 'sha256': 'c4024cbc5cd2283f1246ff2c99008a212a70689de9e3d410d7ff7f4a49e5cf64'}
DEMONSTRATIONS = {'bytes': 129921, 'sha256': '19e4018216376af334fd5ead21e2c33d5761d9d56ce5c76d3a89411483906ed2'}
MANIFEST = {'bytes': 5428, 'sha256': '241870678fed37fca67cc9c64e2e3a0830e0a97f9815332e27fa3018ed6c9f3f'}
PNG_CAP = 65536
RUNTIME_ROOTS = tuple(Path(p) for p in ('/System', '/usr', '/Library/Frameworks'))
POLICY = {'scope': 'complete_predefined_32_person_complement', 'queries': COUNT, 'people': PEOPLE,
    'trials_per_person': 200, 'demonstrations': 4, 'demo_labels': [0, 1, 0, 1],
    'fit_calls': 1, 'query_feedback_or_refitting': False, 'automatic_retry': False,
    'fixed_initial_images_only': True, 'query_failures': 'refuse_complete_qualification',
    'zero_shared_support': 'p=0.5_with_audit; invalid_inputs_are_hard_failures',
    'feature_count': 30, 'six_person_feature_bank': False, 'independent_generalization_claim': False,
    'prior_exposure': '32-case image pilot, aggregate results and retrospective clipping diagnostics; full32 numerical reference previously graded',
    'interpretation': 'exposed-development fixed-reference calibration; experimental event label, not physiological P3 presence'}
METRICS = {'participant_macro_balanced_accuracy': True, 'participant_macro_natural_log_loss': True,
    'positive_threshold_inclusive': 0.5, 'log_loss_clip': 1e-15,
    'uncertainty_endpoint': None, 'new_competence_threshold': None}


def need(value, message):
    if not value:
        raise ValueError(message)


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def decode(body):
    def unique(items):
        value = {}
        for key, item in items:
            need(key not in value, 'Duplicate JSON field'); value[key] = item
        return value
    return json.loads(body, object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def descriptor(row, cap):
    need(type(row) is dict and set(row) == {'bytes', 'sha256'} and type(row['bytes']) is int and
         0 < row['bytes'] <= cap and type(row['sha256']) is str and re.fullmatch('[0-9a-f]{64}', row['sha256']),
         'Exact bounded descriptor')


def ordinary(path):
    value = Path(path)
    need(value.is_absolute() and '..' not in value.parts and
         all(not p.is_symlink() for p in (value, *value.parents)), 'Ordinary absolute path')
    return value


def protected(path):
    value = ordinary(path)
    need(all(not value.is_relative_to(r) and not r.is_relative_to(value) for r in RUNTIME_ROOTS),
         'Protected inputs must not overlap runtime-readable roots')
    return value


def read(path, cap, expected=None, budget=None, empty=False):
    path = ordinary(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
             (0 if empty else 1) <= before.st_size <= cap, 'Bounded ordinary file')
        if budget is not None: budget.input(before.st_size + 1)
        body = stream.read(before.st_size + 1); after = os.fstat(stream.fileno())
    fields = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
    need(fields(before) == fields(after) == fields(path.lstat()) and len(body) == before.st_size,
         'Input changed during capture')
    need(expected is None or pin(body) == expected, 'Frozen content changed')
    return body


def write(path, body, budget):
    budget.output(len(body))
    fd = os.open(ordinary(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(body); stream.flush(); os.fsync(stream.fileno())
    return pin(body)


def load(name, path, body):
    module = types.ModuleType(name); module.__file__ = str(path); sys.modules[name] = module
    exec(compile(body, str(path), 'exec'), module.__dict__)
    return module


def dependencies(repository_root, expected=None):
    need(sys.version_info >= (3, 10), 'Operator requires Python3.10+ for maintained full32 interfaces')
    root = ordinary(repository_root)
    binding_body = read(HERE / 'SOURCE_BINDINGS.json', 65536, expected)
    binding = decode(binding_body)
    need(set(binding) == {'schema', 'own', 'external'} and binding['schema'] == 'erp-full32-image-uncertainty-sources-v1'
         and set(binding['own']) == {'adapter.py', 'client.py'}, 'Exact source closure')
    own = {name: read(HERE / name, 131072, value) for name, value in binding['own'].items()}
    bodies = {}
    for name, value in binding['external'].items():
        need(name.startswith('benchmarks/') and '..' not in Path(name).parts and not Path(name).is_absolute(),
             'Repository-relative dependency')
        descriptor(value, 131072); bodies[name] = read(root / name, 131072, value)
    required = ['image-matched-programme-v1/pair.py', 'full32-provider-pair-v1/pair.py',
                'four-demo-image-uncertainty-v1/reference.py', 'visual-viewer-v1/raster.py']
    need(all(PREFIX + n in bodies for n in required), 'Complete selected dependency interfaces')
    need(pin(bodies[PREFIX + required[2]]) == ALGORITHM, 'Selected zero-support uncertainty algorithm')
    visual_pair = load('erp_image_reference_visual', root / (PREFIX + required[0]), bodies[PREFIX + required[0]])
    numeric_pair = load('erp_image_reference_capture', root / (PREFIX + required[1]), bodies[PREFIX + required[1]])
    visual = visual_pair.dependencies(root / PREFIX, profile=PROFILE)
    capture = numeric_pair.dependencies()
    capture['consumer'] = types.SimpleNamespace(parse_response=parse_response)
    reference_path = root / (PREFIX + required[2])
    result = {'root': root, 'binding': pin(binding_body), 'source': binding, 'own': own,
        'visual_pair': visual_pair, 'visual': visual, 'capture': capture, 'pair': numeric_pair,
        'reference': load('erp_image_reference_unchanged', reference_path, bodies[PREFIX + required[2]]),
        'algorithm_path': reference_path,
        'raster': load('erp_image_reference_raster', root / (PREFIX + required[3]), bodies[PREFIX + required[3]]),
        'codec': visual['transport'].v._profile_dependency('codec', root / PREFIX),
        'source_read_reserve': 32 * 1024**2}
    return result


def check_runtime(spec, budget):
    need(sys.platform == 'darwin', 'Maintained macOS sandbox required; no host fallback')
    for name in ('interpreter', 'sandbox'):
        row = spec[name]
        need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'}, 'Pinned executable')
        path = ordinary(row['path']); descriptor({k: row[k] for k in ('bytes', 'sha256')}, 64 * 1024**2)
        need(any(path.is_relative_to(r) for r in RUNTIME_ROOTS) and os.access(path, os.X_OK), 'Admitted runtime roots')
        read(path, 64 * 1024**2, {k: row[k] for k in ('bytes', 'sha256')}, budget)
    need(spec['sandbox']['path'] == '/usr/bin/sandbox-exec', 'Exact maintained sandbox')


def disjoint_output(path, *roots):
    output = ordinary(path)
    need(not output.exists() and not any(output.is_relative_to(r) for r in RUNTIME_ROOTS), 'Fresh protected output')
    for root in roots:
        root = ordinary(root)
        need(not output.is_relative_to(root) and not root.is_relative_to(output), 'Input/output overlap')
    return output


def limits(value):
    need(type(value) is dict and set(value) == {'read_bytes', 'write_bytes', 'work_seconds', 'closure_seconds',
         'episode_work_seconds', 'episode_cleanup_seconds'}, 'Exact stage limits')
    for key in value:
        need(type(value[key]) is int and value[key] > 0, 'Positive integer limits')
    need(value['read_bytes'] <= 16 * 1024**3 and value['write_bytes'] <= 1024**3 and
         value['work_seconds'] <= 3600 and value['closure_seconds'] <= 600 and
         value['episode_work_seconds'] <= 60 and value['episode_cleanup_seconds'] <= 30,
         'Bounded selected stage limits')
    return value


def new_budget(value, modules):
    limits(value)
    budget = modules['pair'].Budget(value['read_bytes'], value['write_bytes'],
                                    time.monotonic() + value['work_seconds'] + value['closure_seconds'])
    budget.input(modules['source_read_reserve'])
    return budget


def public_metadata(public, manifest_pin, budget):
    need(manifest_pin == MANIFEST, 'Exact original complete full32 packet identity')
    manifest = decode(read(Path(public) / 'PACKET.json', 65536, manifest_pin, budget))
    need(manifest.get('schema') == 'erp-core-full32-public-packet-v1' and
         manifest.get('condition_id') == 'erp-core-remaining-persons-released-marker-v1' and
         manifest.get('benchmark_id') == 'NEURAL-077' and manifest.get('query_count') == COUNT and
         manifest.get('people') == PEOPLE and manifest.get('demonstration_count') == 4 and
         manifest.get('natural_class_prior_supplied') is False and
         manifest.get('files', {}).get('demonstrations.json') == DEMONSTRATIONS, 'Exact full32 public packet')
    roster_body = read(Path(public) / 'roster.json', 4 * 1024**2, manifest['files']['roster.json'], budget)
    rows = decode(roster_body); need(type(rows) is list and len(rows) == COUNT, 'All6400 original cases')
    ids = tuple(r['trial_id'] for r in rows)
    need(ids == tuple(sorted(set(ids))) and all(type(x) is str and re.fullmatch('q-[0-9a-f]{32}', x) for x in ids),
         'Sorted unique complete original roster')
    return roster_body, ids


def validate_contract(value):
    need(type(value) is dict and set(value) == {'schema', 'policy', 'metrics', 'repository_root', 'source_bindings',
         'public_root', 'public_manifest', 'roster', 'demos', 'model', 'algorithm', 'client', 'interpreter', 'sandbox',
         'limits', 'freeze_stage', 'demo_export_provenance'}, 'Exact single-reference contract')
    need(value['schema'] == 'erp-full32-image-uncertainty-contract-v1' and value['policy'] == POLICY and
         value['metrics'] == METRICS and value['algorithm']['file'] == ALGORITHM and
         value['freeze_stage'] == {'fit_calls': 1, 'query_images_processed': 0, 'private_targets_opened': False},
         'Selected uncertainty method, complete scope and pre-query fit')
    protected(value['repository_root']); protected(Path(value['public_root']).parent)
    descriptor(value['source_bindings'], 65536)
    descriptor(value['public_manifest'], 65536); descriptor(value['roster'], 4 * 1024**2)
    for name, cap in (('algorithm', 65536), ('client', 65536), ('model', 65536)):
        row = value[name]; need(set(row) == {'path', 'file'}, 'Exact frozen operand')
        protected(row['path']); descriptor(row['file'], cap)
    need(type(value['demos']) is list and len(value['demos']) == 4, 'Exactly four ordered demos')
    for i, row in enumerate(value['demos']):
        need(set(row) == {'path', 'file', 'record', 'label'} and row['record'] == f'demo{i+1}' and
             type(row['label']) is int and row['label'] == (0, 1, 0, 1)[i], 'Fixed ordered demonstration identity')
        protected(row['path']); descriptor(row['file'], PNG_CAP)
    need(set(value['demo_export_provenance']) == {'bytes', 'sha256'}, 'Frozen accepted export provenance descriptor')
    descriptor(value['demo_export_provenance'], 65536)
    need(set(value['limits']) == {'freeze', 'run', 'evaluate'}, 'Separate cumulative stage allocations')
    for limit in value['limits'].values(): limits(limit)
    need(sum(x['write_bytes'] for x in value['limits'].values()) <= 1024**3 and
         sum(x['read_bytes'] for x in value['limits'].values()) <= 16 * 1024**3 and
         sum(x['work_seconds'] for x in value['limits'].values()) <= 3600 and
         sum(x['closure_seconds'] for x in value['limits'].values()) <= 600, 'Cumulative complete-operation ceiling')
    return value


def verify_frozen(contract, modules, budget):
    validate_contract(contract)
    need(contract['source_bindings'] == modules['binding'] and
         contract['algorithm']['path'] == str(modules['algorithm_path']), 'Bound source closure')
    read(contract['algorithm']['path'], 65536, ALGORITHM, budget)
    need(read(contract['client']['path'], 65536, contract['client']['file'], budget) == modules['own']['client.py'],
         'Only the reviewed fixed wrapper')
    body = read(contract['model']['path'], 65536, contract['model']['file'], budget)
    model = decode(body); modules['reference'].validate_model(model)
    need(model['demonstration_sha256'] == [r['file']['sha256'] for r in contract['demos']], 'Frozen model demo binding')
    for row in contract['demos']: read(row['path'], PNG_CAP, row['file'], budget)
    roster, ids = public_metadata(contract['public_root'], contract['public_manifest'], budget)
    need(pin(roster) == contract['roster'], 'Original roster unchanged')
    return ids


def freeze(spec, output):
    need(type(spec) is dict and set(spec) == {'schema', 'repository_root', 'source_bindings', 'public_root',
         'public_manifest', 'demos', 'demo_export_provenance', 'interpreter', 'sandbox', 'limits'} and
         spec['schema'] == 'erp-full32-image-uncertainty-freeze-spec-v1', 'Exact freeze specification')
    modules = dependencies(spec['repository_root'], spec['source_bindings'])
    budget = new_budget(spec['limits']['freeze'], modules)
    output = disjoint_output(output, HERE, modules['root'], Path(spec['public_root']).parent,
                             *(Path(r['path']).parent for r in spec['demos']))
    contract = {'schema': 'erp-full32-image-uncertainty-contract-v1', 'policy': POLICY, 'metrics': METRICS,
        **{k: spec[k] for k in ('repository_root', 'source_bindings', 'public_root', 'public_manifest',
                              'demos', 'demo_export_provenance', 'interpreter', 'sandbox', 'limits')},
        'roster': {'bytes': 1, 'sha256': '0' * 64},
        'algorithm': {'path': str(modules['algorithm_path']), 'file': ALGORITHM},
        'client': {'path': str(output / 'CLIENT.py'), 'file': pin(modules['own']['client.py'])},
        'model': {'path': str(output / 'MODEL.json'), 'file': {'bytes': 1, 'sha256': '0' * 64}},
        'freeze_stage': {'fit_calls': 1, 'query_images_processed': 0, 'private_targets_opened': False}}
    validate_contract(contract); check_runtime(contract, budget)
    roster, _ = public_metadata(contract['public_root'], contract['public_manifest'], budget)
    output.mkdir(mode=0o700)
    write(output / 'START.json', encode({'schema': 'erp-image-uncertainty-fit-start-v1', 'spec': pin(encode(spec)),
          'query_images_processed': 0, 'fit_attempt': 1}), budget)
    try:
        with modules['visual_pair'].deadline(spec['limits']['freeze']['work_seconds']):
            images = [read(r['path'], PNG_CAP, r['file'], budget) for r in contract['demos']]
            ref = modules['reference']
            features = [ref.extract_features(ref.decode_png(b)) for b in images]
            model = ref.fit_features(features, [pin(b)['sha256'] for b in images], profile=IMAGE_PROFILE)
            contract['model']['file'] = write(output / 'MODEL.json', ref.json_bytes(model), budget)
            contract['roster'] = pin(roster)
            write(output / 'CLIENT.py', modules['own']['client.py'], budget)
            verify_frozen(contract, modules, budget)
            write(output / 'CONTRACT.json', encode(contract), budget)
    except BaseException as exc:
        write(output / 'FAILED.json', encode({'stage': 'fit', 'error': type(exc).__name__, 'fit_attempts': 1,
            'query_images_processed': 0, 'no_retry': True}), budget)
        raise
    return {'status': 'four_demo_model_frozen_before_query_images', 'contract': pin(encode(contract)),
            'read_bytes_charged': budget.read, 'write_bytes_charged': budget.written}


def render(record, modules, *, demonstration=None):
    """Exactly Session._frame's initial raster+lossless-codec path, without actions."""
    viewer = modules['visual']['transport'].v
    state = viewer.initial_state()
    if demonstration is not None: state['record'] = f'demo{demonstration+1}'
    original = modules['raster'].render(record, state, 'four_demo')
    png, encoding = modules['codec'].encode_transport_image(original)
    modules['codec'].verify_equivalence(original, png, encoding)
    need(0 < len(png) <= PNG_CAP, '64KiB compressed image ceiling; no alteration or retry')
    display = viewer.display_metadata(state, record)
    need((demonstration is None) == ('demonstration_target' not in display), 'Only demo labels in display')
    if demonstration is not None:
        need(display['demonstration_target'] == (0, 1, 0, 1)[demonstration], 'Original demo order/labels')
    return png, {'state': state, 'display': display, 'encoding': encoding, 'png': pin(png)}


def open_data(contract, modules, budget, ids):
    visual = modules['visual']
    data = visual['provider'].dataset_for(visual, contract['public_root'], profile=PROFILE,
                                           manifest_pin=contract['public_manifest'], budget=budget)
    try:
        need(tuple(visual['transport'].v.ordered_ids(data)) == ids and len(ids) == COUNT, 'Complete original packet')
        for i, demo in enumerate(data['demos']):
            png, _ = render(demo, modules, demonstration=i)
            need(pin(png) == contract['demos'][i]['file'], 'Fixed demo PNG differs from original packet rendering')
        return data
    except BaseException:
        visual['transport'].v.close_source(data); raise


def image_context(identifier, png_path, png_pin, contract):
    payload = {'schema': 'erp-full32-image-uncertainty-input-v1', 'trial_id': identifier,
        'profile': IMAGE_PROFILE, 'algorithm': contract['algorithm'], 'model': contract['model'],
        'image': {'path': str(png_path), 'file': png_pin}}
    body = encode(payload)
    return {'trial_id': identifier, 'condition': CONDITION, 'context_sha256': pin(body)['sha256'], 'body': body}


def context_frame(context, condition):
    need(condition == CONDITION and context['condition'] == CONDITION and
         pin(context['body'])['sha256'] == context['context_sha256'], 'Exact single-image context')
    return struct.pack('>I', len(context['body'])) + context['body']


def image_wire(wire, operands):
    """Retain original deny policy; add only three exact input file literals."""
    paths = [ordinary(p) for p in operands]
    need(len(paths) == 3 and len(set(paths)) == 3 and
         not any(p.is_relative_to(r) for p in paths for r in RUNTIME_ROOTS), 'Three protected literal inputs')
    def profile(client):
        base = wire.sandbox_profile(client)
        extra = ' '.join('(literal ' + json.dumps(str(p)) + ')' for p in paths)
        return base + ' (allow file-read-data file-read-metadata ' + extra + ')'
    return types.SimpleNamespace(WireFailure=wire.WireFailure, read_frame=wire.read_frame,
                                 write_frame=wire.write_frame, sandbox_profile=profile)


def validate_quality(quality, probability):
    need(type(quality) is dict and set(quality) == {'shared_support_fraction', 'baseline_coverage',
         'coverage', 'shared_weights', 'no_shared_support'}, 'Exact30-feature quality audit')
    for key, size in (('coverage', 30), ('shared_weights', 30), ('baseline_coverage', 2)):
        need(type(quality[key]) is list and len(quality[key]) == size and
             all(type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 1 for v in quality[key]),
             'Finite bounded complete coverage arrays')
    need(all(w <= quality['coverage'][j] * quality['baseline_coverage'][j // 15]
             for j, w in enumerate(quality['shared_weights'])), 'Shared weight cannot exceed query visibility')
    total = sum(quality['shared_weights'])
    fraction = quality['shared_support_fraction']
    need(type(fraction) in (int, float) and math.isfinite(fraction) and fraction == total / 30.0 and
         type(quality['no_shared_support']) is bool and quality['no_shared_support'] == (total == 0),
         'Exact zero-support flag and original support denominator')
    need(total != 0 or probability == 0.5, 'Zero support must return exactly half')


def parse_response(response, identifier):
    value = decode(response)
    need(type(value) is dict and set(value) == {'trial_id', 'target_probability', 'quality'} and
         value['trial_id'] == identifier, 'Exact successor response identity and audit')
    probability = value['target_probability']
    need(type(probability) in (int, float) and math.isfinite(probability) and 0 <= probability <= 1,
         'Finite probability')
    validate_quality(value['quality'], probability)
    return value


def coverage_summary(qualities):
    need(len(qualities) == COUNT, 'Coverage denominator is all6400 cases')
    return {'queries': COUNT, 'features_per_query': 30,
        'feature_order': 'Cz fifteen postmarker50ms bins, then Pz fifteen postmarker50ms bins',
        'no_shared_support_queries': sum(q['no_shared_support'] for q in qualities),
        'feature_defined_queries': [sum(q['coverage'][j] > 0 for q in qualities) for j in range(30)],
        'feature_mean_coverage': [sum(q['coverage'][j] for q in qualities) / COUNT for j in range(30)],
        'feature_mean_shared_weight': [sum(q['shared_weights'][j] for q in qualities) / COUNT for j in range(30)],
        'baseline_mean_coverage': [sum(q['baseline_coverage'][j] for q in qualities) / COUNT for j in range(2)],
        'positive_shared_support_queries': sum(not q['no_shared_support'] for q in qualities),
        'mean_shared_support_fraction': sum(q['shared_support_fraction'] for q in qualities) / COUNT}


def accept_capture(context, envelope, end, incoming, outgoing, stderr, sandbox, expected_sandbox, modules):
    need(modules['capture']['runtime'].end_closed(end) and end.get('status') == 'ok' and
         end.get('generated_protocol_only') is False and type(end.get('returncode')) is int and
         end['returncode'] == 0 and end.get('normal_exit_observed') is True and
         end.get('first_response_immutable') is True and end.get('trailing_byte') == pin(b''),
         'Successful first response and owned resource closure required')
    need(end.get('trial_id') == context['trial_id'] and end.get('condition') == CONDITION and
         end.get('context_sha256') == context['context_sha256'] and
         envelope == {'trial_id': context['trial_id'], 'condition': CONDITION,
            'context_sha256': context['context_sha256'], 'status': 'ok',
            'response': outgoing[4:].decode('utf-8'), 'error': None}, 'Exact captured attempt identity')
    need(incoming == context_frame(context, CONDITION) and end['input'] == pin(incoming) and
         end['output'] == pin(outgoing) and end['attempt'] == pin(encode(envelope)), 'Immutable complete capture bytes')
    need(4 < len(outgoing) <= 4100 and struct.unpack('>I', outgoing[:4])[0] == len(outgoing) - 4,
         'One complete first response frame')
    capture = end.get('stderr_capture') or {}
    need(capture.get('eof_observed') is True and capture.get('overflow') is False and
         capture.get('error') is None and capture.get('file') == pin(stderr) and
         capture.get('retained_bytes') == capture.get('observed_bytes') == len(stderr), 'Complete bounded stderr')
    need(sandbox == expected_sandbox, 'Exact image-only sandbox policy')
    return parse_response(envelope['response'], context['trial_id'])


def episode_files(root, context, contract, modules, budget):
    end_body = read(root / 'END.json', 16384, budget=budget)
    end = decode(end_body)
    elapsed = end.get('elapsed_seconds')
    need(type(elapsed) in (int, float) and math.isfinite(elapsed) and 0 <= elapsed <=
         contract['limits']['run']['episode_work_seconds'] + contract['limits']['run']['episode_cleanup_seconds'],
         'Finite bounded episode clock')
    envelope = decode(read(root / 'ATTEMPT.json', 16384, end['attempt'], budget))
    incoming = read(root / 'INPUT.bin', 16388, end['input'], budget)
    outgoing = read(root / 'OUTPUT.bin', 4100, end['output'], budget)
    stderr = read(root / 'STDERR.bin', 16384, end['stderr_capture']['file'], budget, empty=True)
    wire = image_wire(modules['capture']['wire'], [contract['algorithm']['path'], contract['model']['path'],
                                                  decode(context['body'])['image']['path']])
    expected = wire.sandbox_profile(contract['client']['path']).encode()
    sandbox = read(root / 'sandbox.sb', 16384, budget=budget)
    response = accept_capture(context, envelope, end, incoming, outgoing, stderr, sandbox, expected, modules)
    return response, pin(end_body)


def run(contract, contract_pin, output):
    validate_contract(contract); need(pin(encode(contract)) == contract_pin, 'Frozen contract identity')
    modules = dependencies(contract['repository_root'], contract['source_bindings'])
    budget = new_budget(contract['limits']['run'], modules)
    ids = verify_frozen(contract, modules, budget); check_runtime(contract, budget)
    output = disjoint_output(output, HERE, modules['root'], Path(contract['public_root']).parent,
        Path(contract['model']['path']).parent, *(Path(r['path']).parent for r in contract['demos']))
    output.mkdir(mode=0o700); rows = []; data = None; current = None
    write(output / 'INITIAL.json', encode({'trial_ids': ids, 'contract': contract_pin}), budget)
    began = time.monotonic(); limit = contract['limits']['run']
    try:
        with modules['visual_pair'].deadline(limit['work_seconds']):
            data = open_data(contract, modules, budget, ids)
            for ordinal, identifier in enumerate(ids):
                current = ordinal
                need(time.monotonic() + limit['episode_work_seconds'] + limit['episode_cleanup_seconds'] <
                     began + limit['work_seconds'], 'Complete episode deadline headroom')
                need(budget.written + 256 * 1024 + 4 * 1024**2 <= budget.write_limit, 'Episode/finalization byte headroom')
                directory = output / f'{ordinal:04d}'; directory.mkdir(mode=0o700)
                write(directory / 'START.json', encode({'ordinal': ordinal, 'trial_id': identifier, 'attempt': 1}), budget)
                png, projection = render(data['rows'][ordinal], modules)
                image_pin = write(directory / 'QUERY.png', png, budget)
                write(directory / 'VIEW.json', encode(projection), budget)
                context = image_context(identifier, directory / 'QUERY.png', image_pin, contract)
                capture_modules = dict(modules['capture'])
                capture_modules['wire'] = image_wire(capture_modules['wire'],
                    [contract['algorithm']['path'], contract['model']['path'], directory / 'QUERY.png'])
                facade = types.SimpleNamespace(ordinary_path=ordinary, context_frame=context_frame,
                    PREFIX=struct.Struct('>I'), need=need, pin=pin, encode=encode, write=write)
                # Conservative interpreter/import allowance plus repeated child operand reads.
                budget.input(1024**2 + 6 * (ALGORITHM['bytes'] + contract['model']['file']['bytes'] + len(png)))
                # Reauthenticate the executable wrapper before every dispatch;
                # the wrapper independently checks each method/model/image operand.
                read(contract['client']['path'], 65536, contract['client']['file'], budget)
                modules['capture']['episode'].episode(facade, context, CONDITION, directory / 'capture',
                    contract['client']['path'], contract['interpreter']['path'], limit,
                    began + limit['work_seconds'] + limit['closure_seconds'], capture_modules, budget,
                    generated_protocol_only=False)
                response, end = episode_files(directory / 'capture', context, contract, modules, budget)
                rows.append({'ordinal': ordinal, 'trial_id': identifier, 'image': image_pin,
                    'view': pin(encode(projection)), 'end': end,
                    'quality': pin(encode(response['quality'])), 'target_probability': response['target_probability']})
                write(directory / 'COMPLETE.json', encode(rows[-1]), budget)
                current = None
            need(len(rows) == COUNT, 'No partial reference arm')
            need(verify_frozen(contract, modules, budget) == ids, 'Frozen dependencies changed during run')
            receipt = {'schema': 'erp-full32-image-uncertainty-arm-v1', 'status': 'complete_unscored_reference',
                'contract': contract_pin, 'condition': CONDITION, 'rows': rows, 'query_count': COUNT,
                'private_target_reads': 0, 'scoring_performed': False, 'automatic_retry': False,
                'read_bytes_charged': budget.read, 'written_bytes_charged_before_receipt': budget.written}
            write(output / 'ARM.json', encode(receipt), budget)
            return {'status': receipt['status'], 'arm': pin(encode(receipt)),
                    'read_bytes_charged': budget.read, 'write_bytes_charged': budget.written}
    except BaseException as error:
        write(output / 'FAILED.json', encode({'status': 'failed_no_partial_admission', 'error': type(error).__name__,
            'completed': len(rows), 'current': current, 'unattempted': COUNT - len(rows) - int(current is not None),
            'private_targets_opened': False, 'automatic_retry': False,
            'read_bytes_charged': budget.read, 'written_bytes_charged': budget.written}), budget)
        raise
    finally:
        if data is not None: modules['visual']['transport'].v.close_source(data)


def validate_arm(arm, contract_pin, identifiers):
    need(type(arm) is dict and set(arm) == {'schema', 'status', 'contract', 'condition', 'rows', 'query_count',
         'private_target_reads', 'scoring_performed', 'automatic_retry', 'read_bytes_charged',
         'written_bytes_charged_before_receipt'} and arm['schema'] == 'erp-full32-image-uncertainty-arm-v1' and
         arm['status'] == 'complete_unscored_reference' and arm['contract'] == contract_pin and
         arm['condition'] == CONDITION and arm['query_count'] == COUNT and arm['private_target_reads'] == 0 and
         arm['scoring_performed'] is False and arm['automatic_retry'] is False, 'Complete single-reference receipt')
    need(len(identifiers) == COUNT and len(set(identifiers)) == COUNT and type(arm['rows']) is list and
         len(arm['rows']) == COUNT, 'All6400 unique cases required')
    for ordinal, (identifier, row) in enumerate(zip(identifiers, arm['rows'], strict=True)):
        need(set(row) == {'ordinal', 'trial_id', 'image', 'view', 'end', 'quality', 'target_probability'} and
             type(row['ordinal']) is int and row['ordinal'] == ordinal and row['trial_id'] == identifier,
             'Ordered complete immutable response inventory')
        descriptor(row['image'], PNG_CAP); descriptor(row['view'], 16384); descriptor(row['end'], 16384)
        descriptor(row['quality'], 4096)
        p = row['target_probability']; need(type(p) in (int, float) and math.isfinite(p) and 0 <= p <= 1, 'Finite score')


def ordered_metrics(admit, private_loader, core):
    """Pure ordering seam; production admission and private loader are bound below."""
    predictions = admit()
    need(type(predictions) is dict and len(predictions) == COUNT, 'Complete public admission before private access')
    people = private_loader(set(predictions))
    joined = [identifier for rows in people.values() for identifier, _ in rows]
    need(len(people) == PEOPLE and all(len(r) == 200 and sum(y for _, y in r) == 40 for r in people.values()) and
         len(joined) == len(set(joined)) == COUNT and set(joined) == set(predictions), 'Exact original32-person join')
    return core.metric_rows(predictions, people)


def evaluate(contract, contract_pin, arm_root, arm_pin, private_loader, output):
    validate_contract(contract); need(pin(encode(contract)) == contract_pin, 'Exact frozen contract')
    modules = dependencies(contract['repository_root'], contract['source_bindings'])
    budget = new_budget(contract['limits']['evaluate'], modules)
    ids = verify_frozen(contract, modules, budget); check_runtime(contract, budget)
    arm_root = ordinary(arm_root)
    need(not (arm_root / 'FAILED.json').exists(), 'Failed arm cannot enter evaluation')
    output = disjoint_output(output, HERE, modules['root'], Path(contract['public_root']).parent,
                             Path(contract['model']['path']).parent, arm_root)
    arm = decode(read(arm_root / 'ARM.json', 4 * 1024**2, arm_pin, budget)); validate_arm(arm, contract_pin, ids)
    need(decode(read(arm_root / 'INITIAL.json', 512 * 1024, budget=budget)) ==
         {'trial_ids': list(ids), 'contract': contract_pin}, 'Frozen complete initial inventory')
    data = None; qualities = []
    try:
        with modules['visual_pair'].deadline(contract['limits']['evaluate']['work_seconds']):
            data = open_data(contract, modules, budget, ids)
            def admit():
                predictions = {}
                for ordinal, row in enumerate(arm['rows']):
                    directory = arm_root / f'{ordinal:04d}'
                    need(not (directory / 'FAILED.json').exists(), 'Failed episode cannot qualify')
                    need(decode(read(directory / 'START.json', 16384, budget=budget)) ==
                         {'ordinal': ordinal, 'trial_id': row['trial_id'], 'attempt': 1}, 'One original dispatch attempt')
                    png, projection = render(data['rows'][ordinal], modules)
                    need(pin(png) == row['image'], 'Retained image must equal original fixed-view source rendering')
                    read(directory / 'QUERY.png', PNG_CAP, row['image'], budget)
                    need(read(directory / 'VIEW.json', 16384, row['view'], budget) == encode(projection),
                         'Exact display, codec and original query binding')
                    need(decode(read(directory / 'COMPLETE.json', 16384, budget=budget)) == row,
                         'Episode changed since complete arm commitment')
                    context = image_context(row['trial_id'], directory / 'QUERY.png', row['image'], contract)
                    response, end = episode_files(directory / 'capture', context, contract, modules, budget)
                    need(end == row['end'] and response['target_probability'] == row['target_probability'] and
                         pin(encode(response['quality'])) == row['quality'], 'Exact first-response score and coverage')
                    qualities.append(response['quality'])
                    predictions[row['trial_id']] = response['target_probability']
                need(verify_frozen(contract, modules, budget) == ids, 'Freeze changed before protected access')
                check_runtime(contract, budget)
                return predictions
            def labels(identifiers):
                # Do not even interpret the private descriptor until all image/capture checks pass.
                private = private_loader()
                need(type(private) is dict and set(private) == {'root', 'complete'}, 'Exact private descriptor')
                private_root = protected(private['root'])
                need(private_root == Path(contract['public_root']).parent, 'Private counterpart of the frozen public packet')
                need(not output.is_relative_to(private_root) and not private_root.is_relative_to(output), 'Separate result output')
                budget.input(16 * 1024**2)
                old_budget = {'read': 0}
                return modules['capture']['core'].load_private_people(private, contract['public_manifest'], identifiers, old_budget)
            scores = ordered_metrics(admit, labels, modules['capture']['core'])
        output.mkdir(mode=0o700)
        result = {'schema': 'erp-full32-image-uncertainty-result-v1', 'status': 'complete_exposed_development_reference_calibration',
            'contract': contract_pin, 'arm': arm_pin, 'queries': COUNT, 'people': PEOPLE, 'scores': scores,
            'policy': POLICY, 'metric_policy': METRICS, 'source_bindings': modules['binding'],
            'coverage_summary': coverage_summary(qualities),
            'constant_half_analytic': {'balanced_accuracy': 0.5, 'natural_log_loss': math.log(2)},
            'constant_source_prior_analytic': {'probability': 0.2, 'balanced_accuracy': 0.5,
                'natural_log_loss': -0.2 * math.log(0.2) - 0.8 * math.log(0.8),
                'used_by_classifier': False},
            'all_images_first_responses_and_owned_closures_admitted_before_private': True,
            'direct_or_paired_arm_claim': False, 'independent_generalization_claim': False,
            'competence_threshold_qualified': False, 'new_benchmarks': 0,
            'read_bytes_charged': budget.read, 'written_bytes_charged_before_result': budget.written}
        write(output / 'RESULT.json', encode(result), budget)
        return result
    finally:
        if data is not None: modules['visual']['transport'].v.close_source(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('freeze', 'run', 'evaluate'))
    parser.add_argument('--input', required=True); parser.add_argument('--input-bytes', type=int, required=True)
    parser.add_argument('--input-sha256', required=True); parser.add_argument('--output', required=True)
    parser.add_argument('--arm'); parser.add_argument('--arm-bytes', type=int); parser.add_argument('--arm-sha256')
    parser.add_argument('--private-material')
    args = parser.parse_args(); expected = {'bytes': args.input_bytes, 'sha256': args.input_sha256}
    descriptor(expected, 65536); value = decode(read(args.input, 65536, expected))
    if args.command == 'freeze': result = freeze(value, args.output)
    elif args.command == 'run': result = run(value, expected, args.output)
    else:
        need(args.arm and args.arm_bytes and args.arm_sha256 and args.private_material, 'Complete evaluation operands')
        selected = {'bytes': args.arm_bytes, 'sha256': args.arm_sha256}; descriptor(selected, 4 * 1024**2)
        result = evaluate(value, expected, args.arm, selected,
            lambda: decode(read(args.private_material, 65536)), args.output)
    print(json.dumps({'status': result['status'], 'output': args.output}, sort_keys=True))


if __name__ == '__main__':
    main()
