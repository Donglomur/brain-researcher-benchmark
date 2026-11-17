#!/usr/bin/env python3
"""Audit every workflow SHA occurrence; apply only explicit reviewed pin changes.

The ledger binds occurrences to paths, not content-search guesses. Existing CI
validators still own namespace and specialized semantic checks. This tool never
executes workflow or benchmark code and never discovers replacement source pins.
"""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from neurobench.source_integrity import InvalidSource, Reader, physical_members, relative, require, strict_json, task_registry

LEDGER = 'scripts/maintenance/workflow_source_pins.json'
SHA = re.compile(rb'(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])')
CPU_WORKFLOW = '.github/workflows/neuroscience-source-integrity.yml'
CPU_SOURCE = 'benchmarks/shared/frozen-neural-lifecycle-v1/candidate_entry.py'
GROUP = re.compile(rb'(?m)^(?P<indent> +)rows = (?P<rows>\[.*?\])\n(?P=indent)packages = (?P<packages>\[.*?\])\n(?P<tail>.*?)(?=\n(?P=indent)[A-Z_]+\n)', re.S)


def encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode()


def identity(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def checked_body(root, name, pin):
    # Separate bounded readers permit the complete workflow + 702-source scope
    # without changing the enrolled source checker's smaller global budget.
    reader = Reader(root)
    require(set(pin) == {'bytes', 'sha256'} and type(pin['bytes']) is int
            and 0 <= pin['bytes'] <= 8 * 1024 * 1024, 'Bounded exact source extent required')
    require(type(pin['sha256']) is str and re.fullmatch('[0-9a-f]{64}', pin['sha256']),
            'Exact source digest required')
    body = reader.read(relative(name), limit=8 * 1024 * 1024)
    require(identity(body) == pin, 'Source hash or length mismatch: ' + name)
    return body


def workflows(root):
    base = root / '.github/workflows'
    require(base.is_dir() and not base.is_symlink(), 'Ordinary workflow directory required')
    found = []
    for path in sorted(base.iterdir()):
        require(path.is_file() and not path.is_symlink(), 'Unexpected workflow directory/member')
        require(path.suffix in ('.yml', '.yaml'), 'Unclassified workflow file: ' + str(path))
        found.append(path.relative_to(root).as_posix())
    require(0 < len(found) <= 100, 'Bounded workflow roster required')
    return found


def load_ledger(root):
    value = strict_json(Reader(root).read(LEDGER))
    validate_ledger(value)
    return value


def validate_changes(changes):
    require(type(changes) is dict and set(changes) == {'schema', 'reason', 'updates'}
            and changes['schema'] == 'workflow-pin-changes/v1', 'Closed explicit change request required')
    require(type(changes['reason']) is str and 12 <= len(changes['reason'].strip()) <= 4096, 'Review reason required')
    require(type(changes['updates']) is list and 0 < len(changes['updates']) <= 1000, 'Bounded nonempty updates required')
    paths = set()
    for update in changes['updates']:
        require(type(update) is dict and set(update) == {'previous', 'current'}, 'Closed old/new update required')
        for pin in update.values():
            require(type(pin) is dict and set(pin) == {'path', 'bytes', 'sha256'}, 'Complete old/new descriptors required')
            relative(pin['path'])
            require(type(pin['bytes']) is int and 0 <= pin['bytes'] <= 8 * 1024 * 1024, 'Invalid receipt extent')
            require(type(pin['sha256']) is str and re.fullmatch('[0-9a-f]{64}', pin['sha256']), 'Invalid receipt digest')
        require(update['previous']['path'] not in paths, 'Duplicate source update')
        paths.add(update['previous']['path'])


def validate_ledger(value):
    require(type(value) is dict, 'Ledger object required')
    require(set(value) == {'schema', 'baseline_commit', 'sources', 'workflows', 'reviewed_updates'},
            'Closed occurrence ledger required')
    require(value['schema'] == 'workflow-source-pins/v1', 'Unknown ledger schema')
    require(type(value['baseline_commit']) is str and re.fullmatch('[0-9a-f]{40}', value['baseline_commit']),
            'Exact baseline commit required')
    require(type(value['reviewed_updates']) is list and len(value['reviewed_updates']) <= 1000,
            'Bounded reviewed update history required')
    for changes in value['reviewed_updates']:
        validate_changes(changes)
    require(type(value['sources']) is dict and len(value['sources']) <= 2000, 'Bounded source map required')
    require(type(value['workflows']) is list and len(value['workflows']) <= 100, 'Bounded workflows required')


def cpu_contract(root, body):
    tree = ast.parse(Reader(root).read(CPU_SOURCE))
    limits = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == 'setrlimit' and len(node.args) == 2
                and isinstance(node.args[0], ast.Attribute) and node.args[0].attr == 'RLIMIT_CPU'):
            limits.append(ast.literal_eval(node.args[1]))
    require(len(limits) == 1, 'Expected one child CPU contract')
    soft, hard = limits[0]
    require(type(soft) is int and type(hard) is int and 0 < soft <= hard, 'Invalid child CPU contract')
    text = body.decode()
    match = re.search(r'^  generated-numerical-regressions:\n(.*?)(?=^  [\w-]+:|\Z)', text, re.M | re.S)
    require(match is not None, 'Missing numerical CPU parent job')
    commands = re.findall(r'^\s+(ulimit[^\n]+)$', match[1], re.M)
    require(commands == [f'ulimit -t {hard}', f'ulimit -S -t {soft}'],
            'Numerical parent CPU limits cannot admit the child soft/hard contract')
    return {'soft': soft, 'hard': hard}


def historical_binding(root, name, pin, registered):
    parts = name.split('/')
    if len(parts) != 5 or parts[0] != 'benchmarks' or parts[3] != 'historical':
        return
    if parts[4] not in ('task.pre-improvement.v1.json', 'task.pre-understanding.v1.json'):
        return
    row = registered.get(parts[2])
    require(type(row) is dict, 'Unregistered historical task: ' + name)
    revision = row.get('specification_revision', {})
    require(revision.get('previous_specification') == {'path': name, **pin},
            'Historical workflow pin disagrees with registered predecessor: ' + name)
    original = row['original_specification']
    require(all(original[k] == pin[k] for k in ('bytes', 'sha256')), 'Original task pin was replaced: ' + name)


def literal_groups(root, body, *, verify=True):
    """Retain the complete literal package closures and their aggregate guards."""
    groups = []
    for match in GROUP.finditer(body):
        rows = ast.literal_eval(match['rows'].decode())
        packages = ast.literal_eval(match['packages'].decode())
        require(type(rows) is list and type(packages) is list, 'Literal closure group required')
        require(all(type(r) is dict and set(r) == {'path', 'bytes', 'sha256'} for r in rows),
                'Closed literal group source rows required')
        total = sum(r['bytes'] for r in rows)
        tail = match['tail']
        sums = list(re.finditer(rb"assert sum\(row\['bytes'\] for row in rows\) == (?P<n>[0-9]+)", tail))
        reports = list(re.finditer(rb"'verified_bytes': (?P<n>[0-9]+)", tail))
        counts = list(re.finditer(rb'assert len\(rows\) == (?P<n>[0-9]+)', tail))
        require(len(sums) == len(reports) == len(counts) == 1, 'Unknown literal group aggregate form')
        if verify:
            require(int(sums[0]['n']) == int(reports[0]['n']) == total,
                    'Literal workflow source byte total is stale')
            require(int(counts[0]['n']) == len(rows), 'Literal workflow source count is stale')
            require(len({r['path'] for r in rows}) == len(rows), 'Duplicate literal closure member')
            for package in packages:
                selected = {r['path'] for r in rows if r['path'].startswith(relative(package) + '/')}
                require(physical_members(root, package) == selected, 'Complete package namespace mismatch: ' + package)
        groups.append((match, total, sums[0], reports[0]))
    return groups


def audit(root, *, ledger=None, bodies=None, verify_sources=True):
    root = Path(root).absolute()
    ledger = load_ledger(root) if ledger is None else ledger
    validate_ledger(ledger)
    bodies = {} if bodies is None else bodies
    names = workflows(root)
    require([w['path'] for w in ledger['workflows']] == names, 'Workflow roster differs from reviewed ledger')
    occurrences, external, used, pins, total, group_count = [], 0, set(), {}, 0, 0
    for workflow in ledger['workflows']:
        require(set(workflow) == {'path', 'bytes', 'sha256', 'occurrences'}, 'Closed workflow ledger row required')
        name = workflow['path']
        body = bodies.get(name)
        if body is None:
            body = checked_body(root, name, {k: workflow[k] for k in ('bytes', 'sha256')})
        require(identity(body) == {k: workflow[k] for k in ('bytes', 'sha256')}, 'Workflow snapshot mismatch: ' + name)
        group_count += len(literal_groups(root, body))
        total += len(body)
        require(total <= 4 * 1024 * 1024, 'Workflow read budget exceeded')
        actual = list(SHA.finditer(body))
        require(len(actual) == len(workflow['occurrences']), 'Incomplete SHA occurrence coverage: ' + name)
        for match, occurrence in zip(actual, workflow['occurrences']):
            require(type(occurrence['offset']) is int and occurrence['offset'] == match.start(),
                    'SHA occurrence position changed: ' + name)
            if set(occurrence) == {'offset', 'external'}:
                require(occurrence['external'] == 'pypi-wheel'
                        and body[max(0, match.start()-14):match.start()].endswith(b'--hash=sha256:'),
                        'Only explicit pip wheel hashes may be external')
                external += 1
                continue
            require(set(occurrence) == {'offset', 'source'}, 'Unclassified SHA occurrence: ' + name)
            source = relative(occurrence['source'])
            require(source in ledger['sources'], 'Unbound source occurrence: ' + source)
            descriptor = ledger['sources'][source]
            require(set(descriptor) == {'bytes'}, 'Source bytes descriptor required')
            pin = {**descriptor, 'sha256': match.group().decode()}
            require(source not in pins or pin == pins[source], 'Conflicting workflow pins: ' + source)
            pins[source] = pin
            used.add(source)
            occurrences.append({'workflow': name, 'line': body[:match.start()].count(b'\n') + 1,
                                'offset': match.start(), 'path': source, **pin})
    require(used == set(ledger['sources']), 'Unreferenced ledger source')
    receipts = {}
    for changes in ledger['reviewed_updates']:
        for update in changes['updates']:
            old, new = update['previous'], update['current']
            require(old['path'] not in receipts or receipts[old['path']] == old,
                    'Conflicting source update history: ' + old['path'])
            receipts.pop(old['path'], None)
            require(new['path'] not in receipts, 'Receipt overwrites another source identity')
            receipts[new['path']] = new
    for name, pin in receipts.items():
        require(name in pins and {'path': name, **pins[name]} == pin,
                'Reviewed update history disagrees with workflow source: ' + name)
    require(sum(p['bytes'] for p in pins.values()) <= 32 * 1024 * 1024, 'Source audit byte budget exceeded')
    if verify_sources:
        registered = task_registry(Reader(root))
        for name, pin in pins.items():
            checked_body(root, name, pin)
            historical_binding(root, name, pin, registered)
    cpu_row = next(w for w in ledger['workflows'] if w['path'] == CPU_WORKFLOW)
    cpu_body = bodies.get(CPU_WORKFLOW)
    if cpu_body is None:
        cpu_body = checked_body(root, CPU_WORKFLOW, {k: cpu_row[k] for k in ('bytes', 'sha256')})
    cpu = cpu_contract(root, cpu_body)
    return {'schema': 'workflow-source-audit/v1', 'status': 'passed', 'workflows': len(names),
            'sha256_occurrences': len(occurrences) + external, 'source_occurrences': len(occurrences),
            'external_wheel_occurrences': external, 'source_files': len(used),
            'source_bytes': sum(p['bytes'] for p in pins.values()), 'cpu_contract': cpu,
            'complete_literal_package_groups': group_count,
            'benchmark_execution': False, 'occurrences': occurrences}


def propose(root, changes):
    """No source-discovery or re-pin mode: old/new identities are mandatory."""
    validate_changes(changes)
    ledger = load_ledger(root)
    before = audit(root, ledger=ledger, verify_sources=False)
    current = {row['path']: {'path': row['path'], 'bytes': row['bytes'], 'sha256': row['sha256']}
               for row in before['occurrences']}
    registered = task_registry(Reader(root))
    updates = {}
    for update in changes['updates']:
        require(set(update) == {'previous', 'current'}, 'Closed old/new update required')
        old, new = update['previous'], update['current']
        require(set(old) == set(new) == {'path', 'bytes', 'sha256'}, 'Complete old/new descriptors required')
        require(old['path'] in current and current[old['path']] == old, 'Stale or unbound old pin: ' + old['path'])
        require(old['path'] not in updates, 'Duplicate source update')
        checked_body(root, new['path'], {k: new[k] for k in ('bytes', 'sha256')})
        require('/historical/' not in old['path'], 'Historical evidence cannot be repinned')
        if old['path'] != new['path']:
            require(old['path'].endswith('/task.json') and '/historical/' in new['path'], 'Only task history redirects may change paths')
            require(old['path'].rsplit('/', 1)[0] == new['path'].split('/historical/')[0], 'Cross-task redirect refused')
            require(all(old[k] == new[k] for k in ('bytes', 'sha256')), 'Historical redirect must preserve original bytes/hash')
            expected_history = ('task.pre-understanding.v1.json' if old['path'].startswith('benchmarks/neural/')
                                else 'task.pre-improvement.v1.json')
            require(new['path'] == old['path'].rsplit('/', 1)[0] + '/historical/' + expected_history,
                    'Unrecognized historical destination')
            historical_binding(root, new['path'], {k: new[k] for k in ('bytes', 'sha256')}, registered)
        else:
            require(not old['path'].endswith('/task.json'), 'Canonical task pins require explicit historical redirect')
        updates[old['path']] = update
    output = copy.deepcopy(ledger)
    bodies = {}
    for workflow in output['workflows']:
        original = checked_body(root, workflow['path'], {k: workflow[k] for k in ('bytes', 'sha256')})
        body = original
        edits = []
        for occurrence in workflow['occurrences']:
            update = updates.get(occurrence.get('source'))
            if update is None:
                continue
            old, new = update['previous'], update['current']
            if old['bytes'] != new['bytes'] or old['path'] != new['path']:
                # Only a complete literal descriptor gives an unambiguous size
                # edit. Scalar/CLI size changes need a separately reviewed ledger.
                pattern = rb'[\"\x27]path[\"\x27]\s*:\s*[\"\x27](?P<path>' + re.escape(old['path'].encode()) + rb')[\"\x27]\s*,\s*[\"\x27]bytes[\"\x27]\s*:\s*(?P<size>[0-9]+)\s*,\s*[\"\x27]sha256[\"\x27]\s*:\s*[\"\x27](?P<sha>[0-9a-f]{64})'
                matches = [m for m in re.finditer(pattern, original) if m.start('sha') == occurrence['offset']]
                # One reviewed CLI form authenticates a descriptor by digest
                # alone: it has no inline source-size token to update. Its
                # semantic source binding remains the exact occurrence ledger.
                offset = occurrence['offset']
                line_start = original.rfind(b'\n', 0, offset) + 1
                digest_flag = re.search(rb"--expected-sha256[ \t]+(?P<quote>['\"])$",
                                        original[line_start:offset])
                digest_only = (digest_flag is not None and old['path'] == new['path']
                               and original[offset+64:offset+65] == digest_flag['quote'])
                require((len(matches) == 1 and int(matches[0]['size']) == old['bytes']) or digest_only,
                        'Size-changing or redirected non-dictionary pin needs manual review: ' + old['path'])
                if matches:
                    edits.append((matches[0].start('size'), matches[0].end('size'), str(new['bytes']).encode()))
                    edits.append((matches[0].start('path'), matches[0].end('path'), new['path'].encode()))
            edits.append((occurrence['offset'], occurrence['offset'] + 64, new['sha256'].encode()))
            occurrence['source'] = new['path']
        for start, end, replacement in sorted(set(edits), reverse=True):
            body = body[:start] + replacement + body[end:]
        # Recompute only aggregate guards of the exact literal arrays changed
        # above. Preserve all other control logic and namespace expressions.
        aggregate_edits = []
        for match, total, summed, reported in literal_groups(root, body, verify=False):
            for field in (summed, reported):
                start = match.start('tail') + field.start('n')
                end = match.start('tail') + field.end('n')
                aggregate_edits.append((start, end, str(total).encode()))
        for start, end, replacement in sorted(aggregate_edits, reverse=True):
            body = body[:start] + replacement + body[end:]
        found = list(SHA.finditer(body))
        require(len(found) == len(workflow['occurrences']), 'Update changed SHA occurrence roster')
        for match, occurrence in zip(found, workflow['occurrences']):
            occurrence['offset'] = match.start()
        workflow.update(identity(body))
        bodies[workflow['path']] = body
    for oldpath, update in updates.items():
        del output['sources'][oldpath]
        output['sources'][update['current']['path']] = {'bytes': update['current']['bytes']}
    output['reviewed_updates'].append(changes)
    audit(root, ledger=output, bodies=bodies)
    return output, bodies


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--plan', type=Path, help='Explicit old/new source descriptors; emit reviewed plan')
    mode.add_argument('--apply', type=Path, help='Apply exactly a previously emitted reviewed plan')
    args = parser.parse_args()
    try:
        if args.plan or args.apply:
            supplied = strict_json((args.plan or args.apply).read_bytes())
            changes = supplied if args.plan else supplied['changes']
            ledger, bodies = propose(args.root, changes)
            plan = {'schema': 'workflow-pin-plan/v1', 'changes': changes,
                    'ledger_previous': identity(Reader(args.root).read(LEDGER)),
                    'ledger_current': identity(encoded(ledger)),
                    'workflows': [{'path': name, **identity(body)} for name, body in bodies.items()]}
            if args.apply:
                require(supplied == plan, 'Reviewed plan is stale or altered; re-plan and review')
                # All inputs, sources and outputs validated before the first write.
                for name, body in bodies.items():
                    if Reader(args.root).read(name) != body:
                        (args.root / name).write_bytes(body)
                (args.root / LEDGER).write_bytes(encoded(ledger))
                result = audit(args.root)
            else:
                result = plan
        else:
            result = audit(args.root)
        output = encoded(result)
        if args.output:
            args.output.write_bytes(output)
        else:
            sys.stdout.buffer.write(output)
    except (InvalidSource, OSError, UnicodeError, ValueError, TypeError, KeyError) as error:
        parser.exit(1, 'Workflow source preflight failed: ' + str(error) + '\n')


if __name__ == '__main__':
    main()
