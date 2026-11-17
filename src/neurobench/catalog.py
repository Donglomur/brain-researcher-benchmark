#!/usr/bin/env python3
"""Build a deterministic navigation catalog from published metadata only.

Never follow runtime verification receipts, data paths, private ledgers or
candidate entrypoints. Selected public reports are indexed with their original
scope; neither their presence nor catalog membership is execution qualification.
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import posixpath
import re
import stat
import sys
from urllib.parse import quote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = 'benchmarks/catalog'
COMMON = {'schema_version', 'id', 'track', 'title', 'status', 'primary_outputs',
          'input_assets', 'evaluation', 'resources', 'holds',
          'next_implementation_action', 'provenance', 'admission'}
READ_LIMIT = 24 * 1024 * 1024


def improvement_module():
    spec = importlib.util.spec_from_file_location('neurobench_paper_improvement',
                                                 Path(__file__).with_name('paper_improvement.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def companion_module(name):
    """Load a fixed framework sibling without importing task implementation code."""
    need(name in {'neural_understanding', 'evidence', 'operator_routes'}, 'Unknown framework companion')
    spec = importlib.util.spec_from_file_location('neurobench_' + name,
                                                 Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def understanding_counts(tasks):
    neural = [row for row in tasks if row['track'] == 'neural']
    dispositions = Counter(row.get('neural_understanding', {}).get('disposition', 'not_revised')
                           for row in neural)
    return {'registered': len(neural), 'covered': len(neural) - dispositions['not_revised'],
            'dispositions': dict(sorted(dispositions.items())),
            'count_basis': 'Source delivery scope, not model performance or scientific qualification.'}


def improvement_counts(tasks):
    papers = [row for row in tasks if row['track'] == 'paper']
    dispositions = Counter(row.get('paper_improvement', {}).get('disposition', 'not_audited') for row in papers)
    return {'registered': len(papers), 'covered': len(papers) - dispositions['not_audited'],
            'eligible': dispositions['improvement_ready'] + dispositions['design_ready'],
            'improvement_ready': dispositions['improvement_ready'],
            'design_ready': dispositions['design_ready'], 'source_unresolved': dispositions['source_unresolved'],
            'ineligible': dispositions['ineligible'], 'not_audited': dispositions['not_audited']}


def need(value, message):
    if not value:
        raise ValueError(message)


def public_path(root, relative):
    """Resolve repository navigation links, never arbitrary evidence locators."""
    need(isinstance(relative, str) and relative and not Path(relative).is_absolute()
         and '\\' not in relative, 'Expected a relative public source path')
    need(posixpath.normpath(relative) == relative and relative != '.' and '..' not in Path(relative).parts,
         'Expected a normalized public source path')
    path = root / relative
    resolved = path.resolve()
    need(resolved.is_relative_to(root.resolve()), 'Public source link escapes repository')
    need(not any(p.is_symlink() for p in (path, *path.parents) if p != root.parent),
         'Public source links cannot use symlinks')
    need(path.exists(), 'Missing public source link: ' + relative)
    return resolved


class Reader:
    def __init__(self, root):
        self.root = root.resolve()
        self.bytes = 0

    def read(self, path):
        path = public_path(self.root, path.relative_to(self.root).as_posix())
        info = path.stat()
        need(stat.S_ISREG(info.st_mode) and info.st_size <= 4 * 1024 * 1024,
             'Expected bounded ordinary public metadata: ' + str(path.relative_to(self.root)))
        self.bytes += info.st_size
        need(self.bytes <= READ_LIMIT, 'Public metadata read limit exceeded')
        with path.open('rb') as stream:
            raw = stream.read(4 * 1024 * 1024 + 1)
        after = path.stat()
        need(len(raw) == info.st_size and len(raw) <= 4 * 1024 * 1024
             and (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
             == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
             'Public metadata changed during read')
        def pairs(items):
            result = {}
            for key, value in items:
                need(key not in result, 'Duplicate JSON metadata key')
                result[key] = value
            return result
        doc = json.loads(raw, object_pairs_hook=pairs,
                         parse_constant=lambda value: need(False, 'Non-JSON numeric constant'))
        need(isinstance(doc, dict), 'Public metadata must be an object')
        return doc, {'path': path.relative_to(self.root).as_posix(),
                     'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def counts(tasks):
    result = Counter(row['track'] for row in tasks)
    return {'paper': result['paper'], 'neural': result['neural'], 'total': len(tasks)}



def external_links(doc):
    """Only public HTTP(S) source citations; omit signed/query/userinfo URLs."""
    found = set()
    def collect(value, kind):
        if isinstance(value, str):
            if not value.startswith(('http://', 'https://')):
                return
            try:
                parsed = urlsplit(value)
            except ValueError:
                return
            if (parsed.scheme in ('http', 'https') and parsed.hostname and not parsed.query
                    and not parsed.fragment and not parsed.username and not parsed.password
                    and not any(c.isspace() for c in value)):
                found.add((kind, value))
        elif isinstance(value, dict):
            for child in value.values():
                collect(child, kind)
        elif isinstance(value, list):
            for child in value:
                collect(child, kind)
    for key, kind in [('paper_identity', 'paper'), ('paper', 'paper'),
                      ('official_code', 'code'), ('code', 'code'), ('data', 'data')]:
        collect(doc.get(key), kind)
    input_assets = doc.get('input_assets', {})
    need(isinstance(input_assets, dict), 'Task input_assets must be an object when declared')
    collect(input_assets.get('routes', []), 'source')
    collect(doc.get('sources'), 'source')
    return [{'kind': kind, 'url': url} for kind, url in sorted(found)]


def task_directory(identifier, track):
    need(track in ('paper', 'neural'), 'Unknown task track')
    need(isinstance(identifier, str)
         and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', identifier)
         and len(identifier) <= 200
         and identifier.casefold() != 'readme.md', 'Unsafe task directory ID')
    return f'benchmarks/{track}/{identifier}'


def task_row(identifier, title, track, pin, stage, registry, doc):
    need(isinstance(identifier, str) and identifier and isinstance(title, str) and title,
         'Task ID and title must be nonempty strings')
    need(track in ('paper', 'neural'), 'Unknown task track')
    return {'id': identifier, 'title': title, 'track': track,
            'task_directory': task_directory(identifier, track),
            'specification_id': doc.get('id', doc.get('candidate_id', doc.get('task_id'))),
            'specification_alias': doc.get('id', doc.get('candidate_id', doc.get('task_id'))) != identifier,
            'track_source': 'registry' if registry else 'canonical_specification',
            'declared_specification_status': doc.get('status', doc.get('state')),
            'source_specification': True, 'registration_stage': stage,
            'specification': pin, 'registry': registry,
            'runtime_manifest': None, 'runtime_package': None,
            'runtime_manifest_status': None,
            'scientific_readiness': 'unknown', 'submission_readiness': 'unknown',
            'local_scoring_adapter_verified': None, 'local_program_runner_verified': None,
            'external_links': external_links(doc)}


REGISTRY = 'benchmarks/registry.json'


def checked_pin(reader, pin, label):
    need(isinstance(pin, dict) and type(pin.get('bytes')) is int and pin['bytes'] >= 0
         and isinstance(pin.get('sha256'), str) and re.fullmatch(r'[0-9a-f]{64}', pin['sha256']),
         'Invalid ' + label + ' pin')
    path = public_path(reader.root, pin['path'])
    doc, actual = reader.read(path)
    need(all(pin[key] == actual[key] for key in ('path', 'bytes', 'sha256')),
         label + ' pin mismatch')
    return doc


def checked_implementations(records, by_id, root):
    need(isinstance(records, list), 'Implementation inventory must be a list')
    seen_ids, seen_paths = set(), set()
    for record in records:
        need(isinstance(record, dict), 'Implementation record must be an object')
        identifier, owners = record.get('id'), record.get('owner_ids')
        need(isinstance(identifier, str) and identifier and identifier not in seen_ids,
             'Duplicate or missing implementation ID')
        seen_ids.add(identifier)
        need(isinstance(owners, list) and all(isinstance(owner, str) for owner in owners)
             and len(set(owners)) == len(owners), 'Implementation owner IDs must be unique strings')
        need(set(owners) <= set(by_id), 'Unknown implementation owner')
        related = record.get('related_task_ids', [])
        need(isinstance(related, list) and all(isinstance(identifier, str) for identifier in related)
             and len(set(related)) == len(related), 'Related task IDs must be unique strings')
        need(set(related) <= set(by_id), 'Unknown related task ID')
        need(not set(related).intersection(owners), 'Related task IDs must be distinct from implementation owners')
        scope = record.get('scope')
        need(scope in ('task', 'shared', 'unresolved'), 'Unknown implementation scope')
        need(scope != 'task' or len(owners) == 1, 'Task implementation must have exactly one owner')
        need(scope != 'unresolved' or not owners, 'Unresolved implementation must not claim task owners')
        for field in ('role', 'scope_notes', 'original_path'):
            need(isinstance(record.get(field), str) and record[field].strip(),
                 'Implementation requires explicit ' + field)
        need(isinstance(record.get('source_commit'), str)
             and re.fullmatch(r'[0-9a-f]{40}', record['source_commit']), 'Implementation requires a source commit')
        path = public_path(root, record['path'])
        need(record['path'].casefold() not in seen_paths, 'Duplicate implementation artifact path')
        seen_paths.add(record['path'].casefold())
        need(path.is_dir() or path.is_file(), 'Implementation artifact must be a file or directory')
    return records


def checked_documentation(records, directory, root):
    need(isinstance(records, list), 'Task documentation must be a list')
    seen = set()
    for record in records:
        need(isinstance(record, dict) and isinstance(record.get('label'), str)
             and record['label'].strip(), 'Task documentation needs a label')
        relative = record.get('path')
        need(isinstance(relative, str) and relative.startswith(directory + '/'),
             'Task documentation must be inside its exact task folder')
        need(relative not in seen, 'Duplicate task documentation path')
        seen.add(relative)
        public_path(root, relative)
    return records


def discover(root=ROOT):
    """Read the current registry; never infer task ownership from legacy paths."""
    root = Path(root).resolve()
    reader = Reader(root)
    registry, registry_pin = reader.read(root / REGISTRY)
    need(registry.get('schema_version') == 1
         and registry.get('kind') == 'neuroscience_benchmark_registry', 'Unsupported benchmark registry')
    need(isinstance(registry.get('source_commit'), str)
         and re.fullmatch(r'[0-9a-f]{40}', registry['source_commit']), 'Registry requires its source commit')
    rows = registry['tasks']
    need(isinstance(rows, list) and all(isinstance(row, dict) for row in rows), 'Registry tasks must be objects')
    need(len({row['id'] for row in rows}) == len(rows), 'Duplicate registered task ID')
    improvement_meta = registry.get('paper_improvement')
    previous_rows = None
    if improvement_meta is not None:
        need(isinstance(improvement_meta, dict)
             and improvement_meta.get('schema_version') == 'paper-improvement/v1'
             and improvement_meta.get('objective') == 'surpass_source_paper_same_task'
             and improvement_meta.get('coverage_required') is True
             and type(improvement_meta.get('registered_count')) is int
             and improvement_meta['registered_count'] == sum(row['track'] == 'paper' for row in rows),
             'Invalid current paper improvement registry binding')
        previous_pin = improvement_meta['pre_improvement_registry']
        need(previous_pin['path'] == 'docs/provenance/registrations/paper-pre-improvement-v1.json',
             'Unexpected pre-improvement registry location')
        previous_registry = checked_pin(reader, previous_pin, 'Pre-improvement registry')
        need(previous_registry.get('schema_version') == 1
             and previous_registry.get('kind') == 'neuroscience_benchmark_registry',
             'Unsupported pre-improvement registry')
        previous_rows = {row['id']: row for row in previous_registry['tasks']}
        need(len(previous_rows) == len(previous_registry['tasks'])
             and set(previous_rows) <= {row['id'] for row in rows}
             and {row['id'] for row in previous_rows.values() if row['track'] == 'paper'}
             == {row['id'] for row in rows if row['track'] == 'paper'},
             'Paper overhaul must preserve the original registration roster')
    understanding_meta = registry.get('neural_understanding')
    previous_neural_rows = None
    if understanding_meta is not None:
        need(isinstance(understanding_meta, dict)
             and understanding_meta.get('schema_version') == 'neural-understanding/v1'
             and understanding_meta.get('objective') == 'infer_neural_or_behavioral_targets_from_permitted_observations'
             and understanding_meta.get('coverage_required') is True
             and type(understanding_meta.get('registered_count')) is int
             and understanding_meta['registered_count'] == sum(row['track'] == 'neural' for row in rows),
             'Invalid current neural understanding registry binding')
        previous_pin = understanding_meta['pre_understanding_registry']
        need(previous_pin['path'] == 'docs/provenance/registrations/neural-pre-understanding-v1.json',
             'Unexpected pre-understanding registry location')
        previous_registry = checked_pin(reader, previous_pin, 'Pre-understanding registry')
        need(previous_registry.get('schema_version') == 1
             and previous_registry.get('kind') == 'neuroscience_benchmark_registry',
             'Unsupported pre-understanding registry')
        previous_neural_rows = {row['id']: row for row in previous_registry['tasks']}
        need(len(previous_neural_rows) == len(previous_registry['tasks'])
             and set(previous_neural_rows) <= {row['id'] for row in rows}
             and {row['id'] for row in previous_neural_rows.values() if row['track'] == 'neural'}
             == {row['id'] for row in rows if row['track'] == 'neural'},
             'Neural revision must preserve the original registration roster')
    historical = registry['historical_registries']
    need(isinstance(historical, list), 'Historical registries must be a list')
    historical_paths = set()
    for pin in historical:
        need(pin['path'] not in historical_paths, 'Duplicate historical registry')
        historical_paths.add(pin['path'])
        # Authenticate the preserved JSON body, but do not traverse its old locators.
        checked_pin(reader, pin, 'Historical registry')
    tasks = []
    classes = {'canonical': [], 'expansion': []}
    for row in rows:
        identifier, track = row['id'], row['track']
        directory = task_directory(identifier, track)
        need(row.get('task_directory') == directory, 'Task directory does not match its track and ID')
        need(row['specification']['path'] == directory + '/task.json', 'Authoritative task definition must be task.json in its task folder')
        doc = checked_pin(reader, row['specification'], 'Task specification')
        original = row['original_specification']
        need(isinstance(original, dict) and isinstance(original.get('path'), str), 'Missing original task identity')
        revision = row.get('specification_revision')
        if track == 'paper' and registry.get('paper_improvement', {}).get('coverage_required'):
            need(revision is not None, 'Active paper improvement registry requires every paper contract')
        if track == 'neural' and registry.get('neural_understanding', {}).get('coverage_required'):
            need(revision is not None, 'Active neural understanding registry requires every neural contract')
        improvement = None
        understanding = None
        if revision is None:
            need(all(original.get(key) == row['specification'][key] for key in ('bytes', 'sha256')),
                 'Task definition differs from its preserved original identity')
        elif track == 'neural':
            need(previous_neural_rows is not None, 'Revised neural task requires its authenticated original registry')
            need(type(revision) is dict and set(revision) ==
                 {'version', 'previous_specification', 'understanding_contract'}
                 and revision['version'] == 'neural-understanding/v1',
                 'Unsupported task specification revision')
            previous = revision['previous_specification']
            need(previous['path'] == directory + '/historical/task.pre-understanding.v1.json'
                 and all(previous.get(key) == original.get(key) for key in ('bytes', 'sha256')),
                 'Revised neural task does not preserve its original identity')
            prior_row = previous_neural_rows[identifier]
            need(prior_row['track'] == 'neural'
                 and all(prior_row['specification'].get(key) == previous.get(key) for key in ('bytes', 'sha256'))
                 and original == prior_row['original_specification']
                 and row['specification_id'] == prior_row['specification_id']
                 and row['specification_alias'] == prior_row['specification_alias'],
                 'Revised neural lineage differs from original registry')
            checked_pin(reader, previous, 'Historical neural specification')
            pin = revision['understanding_contract']
            need(pin['path'] == directory + '/understanding.v1.json', 'Understanding contract is outside its task')
            contract = checked_pin(reader, pin, 'Neural understanding contract')
            engine = companion_module('neural_understanding')
            errors = engine.validate_contract(contract, task_id=identifier)
            need(not errors, 'Invalid neural understanding contract: ' + identifier + ': ' + '; '.join(errors))
            expected_binding = {
                'schema_version': 'neural-understanding/v1',
                'objective': 'infer_neural_or_behavioral_targets_from_permitted_observations',
                'contract_path': 'understanding.v1.json', 'contract_sha256': pin['sha256'],
                'original_definition_path': 'historical/task.pre-understanding.v1.json',
                'original_definition_sha256': previous['sha256'],
            }
            need(doc.get('objective') == expected_binding['objective']
                 and doc.get('evaluation', {}).get('neural_understanding') == expected_binding,
                 'Current neural definition is not bound to its understanding contract')
            understanding = {**engine.summary(contract), 'contract': pin,
                             'historical_specification': previous}
        else:
            need(previous_rows is not None, 'Revised paper task requires its authenticated original registry')
            need(track == 'paper' and revision.get('version') == 'paper-improvement/v1',
                 'Unsupported task specification revision')
            previous = revision['previous_specification']
            need(previous['path'] == directory + '/historical/task.pre-improvement.v1.json'
                 and all(previous.get(key) == original.get(key) for key in ('bytes', 'sha256')),
                 'Revised task does not preserve its original identity')
            prior_row = previous_rows[identifier]
            need(prior_row['track'] == 'paper'
                 and all(prior_row['specification'].get(key) == previous.get(key) for key in ('bytes', 'sha256'))
                 and original == prior_row['original_specification']
                 and row['specification_id'] == prior_row['specification_id']
                 and row['specification_alias'] == prior_row['specification_alias'],
                 'Revised paper lineage differs from original registry')
            checked_pin(reader, previous, 'Historical paper specification')
            pin = revision['improvement_contract']
            need(pin['path'] == directory + '/improvement.v1.json', 'Improvement contract is outside its task')
            contract = checked_pin(reader, pin, 'Paper improvement contract')
            engine = improvement_module()
            errors = engine.validate_contract(contract, task_id=identifier)
            need(not errors, 'Invalid paper improvement contract: ' + identifier + ': ' + '; '.join(errors))
            need(doc.get('objective') == 'surpass_source_paper_same_task'
                 and doc.get('evaluation', {}).get('contract') == pin
                 and doc.get('evaluation', {}).get('reproduction_role') == 'calibration_only'
                 and doc.get('status') == contract['disposition'],
                 'Current paper definition is not bound to its improvement contract')
            improvement = {**engine.summary(contract), 'contract': pin,
                           'historical_specification': previous}
        identity = doc.get('id', doc.get('candidate_id', doc.get('task_id')))
        need(isinstance(identity, str) and identity == row['specification_id'], 'Task specification identity mismatch')
        need(type(row['specification_alias']) is bool and row['specification_alias'] == (identity != identifier),
             'Task specification alias must be explicit')
        need(doc.get('track') is None or doc['track'] == track, 'Task specification track mismatch')
        classification = row['registration_class']
        need(classification in classes, 'Unknown registration class')
        if classification == 'canonical':
            need(COMMON.issubset(doc) and type(doc['schema_version']) is int
                 and doc['schema_version'] == 1 and identity == identifier
                 and row['registry'] is None and row['track_source'] == 'canonical_specification',
                 'Canonical task lineage mismatch')
            need(doc['track'] == track, 'Canonical task track must match its registry track')
        else:
            need(row['registry'] in historical_paths and row['track_source'] == 'registry',
                 'Expansion task lineage mismatch')
        # Expansion drafts may omit a title, but a declared authoritative title
        # cannot silently disagree with the registry's display value.
        if 'title' in doc:
            need(isinstance(doc['title'], str) and bool(doc['title'].strip())
                 and row['title'] == doc['title'], 'Task title must match its registry title')
        need(row['declared_specification_status'] == doc.get('status', doc.get('state')),
             'Declared specification status differs from task.json')
        task = task_row(identifier, row['title'], track, row['specification'],
                        row['registration_stage'], row['registry'], doc)
        task.update(original_specification=original, registration_class=classification,
                    runtime_manifest=row.get('runtime_manifest'), runtime_package=row.get('runtime_package'),
                    runtime_manifest_status=row.get('runtime_manifest_status'),
                    runtime_lineage_note='Preserved declaration lineage; not current execution qualification.',
                    implementation_ids=[], related_implementation_ids=[],
                    documentation=checked_documentation(row.get('documentation', []), directory, root))
        if improvement is not None:
            task['paper_improvement'] = improvement
            task['specification_revision'] = revision
            task['runtime_lineage_note'] = 'Historical paper implementations are calibration components; they cannot establish same-task paper improvement.'
        if understanding is not None:
            task['neural_understanding'] = understanding
            task['specification_revision'] = revision
            task['runtime_lineage_note'] = 'Earlier neural runtime declarations retain their original scope; programme results do not establish direct or viewer interpretation.'
        if task['runtime_manifest']:
            runtime = checked_pin(reader, task['runtime_manifest'], 'Runtime declaration')
            need(runtime.get('id') == identifier, 'Runtime declaration task ID mismatch')
            need(task['runtime_package'] == str(Path(task['runtime_manifest']['path']).parent),
                 'Runtime declaration package mismatch')
            need(task['runtime_manifest_status'] == runtime.get('status'), 'Runtime declaration status mismatch')
        else:
            need(task['runtime_package'] is None and task['runtime_manifest_status'] is None,
                 'Orphan runtime declaration fields')
        tasks.append(task)
        classes[classification].append(task)
    tasks.sort(key=lambda row: row['id'])
    need(counts(classes['canonical']) == {'paper': 100, 'neural': 100, 'total': 200},
         'Expected exactly 200 canonical specifications: 100 per track')
    source_counts = registry['source_counts']
    need(all(source_counts.get(key) == value for key, value in counts(tasks).items()), 'Registry source task counts disagree')
    need(source_counts.get('canonical_specifications') == 200
         and source_counts.get('expansion_drafts') == len(classes['expansion']), 'Registry source classification counts disagree')
    by_id = {row['id']: row for row in tasks}
    implementations = checked_implementations(registry['implementations'], by_id, root)
    for implementation in implementations:
        for owner in implementation['owner_ids']:
            by_id[owner]['implementation_ids'].append(implementation['id'])
        for related in implementation.get('related_task_ids', []):
            by_id[related]['related_implementation_ids'].append(implementation['id'])
    for row in tasks:
        row['implementation_ids'].sort()
        row['related_implementation_ids'].sort()
    evidence = companion_module('evidence').load(root, task_ids=set(by_id))
    for row in tasks:
        row['recorded_evidence'] = evidence['records'].get(row['id'], [])
    components = registry.get('components', [])
    shared = registry.get('shared_contracts', [])
    need(isinstance(components, list) and isinstance(shared, list), 'Source collections and shared contracts must be lists')
    need(len(components) == source_counts['source_components'], 'Source component lineage count mismatch')
    runtime_count = sum(row['runtime_manifest'] is not None for row in tasks)
    need(runtime_count == source_counts['linked_runtime_manifests'] == source_counts['runtime_manifests'],
         'Runtime declaration lineage count mismatch')
    result = {'schema_version': 1, 'kind': 'public_neuroscience_source_catalog',
              'registry': registry_pin, 'source_commit': registry['source_commit'],
              'source_counts': source_counts,
              'counts': {**source_counts, 'implementation_artifacts': len(implementations),
                         'tasks_with_implementation_artifacts': sum(bool(row['implementation_ids']) for row in tasks),
                         'tasks_with_related_scientific_sources': sum(bool(row['related_implementation_ids']) for row in tasks),
                         'unresolved_implementation_artifacts': sum(row['scope'] == 'unresolved' for row in implementations)},
              'paper_improvement_counts': improvement_counts(tasks),
              'neural_understanding_counts': understanding_counts(tasks),
              'recorded_evidence': evidence,
              'scientific_readiness': 'unknown', 'submission_readiness': 'unknown',
              'counting_note': 'Registered task definitions, implementation artifacts and legacy runtime declarations are distinct. '
                               'An ownership link is not equivalence to the complete registered scientific contract or execution qualification. '
                               'Only selected public evidence reports are indexed, with their reported scopes; '
                               'no raw receipts, data, candidate code or private construction ledger were followed.',
              'registry_chain': historical, 'shared_contracts': shared, 'tasks': tasks,
              'unmapped_runtime_sources': [], 'components': components,
              'implementations': sorted(implementations, key=lambda record: record['id'])}
    validate(result, root)
    return result


def source_links(catalog):
    yield catalog['registry']['path']
    for report in catalog['recorded_evidence']['reports']:
        yield report['path']
    for implementation in catalog['implementations']:
        yield implementation['path']
    for row in catalog['tasks']:
        for document in row.get('documentation', []):
            yield document['path']
        yield row['specification']['path']
        if row.get('paper_improvement'):
            yield row['paper_improvement']['contract']['path']
            yield row['paper_improvement']['historical_specification']['path']
        if row.get('neural_understanding'):
            yield row['neural_understanding']['contract']['path']
            yield row['neural_understanding']['historical_specification']['path']
        if row['registry']:
            yield row['registry']
        if row['runtime_manifest']:
            yield row['runtime_manifest']['path']
            yield row['runtime_package']
    for row in catalog['registry_chain'] + catalog['shared_contracts'] + catalog['components']:
        yield row['path']
    for row in catalog['unmapped_runtime_sources']:
        yield row['manifest']['path']


def validate(catalog, root=ROOT):
    need(catalog.get('schema_version') == 1 and catalog.get('kind') == 'public_neuroscience_source_catalog',
         'Unsupported public catalog')
    tasks = catalog['tasks']
    need(len({row['id'] for row in tasks}) == len(tasks), 'Duplicate catalog task ID')
    need(all(catalog['counts'][key] == value for key, value in counts(tasks).items()), 'Catalog task totals disagree')
    need(catalog.get('paper_improvement_counts') == improvement_counts(tasks), 'Paper improvement counts disagree')
    need(catalog.get('neural_understanding_counts') == understanding_counts(tasks), 'Neural understanding counts disagree')
    need(catalog['scientific_readiness'] == catalog['submission_readiness'] == 'unknown',
         'Catalog must not manufacture readiness')
    directories = set()
    for row in tasks:
        directory = task_directory(row['id'], row['track'])
        need(row.get('task_directory', directory) == directory, 'Task directory does not match its track and ID')
        need(directory.casefold() not in directories, 'Ambiguous task directory ID')
        directories.add(directory.casefold())
        checked_documentation(row.get('documentation', []), directory, Path(root))
        need(row['scientific_readiness'] == row['submission_readiness'] == 'unknown'
             and row['local_scoring_adapter_verified'] is None
             and row['local_program_runner_verified'] is None, 'Catalog must not manufacture task qualification')
    implementations = checked_implementations(catalog['implementations'], {row['id']: row for row in tasks}, Path(root))
    owners = {row['id']: [] for row in tasks}
    related_tasks = {row['id']: [] for row in tasks}
    for implementation in implementations:
        for owner in implementation['owner_ids']:
            owners[owner].append(implementation['id'])
        for related in implementation.get('related_task_ids', []):
            related_tasks[related].append(implementation['id'])
    for row in tasks:
        need(row['implementation_ids'] == sorted(owners[row['id']]), 'Orphan or mismatched task implementation reference')
        need(row['related_implementation_ids'] == sorted(related_tasks[row['id']]), 'Orphan or mismatched related source reference')
    need(catalog['counts']['implementation_artifacts'] == len(implementations), 'Implementation artifact count mismatch')
    need(catalog['counts']['tasks_with_implementation_artifacts'] == sum(bool(ids) for ids in owners.values()),
         'Task implementation coverage count mismatch')
    need(catalog['counts']['tasks_with_related_scientific_sources'] == sum(bool(ids) for ids in related_tasks.values()),
         'Related scientific source coverage count mismatch')
    need(catalog['counts']['unresolved_implementation_artifacts'] == sum(row['scope'] == 'unresolved' for row in implementations),
         'Unresolved implementation count mismatch')
    for relative in source_links(catalog):
        public_path(Path(root), relative)
    return catalog


def load(root=ROOT):
    # The checked-in registry is authoritative. A generated catalog is a view,
    # so stale cached metadata must not hide changed task definitions or owners.
    return discover(root)


def markdown_link(label, path, base=OUTPUT):
    relative = posixpath.relpath(path, base)
    return '[' + label + '](' + quote(relative, safe='/.-_') + ')'


def paper_count_text(catalog):
    counts = catalog['paper_improvement_counts']
    return (f"Paper improvement audit: **{counts['covered']}/{counts['registered']} covered**; "
            f"**{counts['improvement_ready']} improvement-ready**, **{counts['design_ready']} source-grounded designs**, "
            f"**{counts['source_unresolved']} source-unresolved**, **{counts['ineligible']} ineligible**, "
            f"**{counts['not_audited']} not audited**. Eligibility means an ordered source task was identified; "
            'it does not establish an executable or scientifically qualified comparison. '
            'Reproduction and numerical fidelity are calibration only. A new split is an extension, never a same-task paper victory.\n\n')


def neural_count_text(catalog):
    summary = catalog['neural_understanding_counts']
    if not summary['covered']:
        return ''
    dispositions = ', '.join(f"{number} {name.replace('_', ' ')}"
                             for name, number in summary['dispositions'].items())
    return (f"Neural understanding revision: **{summary['covered']}/{summary['registered']} covered**; "
            + dispositions + '. These describe delivered source scope. Direct observation, typed-viewer interpretation, '
            'tool-assisted investigation and frozen prediction programmes have separate access conditions and evidence. '
            'Programme performance does not establish direct interpretation.\n\n')


def evidence_text(catalog, base=OUTPUT):
    evidence = catalog['recorded_evidence']
    counts = evidence['counts']
    if not counts['tasks_with_recorded_evidence']:
        return ''
    return (f"Recorded public evidence covers **{counts['tasks_with_recorded_evidence']} distinct task IDs**. "
            f"The pilot reports **{counts['paper_calibration_attempts']} historical paper-calibration attempts** and "
            f"**{counts['neural_programme_attempts']} neural-programme attempts**; "
            f"{counts['authentic_engineering_reports']} authentic-input engineering reports are separate software evidence. "
            + markdown_link('Read the published evidence', evidence['reports'][0]['path'], base)
            + ', or run `python3 scripts/neurobench.py evidence [TASK_ID]`. '
            'These records do not establish current runtime qualification or paper improvement.\n\n')


def render(catalog):
    c = catalog['counts']
    files = {'catalog.json': (json.dumps(catalog, indent=2, ensure_ascii=False) + '\n').encode()}
    intro = ('This is a public source inventory, not a list of qualified benchmarks. '
             'Scientific and submission readiness are **unknown here**. Runtime manifests '
             'and source components do not establish successful execution. Registered IDs '
             'may alias earlier contract identifiers; they do not count independent studies or datasets.\n\n')
    files['README.md'] = (f'# Neuroscience task catalog\n\n{intro}' + evidence_text(catalog) + paper_count_text(catalog) + neural_count_text(catalog) +
        f"Browse **{c['total']} registered questions**: [{c['paper']} paper tasks](paper.md) and "
        f"[{c['neural']} neural/behavioral tasks](neural.md). The roster combines 200 canonical specifications "
        f"with {c['expansion_drafts']} expansion drafts.\n\n"
        'Browse the task folders in [paper research](../paper/README.md) and '
        '[neural-data understanding](../neural/README.md). Each track separates its original 100 from expansion drafts.\n\n'
        f"The checkout also contains {c['runtime_manifests']} one-level runtime manifests and "
        f"{c['source_components']} historical [source component collections](components.md). "
        f"The current registry assigns {c['implementation_artifacts']} implementation artifacts, including "
        f"{c['unresolved_implementation_artifacts']} with unresolved ownership. "
        'Participants, conditions, folds, seeds and controls are nested task units, not additional benchmarks.\n\n'
        'The [machine-readable catalog](catalog.json) includes exact specification pins and links to existing public files. '
        'External citations are copied from public specifications; their availability was not rechecked.\n\n'
        'The authoritative [registry](../registry.json) assigns implementations explicitly. Ownership does not establish equivalence to the full registered scientific contract.\n\n'
        'Regenerate with `python3 scripts/catalog.py`; verify with '
        '`python3 scripts/catalog.py --check`, from the repository root.\n\n'
        'Preserved historical registration snapshots (their old task locators are not current discovery inputs):\n\n' +
        ''.join('- ' + markdown_link(row['path'].split('/')[-2], row['path']) + '\n' for row in catalog['registry_chain']) +
        '\nShared scope and interpretation documents:\n\n' +
        ''.join('- ' + markdown_link(row['kind'], row['path']) + '\n' for row in catalog['shared_contracts'])).encode()
    for track in ('paper', 'neural'):
        rows = [row for row in catalog['tasks'] if row['track'] == track]
        text = f'# {track.title()} tasks ({len(rows)})\n\n[Catalog](README.md)\n\n' + intro
        if track == 'paper':
            text += paper_count_text(catalog)
        else:
            text += neural_count_text(catalog)
        text += ('| ID | Scientific question / title | Current improvement disposition | Source stage | Implementation artifacts | Legacy runtime declaration |\n| --- | --- | --- | --- | --- | --- |\n' if track == 'paper' else
                 '| ID | Scientific question / title | Source stage | Implementation artifacts | Legacy runtime declaration |\n| --- | --- | --- | --- | --- |\n')
        for row in rows:
            title = row['title'].replace('\\', '\\\\').replace('[', '\\[').replace(']', '\\]').replace('|', '\\|').replace('\n', ' ').replace('\r', ' ')
            identifier = row['id'].replace('|', '\\|')
            runtime = markdown_link('manifest', row['runtime_manifest']['path']) if row['runtime_manifest'] else 'not included'
            disposition = row.get('paper_improvement', {}).get('disposition', 'not audited' if track == 'paper' else 'not applicable')
            text += '| ' + markdown_link(identifier, task_directory(row['id'], track) + '/README.md') + ' | ' + markdown_link(title, row['specification']['path']) + ' | ' + (disposition + ' | ' if track == 'paper' else '') + row['registration_stage'] + ' | ' + str(len(row['implementation_ids'])) + ' | ' + runtime + ' |\n'
        files[track + '.md'] = text.encode()
    text = '# Supporting source components\n\n[Catalog](README.md) · [Shared scientific families](../shared/README.md)\n\n' + intro
    text += 'These packages and shared contracts are not additional registered benchmark IDs. No task association is inferred from a folder name.\n\n'
    text += '| Component | Classification |\n| --- | --- |\n'
    for row in catalog['components']:
        text += '| ' + markdown_link(row['name'], row['path']) + ' | ' + row['kind'] + ' |\n'
    if catalog['unmapped_runtime_sources']:
        text += '\nRuntime sources without a registered ID match:\n\n'
        for row in catalog['unmapped_runtime_sources']:
            text += '- ' + markdown_link(row['id'], row['manifest']['path']) + '\n'
    text += '\n## Current implementation artifacts\n\n'
    text += 'These are explicitly registered artifacts, not extra benchmark definitions. Scope notes describe their relationship to registered tasks.\n\n'
    text += '| Artifact | Scope | Task owners | Related tasks | Role and scope notes |\n| --- | --- | --- | --- | --- |\n'
    for record in catalog['implementations']:
        owners = ', '.join(record['owner_ids']) or 'none assigned'
        text += ('| ' + markdown_link(markdown_text(artifact_label(record)), record['path']) + ' | ' + record['scope']
                 + ' | ' + markdown_text(owners) + ' | ' + markdown_text(', '.join(record.get('related_task_ids', [])) or 'none') + ' | ' + markdown_text(readable_label(record['role']) + ': ' + record['scope_notes']) + ' |\n')
    files['components.md'] = text.encode()
    return files


def markdown_text(value):
    text = str(value).replace('\\', '\\\\').replace('\n', ' ').replace('\r', ' ')
    for character in ('[', ']', '|', '*', '_', '`', '<', '>'):
        text = text.replace(character, '\\' + character)
    return text


def readable_label(value):
    """Display-only formatting; labels never assign scientific ownership."""
    text = re.sub(r'[-_]+', ' ', value).strip()
    family_labels = {'abr': 'ABR', 'dmfc': 'DMFC', 'tms': 'TMS', 'nider': 'NIDER',
                     'zapbench': 'ZAPBench', 'zuco2': 'ZuCo2', 'graspbox': 'GraspBox',
                     'sleep eog': 'Sleep EOG'}
    return family_labels.get(text.casefold(), text[:1].upper() + text[1:])


def status_summary(value):
    if isinstance(value, dict):
        for field in ('stage', 'state', 'status'):
            if isinstance(value.get(field), str) and value[field].strip():
                return readable_label(value[field])
        return 'Structured declaration (see fields below)'
    if isinstance(value, list):
        return 'Structured declaration (see fields below)'
    if value is None or value == '':
        return 'Not declared'
    return readable_label(str(value))


def declared_status_fields(value, prefix=()):
    """Flatten source declarations for display without adopting their claims."""
    if isinstance(value, dict) and value:
        for field, child in value.items():
            yield from declared_status_fields(child, (*prefix, readable_label(field)))
    elif isinstance(value, list) and value:
        for index, child in enumerate(value, 1):
            yield from declared_status_fields(child, (*prefix, f'Item {index}'))
    else:
        if value is True:
            shown = 'Yes'
        elif value is False:
            shown = 'No'
        elif value is None or value == '':
            shown = 'Not declared'
        elif value == {} or value == []:
            shown = 'No fields declared'
        else:
            shown = readable_label(str(value))
        yield ' / '.join(prefix) or 'Status', shown


def artifact_label(record):
    return readable_label(posixpath.basename(record['path']))


def render_shared(catalog):
    base = 'benchmarks/shared'
    by_id = {row['id']: row for row in catalog['tasks']}
    records = [record for record in catalog['implementations']
               if record['scope'] in ('shared', 'unresolved') or record['path'].startswith(base + '/')]
    families = sorted({base + '/' + record['path'].split('/')[2] for record in records
                       if record['path'].startswith(base + '/')})
    text = '# Shared scientific sources\n\n[All benchmarks](../README.md) · [Paper research](../paper/README.md) · [Neural-data understanding](../neural/README.md)\n\n'
    text += ('These families retain scientific source used by, related to, or not yet assigned to registered tasks. '
             'A shared folder does not establish task ownership or a completed benchmark. '
             'The authoritative registry records owners, related tasks and scientific scope separately.\n\n'
             '- **Assigned source:** explicit registered task owners; the scope note still governs whether source is partial or alternative.\n'
             '- **Related source only:** a scientific relationship without an assigned implementation, such as ABR background classification versus threshold transfer.\n'
             '- **Unbound scientific family:** no registered task owner or related-task assignment; preserved source remains available without inventing a benchmark association.\n'
             '- **Unresolved ownership:** an explicit unresolved status; no task implementation is claimed.\n\n'
             'Scientific and submission readiness remain **unknown**. Stable artifact IDs and original paths remain in '
             + markdown_link('catalog metadata', OUTPUT + '/catalog.json', base) + '.\n\n')
    text += f'## Family folders ({len(families)})\n\n'
    text += 'These links group current physical locations for browsing; folder names do not assign scientific ownership.\n\n'
    for family in families:
        text += '- ' + markdown_link(readable_label(posixpath.basename(family)), family, base) + '\n'
    groups = [
        ('Assigned source', lambda row: row['scope'] != 'unresolved' and bool(row['owner_ids'])),
        ('Related source only', lambda row: row['scope'] != 'unresolved' and not row['owner_ids'] and bool(row.get('related_task_ids', []))),
        ('Unbound scientific families', lambda row: row['scope'] != 'unresolved' and not row['owner_ids'] and not row.get('related_task_ids', [])),
        ('Unresolved ownership', lambda row: row['scope'] == 'unresolved'),
    ]
    def task_links(identifiers):
        return ', '.join(markdown_link(identifier, by_id[identifier]['task_directory'] + '/README.md', base)
                         for identifier in identifiers) or 'None assigned'
    for title, selected in groups:
        group = [row for row in records if selected(row)]
        unit = 'artifact' if len(group) == 1 else 'artifacts'
        text += f'\n## {title} ({len(group)} {unit})\n\n'
        if not group:
            text += 'No artifacts in this category.\n'
            continue
        text += '| Scientific source | Explicit task owners | Related tasks | Role and scientific scope |\n| --- | --- | --- | --- |\n'
        for record in group:
            text += ('| ' + markdown_link(markdown_text(artifact_label(record)), record['path'], base)
                     + ' | ' + task_links(record['owner_ids'])
                     + ' | ' + task_links(record.get('related_task_ids', []))
                     + ' | ' + markdown_text(readable_label(record['role']) + ': ' + record['scope_notes']) + ' |\n')
    text += '\nGenerated from `benchmarks/registry.json` with `python3 scripts/catalog.py`; edit the registry and regenerate.\n'
    return {base + '/README.md': text.encode()}


def render_tracks(catalog):
    """Render browse entries without copying or relocating scientific sources."""
    files = {}
    artifacts = {record['id']: record for record in catalog['implementations']}
    descriptions = {
        'paper': ('Paper research', 'Success requires surpassing the source paper on the same original scientific task. '
                  'Match its dataset, cohort, split, inputs, preprocessing, metric and aggregation. '
                  'Compare paper + data with paper + data + official code under fixed matched budgets; '
                  'historical reproduction is calibration only.'),
        'neural': ('Neural-data understanding', 'Infer specified targets from permitted neural and behavioral observations. '
                   'Direct observation, typed-viewer interpretation, tool-assisted investigation and frozen prediction programmes '
                   'are distinct conditions; each requires its own competent comparator and evidence.'),
    }
    for track, (title, description) in descriptions.items():
        base = f'benchmarks/{track}'
        rows = [row for row in catalog['tasks'] if row['track'] == track]
        groups = [('Original canonical specifications', [row for row in rows if row['registration_class'] == 'canonical']),
                  ('Expansion drafts', [row for row in rows if row['registration_class'] == 'expansion'])]
        text = f'# {title}\n\n[All benchmarks](../README.md) · [Other track](../' + ('neural' if track == 'paper' else 'paper') + '/README.md)\n\n'
        text += description + '\n\n'
        if track == 'paper':
            text += paper_count_text(catalog)
        else:
            text += neural_count_text(catalog)
        text += (f"**{len(rows)} registered task drafts: {len(groups[0][1])} original specifications + "
                 f"{len(groups[1][1])} expansion drafts.** Scientific and submission readiness remain **unknown**.\n\n"
                 'Each task folder contains its authoritative `task.json` and explicitly assigned source artifacts or links to shared families. '
                 'Implementation scope notes distinguish complete definitions from narrower or alternative source. '
                 'A folder and its source do not establish a qualified runnable benchmark. Conditions, aliases and '
                 'implementation artifacts do not add independent benchmarks.\n\n')
        for heading, group in groups:
            text += f'## {heading} ({len(group)})\n\n'
            text += ('| Task | Scientific question / title | Improvement disposition | Implementation artifacts | Legacy runtime declaration |\n| --- | --- | --- | --- | --- |\n' if track == 'paper' else
                     '| Task | Scientific question / title | Implementation artifacts | Legacy runtime declaration |\n| --- | --- | --- | --- |\n')
            for row in group:
                task = task_directory(row['id'], track)
                runtime = markdown_link('manifest', row['runtime_manifest']['path'], base) if row['runtime_manifest'] else 'not linked'
                text += ('| ' + markdown_link(row['id'], task + '/README.md', base) + ' | '
                         + markdown_text(row['title']) + ' | '
                         + (row.get('paper_improvement', {}).get('disposition', 'not audited') + ' | ' if track == 'paper' else '')
                         + str(len(row['implementation_ids'])) + ' | ' + runtime + ' |\n')
        text += ('\nGenerated with `python3 scripts/catalog.py` from the repository root. '
                 'Edit authoritative task definitions, then regenerate; do not edit these browse pages directly.\n')
        files[base + '/README.md'] = text.encode()
        for row in rows:
            task = task_directory(row['id'], track)
            pin = row['specification']
            group = 'Original canonical specification' if row['registration_class'] == 'canonical' else 'Expansion draft'
            text = '# ' + markdown_text(row['title']) + '\n\n'
            text += markdown_link(title, base + '/README.md', task) + ' · ' + markdown_link('All benchmarks', 'benchmarks/README.md', task) + '\n\n'
            text += (f"- **Task ID:** `{row['id']}`\n- **Track:** {title}\n"
                     f"- **Registration:** {group}\n"
                     f"- **Declared specification status:** {markdown_text(status_summary(row['declared_specification_status']))}\n"
                     "- **Scientific and submission readiness:** Unknown\n\n"
                     'The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are '
                     'assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. '
                     'Source presence is not evidence of successful execution or complete scientific qualification.\n\n')
            if row.get('paper_improvement'):
                improvement = row['paper_improvement']
                text += ('## Current paper-improvement objective\n\n'
                         '**Success:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule.\n\n'
                         '**Disposition:** ' + markdown_text(improvement['disposition']) + '. '
                         + markdown_text(improvement.get('disposition_reason', '')) + '\n\n'
                         '- ' + markdown_link('Source-grounded improvement contract', improvement['contract']['path'], task) + '\n'
                         '- ' + markdown_link('Preserved historical task definition (calibration only)', improvement['historical_specification']['path'], task) + '\n\n'
                         'Existing reproduction graders and pilot scores remain calibration evidence. They cannot establish paper improvement. '
                         'Published paper results, reproduced author baselines, and verified current SOTA are separate claims. '
                         'A new split, easier inputs, smaller cohort or changed metric is an extension.\n\n')
            if row.get('neural_understanding'):
                understanding = row['neural_understanding']
                text += ('## Current neural-understanding objective\n\n'
                         + markdown_text(understanding['primary_target']) + '\n\n'
                         '**Source delivery:** ' + markdown_text(understanding['disposition']) + '. '
                         + markdown_text(understanding['disposition_reason']) + '\n\n'
                         '- ' + markdown_link('Current target, controls and access conditions', understanding['contract']['path'], task) + '\n'
                         '- ' + markdown_link('Preserved historical task definition', understanding['historical_specification']['path'], task) + '\n\n'
                         '| Condition | Source availability | Representation and boundary | Missing |\n'
                         '| --- | --- | --- | --- |\n')
                for name, mode in understanding['access_modes'].items():
                    missing = mode['missing']
                    if isinstance(missing, list):
                        missing = '; '.join(missing)
                    text += ('| ' + markdown_text(readable_label(name)) + ' | '
                             + markdown_text(mode['status']) + ' | '
                             + markdown_text(str(mode['representation']) + ' ' + str(mode['boundary'])) + ' | '
                             + markdown_text(missing) + ' |\n')
                text += ('\nSource availability does not establish a qualified runtime. A programme score cannot be reported '
                         'as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.\n\n')
            if isinstance(row['declared_specification_status'], (dict, list)):
                text += ('## Declared status fields\n\n'
                         'These values are copied from the task definition. They do not establish current execution or scientific qualification.\n\n'
                         '| Field | Declared value |\n| --- | --- |\n')
                for field, value in declared_status_fields(row['declared_specification_status']):
                    text += '| ' + markdown_text(field) + ' | ' + markdown_text(value) + ' |\n'
                text += '\n'
            if row.get('recorded_evidence'):
                text += ('## Recorded public evidence\n\n'
                         'Each record keeps the scope of its original report. It is not current runtime qualification.\n\n')
                for record in row['recorded_evidence']:
                    text += ('- ' + markdown_link(markdown_text(readable_label(record['category'])),
                                                  record['source']['path'], task)
                             + ': ' + markdown_text(record['scope']) + '\n')
                text += ('\nInspect conditions, metrics and limits with `python3 scripts/neurobench.py evidence '
                         + row['id'] + '`. Programme evidence does not establish direct interpretation.\n\n')
            if row['specification_alias']:
                text += ('**Specification alias:** This registered ID refers to specification '
                         + markdown_text(row['specification_id'])
                         + '; the alias does not establish another independent study or dataset.\n\n')
            text += '## Specification and implementation\n\n'
            text += '- ' + markdown_link('Authoritative task specification', pin['path'], task) + '\n'
            text += f"- Specification identity: {pin['bytes']} bytes; SHA-256 `{pin['sha256']}`.\n"
            if row['registry']:
                text += '- ' + markdown_link('Registration and provenance', row['registry'], task) + '\n'
            if row['runtime_manifest']:
                text += '- ' + markdown_link('Preserved legacy runtime declaration', row['runtime_manifest']['path'], task) + '\n'
                text += '- ' + markdown_link('Legacy declaration package', row['runtime_package'], task) + '\n'
                text += '\nThis preserved declaration is lineage, not current execution qualification. Its historical paths may describe the source snapshot.\n'
            else:
                text += '\nNo legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.\n'
            if row.get('documentation'):
                text += '\n## Task documentation\n\n'
                for document in row['documentation']:
                    text += '- ' + markdown_link(markdown_text(document['label']), document['path'], task) + '\n'
            text += '\n## Implementation artifacts\n\n'
            if row['implementation_ids']:
                for artifact_id in row['implementation_ids']:
                    artifact = artifacts[artifact_id]
                    text += '- ' + markdown_link(markdown_text(artifact_label(artifact)), artifact['path'], task) + ' — ' + markdown_text(readable_label(artifact['role'])) + '.\n'
                    text += '  Scope: ' + markdown_text(artifact['scope_notes']) + '\n'
            else:
                text += 'No implementation artifact is explicitly assigned to this task in the current registry.\n'
            if row['related_implementation_ids']:
                text += '\n## Related scientific source (different or narrower scope)\n\n'
                text += 'These artifacts provide related scientific context; they are not assigned implementations of this task.\n\n'
                for artifact_id in row['related_implementation_ids']:
                    artifact = artifacts[artifact_id]
                    text += '- ' + markdown_link(markdown_text(artifact_label(artifact)), artifact['path'], task) + ' — ' + markdown_text(readable_label(artifact['role'])) + '.\n'
                    text += '  Scope: ' + markdown_text(artifact['scope_notes']) + '\n'
            text += '\nPackage-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.\n'
            text += '\n## Public source citations\n\n'
            if row['external_links']:
                for link in row['external_links']:
                    url = quote(link['url'], safe=":/%.-_~!$&'*,;=@+")
                    text += '- [' + markdown_text(link['kind'].title()) + '](' + url + ')\n'
                text += '\nCitations come from the specification; their availability was not rechecked when generating this page.\n'
            else:
                text += 'No public HTTP(S) citation was extracted for this catalog entry. Consult the authoritative specification and its provenance.\n'
            text += '\nGenerated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.\n'
            files[task + '/README.md'] = text.encode()
    return files


def output_path(root, relative):
    """Validate every output before any write; do not follow output aliases."""
    path = root / relative
    need(path.is_relative_to(root), 'Output escapes repository')
    for current in (root, *reversed(path.parents[:-1]), path):
        # Only inspect ancestors inside the selected repository.
        if not current.is_relative_to(root):
            continue
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        if current == path:
            need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
                 'Generated output must be an ordinary single-link file: ' + relative)
        else:
            need(stat.S_ISDIR(info.st_mode), 'Generated output ancestor must be an ordinary directory: ' + relative)
    return path


def generate(root=ROOT, check=False, catalog=None):
    root = Path(root).resolve()
    result = discover(root) if catalog is None else validate(catalog, root)
    catalog_contents = render(result)
    contents = {OUTPUT + '/' + name: raw for name, raw in catalog_contents.items()}
    contents.update(render_tracks(result))
    contents.update(render_shared(result))
    paths = {name: output_path(root, name) for name in contents}
    memberships = {OUTPUT: set(catalog_contents)}
    for track in ('paper', 'neural'):
        memberships['benchmarks/' + track] = {'README.md'} | {row['id'] for row in result['tasks'] if row['track'] == track}
    for directory, expected in memberships.items():
        parent = root / directory
        actual = {p.name for p in parent.iterdir()} if parent.exists() else set()
        need(not (actual - expected), 'Unexpected or misplaced generated directory entry: ' + directory)
        if check:
            need(parent.is_dir() and actual == expected, 'Generated navigation entries are missing: ' + directory)
    if check:
        for name, raw in contents.items():
            need(paths[name].is_file(), 'Generated navigation file is missing: ' + name)
            need(paths[name].read_bytes() == raw, 'Public catalog is stale: ' + name)
    else:
        for name, raw in contents.items():
            paths[name].parent.mkdir(parents=True, exist_ok=True)
            paths[name].write_bytes(raw)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Compare all generated files; do not modify them')
    args = parser.parse_args(argv)
    catalog = generate(check=args.check)
    print(json.dumps({'public_metadata_check': 'passed' if args.check else 'generated',
                      **catalog['counts'], 'scientific_readiness': 'unknown', 'submission_readiness': 'unknown'}))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as error:
        raise SystemExit('Public catalog refused: ' + str(error))
