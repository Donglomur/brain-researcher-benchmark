#!/usr/bin/env python3
"""Run a named information condition with the existing qualified task wrappers.

Legacy dispatcher and frozen runtime sources remain unchanged. Conditions are
not additional task IDs. Metadata and --dry-run never execute candidate code.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('neurobench_base', ROOT / 'tools/neurobench.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


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
    elif review is not None or other_reserve_bytes is not None:
        raise ValueError('This runner does not declare review/reserve arguments')
    return [sys.executable, str(wrapper)] + [values.get(arg, arg) for arg in entry['argv'][2:]], root.resolve()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('list')
    p = sub.add_parser('run')
    p.add_argument('id'); p.add_argument('--condition', required=True)
    p.add_argument('--program', required=True); p.add_argument('--output', required=True)
    p.add_argument('--review'); p.add_argument('--other-reserve-bytes', type=int)
    p.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if args.action == 'list':
        result = list_conditions()
    else:
        command, cwd = run_command(args.id, args.condition, args.program, args.output,
                                   review=args.review, other_reserve_bytes=args.other_reserve_bytes)
        if not args.dry_run:
            return subprocess.run(command, cwd=cwd, check=False).returncode
        result = {'argv': command, 'working_directory': str(cwd), 'executed': False}
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({'status': 'refused', 'reason': str(exc)}), file=sys.stderr)
        raise SystemExit(2)
