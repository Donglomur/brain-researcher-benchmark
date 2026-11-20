#!/usr/bin/env python3
"""Portable SMC full-panel preparation, retained-owner execution and protected grade.

Run benchmark.py first to export materials and freeze both methods. This trusted
operator entry accepts explicit material/deployment bindings; it does not create
runtime qualification, provision an image/cgroup, or authorize native execution.
Preparation never launches. Execution replaces this process with the unchanged,
authenticated retained-owner CLI in a fresh Python interpreter. Protected grading
uses a fixed authenticated bounded supervisor and the unchanged private grader.
Source selection alone does not qualify physical runtime containment.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys

HERE = Path(__file__).resolve().parent
COMPONENT_REL = Path('benchmarks/paper/PAPER-SMC-RNN-2024/implementations/full-panel-improvement-v1')
OWNER_REL = Path('benchmarks/paper/PAPER-SMC-RNN-2024/implementations/aggregate-owner-v1')
CONDITIONS = ('paper_data', 'paper_data_author_code_and_weights')
META_CAP = 1024**2
PREPARE_SCHEMA = 'smc_full_panel_public_prepare_v1'
PREPARED_SCHEMA = 'smc_full_panel_public_prepared_v1'
OWNER_SOURCE = {'bytes': 7569, 'sha256': '44026e04ca813e3a22a893b848c2249d642559c49d75d76e3173fa1966e27a86'}
EPISODE_SOURCE = {'bytes': 1485, 'sha256': '3057a8d8f292e299df9dcc66b6efddea6f6233304363c19b90a86fb0aef9696a'}
GRADE_SOURCE = {'bytes': 747, 'sha256': '3948ff68fa412d92b17e484b5f7bd82a07a3e2b4dd6f698dc157cf3aed67c53c'}
GRADE_FILES = {'grade_bound.py', 'grade_child.py', 'owned_exit.py', 'bounded_capture.py', 'label_policy.py'}
STATIC = {
    'benchmark.py': (43093, '2da9e6ee5c8cc47fd5440a3edbc3eeb275020359f6f7fd5d456c6f86d2c96b4f'),
    'full_panel_episode.py': (41057, '7becc1746b068699070bc28f16286246427233e1a0082274b01a6ad75bcf8c3a'),
    'full_panel_worker.py': (4726, 'c9bcc169882d9270812ed3c33b52599c9c0b73d13665d514f2d93904a3e5d8ff'),
    'owner_overlay.py': (6189, '0c21765d8d0168201688566e9a32efb8f6a233dedc3fc80be9e81678abb29cf3'),
    'owner_legacy.py': (2637, '472a06c537f86c5b4e3f01cfa38f801262707692c639f6860bd6309b6327b7fd'),
    'RUNTIME_BINDING.json': (683, 'c2f3ba80a445889aa5e241e300acc9e1f5d64d55f96d22b47237b9061581fdab'),
    'task.json': (5474, '5b3b1008cca8f9106a5031ee9f15dfd028bd11121912316bd1fe788a32580c88'),
    'policy.json': (15519, 'f383e252c52fab1681451cd9247acb324d8ac7588099476155ce03fd92d2e75e'),
}
RUNTIME_FILES = {'full_panel_episode.py', 'full_panel_worker.py', 'owner_overlay.py', 'owner_legacy.py',
                 'RUNTIME_BINDING.json', 'MATERIAL_BINDING.json', 'DEPLOYMENT_BINDING.json'}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def fixed(name):
    size, digest = STATIC[name]
    return {'bytes': size, 'sha256': digest}


def sha(value):
    need(type(value) is str and re.fullmatch('[0-9a-f]{64}', value) and value != '0' * 64,
         'Exact nonzero SHA256 required')
    return value


def path(value):
    p = Path(value)
    need(p.is_absolute() and str(p) == str(value) and '..' not in p.parts
         and not any(q.is_symlink() for q in (p, *p.parents)), 'Canonical unlinked absolute path required')
    return p


def descriptor(row):
    need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'}
         and type(row['bytes']) is int and 0 < row['bytes'] <= META_CAP, 'Bounded exact metadata descriptor required')
    path(row['path']); sha(row['sha256'])
    return row


def body(filename, expected=None):
    p = path(filename)
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    with os.fdopen(fd, 'rb') as stream:
        a = os.fstat(stream.fileno())
        need(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and 0 < a.st_size <= META_CAP,
             'Ordinary bounded single-link metadata/source required')
        raw = stream.read(META_CAP + 1)
        b, c = os.fstat(stream.fileno()), p.lstat()
    fields = ('st_dev', 'st_ino', 'st_size', 'st_mode', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')
    need(len(raw) == a.st_size and all(getattr(a, k) == getattr(b, k) == getattr(c, k) for k in fields),
         'Stable complete named source/metadata required')
    if expected is not None:
        need(pin(raw) == {k: expected[k] for k in ('bytes', 'sha256')}, 'Authenticated source/metadata bytes changed')
    return raw


def decode(raw):
    def unique(items):
        out = {}
        for key, value in items:
            need(key not in out, 'Duplicate JSON keys forbidden')
            out[key] = value
        return out
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: need(False, 'Finite JSON required'))


def reference(filename):
    return {'path': str(path(filename)), **pin(body(filename))}


def checked(row):
    descriptor(row)
    return decode(body(row['path'], row))


def publish(filename, value):
    p = path(filename)
    raw = value if type(value) is bytes else encoded(value)
    need(0 < len(raw) <= META_CAP and p.parent.is_dir(), 'Bounded publication under an existing parent required')
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    return {'path': str(p), **pin(raw)}


def module(name, filename, expected):
    raw = body(filename, expected)
    spec = importlib.util.spec_from_file_location(name, filename)
    result = importlib.util.module_from_spec(spec)
    exec(compile(raw, str(filename), 'exec'), result.__dict__)
    return result


def repository(value):
    root = path(value if value is not None else HERE.parents[4])
    need(root.is_dir(), 'Existing repository root required')
    return root


def outside(output, inputs):
    output = path(output)
    need(not output.exists() and output.parent.is_dir(), 'Fresh output under an existing parent required')
    need(not any((q / '.git').exists() for q in (output.parent, *output.parent.parents)),
         'Preparation output must be outside Git')
    for source in inputs:
        source = path(source)
        need(not output.is_relative_to(source) and not source.is_relative_to(output),
             'Output must be disjoint from every selected source/input root')
    return output


def validate_request(request):
    need(type(request) is dict and set(request) == {'schema', 'pair', 'material_binding', 'deployment_binding',
         'runtime', 'methods', 'output', 'max_component_bytes', 'max_overlay_bytes'}
         and request['schema'] == PREPARE_SCHEMA, 'Exact public preparation request required')
    for name in ('pair', 'material_binding', 'deployment_binding', 'runtime'):
        descriptor(request[name])
    need(type(request['methods']) is dict and set(request['methods']) == set(CONDITIONS),
         'Both independently frozen access-condition methods required')
    for selected in request['methods'].values():
        descriptor(selected)
    for name in ('max_component_bytes', 'max_overlay_bytes'):
        need(type(request[name]) is int and 0 < request[name] <= 16 * 1024**2,
             'Finite positive preparation byte caps required')
    path(request['output'])
    return request


def component_plan(repo, request):
    """Read only fixed public source and explicitly supplied trusted bindings."""
    source = repo / COMPONENT_REL
    files = {name: body(source / name, fixed(name)) for name in STATIC}
    for key, filename in (('material_binding', 'MATERIAL_BINDING.json'),
                          ('deployment_binding', 'DEPLOYMENT_BINDING.json')):
        files[filename] = body(request[key]['path'], request[key])
    manifest = {'schema': 'smc_full_panel_runtime_source_v1', 'route': 'smc_full_panel_aggregate_v1',
                'files': {name: pin(files[name]) for name in sorted(RUNTIME_FILES)},
                'continuous_benchmark': fixed('benchmark.py'), 'retained_episode_source': EPISODE_SOURCE}
    files['RUNTIME_SOURCE.json'] = encoded(manifest)
    need(sum(map(len, files.values())) <= request['max_component_bytes'], 'Complete component exceeds selected byte cap')
    return files


def episode(repo, component):
    facade = module('_smc_public_episode', component / 'full_panel_episode.py', fixed('full_panel_episode.py'))
    return facade.FullPanelEpisode(repo, component)


def prepare(request_path, request_sha256, *, repository_root=None):
    """Prepare private siblings without runner import, invocation, or native launch."""
    repo = repository(repository_root)
    request_path = path(request_path); sha(request_sha256)
    raw = body(request_path)
    need(pin(raw)['sha256'] == request_sha256, 'Selected preparation request changed')
    request = validate_request(decode(raw))
    # Authenticate every selected metadata body before creating the output root.
    for name in ('pair', 'material_binding', 'deployment_binding', 'runtime'):
        checked(request[name])
    for selected in request['methods'].values():
        checked(selected)
    input_roots = [repo, request_path.parent, path(request['pair']['path']).parent]
    input_roots.extend(path(row['path']).parent for row in request['methods'].values())
    input_roots.extend(path(request[name]['path']).parent for name in ('material_binding', 'deployment_binding', 'runtime'))
    root = outside(request['output'], input_roots)
    files = component_plan(repo, request)
    root.mkdir(mode=0o700)
    inputs = root / 'inputs'; inputs.mkdir(mode=0o700)
    selected_request = publish(inputs / 'PREPARE_REQUEST.json', raw)
    component = root / 'component'; component.mkdir(mode=0o700)
    for name, data in sorted(files.items()):
        publish(component / name, data)
    L = episode(repo, component)
    material = L.material_binding()  # Shipped unavailable placeholders fail here.
    need(material['new_pair'] == {k: request['pair'][k] for k in ('bytes', 'sha256')},
         'Explicit selected material binding must match the authenticated pair')
    runtime = L.runtime_config(checked(request['runtime']))  # Metadata admission, not full Linux qualification.
    L.public_context(request['pair']['path'], component / 'task.json')
    methods = {condition: {'path': row['path'], 'sha256': row['sha256']}
               for condition, row in request['methods'].items()}
    L.instantiate(request['pair']['path'], component / 'task.json', methods,
                  request['runtime']['path'], request['runtime']['sha256'], root / 'protocol')
    overlay_module = module('_smc_public_overlay', component / 'owner_overlay.py', fixed('owner_overlay.py'))
    overlay = overlay_module.build_overlay(repo, root / 'overlay', max_bytes=request['max_overlay_bytes'])
    owner_entry = path(overlay['path']) / 'runner.py'
    record = {'schema': PREPARED_SCHEMA, 'repository_root': str(repo), 'root': str(root),
        'entrypoint': reference(Path(__file__).absolute()), 'request': selected_request,
        'component_source': reference(component / 'RUNTIME_SOURCE.json'),
        'protocol': reference(root / 'protocol' / 'PROTOCOL.json'),
        'overlay_source': reference(owner_entry.parent / 'SOURCE.json'), 'owner_entry': reference(owner_entry),
        'execution_root': str(root / 'execution'), 'owner_root': str(root / 'owner'),
        'runtime_qualification': runtime['qualification'],
        'preparation_launched_processes': False, 'native_execution_performed': False,
        'runtime_qualified_by_preparation': False, 'private_target_accessed': False}
    prepared = publish(root / 'PREPARED.json', record)
    inspect_prepared(prepared['path'], prepared['sha256'], repository_root=repo)
    return prepared


def inspect_prepared(prepared_path, prepared_sha256, *, repository_root=None):
    """Authenticate preparation, source, metadata and frozen methods; no launch."""
    repo = repository(repository_root)
    prepared_path = path(prepared_path); sha(prepared_sha256)
    raw = body(prepared_path)
    need(pin(raw)['sha256'] == prepared_sha256, 'Selected prepared record changed')
    record = decode(raw)
    keys = {'schema', 'repository_root', 'root', 'entrypoint', 'request', 'component_source', 'protocol',
            'overlay_source', 'owner_entry', 'execution_root', 'owner_root', 'runtime_qualification',
            'preparation_launched_processes', 'native_execution_performed',
            'runtime_qualified_by_preparation', 'private_target_accessed'}
    need(type(record) is dict and set(record) == keys and record['schema'] == PREPARED_SCHEMA,
         'Exact prepared record required')
    root = path(record['root'])
    need(prepared_path == root / 'PREPARED.json' and record['repository_root'] == str(repo),
         'Same selected private preparation and repository')
    need(all(record[k] is False for k in ('preparation_launched_processes', 'native_execution_performed',
             'runtime_qualified_by_preparation', 'private_target_accessed')),
         'Preparation cannot assert execution, qualification or target access')
    need(record['entrypoint'] == reference(Path(__file__).absolute()), 'Same public entrypoint source')
    need(record['request']['path'] == str(root / 'inputs' / 'PREPARE_REQUEST.json'), 'Exact sibling input snapshot')
    request = validate_request(checked(record['request']))
    need(path(request['output']) == root, 'Preparation output remains selected')
    for name in ('pair', 'material_binding', 'deployment_binding', 'runtime'):
        checked(request[name])
    for selected in request['methods'].values():
        checked(selected)
    component = root / 'component'
    expected_files = component_plan(repo, request)
    need({p.name for p in component.iterdir()} == set(expected_files), 'Closed exact prepared component inventory')
    for name, expected in expected_files.items():
        body(component / name, pin(expected))
    need(record['component_source'] == reference(component / 'RUNTIME_SOURCE.json'), 'Exact component source manifest')
    owner_entry = root / 'overlay' / OWNER_REL / 'runner.py'
    need(record['owner_entry'] == reference(owner_entry)
         and record['overlay_source']['path'] == str(owner_entry.parent / 'SOURCE.json'), 'Exact canonical overlay entrypoint')
    manifest = checked(record['overlay_source'])
    retained = decode(body(repo / OWNER_REL / 'SOURCE.json', OWNER_SOURCE))
    need(retained['schema'] == 'smc_aggregate_owner_source_v1', 'Exact retained owner manifest')
    composition = {'schema': 'smc_full_panel_owner_composition_v1', 'repository_root': str(repo),
        'component_root': str(component), 'component_source': pin(body(component / 'RUNTIME_SOURCE.json')),
        'episode': fixed('full_panel_episode.py'), 'retained_owner_source': OWNER_SOURCE}
    expected_owner = dict(retained['files'])
    expected_owner['legacy.py'] = fixed('owner_legacy.py')
    expected_owner['COMPOSITION.json'] = pin(encoded(composition))
    need(manifest == {'schema': 'smc_full_panel_owner_overlay_v1', 'files': expected_owner,
         'retained_owner_source': OWNER_SOURCE, 'component_source': composition['component_source']},
         'Unchanged retained owner with exact full-panel adapter and component locator')
    need({p.name for p in owner_entry.parent.iterdir()} == set(expected_owner) | {'SOURCE.json'},
         'Closed exact retained owner overlay inventory')
    for name, expected in expected_owner.items():
        need(Path(name).name == name, 'Local owner source member required')
        body(owner_entry.parent / name, expected)
    need(record['protocol'] == reference(root / 'protocol' / 'PROTOCOL.json'), 'Exact prepared protocol')
    need(record['execution_root'] == str(root / 'execution') and record['owner_root'] == str(root / 'owner'),
         'Disjoint owner and execution siblings remain selected')
    L = episode(repo, component)
    material = L.material_binding()
    need(material['new_pair'] == {k: request['pair'][k] for k in ('bytes', 'sha256')}, 'Prepared material binding changed')
    protocol, runtime = L.admit_protocol(record['protocol']['path'], record['protocol']['sha256'])
    need(protocol['pair_path'] == request['pair']['path']
         and protocol['task_path'] == str(component / 'task.json')
         and runtime['qualification'] == record['runtime_qualification'], 'Prepared protocol/runtime inputs unchanged')
    for condition, selected in request['methods'].items():
        need(protocol['programs'][condition]['method'] == {k: selected[k] for k in ('path', 'sha256')},
             'Prepared method selection unchanged')
    return record


def execution_command(prepared_path, prepared_sha256, recovery_read_bytes, recovery_write_bytes,
                      *, repository_root=None):
    record = inspect_prepared(prepared_path, prepared_sha256, repository_root=repository_root)
    need(type(recovery_read_bytes) is int and 131072 <= recovery_read_bytes <= 268435456,
         'Retained owner recovery-read interval required')
    need(type(recovery_write_bytes) is int and 131072 <= recovery_write_bytes <= 67108864,
         'Retained owner recovery-write interval required')
    need(not path(record['execution_root']).exists() and not path(record['owner_root']).exists(),
         'Fresh execution and owner roots required')
    need(not (path(record['root']) / 'EXECUTE_STARTED.json').exists(), 'Execution dispatch is single use')
    return [sys.executable, '-I', '-B', record['owner_entry']['path'], 'execute',
        '--protocol', record['protocol']['path'], '--protocol-sha256', record['protocol']['sha256'],
        '--output', record['execution_root'], '--owner', record['owner_root'],
        '--recovery-read-bytes', str(recovery_read_bytes), '--recovery-write-bytes', str(recovery_write_bytes)]


def grade_module(repo):
    """Load only the fixed maintained grading boundary; no caller helper override."""
    root = repo / COMPONENT_REL / 'grade-bound'
    manifest = decode(body(root / 'SOURCE.json', GRADE_SOURCE))
    need(type(manifest) is dict and set(manifest) == {'schema', 'files'}
         and manifest['schema'] == 'smc_full_panel_grade_sources_v1'
         and type(manifest['files']) is dict and set(manifest['files']) == GRADE_FILES,
         'Closed exact maintained grading source required')
    for name, selected in manifest['files'].items():
        need(type(selected) is dict and set(selected) == {'bytes', 'sha256'}
             and type(selected['bytes']) is int and 0 < selected['bytes'] <= META_CAP,
             'Bounded fixed grading source member required')
        sha(selected['sha256'])
        body(root / name, selected)
    return module('_smc_public_grade_bound', root / 'grade_bound.py', manifest['files']['grade_bound.py'])


def grade_command(prepared_path, prepared_sha256, owner_result_sha256, target, evaluator, output, scratch_bytes,
                  *, grade_runtime_path, grade_runtime_sha256, repository_root=None):
    """Build a bounded invocation after real saved-owner admission, never naked argv."""
    repo = repository(repository_root)
    record = inspect_prepared(prepared_path, prepared_sha256, repository_root=repo)
    L = episode(repo, path(record['root']) / 'component')
    _, runtime = L.admit_protocol(record['protocol']['path'], record['protocol']['sha256'])
    helper = grade_module(repo)
    # These identities come from the authenticated facade, not caller assertions.
    # The helper separately derives the overlay-owner identity for its saved gate.
    return helper.build_invocation(record, str(path(grade_runtime_path)), sha(grade_runtime_sha256),
        sha(owner_result_sha256), str(path(target)), str(path(evaluator)), str(path(output)), scratch_bytes,
        expected_source=L.source_identity(), expected_image_id=runtime['deployment']['image'])


def execute(prepared_path, prepared_sha256, recovery_read_bytes, recovery_write_bytes, *, repository_root=None):
    command = execution_command(prepared_path, prepared_sha256, recovery_read_bytes, recovery_write_bytes,
                                repository_root=repository_root)
    root = path(prepared_path).parent
    publish(root / 'EXECUTE_STARTED.json', {'schema': 'smc_full_panel_public_dispatch_v1',
        'prepared_sha256': prepared_sha256, 'argv': command, 'dispatch_possible': True,
        'creator_closure_established': False, 'failure_or_missing_receipt_proves_closure': False})
    # There is intentionally no cleanup inference if execv fails or this process is lost.
    # The retained runner performs qualification, live production checks, journaling,
    # process/cgroup custody, capture and recovery in its own fresh interpreter.
    os.execv(sys.executable, command)


def protected_grade(prepared_path, prepared_sha256, owner_result_sha256, target, evaluator, output, scratch_bytes,
                    *, grade_runtime_path, grade_runtime_sha256, repository_root=None):
    invocation = grade_command(prepared_path, prepared_sha256, owner_result_sha256,
        target, evaluator, output, scratch_bytes, grade_runtime_path=grade_runtime_path,
        grade_runtime_sha256=grade_runtime_sha256, repository_root=repository_root)
    # Reauthenticate the same fixed source at use. The helper owns process/container
    # capture and cleanup; no direct runner exec or unbounded fallback is available.
    return grade_module(repository(repository_root)).run_grade(invocation)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository-root', type=Path)
    sub = parser.add_subparsers(dest='operation', required=True)
    p = sub.add_parser('prepare', help='Create fresh protocol/component/overlay; never launch')
    p.add_argument('--request', type=Path, required=True)
    p.add_argument('--request-sha256', required=True)
    for name in ('inspect', 'execute', 'protected-grade'):
        p = sub.add_parser(name)
        p.add_argument('--prepared', type=Path, required=True)
        p.add_argument('--prepared-sha256', required=True)
        if name == 'execute':
            p.add_argument('--recovery-read-bytes', type=int, required=True)
            p.add_argument('--recovery-write-bytes', type=int, required=True)
        if name == 'protected-grade':
            p.add_argument('--grade-runtime', type=Path, required=True)
            p.add_argument('--grade-runtime-sha256', required=True)
            p.add_argument('--owner-result-sha256', required=True)
            for option in ('target', 'evaluator', 'output'):
                p.add_argument('--' + option, type=Path, required=True)
            p.add_argument('--scratch-bytes', type=int, required=True)
    args = parser.parse_args(argv)
    common = {'repository_root': args.repository_root}
    if args.operation == 'prepare':
        result = prepare(args.request, args.request_sha256, **common)
    elif args.operation == 'inspect':
        result = inspect_prepared(args.prepared, args.prepared_sha256, **common)
    elif args.operation == 'execute':
        return execute(args.prepared, args.prepared_sha256, args.recovery_read_bytes, args.recovery_write_bytes, **common)
    else:
        result = protected_grade(args.prepared, args.prepared_sha256, args.owner_result_sha256,
            args.target, args.evaluator, args.output, args.scratch_bytes, grade_runtime_path=args.grade_runtime,
            grade_runtime_sha256=args.grade_runtime_sha256, **common)
    print(json.dumps(result, sort_keys=True, indent=2, allow_nan=False))
    return 1 if args.operation == 'protected-grade' and result.get('success') is not True else 0


if __name__ == '__main__':
    raise SystemExit(main())
