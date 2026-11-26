"""Explicit operator routes for already exposed EEG and sleep development panels.

This module checks source and data identities, then dispatches existing tools.
It implements no scientific metric and never turns a receipt into qualification.
"""
import argparse
import hashlib
import types
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = 'src/neurobench/operator-sources.json'
LIFECYCLE = 'benchmarks/shared/frozen-neural-lifecycle-v1/lifecycle.py'
TASKS = {'NEURAL-077': (200, 200), 'NEURAL-007': (2780, 2670)}
CASES = ('development-001', 'development-002')
EXPOSURE = 'Both development people were already exposed during construction; this is not an untouched holdout.'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def unlinked(path):
    path = Path(path).absolute()
    need(all(not p.is_symlink() for p in (path, *path.parents)), 'Linked paths are not admitted')
    return path


def digest(path, cap=64 * 1024**2):
    path = unlinked(path)
    before = path.stat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= cap,
         'Bounded single-link regular file required')
    h = hashlib.sha256()
    with path.open('rb') as stream:
        opened = os.fstat(stream.fileno())
        for block in iter(lambda: stream.read(1024**2), b''):
            h.update(block)
        after = os.fstat(stream.fileno())
    fields = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    need(fields(before) == fields(opened) == fields(after) == fields(path.stat()), 'File changed during authentication')
    return {'bytes': before.st_size, 'sha256': h.hexdigest()}


def read_json(path):
    digest(path, 2 * 1024**2)
    def pairs(items):
        value = {}
        for k, v in items:
            need(k not in value, 'Duplicate metadata key')
            value[k] = v
        return value
    return json.loads(Path(path).read_bytes(), object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'Nonfinite metadata'))


def source_path(root, value):
    need(isinstance(value, str) and value and not Path(value).is_absolute()
         and '..' not in Path(value).parts and str(Path(value)) == value, 'Normalized relative source path required')
    path = unlinked(Path(root) / value)
    need(path.resolve().is_relative_to(Path(root).resolve()), 'Source escapes checkout')
    return path


def sources(root, task):
    """Authenticate bounded executable closure before importing or dispatching it."""
    need(task in TASKS, 'No operator route for this task')
    manifest = read_json(source_path(root, MANIFEST))
    need(manifest.get('schema') == 'neurobench_operator_sources_v1', 'Unknown operator source inventory')
    names = manifest['routes'][task]
    need(isinstance(names, list) and 0 < len(names) <= 100 and len(names) == len(set(names)), 'Bounded source closure required')
    required = {LIFECYCLE, 'benchmarks/shared/frozen-neural-lifecycle-v1/candidate_entry.py',
                'benchmarks/neural/' + task + '/implementations/portable-grading/score.py'}
    if task == 'NEURAL-007':
        required.add('benchmarks/neural/NEURAL-007/implementations/finite-attempt-audit/audit.py')
    need(required.issubset(names), 'Missing executable entrypoint in operator source inventory')
    checked = {}
    for name in names:
        observed = digest(source_path(root, name), 2 * 1024**2)
        need(observed == manifest['files'][name], 'Operator source changed: ' + name)
        checked[name] = observed
    return checked


def load_lifecycle(root):
    path = Path(root) / LIFECYCLE
    module = types.ModuleType('_neurobench_operator_lifecycle')
    module.__file__ = str(path)
    # Execute the authenticated source, never a cached bytecode sibling.
    exec(compile(path.read_bytes(), str(path), 'exec'), module.__dict__)
    return module


def routes(root=ROOT):
    result = []
    for task in TASKS:
        try:
            closure = sources(root, task)
            state = {'source_verified': True, 'source_files': len(closure)}
        except (ValueError, OSError, KeyError, TypeError) as exc:
            state = {'source_verified': False, 'source_error': str(exc)}
        result.append({'task_id': task, **state, 'commands': ['inspect', 'prepare', 'validate', 'grade', 'programme']
                       + (['sleep-audit'] if task == 'NEURAL-007' else []),
                       'development_people': 2, 'development_rows': sum(TASKS[task]),
                       'data_availability': 'not_inspected', 'authentic_grading': 'not_executed',
                       'model_evaluation': 'not_executed', 'scientific_qualification': 'not_established',
                       'exposure': EXPOSURE, 'documentation': 'docs/operator-routes.md'})
    return result


def public_members(root, task):
    """Select only native public-manifest members; never follow private locators."""
    life = load_lifecycle(root)
    filename, size, sha = life.PUBLIC_PINS[task]
    descriptor = Path(root) / 'benchmarks/neural' / task / 'implementations/registered-runtime' / filename
    need(digest(descriptor) == {'bytes': size, 'sha256': sha}, 'Public descriptor changed')
    public = read_json(descriptor)
    rows = []
    if task == 'NEURAL-077':
        for case, members in public['public_training_lazy'].items():
            rows.append((members['features'], 'training/' + case + '/features.npz', 'training_features_and_labels', case))
        for case in CASES:
            rows.append((public['public']['cases'][case]['features'],
                         'development/' + case + '/features.npz', 'development_features', case))
    else:
        for row in public['files']:
            role, case = row['role'], row.get('case_id')
            if role.startswith('training_'):
                logical = 'training/' + case + '/' + Path(row['logical_path']).name
            elif role.startswith('development_'):
                logical = 'development/' + case + '/' + Path(row['logical_path']).name
            else:
                need(role == 'common_model_reader', 'Unknown public input role')
                logical = row['logical_path']
            rows.append((row, logical, role, case))
    return life, rows


def inspect_inputs(root, task, data_root, layout='original'):
    life, selected = public_members(root, task)
    base = unlinked(data_root)
    need(base.is_dir(), 'Existing data directory required')
    report, identities = [], {}
    for expected, prepared_path, role, case in selected:
        relative = expected['path'] if layout == 'original' else prepared_path
        entry = {'member': relative, 'role': role, 'case_id': case,
                 'contains_training_labels': 'labels' in role,
                 'expected': {k: expected[k] for k in ('bytes', 'sha256')}}
        try:
            path = source_path(base, relative)
            entry['observed'] = digest(path)
            need(entry['observed'] == entry['expected'], 'Public input pin mismatch')
            if role == 'development_features':
                n = TASKS[task][CASES.index(case)]
                ids = life._unicode_array(path, 'trial_ids' if task == 'NEURAL-077' else 'epoch_id', n)
                identities[case] = ids
                entry['complete_rows'] = len(ids)
            entry['status'] = 'authenticated'
        except (OSError, ValueError) as exc:
            entry.update(status='unavailable_or_changed', error=type(exc).__name__ + ': ' + str(exc))
        report.append(entry)
    complete = all(x['status'] == 'authenticated' for x in report)
    complete = complete and set(identities) == set(CASES)
    if complete:
        complete = len({i for ids in identities.values() for i in ids}) == sum(TASKS[task])
    return {'status': 'authentic_public_inputs' if complete else 'input_inspection_failed',
            'complete': complete, 'layout': layout, 'members': report,
            'development_rows': sum(len(x) for x in identities.values()), 'private_assets_opened': False,
            'training_label_exposure': 'The selected training feature/label files were hashed; development targets were not opened.',
            'exposure': EXPOSURE}


def fresh_output(root, output):
    output = unlinked(output)
    need(not output.exists() and output.parent.is_dir(), 'Fresh output directory with an existing parent required')
    need(not output.resolve().is_relative_to(Path(root).resolve()), 'Operator evidence and numerical results must be outside the public checkout')
    output.mkdir(mode=0o700)
    return output


def save(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def dispatch(argv, output):
    # Existing native adapters own deadlines and exact container cleanup. Do not
    # kill their parent on an outer timeout and strand an owned container.
    with (output / 'stdout').open('xb') as stdout, (output / 'stderr').open('xb') as stderr:
        completed = subprocess.run(argv, stdout=stdout, stderr=stderr, check=False)
    return completed.returncode


def run(args, root):
    output = fresh_output(root, args.output)
    started = time.monotonic()
    receipt = {'schema': 'neurobench_operator_result_v1', 'task_id': args.task, 'action': args.action,
               'purpose': getattr(args, 'purpose', 'input_inspection'), 'exposure': EXPOSURE,
               'model_evaluation': 'not_established_by_this_operation', 'scientific_qualification': 'not_established',
               'authentic_grading': 'not_executed', 'private_assets_opened_by_dispatcher': False}
    code = 3
    try:
        receipt['source'] = sources(root, args.task)
        if args.action == 'inspect':
            receipt['inspection'] = inspect_inputs(root, args.task, args.data_root, args.layout)
            code = 0 if receipt['inspection']['complete'] else 3
        else:
            argv = [sys.executable, '-I', '-B', '-X', 'pycache_prefix=' + str(output / 'bytecode')]
            if args.action == 'prepare':
                receipt['inspection'] = inspect_inputs(root, args.task, args.data_root, args.layout)
                need(receipt['inspection']['complete'], 'Complete authentic public inputs required before preparation')
                asset_root = Path(args.data_root).absolute()
                if args.layout == 'prepared':
                    # Relocate the exact allowlist for the unchanged native preparer.
                    # Never copy a whole operator parent or trust a packet receipt.
                    life, selected = public_members(root, args.task)
                    original = output / 'source-layout'
                    for expected, prepared_path, _, _ in selected:
                        life.copy_pinned(source_path(asset_root, prepared_path),
                                         source_path(original, expected['path']), expected)
                    asset_root = original
                argv += [str(Path(root) / LIFECYCLE), 'prepare', '--task', args.task,
                         '--asset-root', str(asset_root), '--run', str(output / 'lifecycle')]
            elif args.action in ('validate', 'grade'):
                script = Path(root) / 'benchmarks/neural' / args.task / 'implementations/portable-grading/score.py'
                argv += [str(script), 'score' if args.action == 'grade' else 'validate',
                         '--package-dir', str(script.parent.parent / 'registered-runtime'),
                         '--artifacts', str(Path(args.artifacts).absolute()), '--submission', str(Path(args.submission).absolute()),
                         '--output-dir', str(output / 'native')]
                for key in ('docker_cli', 'docker_host', 'docker_config'):
                    argv += ['--' + key.replace('_', '-'), getattr(args, key)]
            else:
                life = load_lifecycle(root)
                packet = life.packet(args.run)
                need(packet['task_id'] == args.task, 'Prepared attempt task differs from selected route')
                if args.action == 'programme':
                    argv += [str(Path(root) / LIFECYCLE), args.step, '--run', str(Path(args.run).absolute())]
                    if args.step == 'commit':
                        need(args.source, 'Method source required for commitment')
                        argv += ['--source', str(Path(args.source).absolute()), '--entrypoint', args.entrypoint]
                else:
                    need(args.task == 'NEURAL-007', 'Sleep audit supports NEURAL-007 only')
                    script = Path(root) / 'benchmarks/neural/NEURAL-007/implementations/finite-attempt-audit/audit.py'
                    argv += [str(script), args.step, '--run', str(Path(args.run).absolute()), '--witness', args.witness]
                    if args.step == 'commit':
                        need(args.source, 'Method source required for commitment')
                        argv += ['--source', str(Path(args.source).absolute()), '--entrypoint', args.entrypoint]
                    else:
                        for key in ('witness_bytes', 'witness_sha256', 'final_witness'):
                            need(getattr(args, key) is not None, 'Retained commitment anchors and final witness required')
                            argv += ['--' + key.replace('_', '-'), str(getattr(args, key))]
                        if args.step == 'verify':
                            for key in ('final_bytes', 'final_sha256'):
                                need(getattr(args, key) is not None, 'Retained completion anchors required')
                                argv += ['--' + key.replace('_', '-'), str(getattr(args, key))]
            receipt['argv'] = argv
            save(output / 'dispatch.json', receipt)
            if args.action == 'grade':
                receipt['authentic_grading'] = 'dispatch_attempted_not_completed'
            child_code = dispatch(argv, output)
            receipt['child_returncode'] = child_code
            code = child_code if child_code == 0 or (
                args.action in ('validate', 'grade') and child_code in (2, 3)) else 3
            if args.action in ('validate', 'grade'):
                need((output / 'native/result.json').is_file(), 'Native result missing; retain dispatch failure')
                result = read_json(output / 'native/result.json')
                need(isinstance(result, dict), 'Native result must be an object')
                if code == 0:
                    expected_status = 'scored' if args.action == 'grade' else 'valid_prediction_contract'
                    need(result.get('status') == expected_status, 'Native success status does not match action')
                receipt['native_result'] = digest(output / 'native/result.json')
                receipt['native_status'] = result.get('status')
                native_receipt_path = output / 'native/receipt.json'
                if native_receipt_path.is_file():
                    native_receipt = read_json(native_receipt_path)
                    need(isinstance(native_receipt, dict), 'Native receipt must be an object')
                    receipt['private_stage_dispatched'] = native_receipt.get('private_stage_dispatched')
                    receipt['native_receipt'] = digest(native_receipt_path)
                    if args.action == 'grade':
                        receipt['authentic_grading'] = ('attempted_unsuccessful' if receipt['private_stage_dispatched']
                                                       else 'private_stage_not_dispatched')
                if args.action == 'grade' and code == 0 and result.get('status') == 'scored':
                    receipt['authentic_grading'] = 'completed_for_supplied_submission'
                    receipt['evaluation_kind'] = ('authentic_data_software_control' if args.purpose == 'development-control'
                                                  else 'submitted_model_output_score_without_independent_method_provenance')
        receipt['status'] = 'completed' if code == 0 else 'refused_or_failed'
    except (ValueError, OSError, KeyError, TypeError) as exc:
        code = 3
        receipt.update(status='refused_or_failed', error=type(exc).__name__ + ': ' + str(exc))
    finally:
        receipt.update(exit_code=code, wall_seconds=time.monotonic() - started)
        for name in ('stdout', 'stderr'):
            if (output / name).is_file():
                receipt[name] = digest(output / name)
        save(output / 'operator.json', receipt)
    return receipt, code


def main(argv=None, root=ROOT):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=root)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('routes')
    for action in ('inspect', 'prepare', 'validate', 'grade', 'programme', 'sleep-audit'):
        p = sub.add_parser(action)
        p.add_argument('task', choices=list(TASKS))
        p.add_argument('--output', required=True, help='Fresh evidence directory outside the checkout')
        if action in ('inspect', 'prepare'):
            p.add_argument('--data-root', required=True)
            p.add_argument('--layout', choices=('original', 'prepared'), default='original',
                           help='prepared means the existing lifecycle inputs/ directory')
        elif action in ('validate', 'grade'):
            for name in ('artifacts', 'submission', 'docker-cli', 'docker-host', 'docker-config'):
                p.add_argument('--' + name, required=True)
            p.add_argument('--purpose', choices=('development-control', 'model-evaluation'), required=True)
        else:
            p.add_argument('step', choices=('commit', 'execute', 'freeze', 'inspect') if action == 'programme'
                           else ('commit', 'complete', 'verify'))
            p.add_argument('--run', required=True)
            p.add_argument('--source')
            p.add_argument('--entrypoint', default='candidate.py')
            if action == 'sleep-audit':
                p.add_argument('--witness', required=True)
                p.add_argument('--witness-bytes', type=int)
                p.add_argument('--witness-sha256')
                p.add_argument('--final-witness')
                p.add_argument('--final-bytes', type=int)
                p.add_argument('--final-sha256')
    args = parser.parse_args(argv)
    root = args.root.absolute()
    if args.action == 'routes':
        print(json.dumps(routes(root), indent=2))
        return 0
    try:
        report, code = run(args, root)
        print(json.dumps({'status': report['status'], 'task_id': args.task, 'output': args.output, 'exit_code': code}))
        return code
    except (ValueError, OSError) as exc:
        print(json.dumps({'status': 'output_refused', 'error': str(exc)}))
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
