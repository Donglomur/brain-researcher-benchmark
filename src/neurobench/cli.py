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

ROOT = Path(__file__).resolve().parents[2]
COMMON = {'schema_version', 'id', 'track', 'title', 'status', 'primary_outputs',
          'input_assets', 'evaluation', 'resources', 'holds',
          'next_implementation_action', 'provenance', 'admission'}


def public_metadata_mode(root):
    """The current registry is required; historical ledgers never select a mode."""
    path = Path(root) / 'benchmarks/registry.json'
    if not path.is_file():
        raise ValueError('Current benchmark registry is required')
    return True


def public_catalog_module():
    # Explicit sibling load also works under python -I, without changing sys.path.
    spec = importlib.util.spec_from_file_location('neurobench_public_catalog',
                                                 Path(__file__).with_name('catalog.py'))
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
            'paper_improvement': catalog['paper_improvement_counts'],
            'paper_outcomes': catalog['paper_outcome_counts'],
            'neural_understanding': catalog['neural_understanding_counts'],
            'recorded_evidence': {key: catalog['recorded_evidence'][key]
                                  for key in ('counts', 'reports', 'scope')},
            'count_basis': 'Current benchmark registry and its pinned task definitions. '
                           'Selected public reports are indexed separately with their scopes. '
                           'Raw runtime receipts, candidate code, data and private construction ledgers are not inspected.',
            'counting_note': catalog['counting_note']}


def public_implementations(catalog, task):
    """Resolve declared source relationships without importing implementations."""
    artifacts = {record['id']: record for record in catalog['implementations']}

    def sources(identifiers):
        return [
            {**{key: artifacts[identifier][key] for key in
                ('id', 'path', 'role', 'scope', 'owner_ids', 'scope_notes')},
             'related_task_ids': artifacts[identifier].get('related_task_ids', []),
             'declared_source_status': artifacts[identifier].get('status'),
             'scientific_readiness': 'unknown'}
            for identifier in identifiers
        ]

    return {**{key: task[key] for key in ('id', 'title', 'track', 'task_directory',
                                         'scientific_readiness', 'submission_readiness')},
            'paper_improvement': task.get('paper_improvement'),
            'paper_outcomes': task.get('paper_outcomes'),
            'neural_understanding': task.get('neural_understanding'),
            'recorded_evidence': task.get('recorded_evidence', []),
            'evaluation_role': ('same_task_improvement_construction'
                                if task.get('paper_improvement', {}).get('initial_registration')
                                else 'calibration_only' if task['track'] == 'paper' else 'declared_source'),
            'implementations': sources(task['implementation_ids']),
            'related_sources': sources(task['related_implementation_ids']),
            'documentation': task.get('documentation', []),
            'interpretation': 'Explicit source assignments and related scientific sources. '
                              'Presence does not establish complete task coverage or execution readiness. '
                              'The evaluation_role describes retained runtime scope; current outcome contracts and individual source roles remain separate. '
                              'No implementation code, data or verification receipts were opened.'}


def public_metadata_command(action, root, *, track=None, task_id=None):
    builder = public_catalog_module()
    catalog = builder.generate(root, check=True) if action == 'check' else builder.load(root)
    if action in ('status', 'check'):
        result = public_summary(catalog)
        if action == 'check':
            result.update(metadata_check='passed', check_scope='Deterministic public metadata/catalog consistency only')
        return result
    if action == 'list':
        return [{**{key: row[key] for key in ('id', 'title', 'track', 'source_specification',
                  'registration_stage', 'specification', 'runtime_manifest',
                  'implementation_ids', 'related_implementation_ids',
                  'scientific_readiness', 'submission_readiness',
                  'local_scoring_adapter_verified', 'local_program_runner_verified')},
                 'paper_improvement': row.get('paper_improvement'),
                 'paper_outcomes': row.get('paper_outcomes'),
                 'neural_understanding': row.get('neural_understanding'),
                 'recorded_evidence': row.get('recorded_evidence', [])}
                for row in catalog['tasks'] if track is None or row['track'] == track]
    row = next((row for row in catalog['tasks'] if row['id'] == task_id), None)
    if row is None:
        raise ValueError('Specification not yet built for ' + str(task_id))
    source_view = public_implementations(catalog, row)
    if action == 'implementations':
        return source_view
    return {'specification': read(builder.public_path(Path(root), row['specification']['path'])),
            'runtime': read(builder.public_path(Path(root), row['runtime_manifest']['path']))
                       if row['runtime_manifest'] else None,
            'catalog_entry': row, 'sources': source_view}


def read(path):
    return json.loads(path.read_text())


def within(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Path escapes its permitted root')
    return path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _current_registry(root):
    """Read the current ownership registry without traversing historical locators."""
    path = _program_repo_file(root, 'benchmarks/registry.json')
    if not 0 < path.stat().st_size <= 4 * 1024 * 1024:
        raise ValueError('Current registry must be bounded metadata')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate current registry key')
            result[key] = value
        return result
    value = json.loads(path.read_text(), object_pairs_hook=pairs,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite registry metadata')))
    if (not isinstance(value, dict) or value.get('schema_version') != 1
            or value.get('kind') != 'neuroscience_benchmark_registry'):
        raise ValueError('Unsupported current benchmark registry')
    rows = value.get('tasks')
    if not isinstance(rows, list) or not 0 < len(rows) <= 4096:
        raise ValueError('Current registry requires a bounded task roster')
    identities = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Current registry task must be an object')
        identifier, track = row.get('id'), row.get('track')
        if (not isinstance(identifier, str) or not 0 < len(identifier) <= 200
                or not identifier[0].isalnum()
                or any(character not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-' for character in identifier)
                or track not in ('paper', 'neural') or identifier.casefold() in identities):
            raise ValueError('Unsafe, duplicate or wrong-track current task identity')
        identities.add(identifier.casefold())
        directory = 'benchmarks/' + track + '/' + identifier
        if (row.get('task_directory') != directory or not isinstance(row.get('specification'), dict)
                or row['specification'].get('path') != directory + '/task.json'):
            raise ValueError('Task definition must belong to its current task directory')
    return value


def specifications(root=ROOT, complete=False):
    registry = _current_registry(root)
    if (registry.get('paper_improvement', {}).get('coverage_required')
            or registry.get('neural_understanding', {}).get('coverage_required')):
        public_catalog_module().load(root)
    docs, expected = {}, {}
    for row in registry['tasks']:
        pin = _object(row.get('specification'), 'Task specification pin')
        path = _program_pin(root, pin.get('path'), pin.get('sha256'), pin.get('bytes'))
        doc = _object(read(path), 'Task specification')
        identity = doc.get('id', doc.get('candidate_id', doc.get('task_id')))
        if (identity != row.get('specification_id')
                or row.get('specification_alias') != (identity != row['id'])
                or doc.get('track', row['track']) != row['track']):
            raise ValueError('Current task/specification identity differs')
        if row.get('registration_class') == 'canonical' and (not COMMON.issubset(doc) or doc.get('schema_version') != 1):
            raise ValueError('Incomplete canonical delivery schema')
        if row.get('registration_class') == 'canonical':
            admission = _object(doc.get('admission'), 'Canonical source admission')
            allowed = {'specification_only', 'source_only_inactive', 'source_implemented_inactive'}
            if row.get('specification_revision', {}).get('version') == 'paper-improvement/v1':
                allowed |= {'improvement_ready', 'design_ready', 'source_unresolved', 'ineligible'}
            if (doc.get('status') not in allowed
                    or admission.get('runnable') is not False
                    or admission.get('research_qualified') is not False):
                raise ValueError('Source specifications cannot promote runtime or research admission')
        docs[row['id']], expected[row['id']] = doc, row
    if complete:
        totals = registry.get('source_counts', {})
        actual = {'paper': sum(row['track'] == 'paper' for row in expected.values()),
                  'neural': sum(row['track'] == 'neural' for row in expected.values()), 'total': len(expected)}
        if any(totals.get(key) != number for key, number in actual.items()):
            raise ValueError('Current registry task totals disagree')
    return docs, expected


def runtime_manifests(root=ROOT):
    """Use explicitly registered declarations, never scan old package locations."""
    docs = {}
    for row in _current_registry(root)['tasks']:
        pin = row.get('runtime_manifest')
        if pin is None:
            continue
        pin = _object(pin, 'Runtime declaration pin')
        path = _program_pin(root, pin.get('path'), pin.get('sha256'), pin.get('bytes'))
        if (path.parent != within(root, row.get('runtime_package'))
                or not path.is_relative_to(within(root, row['task_directory']) / 'implementations')):
            raise ValueError('Runtime declaration is outside its registered task implementation')
        doc = _object(read(path), 'Runtime declaration')
        if doc.get('id') != row['id']:
            raise ValueError('Runtime declaration task identity differs')
        docs[row['id']] = (path, doc)
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
    public_metadata_mode(root)
    return public_metadata_command('status', root)


def paper_contract(task_id, root=ROOT, *, outcome='improvement'):
    """Read the current pinned public contract, never an implementation's claims."""
    if outcome not in ('reproduction', 'improvement'):
        raise ValueError('Expected reproduction or improvement outcome')
    builder = public_catalog_module()
    catalog = builder.load(root)
    task = next((row for row in catalog['tasks'] if row['id'] == task_id), None)
    if task is None or task['track'] != 'paper':
        raise ValueError('Expected a registered paper task')
    if outcome == 'reproduction':
        binding = task.get('paper_outcomes')
        if not binding:
            raise ValueError('No current paper outcome contracts are bound for ' + task_id)
        pin = binding.get('reproduction_contract')
        if pin is None:
            raise ValueError('No reproduction proposal is bound for inspection: ' + task_id)
    else:
        binding = task.get('paper_outcomes', {})
        if binding.get('availability') == 'unavailable':
            raise ValueError('Primary paper outcomes are unavailable: ' + binding['reason'])
        improvement = task.get('paper_improvement')
        if not improvement:
            raise ValueError('No current paper improvement contract is bound for ' + task_id)
        pin = improvement['contract']
    raw = _program_pin(root, pin['path'], pin['sha256'], pin['bytes'], return_bytes=True)
    return builder.improvement_module().loads_contract(raw.decode('utf-8'))


def _paper_outcome_documents(task_id, root, *, allow_unavailable=False):
    """Read only exact public pins after complete current/previous lineage checks."""
    builder = public_catalog_module()
    catalog = builder.load(root)
    task = next((row for row in catalog['tasks'] if row['id'] == task_id), None)
    if task is None or task['track'] != 'paper':
        raise ValueError('Expected a registered paper task')
    binding = task.get('paper_outcomes')
    if not binding:
        raise ValueError('No current paper outcome contracts are bound for ' + task_id)
    unavailable = binding.get('availability') == 'unavailable'
    if unavailable and not allow_unavailable:
        raise ValueError('Primary paper outcomes are unavailable: ' + binding['reason'])
    outcome_binding = builder.companion_module('paper_outcomes_binding')
    parser = builder.improvement_module().loads_contract
    documents = {}
    for name, field in (('reproduction', 'reproduction_contract'), ('improvement', 'improvement_contract'),
                        ('outcomes', 'outcomes')):
        pin = binding.get(field)
        if pin is None:
            documents[name] = None
            continue
        raw = _program_pin(root, pin['path'], pin['sha256'], pin['bytes'], return_bytes=True)
        documents[name] = parser(raw.decode('utf-8'))
    engine = outcome_binding.engine(documents['reproduction'])
    if unavailable:
        return task, binding, documents, engine
    errors = engine.outcomes_validate(documents['outcomes'], documents['reproduction'], documents['improvement'])
    if errors or documents['outcomes']['original_task_sha256'] != task['specification']['sha256']:
        raise ValueError('Paper outcome contracts differ from the authenticated current task: ' + '; '.join(errors))
    return task, binding, documents, engine


def paper_outcomes(task_id, root=ROOT):
    """Inspect one task's four declared cells without supplying or inferring runs."""
    task, binding, documents, engine = _paper_outcome_documents(task_id, root, allow_unavailable=True)
    summary = ({'task_id': task_id, 'task_count': 1, **binding}
               if binding.get('availability') == 'unavailable' else
               engine.summary(documents['outcomes'], documents['reproduction'], documents['improvement']))
    if 'primary_scope_correction' in binding:
        summary['primary_scope_correction'] = binding['primary_scope_correction']
    return {'task_id': task_id, 'specification': task['specification'],
            'binding': {key: binding[key] for key in
                        ('previous_specification', 'reproduction_contract', 'improvement_contract', 'outcomes')},
            'descriptor': documents['outcomes'],
            'summary': summary}


def _outcome_receipt(path, engine):
    """Read explicit bounded metadata, never follow its evidence locators."""
    path = Path(path).absolute()
    limit = 2 * 1024 * 1024
    message = 'Outcome receipt must be bounded ordinary JSON metadata'
    if any(item.is_symlink() for item in (path, *path.parents)) or not path.is_file():
        raise ValueError(message)
    before = path.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or not 0 < before.st_size <= limit:
        raise ValueError(message)
    with path.open('rb') as stream:
        raw = stream.read(limit + 1)
    after = path.stat()
    if (len(raw) != before.st_size or len(raw) > limit
            or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns, before.st_nlink)
            != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns, after.st_nlink)):
        raise ValueError('Outcome receipt changed during bounded read')
    return engine.loads_contract(raw.decode('utf-8'))


def check_paper_outcome(task_id, receipt_path, root=ROOT):
    """Validate one declared AI outcome receipt; this does not score science."""
    _, _, documents, engine = _paper_outcome_documents(task_id, root)
    receipt = _outcome_receipt(receipt_path, engine)
    return engine.admit_outcome(documents['outcomes'], documents['reproduction'], documents['improvement'], receipt)


def neural_contract(task_id, root=ROOT):
    """Return the current registered neural objective and separate access conditions."""
    builder = public_catalog_module()
    catalog = builder.load(root)
    task = next((row for row in catalog['tasks'] if row['id'] == task_id), None)
    if task is None or task['track'] != 'neural':
        raise ValueError('Expected a registered neural task')
    understanding = task.get('neural_understanding')
    if not understanding:
        raise ValueError('No current neural understanding contract is bound for ' + task_id)
    pin = understanding['contract']
    raw = _program_pin(root, pin['path'], pin['sha256'], pin['bytes'], return_bytes=True)
    return json.loads(raw)


def recorded_evidence(task_id=None, root=ROOT):
    builder = public_catalog_module()
    catalog = builder.load(root)
    evidence = catalog['recorded_evidence']
    if task_id is None:
        return evidence
    if task_id not in {row['id'] for row in catalog['tasks']}:
        raise ValueError('Expected a registered task ID')
    return {'task_id': task_id, 'records': evidence['records'].get(task_id, []),
            'scope': evidence['scope']}


def compare_paper(task_id, result_path, root=ROOT):
    contract = paper_contract(task_id, root)
    # Result evidence is public aggregate metadata, not prediction or target data.
    path = Path(result_path).absolute()
    limit = 2 * 1024 * 1024
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
        raise ValueError('Comparison result must be bounded ordinary JSON metadata')
    before = path.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or not 0 < before.st_size <= limit:
        raise ValueError('Comparison result must be bounded ordinary JSON metadata')
    with path.open('rb') as stream:
        raw = stream.read(limit + 1)
    after = path.stat()
    if (len(raw) != before.st_size or len(raw) > limit
            or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)):
        raise ValueError('Comparison result changed during bounded read')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate comparison evidence key')
            result[key] = value
        return result
    doc = json.loads(raw, object_pairs_hook=pairs,
                     parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite comparison evidence')))
    return public_catalog_module().improvement_module().compare(contract, doc)


def require_paper_role(row, calibration):
    if row['track'] == 'paper' and not calibration:
        raise ValueError('Paper reproduction and same-task source-paper superiority use independent outcome contracts. '
                         'Historical score/run adapters are calibration only; use scripts/neurobench.py score/run --calibration explicitly, '
                         'or inspect the separate reproduction and improvement contracts with paper-contract --outcome and paper-outcomes. '
                         'compare-paper and check-paper-outcome validate declared metadata without establishing scientific success.')


def require_neural_role(row, calibration, root=ROOT):
    """A passing old adapter cannot redefine a revised neural scientific target."""
    if (row['track'] != 'neural'
            or row.get('specification_revision', {}).get('version') != 'neural-understanding/v1'):
        return
    # Authenticate the current contract; the registry's display summary is not
    # an authority for target fidelity. This precedes runtime verification and
    # candidate/target I/O; the catalog only reads public declaration metadata.
    contract = neural_contract(row['id'], root)
    fidelity = contract['implementation']['target_fidelity']
    if fidelity in {'different_target', 'no_target_evaluator', 'unresolved'} and not calibration:
        raise ValueError('The current neural target has ' + fidelity + ' source fidelity. '
                         'A verified historical adapter cannot establish that target. '
                         'Use --calibration explicitly for its historical scope, or inspect '
                         'neural-contract ' + row['id'] + ' for the current observations and target.')


def score_command(task_id, submission, output, root=ROOT, *, review=None, other_reserve_bytes=None, calibration=False):
    _, canonical = specifications(root)
    if task_id not in canonical:
        raise ValueError('Unknown canonical task')
    require_paper_role(canonical[task_id], calibration)
    require_neural_role(canonical[task_id], calibration, root)
    runtime = runtime_manifests(root)
    if task_id not in runtime:
        raise ValueError('No local scoring adapter is registered for this command and task: ' + task_id
                         + '. Use implementations ' + task_id + ' to inspect available source.')
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


def run_command(task_id, program, output, root=ROOT, *, review=None, other_reserve_bytes=None, calibration=False):
    """Construct one wrapper call. Never import or inspect candidate source text."""
    _, canonical = specifications(root)
    if task_id not in canonical:
        raise ValueError('Unknown canonical task')
    require_paper_role(canonical[task_id], calibration)
    require_neural_role(canonical[task_id], calibration, root)
    runtime = runtime_manifests(root)
    if task_id not in runtime:
        raise ValueError('No local program runner is registered for this command and task: ' + task_id
                         + '. Use implementations ' + task_id + ' to inspect available source.')
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
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == 'operator':
        return public_catalog_module().companion_module('operator_routes').main(argv[1:], root=root)
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='action', required=True)
    subs.add_parser('status')
    subs.add_parser('check')
    p = subs.add_parser('list'); p.add_argument('--track', choices=['paper', 'neural'])
    p = subs.add_parser('show'); p.add_argument('id')
    p = subs.add_parser('implementations', help='Show current source paths, roles and limits for a task')
    p.add_argument('id')
    p = subs.add_parser('paper-contract', help='Inspect one current source-grounded paper outcome contract')
    p.add_argument('id')
    p.add_argument('--outcome', choices=['reproduction', 'improvement'], default='improvement')
    p = subs.add_parser('paper-outcomes', help='Inspect separate paper outcomes and paired information conditions')
    p.add_argument('id')
    p = subs.add_parser('check-paper-outcome', help='Validate one declared outcome receipt; execute no scientific evaluator')
    p.add_argument('id'); p.add_argument('--receipt', required=True)
    p = subs.add_parser('neural-contract', help='Inspect the current target and separate neural access conditions')
    p.add_argument('id')
    p = subs.add_parser('evidence', help='Read scoped public execution reports without promoting qualification')
    p.add_argument('id', nargs='?')
    p = subs.add_parser('operator', help='Inspect authentic inputs, prepare supported routes or grade existing submissions')
    p.add_argument('arguments', nargs=argparse.REMAINDER)
    p = subs.add_parser('compare-paper', help='Check aggregate comparison evidence against the frozen same-task contract')
    p.add_argument('id'); p.add_argument('--result', required=True)
    p = subs.add_parser('score'); p.add_argument('id'); p.add_argument('--submission', required=True)
    p.add_argument('--output', required=True); p.add_argument('--dry-run', action='store_true')
    p.add_argument('--review'); p.add_argument('--other-reserve-bytes', type=int)
    p.add_argument('--calibration', action='store_true', help='Explicitly use historical calibration scope; cannot establish current paper or neural success')
    p = subs.add_parser('run'); p.add_argument('id'); p.add_argument('--program', required=True)
    p.add_argument('--output', required=True); p.add_argument('--dry-run', action='store_true')
    p.add_argument('--review'); p.add_argument('--other-reserve-bytes', type=int)
    p.add_argument('--calibration', action='store_true', help='Explicitly use historical calibration scope; cannot establish current paper or neural success')
    args = parser.parse_args(argv)
    if args.action == 'paper-contract':
        result = paper_contract(args.id, root, outcome=args.outcome)
    elif args.action == 'paper-outcomes':
        result = paper_outcomes(args.id, root)
    elif args.action == 'check-paper-outcome':
        result = check_paper_outcome(args.id, args.receipt, root)
    elif args.action == 'neural-contract':
        result = neural_contract(args.id, root)
    elif args.action == 'evidence':
        result = recorded_evidence(args.id, root)
    elif args.action == 'compare-paper':
        result = compare_paper(args.id, args.result, root)
    elif args.action in ('status', 'check', 'list', 'show', 'implementations') and public_metadata_mode(root):
        result = public_metadata_command(args.action, root, track=getattr(args, 'track', None),
                                         task_id=getattr(args, 'id', None))
    else:
        if args.calibration:
            dispatch_options['calibration'] = True
        if args.action == 'run':
            command, cwd = run_command(args.id, args.program, args.output, **dispatch_options,
                                       review=args.review, other_reserve_bytes=args.other_reserve_bytes)
        else:
            command, cwd = score_command(args.id, args.submission, args.output, **dispatch_options,
                                         review=args.review, other_reserve_bytes=args.other_reserve_bytes)
        if not args.dry_run:
            if args.calibration:
                print(json.dumps({'evaluation_role': 'calibration_only', 'paper_win': False,
                                  'current_task_success': False}), file=sys.stderr)
            return subprocess.run(command, cwd=cwd, check=False).returncode
        result = {'argv': command, 'working_directory': str(cwd), 'executed': False}
        if args.calibration:
            result.update(evaluation_role='calibration_only', paper_win=False, current_task_success=False)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if args.action == 'compare-paper' and result.get('comparison_admitted') is not True:
        return 2
    if args.action == 'check-paper-outcome' and result.get('metadata_admitted') is not True:
        return 2
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({'status': 'refused', 'reason': str(exc)}), file=sys.stderr)
        raise SystemExit(2)
