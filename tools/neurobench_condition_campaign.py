#!/usr/bin/env python3
"""Run a named information condition with the existing qualified task wrappers.

Legacy dispatcher and frozen runtime sources remain unchanged. Conditions are
not additional task IDs. Metadata and --dry-run never execute candidate code.
"""
import argparse
import importlib.util
import json
import hashlib
import os
import types
from pathlib import Path
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE_PIN = {'bytes': 26686, 'sha256': 'b17b4317427f83ce28ab7ea5a4fbc42b689870ef2a7144a7e094ecb0bef9e59e'}

def _base():
    path = ROOT / 'tools/neurobench_campaign.py'
    if any(x.is_symlink() for x in (path, *path.parents)):
        raise ValueError('Linked base dispatcher')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if not (stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == BASE_PIN['bytes']):
            raise ValueError('Base dispatcher extent')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            body = stream.read(BASE_PIN['bytes'] + 1)
        fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_nlink')
        after, named = os.fstat(fd), path.lstat()
        if (len(body) != before.st_size or hashlib.sha256(body).hexdigest() != BASE_PIN['sha256']
                or not all(getattr(before, k) == getattr(after, k) == getattr(named, k) for k in fields)):
            raise ValueError('Base dispatcher identity')
    finally:
        os.close(fd)
    module = types.ModuleType('neurobench_base')
    module.__file__ = str(path)
    exec(compile(body, str(path), 'exec'), module.__dict__)
    return module

base = _base()


def condition_document(doc, condition):
    options = base._object(doc.get('program_conditions', {}), 'Program conditions')
    if condition not in options:
        raise ValueError('Unknown program condition for ' + doc['id'] + ': ' + condition)
    meta = options[condition]
    if meta == 'default':
        meta = doc.get('program_execution')
    return {**doc, 'program_execution': base._object(meta, 'Program condition')}


def list_conditions(root=ROOT):
    rows = []
    for ident, (path, doc) in base.runtime_manifests(root).items():
        for condition in base._object(doc.get('program_conditions', {}), 'Program conditions'):
            selected = condition_document(doc, condition)
            rows.append({'id': ident, 'condition': condition,
                         'qualified': base.verified_program_runtime(path, selected, root),
                         'additional_task': False})
    return rows


def run_command(task_id, condition, program, output, root=ROOT, *, review=None, other_reserve_bytes=None):
    _, canonical = base.specifications(root)
    if task_id not in canonical:
        raise ValueError('Unknown canonical task')
    runtime = base.runtime_manifests(root)
    if task_id not in runtime:
        raise ValueError('No local program runner is implemented for ' + task_id)
    path, doc = runtime[task_id]
    selected = condition_document(doc, condition)
    if not base.verified_program_runtime(path, selected, root):
        raise ValueError('Selected condition has no separate passing qualification')
    entry, wrapper = base._program_entry(selected['program_execution'], root)
    program, output = Path(program).absolute(), Path(output).absolute()
    if any(p.is_symlink() for p in (program, *program.parents)):
        raise ValueError('Candidate program path must not contain symlinks')
    info = program.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('Candidate program must be an ordinary single-link file')
    if output.exists() or any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError('Choose a fresh output directory without symlinks')
    if any(p.exists() and not p.is_dir() for p in output.parents):
        raise ValueError('Program output directory has a non-directory ancestor')
    values = {'{program}': str(program.resolve()), '{output}': str(output.resolve())}
    if '{review}' in entry['argv']:
        if review is None or type(other_reserve_bytes) is not int or other_reserve_bytes < 0:
            raise ValueError('This runner requires --review and a nonnegative integer --other-reserve-bytes')
        review_path = Path(review).absolute()
        if not review_path.is_relative_to(root.resolve()):
            raise ValueError('Execution review must be inside the repository')
        review_path = base._program_repo_file(root, review_path.relative_to(root.resolve()).as_posix())
        if not 0 < review_path.stat().st_size <= 32768:
            raise ValueError('Execution review must be a nonempty file of at most 32768 bytes')
        values.update({'{review}': str(review_path), '{other_reserve_bytes}': str(other_reserve_bytes)})
    elif '{other_reserve_bytes}' in entry['argv']:
        if review is not None or type(other_reserve_bytes) is not int or other_reserve_bytes < 0:
            raise ValueError('This reserve-only runner requires an explicit nonnegative integer --other-reserve-bytes and no --review')
        values['{other_reserve_bytes}'] = str(other_reserve_bytes)
    elif review is not None or other_reserve_bytes is not None:
        raise ValueError('This runner does not declare review/reserve arguments')
    index = base._campaign_module(root).python_launch(entry['argv'])
    return ([sys.executable] + entry['argv'][1:index] + [str(wrapper)]
            + [values.get(arg, arg) for arg in entry['argv'][index + 1:]]), root.resolve()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('list')
    p = sub.add_parser('run')
    p.add_argument('id'); p.add_argument('--condition', required=True)
    p.add_argument('--program', required=True); p.add_argument('--output', required=True)
    p.add_argument('--review'); p.add_argument('--other-reserve-bytes', type=int)
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--campaign-request', required=True)
    p.add_argument('--campaign-request-sha256', required=True)
    p.add_argument('--work-sha256', required=True)
    args = parser.parse_args()
    if args.action == 'list':
        result = list_conditions()
    else:
        gate = base._campaign_module(ROOT)
        first = gate.admit(ROOT, args.id, 'run', args.condition, args.campaign_request,
                           args.campaign_request_sha256, args.work_sha256)
        first['preferred_program_route'] = gate.preferred_route(
            ROOT, args.id, 'run', args.condition, args.work_sha256, base.runtime_manifests(ROOT).get(args.id))
        first['metadata_read_charge_bytes'] += first['preferred_program_route']['metadata_read_charge_bytes']
        command, cwd = run_command(args.id, args.condition, args.program, args.output,
                                   review=args.review, other_reserve_bytes=args.other_reserve_bytes)
        second = gate.admit(ROOT, args.id, 'run', args.condition, args.campaign_request,
                            args.campaign_request_sha256, args.work_sha256)
        second['preferred_program_route'] = gate.preferred_route(
            ROOT, args.id, 'run', args.condition, args.work_sha256, base.runtime_manifests(ROOT).get(args.id))
        second['metadata_read_charge_bytes'] += second['preferred_program_route']['metadata_read_charge_bytes']
        admission = gate.finish(first, second, command, cwd)
        if not args.dry_run:
            print(json.dumps({'campaign_admission': admission}, sort_keys=True, separators=(',', ':')), file=sys.stderr, flush=True)
            return subprocess.run(command, cwd=cwd, check=False).returncode
        result = {'argv': command, 'working_directory': str(cwd), 'executed': False,
                  'campaign_admission': admission}
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({'status': 'refused', 'reason': str(exc)}), file=sys.stderr)
        raise SystemExit(2)
