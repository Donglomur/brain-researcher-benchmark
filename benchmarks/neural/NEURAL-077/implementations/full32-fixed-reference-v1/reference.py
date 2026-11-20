"""Independent full32 fixed-reference route; paired entrypoints stay unchanged.

Production is always 6400 original events from32 people. No provider/direct arm
or fixture-count mode exists. Protected labels are opened only after the entire
reference first-response inventory and known closures authenticate.
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
import sys
import time
import types

HERE = Path(__file__).resolve().parent
RELATIVE = 'benchmarks/neural/NEURAL-077/implementations/full32-fixed-reference-v1'
BASELINE = 'benchmarks/neural/NEURAL-077/implementations/full32-demonstration-baseline-v1'
COUNT = 6400
PEOPLE = 32
CONDITION = 'numeric_program_four_demo'
PAIR_BINDING = {'bytes': 2744, 'sha256': '9183eb923163b05560f185f7f23db23a747bc4f83e3a03aee118c5f89f125971'}
BASELINE_PINS = {
    'candidate': {'bytes': 10830, 'sha256': 'e55bd34611eaa3b74a8660d7d6e7c9e55bb769758caee161d5e270178b3d1031'},
    'config': {'bytes': 208, 'sha256': '2e0756770b6d613066e9b4fb11f09c43af461f0e6e11f3e2fc6e48d930cbc0e8'},
    'manifest': {'bytes': 123, 'sha256': '97017c646f461fedd26163a01cbadcc2a5bef69629059ad40f083467e6078be3'},
    'method': {'bytes': 2492, 'sha256': '453a0ab5006274bf46aecc6e628fa12b20f7875b74c6eb850aad0f6b1e44cb7a'},
}
POLICY = {'same_four_demonstrations': True, 'single_query_only': True,
          'no_other_query_or_pooled_learning': True, 'no_private_answers': True,
          'no_six_person_training_or_fitted_coefficients': True, 'no_natural_class_prior': True,
          'programme_frozen_before_queries': True, 'no_feedback_until_reference_closed': True,
          'old_negative_baselines_preserved': True}
METRIC_POLICY = {'participant_macro_balanced_accuracy': True, 'participant_macro_natural_log_loss': True,
                 'positive_threshold_inclusive': 0.5, 'log_loss_clip': 1e-15,
                 'participant_count': 32, 'trials_per_participant': 200, 'query_count': 6400,
                 'target': 'released experimental event label; not physiological P3 presence',
                 'uncertainty_endpoint': None}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def decode(body):
    def unique(items):
        result = {}
        for key, value in items:
            need(key not in result, 'Duplicate JSON field')
            result[key] = value
        return result
    return json.loads(body, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def descriptor(value, cap=1048576):
    need(type(value) is dict and set(value) == {'bytes', 'sha256'} and type(value['bytes']) is int and
         0 < value['bytes'] <= cap and type(value['sha256']) is str and
         re.fullmatch('[0-9a-f]{64}', value['sha256']), 'Exact bounded content descriptor')


def ordinary(path):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts and all(not p.is_symlink() for p in (path, *path.parents)),
         'Absolute ordinary path')
    return path


def read_source(path, cap, expected=None):
    path = ordinary(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap, 'Bounded source file')
        body = stream.read(before.st_size + 1); after = os.fstat(stream.fileno())
    identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
    need(identity(before) == identity(after) == identity(path.lstat()) and len(body) == before.st_size,
         'Source changed during read')
    need(expected is None or pin(body) == expected, 'Committed source changed')
    return body


def load(name, path, body):
    module = types.ModuleType(name); module.__file__ = str(path); sys.modules[name] = module
    exec(compile(body, str(path), 'exec'), module.__dict__)
    return module


def dependencies(expected=None):
    body = read_source(HERE / 'SOURCE_BINDINGS.json', 16384, expected); value = decode(body)
    need(set(value) == {'schema', 'members'} and value['schema'] == 'erp-full32-fixed-reference-sources-v1',
         'Exact reference source schema')
    rows = value['members']; root = HERE.parents[4]
    pair_names = {'pair', 'bridge', 'client', 'broker', 'http_client', 'core', 'consumer', 'bundle',
                  'core_bindings', 'runtime', 'profile', 'episode', 'wire', 'owned'}
    need(set(rows) == {'reference', 'producer', 'pair_bindings', *('pair_' + n for n in pair_names),
                      *('baseline_' + n for n in BASELINE_PINS)}, 'Complete reference dependency closure')
    bodies = {}
    for name, row in rows.items():
        need(set(row) == {'path', 'bytes', 'sha256'} and type(row['path']) is str and
             row['path'].startswith('benchmarks/') and '..' not in Path(row['path']).parts and
             not Path(row['path']).is_absolute(), 'Repository-relative named dependency')
        expected_pin = {k: row[k] for k in ('bytes', 'sha256')}; descriptor(expected_pin, 131072)
        bodies[name] = read_source(root / row['path'], 131072, expected_pin)
    need(rows['reference']['path'] == RELATIVE + '/reference.py' and rows['producer']['path'] == RELATIVE + '/producer.py' and
         rows['pair_bindings']['path'] == 'benchmarks/neural/NEURAL-077/implementations/full32-provider-pair-v1/SOURCE_BINDINGS.json' and
         pin(bodies['pair_bindings']) == PAIR_BINDING, 'Selected unchanged paired interface')
    old = decode(bodies['pair_bindings'])['members']
    need(all(rows['pair_' + name] == row for name, row in old.items()), 'Paired source closure changed')
    baseline_paths = {'candidate': 'programme/erp_template.py', 'config': 'programme/config.json',
                      'manifest': 'BUNDLE_MANIFEST.json', 'method': 'METHOD.json'}
    for name, selected in BASELINE_PINS.items():
        need(rows['baseline_' + name]['path'] == BASELINE + '/' + baseline_paths[name] and
             pin(bodies['baseline_' + name]) == selected, 'Unchanged selected reference programme required')
    pair = load('erp_fixed_reference_pair', root / rows['pair_pair']['path'], bodies['pair_pair'])
    modules = pair.dependencies(PAIR_BINDING)
    modules.update(pair=pair, source_members=rows, source_binding_pin=pin(body), repository_root=root,
                   source_bodies=bodies, producer=load('erp_fixed_reference_producer', root / rows['producer']['path'], bodies['producer']))
    return modules


def validate_exposure(value):
    need(type(value) is dict and set(value) == {'schema', 'declared_authoring_inputs',
         'remaining32_query_or_answer_tuning_declared', 'six_person_feature_training_declared',
         'prior_ungraded_query_count', 'prior_query_labels_opened', 'programme_changed_since_prior_query',
         'pretraining_exposure', 'notes'}, 'Exact reference authoring/exposure declaration')
    need(value['schema'] == 'erp-full32-fixed-reference-exposure-v1' and
         type(value['declared_authoring_inputs']) is list and 1 <= len(value['declared_authoring_inputs']) <= 64 and
         all(type(x) is str and 0 < len(x) <= 512 for x in value['declared_authoring_inputs']) and
         value['remaining32_query_or_answer_tuning_declared'] is False and
         value['six_person_feature_training_declared'] is False and
         type(value['prior_ungraded_query_count']) is int and value['prior_ungraded_query_count'] == 1 and
         value['prior_query_labels_opened'] is False and value['programme_changed_since_prior_query'] is False and
         value['pretraining_exposure'] == 'unknown' and type(value['notes']) is str and 0 < len(value['notes']) <= 4096,
         'Prior ungraded query must remain explicit; no tuning or hidden-exposure proof')
    return value


def validate_contract(contract):
    need(type(contract) is dict and set(contract) == {'schema', 'selected', 'condition_id', 'condition', 'query_count', 'people',
         'public_root', 'public_manifest', 'roster', 'frozen_roster', 'programme', 'authoring_exposure', 'interpreter', 'sandbox',
         'limits', 'information_policy', 'metric_policy', 'source_bindings', 'adapter_sources', 'freeze_stage'}, 'Exact reference-only contract')
    need(contract['schema'] == 'erp-full32-fixed-reference-contract-v1' and contract['selected'] is True and
         contract['condition_id'] == 'erp-core-remaining-persons-released-marker-v1' and contract['condition'] == CONDITION and
         type(contract['query_count']) is int and contract['query_count'] == COUNT and
         type(contract['people']) is int and contract['people'] == PEOPLE and contract['information_policy'] == POLICY and
         contract['metric_policy'] == METRIC_POLICY and contract['freeze_stage'] == {'query_records_opened': 0},
         'Original full32 reference scope and metric policy')
    ordinary(contract['public_root']); descriptor(contract['public_manifest'], 1048576)
    descriptor(contract['roster'], 4 * 1024**2); descriptor(contract['source_bindings'], 16384)
    for name, cap in (('programme', 1048576), ('authoring_exposure', 16384), ('frozen_roster', 4 * 1024**2)):
        row = contract[name]
        need(type(row) is dict and set(row) == ({'path', 'file', 'bundle_identity'} if name == 'programme' else {'path', 'file'}),
             'Frozen selected operand')
        ordinary(row['path']); descriptor(row['file'], cap)
    descriptor(contract['programme']['bundle_identity'])
    need(contract['frozen_roster']['file'] == contract['roster'], 'Original full roster frozen exactly')
    for name in ('interpreter', 'sandbox'):
        row = contract[name]
        need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'}, 'Pinned runtime operand')
        ordinary(row['path']); descriptor({k: row[k] for k in ('bytes', 'sha256')}, 64 * 1024**2)
    need(contract['sandbox']['path'] == '/usr/bin/sandbox-exec', 'Unchanged supported macOS sandbox')
    validate_limits(contract['limits'])
    need(type(contract['adapter_sources']) is dict and bool(contract['adapter_sources']), 'Frozen source closure')
    return contract


def validate_limits(limits):
    need(type(limits) is dict and set(limits) == {'episode_work_seconds', 'episode_cleanup_seconds', 'campaign_seconds',
         'read_bytes', 'write_bytes'}, 'Finite explicit execution limits')
    for key, maximum in (('episode_work_seconds', 3600), ('episode_cleanup_seconds', 30), ('campaign_seconds', 2**31)):
        need(type(limits[key]) in (int, float) and math.isfinite(limits[key]) and 0 < limits[key] <= maximum, 'Finite selected clocks')
    need(limits['campaign_seconds'] > limits['episode_work_seconds'] + limits['episode_cleanup_seconds'] + 5, 'Whole/work/finalization margin')
    need(all(type(limits[k]) is int and 0 < limits[k] <= 1024**4 for k in ('read_bytes', 'write_bytes')), 'Finite byte limits')
    return limits


def verify_frozen(contract, modules, budget=None):
    validate_contract(contract); pair = modules['pair']
    need(contract['source_bindings'] == modules['source_binding_pin'] and contract['adapter_sources'] == modules['source_members'],
         'Reference source changed after freeze')
    programme = pair.read(contract['programme']['path'], 1048576, contract['programme']['file'], budget)
    frozen = decode(programme); client = modules['bundle'].verify(frozen)
    need(frozen['bundle_identity'] == contract['programme']['bundle_identity'], 'Frozen programme identity changed')
    need(frozen['manifest'] == decode(modules['source_bodies']['baseline_manifest']) and
         all({k: frozen['members'][name][k] for k in ('bytes', 'sha256')} == BASELINE_PINS[key]
             for name, key in (('erp_template.py', 'candidate'), ('config.json', 'config'))), 'Only unchanged baseline source/config')
    exposure = pair.read(contract['authoring_exposure']['path'], 16384, contract['authoring_exposure']['file'], budget)
    validate_exposure(decode(exposure))
    pair.read(contract['frozen_roster']['path'], 4 * 1024**2, contract['roster'], budget)
    return {'programme': programme, 'client': client, 'exposure': exposure}


def _public_metadata(root, manifest_pin, roster_pin, pair, budget=None):
    root = ordinary(root)
    manifest = decode(pair.read(root / 'PACKET.json', 1048576, manifest_pin, budget))
    need(manifest.get('schema') == 'erp-core-full32-public-packet-v1' and manifest.get('benchmark_id') == 'NEURAL-077' and
         manifest.get('condition_id') == 'erp-core-remaining-persons-released-marker-v1' and manifest.get('query_count') == COUNT and
         manifest.get('people') == PEOPLE and manifest.get('demonstration_count') == 4 and
         manifest.get('natural_class_prior_supplied') is False and manifest['files']['roster.json'] == roster_pin,
         'Original full32 input metadata')
    body = pair.read(root / 'roster.json', 4 * 1024**2, roster_pin, budget); roster = decode(body)
    need(type(roster) is list and len(roster) == COUNT and all(type(r) is dict and
         set(r) == {'trial_id', 'path', 'offset', 'bytes', 'sha256'} for r in roster), 'Complete original roster fields')
    ids = tuple(r['trial_id'] for r in roster)
    need(all(type(x) is str and re.fullmatch('q-[0-9a-f]{32}', x) for x in ids) and ids == tuple(sorted(set(ids))),
         'Complete sorted unique 6400 roster')
    return body, ids


def prequery_metadata(contract, modules, budget):
    body, ids = _public_metadata(contract['public_root'], contract['public_manifest'], contract['roster'], modules['pair'], budget)
    need(pin(body) == contract['frozen_roster']['file'], 'Full roster changed since pre-query freeze')
    return ids


def protected_roots(contract, modules):
    return (HERE, *((modules['repository_root'] / r['path']).parent for r in modules['source_members'].values()),
            Path(contract['public_root']).parent, Path(contract['programme']['path']).parent,
            Path(contract['authoring_exposure']['path']).parent, Path(contract['frozen_roster']['path']).parent)


def freeze(spec, output, modules=None):
    need(type(spec) is dict and set(spec) == {'schema', 'public_root', 'public_manifest', 'roster', 'programme_root',
         'programme_manifest', 'authoring_exposure', 'interpreter', 'sandbox', 'limits'} and
         spec['schema'] == 'erp-full32-fixed-reference-freeze-spec-v1', 'Exact provider-free freeze specification')
    limits = validate_limits(spec['limits']); descriptor(spec['public_manifest']); descriptor(spec['roster'], 4 * 1024**2)
    modules = dependencies() if modules is None else modules; pair = modules['pair']
    budget = pair.Budget(limits['read_bytes'], limits['write_bytes'], time.monotonic() + limits['campaign_seconds'])
    budget.input(4 * 1024**2)
    roots = (HERE, *((modules['repository_root'] / r['path']).parent for r in modules['source_members'].values()),
             Path(spec['public_root']).parent, Path(spec['programme_root']),
             Path(spec['programme_manifest']['path']).parent, Path(spec['authoring_exposure']['path']).parent)
    output = pair.disjoint_output(output, modules, roots)
    declaration_row = spec['programme_manifest']; exposure_row = spec['authoring_exposure']
    for row in (declaration_row, exposure_row):
        need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'}, 'Exact committed authoring operand')
        ordinary(row['path']); descriptor({k: row[k] for k in ('bytes', 'sha256')}, 65536)
    declaration = pair.read(declaration_row['path'], 65536, {k: declaration_row[k] for k in ('bytes', 'sha256')}, budget)
    need(pin(declaration) == BASELINE_PINS['manifest'], 'Unchanged baseline declaration')
    budget.input(BASELINE_PINS['candidate']['bytes'] + BASELINE_PINS['config']['bytes'])
    captured = modules['bundle'].capture(spec['programme_root'], decode(declaration))
    need(all({k: captured['members'][name][k] for k in ('bytes', 'sha256')} == BASELINE_PINS[key]
             for name, key in (('erp_template.py', 'candidate'), ('config.json', 'config'))), 'Unchanged baseline before query access')
    programme = modules['bundle'].encoded(captured)
    exposure = pair.read(exposure_row['path'], 16384, {k: exposure_row[k] for k in ('bytes', 'sha256')}, budget)
    validate_exposure(decode(exposure))
    roster, _ids = _public_metadata(spec['public_root'], spec['public_manifest'], spec['roster'], pair, budget)
    contract = {'schema': 'erp-full32-fixed-reference-contract-v1', 'selected': True,
        'condition_id': 'erp-core-remaining-persons-released-marker-v1', 'condition': CONDITION, 'query_count': COUNT, 'people': PEOPLE,
        **{k: spec[k] for k in ('public_root', 'public_manifest', 'roster', 'interpreter', 'sandbox', 'limits')},
        'frozen_roster': {'path': str(output / 'ROSTER.json'), 'file': pin(roster)},
        'programme': {'path': str(output / 'PROGRAMME.json'), 'file': pin(programme), 'bundle_identity': captured['bundle_identity']},
        'authoring_exposure': {'path': str(output / 'EXPOSURE.json'), 'file': pin(exposure)},
        'information_policy': POLICY, 'metric_policy': METRIC_POLICY,
        'source_bindings': modules['source_binding_pin'], 'adapter_sources': modules['source_members'],
        'freeze_stage': {'query_records_opened': 0}}
    validate_contract(contract)
    pair.executable(contract['interpreter'], budget); pair.executable(contract['sandbox'], budget)
    output.mkdir(mode=0o700)
    pair.write(output / 'ROSTER.json', roster, budget); pair.write(output / 'PROGRAMME.json', programme, budget)
    pair.write(output / 'EXPOSURE.json', exposure, budget)
    selected = pair.write(output / 'CONTRACT.json', encode(contract), budget)
    return {'status': 'full32_reference_frozen_before_queries', 'contract': selected, 'query_records_opened': 0,
            'bundle_identity': captured['bundle_identity'], 'prior_ungraded_query_count': 1}


def validate_reference_header(receipt, contract_pin, contract, modules=None):
    modules = dependencies(contract['source_bindings']) if modules is None else modules
    need(receipt.get('reference_scope') == 'full32_fixed_reference_only', 'Independent fixed-reference scope required')
    modules['pair'].verify_arm_header(receipt, CONDITION, contract_pin, contract)
    ids = [row.get('trial_id') for row in receipt['episodes']]
    need(all(type(x) is str and re.fullmatch('q-[0-9a-f]{32}', x) for x in ids) and
         len(set(ids)) == COUNT and ids == sorted(ids) and all(row.get('status') == 'ok' for row in receipt['episodes']),
         'Every unique first response and successful episode required')
    return receipt


def checked_metric_rows(predictions, people, core):
    """Pure coverage check around unchanged metrics; no file/target access."""
    need(type(predictions) is dict and type(people) is dict and people, 'Nonempty admitted predictions/person panel')
    identifiers = [identifier for rows in people.values() for identifier, _label in rows]
    need(len(identifiers) == len(set(identifiers)) and set(identifiers) == set(predictions),
         'Every admitted prediction must join exactly one retained person')
    return core.metric_rows(predictions, people)


def _ordered_metrics(admit_reference, load_people, core):
    """Internal ordering seam. Test authority uses only generated memory callbacks.

    This helper has no production status, path, count mode or original-label
    loader. The production entry below binds strict real admission and private
    join itself; tests cannot configure that entry to accept a reduced cohort.
    """
    predictions = admit_reference()
    people = load_people(set(predictions))
    return checked_metric_rows(predictions, people, core)


def evaluate_reference(contract, contract_pin, arm, private_material_descriptor, output, *, modules=None):
    validate_contract(contract); need(pin(encode(contract)) == contract_pin, 'Frozen reference contract changed')
    modules = dependencies(contract['source_bindings']) if modules is None else modules; pair = modules['pair']
    deadline = time.monotonic() + contract['limits']['campaign_seconds']
    budget = pair.Budget(contract['limits']['read_bytes'], contract['limits']['write_bytes'], deadline)
    budget.input(3 * 384000000 + 4 * 1024**2)
    verify_frozen(contract, modules, budget)
    need(type(arm) is dict and set(arm) == {'root', 'receipt'}, 'One complete reference arm descriptor')
    root = ordinary(arm['root']); output = pair.disjoint_output(output, modules, (*protected_roots(contract, modules), root))
    validate_reference_header(decode(pair.read(root / 'ARM.json', 4 * 1024**2, arm['receipt'], budget)), contract_pin, contract, modules)
    expected_ids = prequery_metadata(contract, modules, budget)
    with modules['consumer'].PacketSession(contract['public_root'], contract['public_manifest']) as session:
        need(tuple(session.trial_ids) == expected_ids and len(session.trial_ids) == COUNT, 'Original full6400 cohort only')
        def admit():
            values = pair.admit_program_arm(arm, contract, contract_pin, session, modules, budget, deadline)
            need(len(values) == COUNT and set(values) == set(expected_ids), 'Complete immutable first predictions')
            return values
        def labels(ids):
            need(budget.read + 16 * 1024**2 <= budget.read_limit, 'Private join bounded read headroom')
            private = private_material_descriptor() if callable(private_material_descriptor) else private_material_descriptor
            private_root = ordinary(private['root'])
            need(not output.is_relative_to(private_root) and not private_root.is_relative_to(output), 'Separate protected result output')
            old_budget = {'read': 0}
            try:
                people = modules['core'].load_private_people(private, contract['public_manifest'], ids, old_budget)
            finally:
                budget.input(old_budget['read'])
            need(len(people) == PEOPLE and all(len(rows) == 200 for rows in people.values()), 'All original32 people required')
            return people
        scores = _ordered_metrics(admit, labels, modules['core'])
    result = {'schema': 'erp-full32-fixed-reference-evaluation-v1', 'status': 'complete_fixed_reference_finite_cohort',
        'people': PEOPLE, 'queries': COUNT, 'scores': scores, 'contract': contract_pin, 'reference_arm_receipt': arm['receipt'],
        'metric_policy': METRIC_POLICY, 'all_reference_first_responses_and_known_closures_validated_before_private': True,
        'programme_identity': contract['programme']['bundle_identity'], 'authoring_exposure': contract['authoring_exposure']['file'],
        'prior_ungraded_query_count': 1, 'baseline_changed_after_prior_query': False,
        'source_evidence': {'reference_bindings': contract['source_bindings'], 'original_grader': modules['source_members']['pair_core']},
        'read_bytes_charged': budget.read, 'provider_calls': 0, 'direct_arm_claim': False, 'paired_result_claim': False,
        'calibration_qualified': False, 'physiological_P3_presence_claim': False, 'new_benchmarks': 0,
        'outer_campaign_and_resource_qualification_required': True, 'uncertainty_endpoint': None}
    output.mkdir(mode=0o700); pair.write(output / 'RESULT.json', encode(result), budget)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__); commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('freeze'); p.add_argument('--spec', required=True)
    p.add_argument('--spec-bytes', required=True, type=int); p.add_argument('--spec-sha256', required=True); p.add_argument('--output', required=True)
    for name in ('run-reference', 'evaluate-reference'):
        p = commands.add_parser(name); p.add_argument('--contract', required=True)
        p.add_argument('--contract-bytes', required=True, type=int); p.add_argument('--contract-sha256', required=True)
        p.add_argument('--output', required=True)
        if name == 'evaluate-reference':
            p.add_argument('--arm', required=True); p.add_argument('--private-material', required=True)
    args = parser.parse_args(argv)
    if args.command == 'freeze':
        selected = {'bytes': args.spec_bytes, 'sha256': args.spec_sha256}; descriptor(selected, 65536)
        result = freeze(decode(read_source(args.spec, 65536, selected)), args.output)
    else:
        selected = {'bytes': args.contract_bytes, 'sha256': args.contract_sha256}; descriptor(selected, 65536)
        contract = decode(read_source(args.contract, 65536, selected))
        if args.command == 'run-reference':
            modules = dependencies(contract['source_bindings'])
            result = modules['producer'].run_reference(sys.modules[__name__], contract, selected, args.output, modules=modules)
        else:
            arm = decode(read_source(args.arm, 65536))
            result = evaluate_reference(contract, selected, arm, lambda: decode(read_source(args.private_material, 65536)), args.output)
    print(json.dumps({'status': result['status'], 'output': args.output}, sort_keys=True))


if __name__ == '__main__':
    main()
