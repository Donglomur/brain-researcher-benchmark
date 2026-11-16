#!/usr/bin/env python3
"""List construction targets and dispatch separately verified scores or programs.

Specifications, working score adapters, native development tasks, and research
admission are deliberately different counters. Program execution needs its own
qualification and frozen wrapper; scoring qualification never enables it. This
command never starts an LLM. Metadata commands and --dry-run execute no candidate.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
COMMON = {'schema_version', 'id', 'track', 'title', 'status', 'primary_outputs',
          'input_assets', 'evaluation', 'resources', 'holds',
          'next_implementation_action', 'provenance', 'admission'}


def public_metadata_mode(root):
    """A public clone has source specs, not the private construction ledgers."""
    paths = [Path(root) / 'docs/neuroscience-benchmarks/build' / name
             for name in ('paper_100.json', 'neural_100.json')]
    present = [path.is_file() for path in paths]
    if any(present) and not all(present):
        raise ValueError('Incomplete legacy roster pair')
    return not all(present)


def public_catalog_module():
    # Explicit sibling load also works under python -I, without changing sys.path.
    spec = importlib.util.spec_from_file_location('neurobench_public_catalog',
                                                 Path(__file__).with_name('build_public_catalog.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def public_summary(catalog):
    counts = catalog['counts']
    return {'target_assignments': counts['total'], 'delivery_specifications': counts['total'],
            'paper_specifications': counts['paper'], 'neural_specifications': counts['neural'],
            'canonical_source_specifications': counts['canonical_specifications'],
            'expansion_drafts': counts['expansion_drafts'],
            'runtime_manifests_present': counts['runtime_manifests'],
            'supporting_source_components': counts['source_components'],
            'local_score_adapters_verified': None, 'score_adapter_ids': None,
            'local_program_runners_verified': None, 'program_runner_ids': None,
            'bounded_reference_runs_recorded': None, 'bounded_reference_ids': None,
            'distinct_ids_with_reference_or_score_adapter': None,
            'historical_native_development_packages': None,
            'distinct_ids_with_native_package_or_scoring_adapter': None,
            'full_candidate_contracts_completed': None, 'research_qualified': None,
            'submission_ready': None, 'scientific_readiness': 'unknown',
            'submission_readiness': 'unknown',
            'count_basis': 'Published source specifications and the complete expansion registry chain. '
                           'Runtime receipts, candidate code, data and private construction ledgers are not inspected.',
            'counting_note': catalog['counting_note']}


def public_metadata_command(action, root, *, track=None, task_id=None):
    builder = public_catalog_module()
    catalog = builder.generate(root, check=True) if action == 'check' else builder.load(root)
    if action in ('status', 'check'):
        result = public_summary(catalog)
        if action == 'check':
            result.update(metadata_check='passed', check_scope='Deterministic public metadata/catalog consistency only')
        return result
    if action == 'list':
        return [{key: row[key] for key in ('id', 'title', 'track', 'source_specification',
                  'registration_stage', 'specification', 'runtime_manifest',
                  'scientific_readiness', 'submission_readiness',
                  'local_scoring_adapter_verified', 'local_program_runner_verified')}
                for row in catalog['tasks'] if track is None or row['track'] == track]
    row = next((row for row in catalog['tasks'] if row['id'] == task_id), None)
    if row is None:
        raise ValueError('Specification not yet built for ' + str(task_id))
    return {'specification': read(builder.public_path(Path(root), row['specification']['path'])),
            'runtime': read(builder.public_path(Path(root), row['runtime_manifest']['path']))
                       if row['runtime_manifest'] else None,
            'catalog_entry': row}


def read(path):
    return json.loads(path.read_text())


def within(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Path escapes its permitted root')
    return path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def specifications(root=ROOT, complete=False):
    if public_metadata_mode(root):
        builder = public_catalog_module()
        catalog = builder.discover(root) if complete else builder.load(root)
        expected = {row['id']: row for row in catalog['tasks']}
        docs = {identifier: read(builder.public_path(Path(root), row['specification']['path']))
                for identifier, row in expected.items()}
        return docs, expected
    expected = {}
    for name in ('paper_100.json', 'neural_100.json'):
        for task in read(root / 'docs/neuroscience-benchmarks/build' / name)['tasks']:
            if task['id'] in expected:
                raise ValueError('Duplicate canonical task ID')
            expected[task['id']] = task
    docs = {}
    for path in sorted((root / 'benchmarks/manifests').glob('*/*.json')):
        doc = read(path)
        if not isinstance(doc, dict) or not COMMON.issubset(doc):
            raise ValueError('Incomplete delivery schema: ' + str(path))
        task_id = doc['id']
        if task_id not in expected or task_id in docs or path.stem != task_id:
            raise ValueError('Unknown, duplicated, or misnamed task specification: ' + str(task_id))
        if doc['schema_version'] != 1 or doc['status'] != 'specification_only':
            raise ValueError('Specifications cannot claim runtime completion')
        if doc['track'] != path.parent.name or not doc['primary_outputs']:
            raise ValueError('Wrong track or missing task-specific scientific output')
        if doc['admission'].get('runnable') is not False or doc['admission'].get('research_qualified') is not False:
            raise ValueError('Source metadata cannot promote scientific or runtime admission')
        docs[task_id] = doc
    if complete and (len(expected) != 200 or set(docs) != set(expected)):
        raise ValueError(f'Expected exactly 200 specifications; found {len(docs)}')
    return docs, expected


def runtime_manifests(root=ROOT):
    docs = {}
    for path in sorted((root / 'benchmarks/neuroscience').glob('*/manifest.json')):
        doc = read(path)
        task_id = doc['id']
        if task_id in docs:
            raise ValueError('Duplicate runtime for ' + task_id)
        docs[task_id] = (path, doc)
    return docs


def verified_runtime(path, doc, root=ROOT):
    verification = doc.get('verification', {})
    if verification.get('status') != 'passed' or doc.get('admission', {}).get('runnable') is not True:
        return False
    receipt = within(root, verification['receipt_path'])
    if not receipt.is_file() or digest(receipt) != verification['receipt_sha256']:
        raise ValueError('Missing or changed verification receipt for ' + doc['id'])
    entry = doc['entrypoints']['score']
    script = within(root, entry['argv'][1])
    if not script.is_relative_to(path.parent.resolve()) or not script.is_file() or digest(script) != entry['sha256']:
        raise ValueError('Changed or misplaced scoring entrypoint for ' + doc['id'])
    return True


def _object(value, label):
    if not isinstance(value, dict):
        raise ValueError(label + ' must be an object')
    return value


def _sha256(value, label):
    if (not isinstance(value, str) or len(value) != 64
            or any(c not in '0123456789abcdef' for c in value)):
        raise ValueError(label + ' must be a lowercase SHA256')
    return value


def _program_repo_file(root, relative):
    """Require canonical repository-relative, regular, unlinked source/evidence."""
    if (not isinstance(relative, str) or not relative or '\\' in relative
            or Path(relative).is_absolute() or '..' in Path(relative).parts
            or Path(relative).as_posix() != relative):
        raise ValueError('Program source/evidence path must be canonical and repository-relative')
    path = root.resolve()
    for part in Path(relative).parts:
        path = path / part
        if path.is_symlink():
            raise ValueError('Program source/evidence cannot use symlinks')
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('Program source/evidence must be an ordinary single-link file')
    return path


def _program_pin(root, relative, expected_sha, expected_bytes=None, limit=16 * 1024 * 1024,
                 return_bytes=False):
    path = _program_repo_file(root, relative)
    _sha256(expected_sha, 'Program source/evidence hash')
    before = path.stat()
    if expected_bytes is not None and (type(expected_bytes) is not int or expected_bytes < 0):
        raise ValueError('Frozen source bytes must be a nonnegative integer')
    if before.st_size > limit or (expected_bytes is not None and before.st_size != expected_bytes):
        raise ValueError('Program source/evidence size differs from its bounded pin: ' + relative)
    with path.open('rb') as stream:
        body = stream.read(limit + 1)
    actual = hashlib.sha256(body).hexdigest()
    after = path.stat()
    if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            or len(body) > limit or actual != expected_sha):
        raise ValueError('Missing or changed program source/evidence: ' + relative)
    return body if return_bytes else path


def _program_json(root, relative, expected_sha):
    body = _program_pin(root, relative, expected_sha, limit=2 * 1024 * 1024, return_bytes=True)
    # Reject ambiguous duplicate fields and non-JSON numeric constants in evidence.
    def pairs(items):
        obj = {}
        for key, value in items:
            if key in obj:
                raise ValueError('Duplicate program evidence key: ' + key)
            obj[key] = value
        return obj
    def constant(value):
        raise ValueError('Invalid program evidence constant: ' + value)
    return _object(json.loads(body, object_pairs_hook=pairs,
                              parse_constant=constant), 'Program evidence')


def _program_entry(meta, root):
    entry = _object(meta.get('entrypoint'), 'Program entrypoint')
    argv = entry.get('argv')
    if (not isinstance(argv, list) or len(argv) < 4
            or not all(isinstance(arg, str) and '\0' not in arg for arg in argv)
            or argv[0] not in ('python3', '{python}') or '{' in argv[1] or '}' in argv[1]):
        raise ValueError('Expected a trusted Python program wrapper argv')
    # Substitution is whole-token only. No shell, format expressions or extra fields.
    if any(('{' in arg or '}' in arg) and arg not in
           ('{program}', '{output}', '{review}', '{other_reserve_bytes}')
           for arg in argv[2:]):
        raise ValueError('Program argv has an undeclared or embedded placeholder')
    if argv[2:].count('{program}') != 1 or argv[2:].count('{output}') != 1:
        raise ValueError('Program argv must contain each of {program} and {output} exactly once')
    if (argv[2:].count('{review}'), argv[2:].count('{other_reserve_bytes}')) not in ((0, 0), (1, 1)):
        raise ValueError('Reviewed program argv must contain review and reserve placeholders exactly once together')
    if entry.get('working_directory') != '.':
        raise ValueError('Only repository-root program execution is supported')
    wrapper = _program_pin(root, argv[1], entry.get('sha256'))
    if wrapper.suffix != '.py':
        raise ValueError('Program entrypoint must be a frozen Python wrapper')
    return entry, wrapper


def verified_program_runtime(path, doc, root=ROOT):
    """Check registered evidence consistency, not execution or scientific admission.

    Evidence: a passed terminal receipt linked to passed named control results,
    and an independently pinned start record linking that candidate to a source
    freeze. The wrapper and every freeze.files pin must still match. These local
    hashes are not signatures or proof of who authored the receipts.
    """
    meta = doc.get('program_execution')
    if meta is None:
        return False
    meta = _object(meta, 'program_execution')
    verification = _object(meta.get('verification', {}), 'Program verification')
    if verification.get('status') != 'passed':
        return False
    receipt = _program_json(root, verification.get('receipt_path'), verification.get('receipt_sha256'))
    qualification = _program_json(root, verification.get('qualification_path'),
                                  verification.get('qualification_sha256'))
    binding = _program_json(root, verification.get('source_binding_path'),
                            verification.get('source_binding_sha256'))
    if any(record.get('candidate_id') != doc['id'] for record in (receipt, qualification, binding)):
        raise ValueError('Program qualification candidate identity differs')
    if (receipt.get('status') != 'passed' or qualification.get('status') != 'passed'
            or type(receipt.get('returncode')) is not int or receipt['returncode'] != 0):
        raise ValueError('Program qualification has no passing terminal evidence')
    if receipt.get('verification_sha256') != verification['qualification_sha256']:
        raise ValueError('Program terminal receipt does not bind the registered qualification')
    controls = qualification.get('controls')
    if (not isinstance(controls, list) or not controls
            or any(not isinstance(c, dict) or not isinstance(c.get('name'), str)
                   or not c['name'] or c.get('passed') is not True for c in controls)
            or len({c['name'] for c in controls}) != len(controls)):
        raise ValueError('Program qualification must retain passed, uniquely named controls')
    frozen = _object(meta.get('source_freeze'), 'Program source freeze')
    freeze = _program_json(root, frozen.get('path'), frozen.get('sha256'))
    if any(record.get('source_freeze_sha256') != frozen['sha256']
           for record in (receipt, binding)):
        raise ValueError('Program terminal/start records do not bind the registered source freeze')
    files = _object(freeze.get('files'), 'Program frozen files')
    if not files or len(files) > 512:
        raise ValueError('Program source freeze must contain 1 to 512 files')
    entry, _ = _program_entry(meta, root)
    if entry['argv'][1] not in files:
        raise ValueError('Program wrapper is absent from the qualified source closure')
    total = 0
    for relative, pin in files.items():
        pin = _object(pin, 'Frozen source pin')
        size = pin.get('bytes')
        if type(size) is not int or size < 0:
            raise ValueError('Frozen source bytes must be a nonnegative integer')
        total += size
        if total > 64 * 1024 * 1024:
            raise ValueError('Program source closure exceeds the 64 MiB metadata-check limit')
        _program_pin(root, relative, pin.get('sha256'), size)
    if files[entry['argv'][1]]['sha256'] != entry['sha256']:
        raise ValueError('Program wrapper pin differs from the qualified source closure')
    return True


def summary(root=ROOT):
    if public_metadata_mode(root):
        return public_metadata_command('status', root)
    docs, canonical = specifications(root)
    runtime = runtime_manifests(root)
    if set(runtime) - set(canonical):
        raise ValueError('Runtime references an unknown candidate ID')
    verified = [k for k, (p, d) in runtime.items() if verified_runtime(p, d, root)]
    programs = [k for k, (p, d) in runtime.items() if verified_program_runtime(p, d, root)]
    legacy = read(root / 'docs/neuroscience-benchmarks/build/implementation_status.json')
    native = [p for p in legacy['packages'] if p.get('native_harbor_oracle') == 1 and p.get('native_harbor_nop') == 0]
    delivery = legacy['current_delivery']
    references = delivery['bounded_reference_ids']
    if (len(references) != len(set(references)) or set(references) - set(canonical)
            or len(references) != delivery['bounded_reference_candidate_ids']):
        raise ValueError('Reference-run inventory is inconsistent with the canonical roster')
    return {'target_assignments': len(canonical), 'delivery_specifications': len(docs),
            'paper_specifications': sum(d['track'] == 'paper' for d in docs.values()),
            'neural_specifications': sum(d['track'] == 'neural' for d in docs.values()),
            'local_score_adapters_verified': len(verified), 'score_adapter_ids': sorted(verified),
            'local_program_runners_verified': len(programs), 'program_runner_ids': sorted(programs),
            'program_count_basis': 'Separate passed program qualification and pinned source closure; no candidate is run by metadata commands.',
            'bounded_reference_runs_recorded': len(references),
            'bounded_reference_ids': sorted(references),
            'distinct_ids_with_reference_or_score_adapter': len(set(references) | set(verified)),
            'reference_count_basis': 'Recorded scientific runs in the live construction ledger; this metadata command does not rerun them.',
            'historical_native_development_packages': len(native),
            'distinct_ids_with_native_package_or_scoring_adapter': len(set(verified) | {p['candidate_id'] for p in native}),
            'full_candidate_contracts_completed': legacy['full_candidate_contracts_completed'],
            'research_qualified': legacy['research_qualified'], 'submission_ready': legacy['submission_ready'],
            'counting_note': 'Reference and adapter counts overlap. Source specs and partial development components are not completed research tasks. No new model run is implied.'}


def score_command(task_id, submission, output, root=ROOT, *, review=None, other_reserve_bytes=None):
    _, canonical = specifications(root)
    if task_id not in canonical:
        raise ValueError('Unknown canonical task')
    runtime = runtime_manifests(root)
    if task_id not in runtime:
        raise ValueError('No local scoring adapter is implemented for ' + task_id)
    path, doc = runtime[task_id]
    if not verified_runtime(path, doc, root):
        raise ValueError('Scoring adapter has not passed its reference/negative checks')
    entry = doc['entrypoints']['score']
    argv = entry['argv']
    if (not isinstance(argv, list) or len(argv) < 2 or argv[0] not in ('python3', '{python}')
            or not all(isinstance(x, str) for x in argv)):
        raise ValueError('Expected a trusted Python scoring entrypoint')
    # Retain legacy submission/output formatting, but require new review inputs
    # as paired whole-token placeholders, just like program execution.
    if any(('{review' in arg or '{other_reserve_bytes' in arg)
           and arg not in ('{review}', '{other_reserve_bytes}') for arg in argv[2:]):
        raise ValueError('Scoring review/reserve placeholders must be whole tokens')
    if (argv[2:].count('{review}'), argv[2:].count('{other_reserve_bytes}')) not in ((0, 0), (1, 1)):
        raise ValueError('Reviewed scoring argv must contain review and reserve placeholders exactly once together')
    script = within(root, argv[1])
    if not script.is_relative_to(path.parent.resolve()) or not script.is_file():
        raise ValueError('Entrypoint must be inside the registered package')
    if digest(script) != entry['sha256']:
        raise ValueError('Scoring entrypoint changed after verification')
    cwd = within(root, entry.get('working_directory', '.'))
    if cwd != root.resolve():
        raise ValueError('Only repository-root scoring is supported')
    submission, output = Path(submission).resolve(), Path(output).resolve()
    if not submission.exists():
        raise ValueError('Submission does not exist')
    if output.exists():
        raise ValueError('Choose a fresh output path; existing results are never overwritten')
    values = {'submission': str(submission), 'output': str(output)}
    if '{review}' in argv[2:]:
        if review is None or type(other_reserve_bytes) is not int or other_reserve_bytes < 0:
            raise ValueError('This scorer requires --review and a nonnegative integer --other-reserve-bytes')
        review_path = Path(review).absolute()
        if not review_path.is_relative_to(root.resolve()):
            raise ValueError('Execution review must be inside the repository')
        review_path = _program_repo_file(root, review_path.relative_to(root.resolve()).as_posix())
        if not 0 < review_path.stat().st_size <= 32768:
            raise ValueError('Execution review must be a nonempty file of at most 32768 bytes')
        # Approval, current costs and reservations remain the pinned scorer's
        # responsibility. Argv construction and dry runs grant no authority.
        values.update(review=str(review_path), other_reserve_bytes=str(other_reserve_bytes))
    elif review is not None or other_reserve_bytes is not None:
        raise ValueError('This scorer does not declare review/reserve arguments')
    command = [sys.executable, str(script)] + [arg.format_map(values) for arg in argv[2:]]
    return command, cwd


def run_command(task_id, program, output, root=ROOT, *, review=None, other_reserve_bytes=None):
    """Construct one wrapper call. Never import or inspect candidate source text."""
    _, canonical = specifications(root)
    if task_id not in canonical:
        raise ValueError('Unknown canonical task')
    runtime = runtime_manifests(root)
    if task_id not in runtime:
        raise ValueError('No local program runner is implemented for ' + task_id)
    path, doc = runtime[task_id]
    if not verified_program_runtime(path, doc, root):
        raise ValueError('Program runner has no separate passing qualification; score verification is insufficient')
    entry, wrapper = _program_entry(doc['program_execution'], root)
    program, output = Path(program).absolute(), Path(output).absolute()
    if any(p.is_symlink() for p in (program, *program.parents)):
        raise ValueError('Candidate program path must not contain symlinks')
    info = program.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('Candidate program must be an ordinary single-link file')
    if output.exists() or any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError('Choose a fresh output directory without symlinks; existing results are never overwritten')
    if any(p.exists() and not p.is_dir() for p in output.parents):
        raise ValueError('Program output directory has a non-directory ancestor')
    values = {'{program}': str(program.resolve()), '{output}': str(output.resolve())}
    if '{review}' in entry['argv']:
        if review is None or type(other_reserve_bytes) is not int or other_reserve_bytes < 0:
            raise ValueError('This runner requires --review and a nonnegative integer --other-reserve-bytes')
        review_path = Path(review).absolute()
        if not review_path.is_relative_to(root.resolve()):
            raise ValueError('Execution review must be inside the repository')
        review_path = _program_repo_file(root, review_path.relative_to(root.resolve()).as_posix())
        if not 0 < review_path.stat().st_size <= 32768:
            raise ValueError('Execution review must be a nonempty file of at most 32768 bytes')
        # The pinned task wrapper validates approval, current cost, qualification,
        # and reservations. Constructing an argv or dry run grants no authority.
        values.update({'{review}': str(review_path), '{other_reserve_bytes}': str(other_reserve_bytes)})
    elif review is not None or other_reserve_bytes is not None:
        raise ValueError('This runner does not declare review/reserve arguments')
    command = [sys.executable, str(wrapper)] + [values.get(arg, arg) for arg in entry['argv'][2:]]
    return command, root.resolve()


def main(argv=None, root=None):
    dispatch_options = {} if root is None else {'root': Path(root)}
    root = ROOT if root is None else Path(root)
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='action', required=True)
    subs.add_parser('status')
    subs.add_parser('check')
    p = subs.add_parser('list'); p.add_argument('--track', choices=['paper', 'neural'])
    p = subs.add_parser('show'); p.add_argument('id')
    p = subs.add_parser('score'); p.add_argument('id'); p.add_argument('--submission', required=True)
    p.add_argument('--output', required=True); p.add_argument('--dry-run', action='store_true')
    p.add_argument('--review'); p.add_argument('--other-reserve-bytes', type=int)
    p = subs.add_parser('run'); p.add_argument('id'); p.add_argument('--program', required=True)
    p.add_argument('--output', required=True); p.add_argument('--dry-run', action='store_true')
    p.add_argument('--review'); p.add_argument('--other-reserve-bytes', type=int)
    args = parser.parse_args(argv)
    if args.action in ('status', 'check', 'list', 'show') and public_metadata_mode(root):
        result = public_metadata_command(args.action, root, track=getattr(args, 'track', None),
                                         task_id=getattr(args, 'id', None))
    elif args.action == 'status':
        result = summary(root)
    elif args.action == 'check':
        specifications(root, complete=True)
        result = {'metadata_check': 'passed', **summary(root)}
    elif args.action == 'list':
        docs, _ = specifications(root)
        runtime = runtime_manifests(root)
        result = [{'id': d['id'], 'title': d['title'], 'track': d['track'],
                   'source_specification': True,
                   'local_scoring_adapter_verified': d['id'] in runtime and verified_runtime(*runtime[d['id']], root),
                   'local_program_runner_verified': d['id'] in runtime and verified_program_runtime(*runtime[d['id']], root)}
                  for d in docs.values() if args.track is None or d['track'] == args.track]
    elif args.action == 'show':
        docs, _ = specifications(root)
        if args.id not in docs:
            raise ValueError('Specification not yet built for ' + args.id)
        result = {'specification': docs[args.id],
                  'runtime': runtime_manifests(root).get(args.id, (None, None))[1]}
    else:
        if args.action == 'run':
            command, cwd = run_command(args.id, args.program, args.output, **dispatch_options,
                                       review=args.review, other_reserve_bytes=args.other_reserve_bytes)
        else:
            command, cwd = score_command(args.id, args.submission, args.output, **dispatch_options,
                                         review=args.review, other_reserve_bytes=args.other_reserve_bytes)
        if not args.dry_run:
            return subprocess.run(command, cwd=cwd, check=False).returncode
        result = {'argv': command, 'working_directory': str(cwd), 'executed': False}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({'status': 'refused', 'reason': str(exc)}), file=sys.stderr)
        raise SystemExit(2)
