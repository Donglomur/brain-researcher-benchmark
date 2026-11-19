"""One admitted original Figure3b author reference; no alternative executor.

This entry runs the fixed source-author programme through the maintained native
provider and verifies its full lifecycle before unchanged original recovery.
It is operator calibration, never either AI access arm or full224 reproduction.
Importing this module uses only the standard library and performs no execution.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time
import types

ROLE = 'executed_author_reference'
CONDITION = 'paper_data_author_code'
TOKEN = 'execute-admitted-original-author-reference'
SCHEMA = 'language-original-author-reference-protocol/v1'
ADMISSION_SCHEMA = 'language-original-author-reference-admission/v1'
CENSUS = '3d2d46bbc6534b282f97d29c51b1961c8d284cf7a9894839fb851550b7549e37'
AUTHOR = {'bytes': 850, 'sha256': '7e806fb885dbba39bb6a4424134374e0d9dc9b405efe31b3c13ee2c517573bbb'}
PAIR = {'bytes': 22851, 'sha256': 'c5da4304846f65c89a01fc3b5d22d0a4adf07fce32729db1f0e0e92dab1e4380'}
PAIR_SOURCE = {'bytes': 14073, 'sha256': 'a96429fef0bc11cd6826f2224af31e59e091206e7a54ea8ecd6c9fe21699e587'}
ENTRY = {'bytes': 8378, 'sha256': 'da65bd364986d33650e0a4cb84efb653ecff9e8f986bcff5ea56f100d8484a68'}
PROTOCOL_KEYS = {
    'schema', 'selected_for_execution', 'role', 'entry_sha256', 'task_home',
    'store_root', 'store_sha256', 'schedule_sha256', 'source_support_sha256',
    'output_root', 'provider_config', 'provider_admission', 'limits',
    'store_read_limit', 'store_working_limit', 'extra_read_limit',
    'reference_working_limit', 'preflight_tree_read_limit', 'output_limit',
    'wall_seconds', 'numpy_version', 'operator_joint_admission_bytes',
    'external_hard_deadline_required', 'qualification_sha256',
}
ADMISSION_KEYS = {'schema', 'protocol_sha256', 'entry_sha256',
                  'root_admission_id', 'expires_unix', 'wall_seconds'}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def parse(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'Nonfinite JSON'))


def digest(value):
    need(type(value) is str and len(value) == 64
         and all(c in '0123456789abcdef' for c in value), 'Exact SHA256')
    return value


def ordinary(path):
    need(type(path) is str and 0 < len(path) <= 4096 and Path(path).is_absolute(),
         'Explicit absolute ordinary path')
    result = Path(path)
    need(str(result) == path and '..' not in result.parts, 'Canonical absolute spelling without parent traversal')
    need(not any(p.is_symlink() for p in (result, *result.parents)), 'No path aliases')
    return result


def read_pinned(path, expected, cap):
    path = ordinary(str(path)); digest(expected['sha256'])
    need(type(expected.get('bytes')) is int and 0 < expected['bytes'] <= cap,
         'Bounded exact source/metadata extent before read')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        stamp = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and before.st_size == expected['bytes'], 'Exact ordinary file identity')
        raw = stream.read(expected['bytes']+1)
        need(len(raw) == expected['bytes'] and sha(raw) == expected['sha256']
             and stamp(before) == stamp(os.fstat(stream.fileno())) == stamp(path.lstat()),
             'Stable complete source/metadata authentication')
    return raw


def read_json(path, expected_sha256):
    path = ordinary(str(path)); size = path.lstat().st_size
    raw = read_pinned(path, {'bytes': size, 'sha256': expected_sha256}, 262144)
    value = parse(raw)
    need(encoded(value) == raw, 'Canonical externally pinned JSON')
    return value


def load_maintained(task_home):
    """Authenticate exact existing implementation bytes; never an injected provider."""
    home = ordinary(task_home)/'implementations'
    pairing = home/'original-author-pairing-v1'
    read_pinned(pairing/'SOURCE.json', PAIR_SOURCE, 32768)
    read_pinned(pairing/'author_programme.py', AUTHOR, 1024)
    read_pinned(home/'original-exec-provider-v1/participant_entry.py', ENTRY, 16384)
    raw = read_pinned(pairing/'paired.py', PAIR, 32768)
    name = '_language_original_author_reference_paired'
    module = types.ModuleType(name)
    module.__file__, module.__package__ = str(pairing/'paired.py'), ''
    previous = sys.modules.get(name); sys.modules[name] = module
    try:
        exec(compile(raw, module.__file__, 'exec', dont_inherit=True), module.__dict__)
        reference, descriptor = module.load_component(PAIR_SOURCE['sha256'])
        need(descriptor['files']['author_programme.py'] == AUTHOR,
             'Unchanged literal source-author programme')
        e, reader, provider = reference.load_stack(task_home)
        return module, reference, e, reader, provider
    except BaseException:
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous
        raise


def validate_protocol(p, admission, entry_sha256, e, provider, *, now):
    need(type(p) is dict and set(p) == PROTOCOL_KEYS and p['schema'] == SCHEMA,
         'Exact one-role author-reference protocol')
    need(p['selected_for_execution'] is True and p['role'] == ROLE,
         'Explicit original author-reference selection; no generated or participant override')
    need(type(admission) is dict and set(admission) == ADMISSION_KEYS
         and admission['schema'] == ADMISSION_SCHEMA
         and admission['protocol_sha256'] == sha(encoded(p))
         and admission['entry_sha256'] == p['entry_sha256'] == digest(entry_sha256),
         'Independent exact protocol/entry admission')
    need(type(admission['root_admission_id']) is str and 0 < len(admission['root_admission_id']) <= 128,
         'Explicit root admission identity')
    need(type(p['wall_seconds']) is int and 1 <= p['wall_seconds'] <= 86400
         and admission['wall_seconds'] == p['wall_seconds']
         and type(admission['expires_unix']) is int
         and admission['expires_unix'] >= now+p['wall_seconds']
         and p['external_hard_deadline_required'] is True,
         'Finite complete externally enforced original-operation deadline')
    for key in ('store_sha256', 'schedule_sha256', 'source_support_sha256', 'qualification_sha256'):
        digest(p[key])
    need(p['source_support_sha256'] == CENSUS and p['numpy_version'] == '1.24.3'
         and e.np.__version__ == p['numpy_version'], 'Original support and exact scoring runtime')
    limits = e.limits_snapshot(p['limits'])
    for key in ('store_read_limit', 'store_working_limit', 'extra_read_limit',
                'reference_working_limit', 'preflight_tree_read_limit', 'output_limit'):
        need(type(p[key]) is int and 0 < p[key] <= 2**34, 'Finite allowance: '+key)
    need(256*1024**2 <= p['reference_working_limit'] <= 1024**3
         and p['output_limit'] <= 16*1024**2 and p['extra_read_limit'] <= 16*1024**2,
         'Bounded reference recovery workspace and metadata')
    config = provider.config_snapshot(p['provider_config'])
    need(config['condition'] == CONDITION and config['mode'] == 'exec_reset_bwrap_v1'
         and config['provider_source_sha256'] == provider.identity()
         and config['store_sha256'] == p['store_sha256']
         and config['schedule_sha256'] == p['schedule_sha256']
         and config['caps']['max_jobs'] == 42 and config['caps']['max_requests'] == 5685,
         'Exactly one original full42/5685 fresh-exec author schedule')
    native = provider.admission_snapshot(config, p['provider_admission'])
    need(native['qualification_sha256'] == p['qualification_sha256']
         and native['admitted_until_unix'] >= admission['expires_unix'],
         'Existing genuine native qualification/admission covers this complete operation')
    roots = [ordinary(p[k]) for k in ('task_home', 'store_root', 'output_root')]
    roots += [ordinary(config[k]['root']) for k in ('runtime', 'candidate', 'assistance')]
    need(all(a != b and a not in b.parents and b not in a.parents
             for i, a in enumerate(roots) for b in roots[i+1:]), 'Disjoint source/store/output/native material roots')
    output = roots[2]
    need(not output.exists(), 'Fresh full original-operation output root')
    for kind in ('runtime', 'candidate', 'assistance'):
        manifest = ordinary(config[kind]['manifest'])
        need(output != manifest and output not in manifest.parents and manifest not in output.parents,
             'Output cannot overlap any authenticated native manifest')
    joint = (3*limits['working_bytes']+limits['cache_working_bytes']+p['store_working_limit']
             +p['reference_working_limit']+config['caps']['working_bytes'])
    need(type(p['operator_joint_admission_bytes']) is int
         and joint <= p['operator_joint_admission_bytes'] <= 2**34,
         'Additive complete operator memory admission, not measured RSS')
    need(p['wall_seconds'] >= config['caps']['run_seconds']+2*limits['wall_seconds'],
         'Provider and both recovery-stage cooperative ceilings fit the outer deadline')
    return parse(encoded(p)), config


def authenticate_author_trees(p, config, pairing, reference, provider):
    """Only the literal author file and empty assistance; no arbitrary programme."""
    meter = reference.Meter(p['extra_read_limit']); manifests = {}
    for kind in ('candidate', 'assistance'):
        desc = config[kind]; path = Path(desc['manifest'])
        raw = reference.owned_bytes(path, {'bytes': path.stat().st_size, 'sha256': desc['manifest_sha256']}, 262144, meter)
        doc = reference.parse(raw)
        need(type(doc) is dict and set(doc) == {'schema', 'kind', 'condition', 'directories', 'files'}
             and doc['kind'] == kind and doc['condition'] == CONDITION,
             'Exact source-author material kind/information condition')
        pairing.file_records(doc['files'])
        expected = [dict(path='candidate.py', mode=0o444, **AUTHOR)] if kind == 'candidate' else []
        need(doc['files'] == expected and doc['directories'] == [],
             'Only the exact author candidate.py and empty assistance are admitted')
        manifests[kind] = doc
    one = {'roles': [{'role': ROLE, 'config': config}],
           'preflight_tree_read_limit': p['preflight_tree_read_limit']}
    tree_reads = pairing.preflight_trees(one, provider, {ROLE: manifests})
    return {'manifest_read_bytes': meter.used, 'tree_read_bytes': tree_reads}


def _execute_one(p, config, reference, e, reader_module, provider_module, root, live):
    """Private orchestration seam for generated call-order/failure controls.

    Public execution always supplies load_maintained's authenticated modules.
    Tests may supply synthetic doubles here; such calls are not original results.
    No provider factory or arbitrary module is accepted by the CLI/protocol.
    """
    native = reader = None
    try:
        live()
        native = provider_module.NativeProvider(config, p['provider_admission'], evidence_root=root/'provider')
        reader = reader_module.StoreReader(p['store_root'], expected_store_sha256=p['store_sha256'],
            read_limit=p['store_read_limit'], working_limit=p['store_working_limit'])
        run = e.J.make_run(store_sha256=p['store_sha256'], candidate_sha256=config['candidate_sha256'],
            schedule_sha256=p['schedule_sha256'], provider_source_sha256=config['provider_source_sha256'],
            condition=CONDITION, working_limit=p['limits']['working_bytes'])
        collection, pin = e.collect(reader, native, run, root/'collection', limits=p['limits'])
        reader = native = None
        need(collection.get('jobs') == 42 and collection.get('software_callbacks') == 5685
             and collection['provider']['admission'] == p['provider_admission'],
             'Complete collection and exact original native admission before recovery')
        live()
        product = reference.recover_executed(e, reader_module, run, collection,
            {'bytes': pin['bytes'], 'sha256': pin['sha256']}, ROLE, config,
            store_root=p['store_root'], output_root=root/'collection', evidence_root=root/'provider',
            store_limit=p['store_read_limit'], store_working=p['store_working_limit'], limits=p['limits'],
            support_sha256=p['source_support_sha256'], extra_read_limit=p['extra_read_limit'],
            working_limit=p['reference_working_limit'])
        live()
        return reference.snapshot(product)
    finally:
        e.close_owned(native, reader)


def run_original(p, admission, entry_sha256):
    # Disabled templates refuse before loading numpy, provider code or inputs.
    need(type(p) is dict and p.get('selected_for_execution') is True and p.get('role') == ROLE,
         'Original execution is unselected')
    own = Path(__file__)
    read_pinned(own, {'bytes': own.lstat().st_size, 'sha256': entry_sha256}, 65536)
    pairing, reference, e, reader, provider = load_maintained(p['task_home'])
    p, config = validate_protocol(p, admission, entry_sha256, e, provider, now=time.time())
    preflight = authenticate_author_trees(p, config, pairing, reference, provider)
    provider.LinuxBackend.require_platform()  # Before target reads/output/native creation.
    root = ordinary(p['output_root']); root.mkdir(mode=0o700)
    started = time.monotonic(); deadline = started+p['wall_seconds']; written = 0
    def live():
        need(started <= time.monotonic() < deadline, 'Post-preflight one-role deadline; caller bounds the whole entry')
    def publish(name, value):
        nonlocal written
        raw = encoded(value)
        need(written+len(raw) <= p['output_limit'], 'Cumulative one-role result allocation')
        # Reserve before publication; partial writes or fsync failure stay charged.
        written += len(raw)
        with (root/name).open('xb') as stream:
            need(stream.write(raw) == len(raw), 'Complete one-role receipt publication')
            stream.flush(); os.fsync(stream.fileno())
    try:
        product = _execute_one(p, config, reference, e, reader, provider, root, live)
        need(product.get('schema') == 'language-executed-selected-product/v1'
             and product.get('role') == ROLE and product.get('information_condition') is None,
             'Only the verified original operator-reference product is publishable')
        result = {'schema': 'language-original-author-reference-result/v1',
            'protocol_sha256': sha(encoded(p)), 'entry_sha256': entry_sha256,
            'role': ROLE, 'operator_calibration_not_AI': True, 'jobs': 42,
            'software_callbacks': 5685, 'fresh_exec_invocations_required': 5685,
            'product': product, 'preflight': preflight,
            'provided_author_reference_untouched': True,
            'full_224_array_reproduction_executed': False,
            'scientific_qualification': False, 'binary_win': None, 'current_sota': False,
            'declared_costs': {'source_reader_traversals': 3,
                'source_reader_read_ceiling_bytes': 3*p['store_read_limit'],
                'extra_metadata_read_ceiling_bytes': 2*p['extra_read_limit'],
                'additional_preflight_tree_read_ceiling_bytes': p['preflight_tree_read_limit'],
                'operator_joint_admission_bytes': p['operator_joint_admission_bytes'],
                'external_hard_deadline_required': True,
                'separate_counters': ['source/bootstrap imports', 'cache/frozen/dispatched bundles',
                    'provider trees/features/kernel/staging/pipes/journals',
                    'two authority-reader traversals', 'one packed recovery', 'phase receipts']},
            'limits': ['Source retrospective preprocessing/public exposure unchanged.',
                'No supplied-reference numerical comparison, AI execution or superiority is claimed here.',
                'Full224 results, historical exact replay and 567/579 identity remain separate.']}
        live(); publish('AUTHOR_REFERENCE.json', result)
        return result
    except BaseException as exc:
        try:
            publish('AUTHOR_REFERENCE_FAILURE.json', {'schema': 'language-original-author-reference-failure/v1',
                'protocol_sha256': sha(encoded(p)), 'error_type': type(exc).__name__,
                'error': str(exc)[:512], 'complete': False, 'scientific_qualification': False})
        except BaseException:
            pass
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('protocol', 'protocol-sha256', 'admission', 'admission-sha256', 'entry-sha256', 'execute-admitted-native'):
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args(argv)
    need(args.execute_admitted_native == TOKEN, 'Exact original execution token')
    p, admission = read_json(args.protocol, args.protocol_sha256), read_json(args.admission, args.admission_sha256)
    result = run_original(p, admission, args.entry_sha256)
    print(json.dumps({'schema': result['schema'], 'role': ROLE, 'jobs': 42,
        'software_callbacks': 5685, 'operator_calibration_not_AI': True,
        'result_path': str(Path(p['output_root'])/'AUTHOR_REFERENCE.json')}))


if __name__ == '__main__':
    main()
