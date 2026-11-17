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
# Covers both tracks' versioned contracts plus exact preserved predecessors.
# Per-member bounds and the cumulative refusal remain independent controls.
READ_LIMIT = 80 * 1024 * 1024
PAPER_PRE_IMPROVEMENT_COUNT = 116
PRIMARY_SUCCESSOR_PUBLIC_FIELDS = (
    'improvement_disposition', 'retained_improvement_contract', 'retained_improvement_role',
    'primary_policy_revision', 'primary_policy_provenance', 'candidate_interface', 'author_reproduction_routes',
)
RETAINED_POLICY_ROLE = 'retained_pre_outcomes_policy'


def improvement_module():
    spec = importlib.util.spec_from_file_location('neurobench_paper_improvement',
                                                 Path(__file__).with_name('paper_improvement.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def companion_module(name):
    """Load a fixed framework sibling without importing task implementation code."""
    need(name in {'neural_understanding', 'evidence', 'operator_routes', 'paper_outcomes_binding'},
         'Unknown framework companion')
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


def paper_outcome_counts(tasks):
    """Count registered identities once; outcome conditions are nested metadata."""
    papers = [row for row in tasks if row['track'] == 'paper']
    covered = [row for row in papers if row.get('paper_outcomes')]
    reproduction = Counter(primary_paper_disposition(row, 'reproduction') for row in covered)
    improvement = Counter(primary_paper_disposition(row, 'improvement') for row in covered)
    result = {'registered': len(papers), 'covered': len(covered), 'not_bound': len(papers) - len(covered),
            'primary_unavailable': sum(row['paper_outcomes'].get('availability') == 'unavailable' for row in covered),
            'reproduction_eligibility': dict(sorted(reproduction.items())),
            'improvement_disposition': dict(sorted(improvement.items())),
            'scientific_outcomes': {'reproduction': 'unknown', 'improvement': 'unknown'},
            'count_basis': 'Distinct registered paper task IDs. Outcome eligibility and access conditions '
                           'do not add tasks or establish scientific performance.'}
    gaps = sum(source_declaration_gap(row['paper_outcomes']) for row in covered)
    if gaps:
        result['source_declaration_unavailable'] = gaps
    return result


def continuous_paper_selection(outcomes):
    """Select one authenticated SMC continuous version; mixed claims refuse."""
    selections = [outcomes[field] for field in ('continuous_outcomes_v1', 'continuous_outcomes_v2')
                  if field in outcomes]
    need(len(selections) <= 1 and all(type(value) is dict for value in selections),
         'Expected exactly one current continuous policy version when declared')
    return selections[0] if selections else None


def primary_paper_disposition(row, outcome):
    """A retained secondary policy cannot make an unavailable primary eligible."""
    binding = row.get('paper_outcomes', {})
    if binding.get('availability') == 'unavailable':
        return 'unavailable'
    if continuous_paper_selection(binding) is not None:
        return 'continuous_measurement'
    if source_declaration_gap(binding):
        return ('source_declaration_unavailable' if outcome == 'reproduction'
                else binding['improvement_disposition'])
    if outcome == 'reproduction':
        disposition = binding.get('reproduction_eligibility', 'not bound')
        need(type(disposition) is str, 'Reproduction eligibility requires an explicit assessment mode')
        return disposition
    if binding.get('primary_policy_revision') is not None:
        need(type(binding.get('improvement_disposition')) is str, 'Selected primary policy requires its current disposition')
        return binding['improvement_disposition']
    return row.get('paper_improvement', {}).get('disposition', 'not audited')


def neutral_unavailable_reason(outcomes):
    return (outcomes.get('availability') == 'unavailable'
            and outcomes.get('reason_code') == 'full_primary_pairing_unavailable')


def source_declaration_gap(outcomes):
    return outcomes.get('availability') == 'source_declaration_unavailable'


def registered_improvement_summary(bound, registered):
    """Summarize the original policy with its unchanged registration provenance."""
    revision = registered['specification_revision']
    result = {**improvement_module().summary(bound['retained_improvement_contract']),
              'contract': bound['retained_improvement_contract_pin']}
    if revision['version'] == 'paper-improvement/initial-v1':
        result.update(historical_specification=None, initial_registration=revision['initial_registration'])
    else:
        need(revision['version'] == 'paper-improvement/v1', 'Unsupported retained successor policy lineage')
        result['historical_specification'] = revision['previous_specification']
    return result


def retained_successor_policy(bound, registered):
    return {**registered_improvement_summary(bound, registered), 'role': RETAINED_POLICY_ROLE}


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
    outcome_binding = companion_module('paper_outcomes_binding')
    read_outcome_pin = lambda pin, label: checked_pin(reader, pin, label)
    previous_outcome_rows = outcome_binding.coverage(registry, read_outcome_pin)
    outcome_snapshot = registry.get('paper_outcomes', {}).get('pre_outcomes_registry')
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
        need(type(previous_registry.get('schema_version')) is int and previous_registry['schema_version'] == 1
             and previous_registry.get('kind') == 'neuroscience_benchmark_registry',
             'Unsupported pre-improvement registry')
        previous_rows = {row['id']: row for row in previous_registry['tasks']}
        if any(row.get('specification_revision', {}).get('version') == 'paper-improvement/initial-v1' for row in rows):
            prior_rows = list(previous_rows.values())
            need(all(row.get('track') in ('paper', 'neural')
                     and row.get('registration_class') in ('canonical', 'expansion') for row in prior_rows),
                 'Invalid pre-improvement track or registration class')
            expected_counts = {**counts(prior_rows),
                               'canonical_specifications': sum(row['registration_class'] == 'canonical' for row in prior_rows),
                               'expansion_drafts': sum(row['registration_class'] == 'expansion' for row in prior_rows)}
            prior_counts = previous_registry.get('source_counts')
            need(type(prior_counts) is dict
                 and all(type(prior_counts.get(key)) is int and prior_counts[key] == value
                         for key, value in expected_counts.items()),
                 'Pre-improvement registration roster counts disagree')
            need(sum(row['track'] == 'paper' for row in previous_rows.values()) == PAPER_PRE_IMPROVEMENT_COUNT
                 and previous_registry.get('source_counts', {}).get('paper') == PAPER_PRE_IMPROVEMENT_COUNT,
                 'Initial paper registrations must preserve all original paper registrations')
        need(len(previous_rows) == len(previous_registry['tasks'])
             and set(previous_rows) <= {row['id'] for row in rows}
             and {row['id'] for row in previous_rows.values() if row['track'] == 'paper'}
             == {row['id'] for row in rows if row['track'] == 'paper'
                 and row.get('specification_revision', {}).get('version') != 'paper-improvement/initial-v1'},
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
    need(outcome_snapshot is None or outcome_snapshot in historical,
         'Pre-outcomes registry snapshot must be exactly enrolled')
    historical_paths = set()
    for pin in historical:
        need(pin['path'] not in historical_paths, 'Duplicate historical registry')
        historical_paths.add(pin['path'])
        # Authenticate the preserved JSON body, but do not traverse its old locators.
        # The outcome helper has already authenticated this exact snapshot.
        # Its historical enrollment still participates in the unique-path check.
        if pin != outcome_snapshot:
            checked_pin(reader, pin, 'Historical registry')
    tasks = []
    classes = {'canonical': [], 'expansion': []}
    for row in rows:
        identifier, track = row['id'], row['track']
        directory = task_directory(identifier, track)
        need(row.get('task_directory') == directory, 'Task directory does not match its track and ID')
        need(row['specification']['path'] == directory + '/task.json', 'Authoritative task definition must be task.json in its task folder')
        doc = checked_pin(reader, row['specification'], 'Task specification')
        current_row, current_document = row, doc
        bound_outcomes = outcome_binding.context(row, doc, previous_outcome_rows, read_outcome_pin)
        if bound_outcomes is not None:
            # These unchanged lineage checks describe the preserved pre-outcome
            # definition. The current dual projection is authenticated separately.
            row, doc = bound_outcomes['previous_row'], bound_outcomes['previous_document']
        original = row['original_specification']
        need(isinstance(original, dict) and isinstance(original.get('path'), str), 'Missing original task identity')
        revision = row.get('specification_revision')
        need(revision is None or type(revision) is dict, 'Task specification revision must be an object')
        if track == 'paper' and registry.get('paper_improvement', {}).get('coverage_required'):
            need(revision is not None, 'Active paper improvement registry requires every paper contract')
        if track == 'neural' and registry.get('neural_understanding', {}).get('coverage_required'):
            need(revision is not None, 'Active neural understanding registry requires every neural contract')
        improvement = None
        understanding = None
        if revision is None:
            need(all(original.get(key) == row['specification'][key] for key in ('bytes', 'sha256')),
                 'Task definition differs from its preserved original identity')
        elif revision.get('version') == 'paper-improvement/initial-v1':
            need(track == 'paper' and previous_rows is not None and identifier not in previous_rows
                 and set(revision) == {'version', 'improvement_contract', 'initial_registration'},
                 'Initial paper registration cannot replace a historical task')
            need(row['registration_class'] == 'expansion' and row['specification_id'] == identifier
                 and row['specification_alias'] is False and original == row['specification']
                 and set(row['specification']) == {'path', 'bytes', 'sha256'},
                 'Initial paper specification must retain its exact registered identity')
            registration_pin = revision['initial_registration']
            registration_path = 'docs/provenance/registrations/paper-initial/' + identifier + '.json'
            need(type(registration_pin) is dict and set(registration_pin) == {'path', 'bytes', 'sha256'}
                 and registration_pin['path'] == registration_path and row['registry'] == registration_path
                 and registration_pin in historical, 'Initial paper registration snapshot is not enrolled')
            registration = checked_pin(reader, registration_pin, 'Initial paper registration')
            pin = revision['improvement_contract']
            need(type(pin) is dict and set(pin) == {'path', 'bytes', 'sha256'}
                 and pin['path'] == directory + '/improvement.v1.json', 'Improvement contract is outside its task')
            need(set(registration) == {'schema_version', 'task_id', 'source_commit', 'specification', 'improvement_contract'}
                 and registration['schema_version'] == 'paper-improvement/initial-v1'
                 and registration['task_id'] == identifier
                 and isinstance(registration['source_commit'], str)
                 and re.fullmatch(r'[0-9a-f]{40}', registration['source_commit'])
                 and registration['specification'] == row['specification']
                 and registration['improvement_contract'] == pin,
                 'Initial paper registration differs from its preserved snapshot')
            contract = (bound_outcomes['retained_improvement_contract'] if bound_outcomes is not None
                        else checked_pin(reader, pin, 'Paper improvement contract'))
            engine = improvement_module()
            errors = engine.validate_contract(contract, task_id=identifier)
            need(not errors, 'Invalid paper improvement contract: ' + identifier + ': ' + '; '.join(errors))
            need(contract.get('legacy', {}).get('role') == 'no_predecessor'
                 and contract['legacy'].get('original_task') is None,
                 'Initial paper contract must not fabricate historical calibration')
            need(doc.get('id') == identifier and doc.get('track') == 'paper'
                 and doc.get('objective') == 'surpass_source_paper_same_task'
                 and doc.get('evaluation') == {'objective': 'surpass_source_paper_same_task',
                     'contract': pin, 'disposition': contract['disposition'], 'reproduction_role': 'not_applicable'}
                 and doc.get('status') == contract['disposition']
                 and doc.get('admission', {}).get('runnable') is False
                 and doc['admission'].get('research_qualified') is False
                 and doc['admission'].get('submission_ready', False) is False,
                 'Initial paper definition is not bound to its improvement contract')
            improvement = {**engine.summary(contract), 'contract': pin,
                           'historical_specification': None, 'initial_registration': registration_pin}
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
            contract = (bound_outcomes['retained_improvement_contract'] if bound_outcomes is not None
                        else checked_pin(reader, pin, 'Paper improvement contract'))
            engine = improvement_module()
            errors = engine.validate_contract(contract, task_id=identifier)
            need(not errors, 'Invalid paper improvement contract: ' + identifier + ': ' + '; '.join(errors))
            need(contract.get('legacy', {}).get('role') == 'calibration_only'
                 and contract['legacy'].get('original_task') == 'historical/task.pre-improvement.v1.json',
                 'Historical paper contract must preserve its calibration predecessor')
            need(doc.get('objective') == 'surpass_source_paper_same_task'
                 and doc.get('evaluation', {}).get('contract') == pin
                 and doc.get('evaluation', {}).get('reproduction_role') == 'calibration_only'
                 and doc.get('status') == contract['disposition'],
                 'Current paper definition is not bound to its improvement contract')
            improvement = {**engine.summary(contract), 'contract': pin,
                           'historical_specification': previous}
        row, doc = current_row, current_document
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
            task['runtime_lineage_note'] = ('Historical paper implementations are calibration components; they cannot establish same-task paper improvement.'
                                            if improvement['historical_specification'] else
                                            'Initial source-paper task with no predecessor benchmark; source preparation and author calibration do not establish candidate superiority.')
        if bound_outcomes is not None:
            task['paper_outcomes'] = outcome_binding.public_summary(row, bound_outcomes)
            if bound_outcomes.get('primary_policy_revision') is not None:
                task['paper_improvement']['role'] = RETAINED_POLICY_ROLE
                task['runtime_lineage_note'] = (
                    'The current source interface measures both outcomes continuously; retained policies and author-source routes '
                    'preserve their original scopes. Participant results are not attempted.'
                    if continuous_paper_selection(task['paper_outcomes']) is not None else
                    'The selected offline candidate and retained author-source routes are separate source interfaces; '
                    'their metadata does not establish execution or scientific qualification.'
                    if bound_outcomes['candidate_interface'] is not None else
                    'The selected primary policy and retained predecessor policy are separate metadata records; '
                    'neither establishes execution or scientific qualification.')
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
              'paper_outcome_counts': paper_outcome_counts(tasks),
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
    validate(result, root, _reader=reader)
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
            if row['paper_improvement']['historical_specification']:
                yield row['paper_improvement']['historical_specification']['path']
            else:
                yield row['paper_improvement']['initial_registration']['path']
        if row.get('paper_outcomes'):
            for field in ('previous_specification', 'reproduction_contract', 'outcomes', 'source_declaration_gap'):
                if row['paper_outcomes'].get(field) is not None:
                    yield row['paper_outcomes'][field]['path']
            decision = row['paper_outcomes'].get('root_scope_decision')
            if decision is not None:
                yield decision['path']
            correction = row['paper_outcomes'].get('primary_scope_correction')
            if correction is not None:
                yield correction['root_scope_decision']['path']
            outcomes = row['paper_outcomes']
            continuous = continuous_paper_selection(outcomes)
            if continuous is not None:
                for field in ('policy', 'entrypoint', 'revision'):
                    yield continuous[field]['path']
                for field in ('task', 'reproduction', 'improvement', 'outcomes', 'revision'):
                    yield continuous['retained_temporal'][field]['path']
                if 'continuous_outcomes_v2' in outcomes:
                    yield continuous['asset_allowlist']['path']
                    for field in ('task', 'policy', 'entrypoint', 'revision'):
                        yield continuous['retained_v1'][field]['path']
            if outcomes.get('primary_policy_revision') is not None:
                for field in ('improvement_contract', 'retained_improvement_contract', 'primary_policy_revision'):
                    yield outcomes[field]['path']
                for pin in outcomes['primary_policy_provenance'].values():
                    yield pin['path']
                if outcomes['candidate_interface'] is not None:
                    for field in ('delivery', 'scorer', 'policy'):
                        yield outcomes['candidate_interface'][field]['path']
                if outcomes['author_reproduction_routes'] is not None:
                    for field in ('delivery', 'scorer', 'protocol'):
                        yield outcomes['author_reproduction_routes'][field]['path']
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


def validate(catalog, root=ROOT, *, _reader=None):
    need(catalog.get('schema_version') == 1 and catalog.get('kind') == 'public_neuroscience_source_catalog',
         'Unsupported public catalog')
    tasks = catalog['tasks']
    need(len({row['id'] for row in tasks}) == len(tasks), 'Duplicate catalog task ID')
    need(all(catalog['counts'][key] == value for key, value in counts(tasks).items()), 'Catalog task totals disagree')
    need(catalog.get('paper_improvement_counts') == improvement_counts(tasks), 'Paper improvement counts disagree')
    need(catalog.get('paper_outcome_counts') == paper_outcome_counts(tasks), 'Paper outcome counts disagree')
    need(catalog.get('neural_understanding_counts') == understanding_counts(tasks), 'Neural understanding counts disagree')
    need(catalog['scientific_readiness'] == catalog['submission_readiness'] == 'unknown',
         'Catalog must not manufacture readiness')
    # Reuse discovery's cumulative accounting, but never its source claims.
    # Public supplied views get a fresh bounded reader. Source authentication is
    # local to this invocation and cannot be replaced by supplied view metadata.
    reader = _reader if _reader is not None else Reader(Path(root))
    need(reader.root == Path(root).resolve(), 'Catalog reader must use the selected repository root')
    source_state = None
    primary_source = None
    authenticated_previous_rows = None

    def read_bound(pin, label):
        need(type(pin) is dict and set(pin) == {'path', 'bytes', 'sha256'}
             and type(pin['path']) is str and type(pin['bytes']) is int and type(pin['sha256']) is str,
             'Invalid ' + label + ' pin')
        return checked_pin(reader, pin, label)

    def current_source():
        nonlocal source_state
        if source_state is None:
            module = companion_module('paper_outcomes_binding')
            module.require_pin(catalog.get('registry'), REGISTRY, 'current registry')
            source_registry = read_bound(catalog['registry'], 'Current outcome registry')
            need(source_registry.get('schema_version') == 1
                 and source_registry.get('kind') == 'neuroscience_benchmark_registry',
                 'Outcome scope requires the current registry')
            source_rows = source_registry.get('tasks')
            need(type(source_rows) is list and all(type(item) is dict and type(item.get('id')) is str for item in source_rows),
                 'Outcome scope requires current registered identities')
            source_by_id = {item['id']: item for item in source_rows}
            need(len(source_by_id) == len(source_rows), 'Outcome scope registry has duplicate identities')
            source_state = module, source_registry, source_by_id
        return source_state

    module, source_registry, source_by_id = current_source()
    source_entries = {}
    source_scope = None
    source_metadata = source_registry.get('paper_outcomes')
    # The original roster is authoritative even if a supplied view or the
    # current roster has removed a fixed declaration-gap task. Source-only
    # coverage returns None without reading an unregistered snapshot.
    authenticated_previous_rows = module.coverage(source_registry, read_bound)
    gap_ids = (set(authenticated_previous_rows) & module.SOURCE_DECLARATION_GAP_IDS
               if authenticated_previous_rows is not None else set())
    need(gap_ids <= {row['id'] for row in tasks}, 'Source declaration gap tasks cannot be omitted')
    if type(source_metadata) is dict and 'scope_decisions' in source_metadata:
        module.require_pin(source_metadata['scope_decisions'], module.SCOPE_PATH, 'scope decisions')
        source_scope = module.scope_decisions(read_bound(source_metadata['scope_decisions'], 'Outcome scope decision'))
        source_entries = source_scope['entries']
    neutral_ids = {identifier for identifier, entry in source_entries.items()
                   if entry['paired_bundle_status'] == 'unavailable_complete_primary_pairing'
                   and identifier in source_by_id
                   and type(source_by_id[identifier].get('paper_outcomes')) is dict}
    need(neutral_ids <= {row['id'] for row in tasks}, 'Neutral unavailable source tasks cannot be omitted')
    fixed_successors = ({module.PRIMARY_SUCCESSOR_TASK} | module.SCOPE_POLICY_SUCCESSOR_TASKS
                        | module.REFERENCE_SUCCESSOR_TASKS)
    successor_ids = ({identifier for identifier, original in authenticated_previous_rows.items()
                      if original.get('track') == 'paper' and identifier in fixed_successors}
                     if authenticated_previous_rows is not None else set())
    need(successor_ids <= {row['id'] for row in tasks}, 'Adopted primary successor tasks cannot be omitted')
    for registered in source_by_id.values():
        declaration = registered.get('paper_outcomes')
        if type(declaration) is dict and module.PRIMARY_SUCCESSOR_FIELDS & set(declaration):
            module.has_primary_successor(registered)
        if type(declaration) is dict and 'source_declaration_gap' in declaration:
            module.has_source_declaration_gap(registered)
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
        outcomes = row.get('paper_outcomes')
        successor_fields = ((set(PRIMARY_SUCCESSOR_PUBLIC_FIELDS) | {'continuous_outcomes_v1', 'continuous_outcomes_v2'}) & set(outcomes)
                            if type(outcomes) is dict else set())
        if row['id'] in gap_ids:
            successor_fields.discard('improvement_disposition')
        gap_claim = type(outcomes) is dict and (source_declaration_gap(outcomes)
            or outcomes.get('reason_code') == 'source_declaration_unavailable'
            or any(field in outcomes for field in ('source_declaration_gap', 'scientific_ineligibility_inferred',
                                                   'improvement_unavailable_by_reproduction_dependency', 'paired_outcome_admission')))
        need(row['id'] in gap_ids or not gap_claim, 'Declaration gap claims require the authenticated original source task')
        if row['id'] in gap_ids:
            need(type(outcomes) is dict and source_declaration_gap(outcomes),
                 'Source declaration gap cannot be omitted or reclassified')
        retained_policy = row.get('paper_improvement')
        retained_role = type(retained_policy) is dict and retained_policy.get('role') == RETAINED_POLICY_ROLE
        need(row['id'] in successor_ids or not (successor_fields or retained_role),
             'Primary successor claims require an adopted fixed reviewed source task')
        if row['id'] in successor_ids:
            need(type(outcomes) is dict and outcomes.get('primary_policy_revision') is not None,
                 'Adopted primary successor selection cannot be omitted or replaced by a retained policy')
        if row['id'] in neutral_ids:
            need(type(outcomes) is dict and neutral_unavailable_reason(outcomes),
                 'Neutral unavailable source classification cannot be omitted or relabeled')
        if outcomes is not None:
            need(row['track'] == 'paper' and type(outcomes) is dict
                 and outcomes.get('availability', 'available') in ('available', 'unavailable', 'source_declaration_unavailable')
                 and outcomes.get('scientific_outcomes') == {'reproduction': 'unknown', 'improvement': 'unknown'},
                 'Paper outcome metadata cannot manufacture scientific results')
            cells = outcomes.get('cells')
            conditions = (('paper_data', 'paper_data_author_code_and_weights')
                          if 'continuous_outcomes_v2' in outcomes else ('paper_data', 'paper_data_author_code'))
            need(type(cells) is list and len(cells) == 4
                 and {(cell.get('outcome'), cell.get('condition')) for cell in cells if type(cell) is dict}
                 == {(outcome, condition) for outcome in ('reproduction', 'improvement')
                     for condition in conditions}
                 and all(type(cell) is dict and cell.get('scientific_outcome') == 'unknown'
                         and cell.get('receipt') is None for cell in cells),
                 'Paper catalog requires four unscored outcome conditions')
            if row['id'] in gap_ids:
                registered = source_by_id.get(row['id'])
                need(type(registered) is dict and registered.get('track') == 'paper'
                     and module.encode(registered.get('specification')) == module.encode(row.get('specification'))
                     and registered.get('title') == row.get('title'),
                     'Declaration gap differs from current task identity')
                document = read_bound(registered['specification'], 'Current declaration gap task')
                bound = module.context(registered, document, authenticated_previous_rows, read_bound)
                need(bound is not None and bound.get('availability') == 'source_declaration_unavailable'
                     and module.encode(outcomes) == module.encode(module.public_summary(registered, bound)),
                     'Declaration gap view differs from authenticated source')
                need(module.encode(row.get('paper_improvement')) == module.encode(registered_improvement_summary(bound, registered))
                     and module.encode(row.get('specification_revision')) == module.encode(registered['specification_revision'])
                     and module.encode(row.get('original_specification')) == module.encode(registered['original_specification']),
                     'Declaration gap must preserve its independent improvement policy and original lineage')
            if outcomes.get('availability') == 'unavailable':
                need(outcomes.get('reason_code') in ('primary_secondary_scope_mismatch', 'full_primary_pairing_unavailable'),
                     'Unavailable primary outcomes require a supported source reason')
                source_entry = source_entries.get(row['id'])
                need(row['id'] in source_by_id and type(source_by_id[row['id']].get('paper_outcomes')) is dict
                     and type(source_entry) is dict
                     and outcomes['reason_code'] == module.UNAVAILABLE_REASONS[source_entry['paired_bundle_status']],
                     'Unavailable outcome reason differs from authenticated source route')
                need(all(cell.get('eligibility') == cell.get('pairing_status') == 'unavailable'
                         and cell.get('endpoint_eligible') is False and cell.get('condition_available') is False
                         for cell in cells), 'Unavailable primary outcomes cannot gain eligibility or paired access')
            if neutral_unavailable_reason(outcomes):
                module, source_registry, source_by_id = current_source()
                if authenticated_previous_rows is None:
                    authenticated_previous_rows = module.coverage(source_registry, read_bound)
                    need(authenticated_previous_rows is not None, 'Neutral unavailable scope requires adopted outcome metadata')
                registered = source_by_id.get(row['id'])
                need(type(registered) is dict and registered.get('track') == 'paper'
                     and module.encode(registered.get('specification')) == module.encode(row.get('specification'))
                     and registered.get('title') == row.get('title'),
                     'Neutral unavailable scope differs from current task identity')
                document = read_bound(registered['specification'], 'Current neutral outcome task')
                bound = module.context(registered, document, authenticated_previous_rows, read_bound)
                need(bound is not None
                     and module.encode(outcomes) == module.encode(module.public_summary(registered, bound)),
                     'Neutral unavailable scope differs from authenticated source')
            if row['id'] in successor_ids:
                if authenticated_previous_rows is None:
                    authenticated_previous_rows = module.coverage(source_registry, read_bound)
                    need(authenticated_previous_rows is not None, 'Primary successor requires adopted outcome metadata')
                registered = source_by_id[row['id']]
                need(module.encode(registered['specification']) == module.encode(row.get('specification'))
                     and registered['title'] == row.get('title'), 'Primary successor differs from current task identity')
                document = read_bound(registered['specification'], 'Current primary successor task')
                bound = module.context(registered, document, authenticated_previous_rows, read_bound)
                need(bound is not None and bound.get('primary_policy_revision') is not None
                     and module.encode(outcomes) == module.encode(module.public_summary(registered, bound)),
                     'Primary successor view differs from authenticated current selection')
                need(module.encode(row.get('paper_improvement')) == module.encode(retained_successor_policy(bound, registered))
                     and module.encode(row.get('specification_revision')) == module.encode(registered['specification_revision'])
                     and module.encode(row.get('original_specification')) == module.encode(registered['original_specification']),
                     'Retained successor policy differs from authenticated original lineage')
            correction = outcomes.get('primary_scope_correction')
            if correction is not None:
                need(type(correction) is dict and outcomes.get('availability') == 'available'
                     and correction.get('disposition') == 'same_primary_unqualified'
                     and correction.get('scientific_outcome') == 'unknown'
                     and outcomes.get('reproduction_eligibility') == 'source_unresolved'
                     and primary_paper_disposition(row, 'improvement') != 'improvement_ready'
                     and type(correction.get('root_scope_decision')) is dict
                     and correction.get('root_scope_decision', {}).get('task_entry_id') == row['id'],
                     'Primary scope correction cannot qualify an outcome or change its availability')
                if primary_source is None:
                    module, source_registry, source_by_id = current_source()
                    metadata = source_registry.get('paper_outcomes')
                    need(type(metadata) is dict and metadata.get('schema_version') == module.VERSION
                         and metadata.get('coverage_required') is True,
                         'Primary scope correction requires adopted outcome metadata')
                    scope_pin = metadata.get('scope_decisions')
                    module.require_pin(scope_pin, module.SCOPE_PATH, 'scope decisions')
                    scope = source_scope
                    need(scope is not None, 'Primary scope correction requires an authenticated scope decision')
                    primary_source = module, source_by_id, scope_pin, scope.get('same_primary_corrections', {})
                module, source_by_id, scope_pin, source_corrections = primary_source
                registered = source_by_id.get(row['id'])
                need(type(registered) is dict and registered.get('track') == 'paper'
                     and registered.get('specification') == row.get('specification')
                     and type(registered.get('paper_outcomes')) is dict,
                     'Primary scope correction differs from the current registered task')
                registered_binding = registered['paper_outcomes']
                registered_revision = registered.get('specification_revision')
                expected_improvement = (bound['improvement_contract_pin'] if row['id'] in successor_ids else
                                        registered_revision.get('improvement_contract') if type(registered_revision) is dict else None)
                need(registered_binding.get('schema_version') == module.VERSION
                     and type(registered_revision) is dict
                     and outcomes.get('improvement_contract') == expected_improvement
                     and all(outcomes.get(field) == registered_binding.get(field)
                             for field in ('previous_specification', 'reproduction_contract', 'outcomes')),
                     'Primary scope correction differs from current outcome bindings')
                entry = source_corrections.get(row['id'])
                need(type(entry) is dict
                     and module.encode(correction) == module.encode(module.public_primary_scope_correction(entry, scope_pin, row['id'])),
                     'Primary scope correction differs from authenticated source')
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
    outcomes = catalog['paper_outcome_counts']
    neutral_count = sum(neutral_unavailable_reason(row.get('paper_outcomes', {})) for row in catalog['tasks'])
    successor_count = sum(row.get('paper_outcomes', {}).get('primary_policy_revision') is not None for row in catalog['tasks'])
    scope_successor_count = sum(row.get('paper_outcomes', {}).get('primary_policy_revision') is not None
                                and row['paper_outcomes']['candidate_interface'] is None
                                and row['id'] != 'PAPER-ROOT-ADD-001' for row in catalog['tasks'])
    reference_successor_count = sum(row['id'] == 'PAPER-ROOT-ADD-001'
                                    and row.get('paper_outcomes', {}).get('primary_policy_revision') is not None
                                    for row in catalog['tasks'])
    continuous_count = sum(continuous_paper_selection(row.get('paper_outcomes', {})) is not None
                           for row in catalog['tasks'])
    official_assets_count = sum('continuous_outcomes_v2' in row.get('paper_outcomes', {}) for row in catalog['tasks'])
    temporal_successor_count = successor_count - scope_successor_count - reference_successor_count - continuous_count
    dual_text = ''
    if outcomes['covered']:
        eligibility = ', '.join(f"{count} {status.replace('_', ' ')}"
                                for status, count in outcomes['reproduction_eligibility'].items())
        dual_text = (f"Outcome metadata covers **{outcomes['covered']}/{outcomes['registered']} paper tasks**. "
                     'This counts contract declarations and unavailability records; completion of both outcomes requires separate qualifying execution evidence. '
                     f"Reproduction eligibility: {eligibility}. "
                     + ('Each task retains its declared information conditions; SMC compares paper+data with paper+data+official-code-and-weights. '
                        if official_assets_count else
                        'The two goals retain paper+data and paper+data+author-code condition labels; missing declarations do not establish paired protocols. '
                        if outcomes.get('source_declaration_unavailable') else
                        'Reproduction and improvement are assessed separately under paper+data and paper+data+author-code conditions. ')
                     + 'These are nested conditions of the same registered tasks; both scientific outcomes remain **unknown**.\n\n')
        mismatch_count = outcomes['primary_unavailable'] - neutral_count
        if mismatch_count:
            dual_text += (f"Complete primary-outcome pairing is unavailable for **{mismatch_count} tasks** with an explicit scientific scope mismatch. "
                          'Their retained secondary improvement policies are not admitted as primary outcomes.\n\n')
        if neutral_count:
            dual_text += (f"Complete primary-outcome pairing is unavailable for **{neutral_count} tasks**. "
                          'Their retained improvement contracts and declared coverage remain visible; these records do not establish completed primary outcomes.\n\n')
        if outcomes.get('source_declaration_unavailable'):
            dual_text += (f"Source-grounded reproduction declarations and matched paired protocols are not adopted for **{outcomes['source_declaration_unavailable']} tasks**. "
                          'Their existing improvement contracts remain independently inspectable under their original criteria. '
                          'Missing declarations do not imply scientific ineligibility, paired access, or completed outcomes.\n\n')
        if continuous_count:
            dual_text += (f"**{continuous_count} task** declares continuous measurements for both paper outcomes, without binary eligibility or pass thresholds. "
                          'Matched episode protocols remain uninstantiated and participant results are not attempted; '
                          'an AI attempt is not required for benchmark construction.\n\n')
        if official_assets_count:
            dual_text += ('Only the assisted SMC condition receives the exact official source and pinned released-model assets. '
                          'The earlier source-only condition remains a separate historical ablation.\n\n')
        if successor_count:
            dispositions = ', '.join(f"{count} {status.replace('_', ' ')}"
                                      for status, count in outcomes['improvement_disposition'].items())
            dual_text += 'Current primary improvement dispositions: ' + dispositions + '. '
            if temporal_successor_count:
                dual_text += ('For the revised SMC task, the old contract remains an author-source policy; '
                              'the selected contract defines the candidate interface.')
            if reference_successor_count:
                dual_text += ('The LANGUAGE reference successor records author-provided-array/current-runtime reference recovery; '
                              'its current improvement policy and remaining source limits are explicit, with no AI outcome or qualification. ')
            if scope_successor_count:
                dual_text += (' ' if temporal_successor_count else '')
                dual_text += ('For the reviewed scope-policy selections, the current primary policy governs improvement; '
                              'predecessor policies remain preserved with their original source scope. Runtime routes are not declared by those policy records.')
            if continuous_count:
                dual_text += (' ' if temporal_successor_count or scope_successor_count else '')
                dual_text += ('For SMC, the shared continuous policy governs both current outcomes; '
                              'the original and temporal policies remain retained source history.')
            dual_text += '\n\n'
    audit_label = 'Retained registration-policy audit' if successor_count else 'Current paper-improvement contract audit'
    return dual_text + (f"{audit_label}: **{counts['covered']}/{counts['registered']} covered**; "
            f"**{counts['improvement_ready']} improvement-ready**, **{counts['design_ready']} source-grounded designs**, "
            f"**{counts['source_unresolved']} source-unresolved**, **{counts['ineligible']} ineligible**, "
            f"**{counts['not_audited']} not audited**. Eligibility means an ordered source task was identified; "
            'it does not establish an executable or scientifically qualified comparison. '
            'Paper reproduction is a separate first-class outcome; these counts describe the existing improvement contracts, '
            + ('including retained contracts with their declared coverage, not primary-outcome availability or reproduction qualification. '
               if neutral_count else 'including any retained secondary policies, not primary-outcome availability or reproduction qualification. ')
            + 'Numerical fidelity remains a necessary comparison check. '
            'A new split is an extension, never a same-task paper victory.\n\n')


def neural_count_text(catalog):
    summary = catalog['neural_understanding_counts']
    if not summary['covered']:
        return ''
    dispositions = ', '.join(f"{number} {name.replace('_', ' ')}"
                             for name, number in summary['dispositions'].items())
    return (f"Neural understanding revision: **{summary['covered']}/{summary['registered']} covered**; "
            + dispositions + '. These describe delivered source scope. Direct observation, typed-viewer interpretation, '
            'tool-assisted investigation and frozen prediction programmes have separate access conditions and evidence. '
            'Native interpretation and tool/model building are separate first-class outcomes. '
            'Programme performance does not establish direct interpretation.\n\n')


def evidence_text(catalog, base=OUTPUT):
    evidence = catalog['recorded_evidence']
    counts = evidence['counts']
    if not counts['tasks_with_recorded_evidence']:
        return ''
    probes = counts.get('author_model_inference_probes', 0)
    probe_text = (f"Separately, **{probes} author-model inference probes** record partial source-model execution; "
                  'complete author calibration remains unqualified. ') if probes else ''
    return (f"Recorded public evidence covers **{counts['tasks_with_recorded_evidence']} distinct task IDs**. "
            f"The pilot reports **{counts['paper_calibration_attempts']} historical paper-calibration attempts** and "
            f"**{counts['neural_programme_attempts']} neural-programme attempts**; "
            f"{counts['authentic_engineering_reports']} authentic-input engineering reports, "
            f"{counts.get('paper_source_preparation_reports', 0)} paper and "
            f"{counts.get('neural_source_preparation_reports', 0)} neural source-preparation reports, and "
            f"{counts['native_operator_controls']} native software controls are separate from model attempts. "
            + probe_text
            + markdown_link('Read the published evidence', 'docs/status/README.md', base)
            + ', or run `python3 scripts/neurobench.py evidence [TASK_ID]`. '
            'These records do not establish current runtime qualification or paper improvement.\n\n')


def render(catalog):
    c = catalog['counts']
    files = {'catalog.json': (json.dumps(catalog, indent=2, ensure_ascii=False) + '\n').encode()}
    intro = ('This is a public source inventory, not a list of qualified benchmarks. '
             'Scientific and submission readiness are **unknown here**. Runtime manifests '
             'and source components do not establish successful execution. Registered IDs '
             'may alias earlier contract identifiers; they do not count independent studies or datasets.\n\n'
             'The project targets four first-class outcomes: paper reproduction, paper improvement, native neural interpretation, '
             'and neural tool/model building. Outcome conditions share scientific task IDs while retaining separate evidence and qualification. '
             + markdown_link('Read the four-outcome design', 'docs/design/four-outcomes.md') + '.\n\n')
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
        text += ('| ID | Scientific question / title | Reproduction eligibility | Current improvement disposition | Source stage | Implementation artifacts | Legacy runtime declaration |\n| --- | --- | --- | --- | --- | --- | --- |\n' if track == 'paper' else
                 '| ID | Scientific question / title | Source stage | Implementation artifacts | Legacy runtime declaration |\n| --- | --- | --- | --- | --- |\n')
        for row in rows:
            title = row['title'].replace('\\', '\\\\').replace('[', '\\[').replace(']', '\\]').replace('|', '\\|').replace('\n', ' ').replace('\r', ' ')
            identifier = row['id'].replace('|', '\\|')
            runtime = markdown_link('manifest', row['runtime_manifest']['path']) if row['runtime_manifest'] else 'not included'
            disposition = primary_paper_disposition(row, 'improvement')
            reproduction = primary_paper_disposition(row, 'reproduction')
            text += '| ' + markdown_link(identifier, task_directory(row['id'], track) + '/README.md') + ' | ' + markdown_link(title, row['specification']['path']) + ' | ' + (reproduction + ' | ' + disposition + ' | ' if track == 'paper' else '') + row['registration_stage'] + ' | ' + str(len(row['implementation_ids'])) + ' | ' + runtime + ' |\n'
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
        'paper': ('Paper research', 'Paper reproduction and paper improvement are separate first-class outcomes on the same scientific task. '
                  'Reproduction assesses faithful recovery of the source result; improvement assesses superior performance. '
                  'Match its dataset, cohort, split, inputs, preprocessing, metric and aggregation. '
                  'Compare paper + data with paper + data + official code under fixed matched budgets; '
                  'existing historical attempts retain their recorded scope and are not automatically qualified for either outcome.'),
        'neural': ('Neural-data understanding', 'Native interpretation and tool/model building are separate first-class outcomes. '
                   'Infer specified targets from permitted neural and behavioral observations. '
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
            text += ('| Task | Scientific question / title | Reproduction eligibility | Improvement disposition | Implementation artifacts | Legacy runtime declaration |\n| --- | --- | --- | --- | --- | --- |\n' if track == 'paper' else
                     '| Task | Scientific question / title | Implementation artifacts | Legacy runtime declaration |\n| --- | --- | --- | --- |\n')
            for row in group:
                task = task_directory(row['id'], track)
                runtime = markdown_link('manifest', row['runtime_manifest']['path'], base) if row['runtime_manifest'] else 'not linked'
                text += ('| ' + markdown_link(row['id'], task + '/README.md', base) + ' | '
                         + markdown_text(row['title']) + ' | '
                         + (primary_paper_disposition(row, 'reproduction') + ' | '
                            + primary_paper_disposition(row, 'improvement') + ' | ' if track == 'paper' else '')
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
            if row.get('paper_outcomes'):
                outcomes = row['paper_outcomes']
                unavailable = outcomes.get('availability') == 'unavailable'
                gap = source_declaration_gap(outcomes)
                continuous = continuous_paper_selection(outcomes)
                text += '## Separate paper outcomes\n\n'
                if continuous is not None:
                    text += ('Both first-class outcomes use continuous fixed-panel measurements under the same typed policy. '
                             'Reproduction reports both original source methods and all eight findings; improvement reports one complete offline four-metric vector '
                             'with separate reference differences. No binary reproduction or improvement pass is assigned.\n\n'
                             '**Matched episode protocol:** Not instantiated. **Participant results:** Not attempted. '
                             'An AI attempt is not required for benchmark construction; actual bound materials and matched episode settings remain separate requirements.\n\n')
                    if 'continuous_outcomes_v2' in outcomes:
                        text += ('**Primary access pair:** `paper_data` versus `paper_data_author_code_and_weights`. '
                                 'Both conditions receive identical permitted observations, paper, task and per-outcome resource settings. '
                                 'Only the assisted condition receives the exact official code and ten pinned released-model assets. '
                                 'Faithful released-model inference is allowed reproduction in that condition; it does not establish independent training. '
                                 'Actual asset use and participant execution remain separately evidenced.\n\n')
                elif gap:
                    text += ('Reproduction is a first-class goal, but its source-grounded declaration and matched paired protocols have not been adopted. '
                             'The unchanged improvement contract remains independently inspectable under its original criteria. '
                             'All scientific outcomes remain unknown.\n\n'
                             + '**Source declaration gap:** ' + markdown_text(outcomes['reason']) + '\n\n'
                             + '**Remaining source limits:**\n\n'
                             + ''.join('- ' + markdown_text(limit) + '\n' for limit in outcomes['remaining_source_limits'])
                             + '\n')
                elif unavailable:
                    text += ('**Current complete-primary paired-outcome admission is unavailable.** '
                             'Independent reproduction remains separately assessable under the stated source limits. '
                             + markdown_text(outcomes['reason']) + '\n\n'
                             + '**Primary scientific scope:** ' + markdown_text(outcomes['primary_scope']) + '\n\n'
                             + ('**Retained improvement contract coverage:** ' if neutral_unavailable_reason(outcomes)
                                else '**Retained secondary policy:** ')
                             + markdown_text(outcomes['retained_secondary_improvement']['scope_description']) + '\n\n')
                else:
                    text += ('The current definition supports two independent outcomes: recreate the original findings and exceed them on the same task. '
                             'Each uses matched paper+data and paper+data+author-code conditions. '
                             'Contract eligibility and declared protocol availability do not establish a delivered runtime or scientific result.\n\n')
                correction = outcomes.get('primary_scope_correction')
                if correction is not None:
                    text += ('**Corrected primary scope; outcomes remain unqualified.** '
                             'Both outcome contracts retain the same primary scientific task. '
                             'Unresolved source criteria still limit receipt admission.\n\n'
                             '**Primary goal:** ' + markdown_text(correction['primary_goal']) + '\n\n'
                             '**Primary scientific scope:** ' + markdown_text(correction['primary_scope']) + '\n\n')
                    if correction['remaining_source_limits']:
                        text += (('**Retained scope-adjudication limits (see current reference successor below):**\n\n'
                                  if row['id'] == 'PAPER-ROOT-ADD-001' and outcomes.get('primary_policy_revision') is not None
                                  else '**Remaining source limits:**\n\n')
                                 + ''.join('- ' + markdown_text(limit) + '\n' for limit in correction['remaining_source_limits'])
                                 + '\n')
                    if correction.get('retained_scope_notes'):
                        text += '**Retained source scope:** ' + markdown_text(correction['retained_scope_notes']) + '\n\n'
                    if correction.get('retained_source_roles'):
                        text += ('**Retained source roles:**\n\n| Source field | Declared role |\n| --- | --- |\n'
                                 + ''.join('| ' + markdown_text(field) + ' | ' + markdown_text(value) + ' |\n'
                                           for field, value in declared_status_fields(correction['retained_source_roles']))
                                 + '\n')
                    text += ('- ' + markdown_link('Reviewed primary scope correction',
                                                 correction['root_scope_decision']['path'], task) + '\n')
                if outcomes.get('primary_policy_revision') is not None:
                    candidate = outcomes['candidate_interface']
                    author = outcomes['author_reproduction_routes']
                    text += ('### Current continuous measurement policy\n\n' if continuous is not None else
                             '### Current primary improvement policy\n\n')
                    text += '**Disposition:** ' + markdown_text(outcomes['improvement_disposition']) + '.\n\n'
                    if continuous is not None:
                        text += ('- ' + markdown_link('Shared reproduction and improvement policy', continuous['policy']['path'], task) + '\n'
                                 '- ' + markdown_link('Authenticated continuous revision', continuous['revision']['path'], task) + '\n'
                                 '- ' + markdown_link('Reviewed task amendment', outcomes['primary_policy_provenance']['amendment']['path'], task) + '\n'
                                 '- ' + markdown_link('Continuous operator entrypoint', continuous['entrypoint']['path'], task)
                                 + ': ' + ', '.join('`' + command + '`' for command in continuous['operator_entrypoint']['commands']) + '.\n\n'
                                 + markdown_text(candidate['selection_limit']) + '\n\n')
                        if 'continuous_outcomes_v2' in outcomes:
                            text += ('- ' + markdown_link('Exact official-asset allowlist', continuous['asset_allowlist']['path'], task) + '\n\n'
                                     '### Retained source-only continuous policy\n\n'
                                     'The historical `paper_data_author_code` condition remains a separate source-only ablation. '
                                     'It is not pooled with the current code-and-weights pair.\n\n')
                            for field, label in (('task', 'Preserved source-only task'), ('policy', 'Retained source-only policy'),
                                                 ('entrypoint', 'Retained source-only entrypoint'), ('revision', 'Retained source-only revision')):
                                text += '- ' + markdown_link(label, continuous['retained_v1'][field]['path'], task) + '\n'
                            text += '\n'
                        text += ('### Retained pre-continuous policies\n\n'
                                 'These policies and the archived task preserve their prior scope; they do not impose binary thresholds on current continuous measurements.\n\n')
                        retained = continuous['retained_temporal']
                        for field, label in (('task', 'Pre-continuous task'), ('reproduction', 'Retained reproduction policy'),
                                             ('improvement', 'Retained temporal improvement policy'),
                                             ('outcomes', 'Retained outcome binding'), ('revision', 'Retained temporal revision')):
                            text += '- ' + markdown_link(label, retained[field]['path'], task) + '\n'
                        text += ('\n### Retained author-source reproduction routes\n\n'
                                 + ', '.join(markdown_text(recipe) for recipe in author['recipes']) + '. '
                                 + markdown_text(author['selection_limit']) + '\n\n'
                                 '| Author source | Selector |\n| --- | --- |\n')
                        for field in ('delivery', 'scorer', 'protocol'):
                            text += '| ' + readable_label(field) + ' | ' + markdown_link(author[field]['path'].split('/')[-1], author[field]['path'], task) + ' |\n'
                        text += '\n'
                    elif row['id'] == 'PAPER-ROOT-ADD-001':
                        provenance = outcomes['primary_policy_provenance']
                        text += ('The reference successor records author-provided-array/current-runtime measurements. '
                                 'It does not establish AI reproduction, fresh author training, paired improvement or scientific qualification. '
                                 'The retained scope decision above keeps its historical limits; the selected current contracts record reference recovery and remaining obligations.\n\n'
                                 '- ' + markdown_link('Selected current improvement contract', outcomes['improvement_contract']['path'], task) + '\n'
                                 '- ' + markdown_link('Authenticated reference successor', outcomes['primary_policy_revision']['path'], task) + '\n'
                                 '- ' + markdown_link('Provided-author reference report', provenance['provided_reference']['path'], task) + '\n'
                                 '- ' + markdown_link('Reference recovery receipt', provenance['reference_receipt']['path'], task) + '\n\n')
                        text += ('**Current reproduction/source limits:**\n\n'
                                 + ''.join('- ' + markdown_text(limit) + '\n' for limit in outcomes['reproduction_blocking_issues'])
                                 + '\n')
                    elif candidate is None:
                        text += ('The reviewed current policy selects the primary scientific scope. '
                                 'Runtime routes are not declared by this policy metadata.\n\n'
                                 '- ' + markdown_link('Selected current improvement contract', outcomes['improvement_contract']['path'], task) + '\n'
                                 '- ' + markdown_link('Authenticated policy revision', outcomes['primary_policy_revision']['path'], task) + '\n'
                                 '- ' + markdown_link('Reviewed primary scope decision', outcomes['primary_policy_provenance']['scope_decision']['path'], task) + '\n\n')
                    else:
                        text += ('The candidate source interface accepts one complete offline prediction set over the full 35-bin panel. '
                                 + markdown_text(candidate['selection_limit']) + '\n\n'
                                 '- ' + markdown_link('Selected current improvement contract', outcomes['improvement_contract']['path'], task) + '\n'
                                 '- ' + markdown_link('Authenticated policy revision', outcomes['primary_policy_revision']['path'], task) + '\n'
                                 '- ' + markdown_link('Current scientific contract', outcomes['primary_policy_provenance']['scientific_contract']['path'], task) + '\n'
                                 '- ' + markdown_link('Reviewed task projection', outcomes['primary_policy_provenance']['projection']['path'], task) + '\n\n'
                                 '| Candidate source | Selector |\n| --- | --- |\n')
                        for field in ('delivery', 'scorer', 'policy'):
                            text += '| ' + readable_label(field) + ' | ' + markdown_link(candidate[field]['path'].split('/')[-1], candidate[field]['path'], task) + ' |\n'
                        text += ('\n### Retained author-source reproduction routes\n\n'
                                 'Both author recipes remain available as source routes: '
                                 + ', '.join(markdown_text(recipe) for recipe in author['recipes']) + '. '
                                 + markdown_text(author['selection_limit']) + '\n\n'
                                 '| Author source | Selector |\n| --- | --- |\n')
                        for field in ('delivery', 'scorer', 'protocol'):
                            text += '| ' + readable_label(field) + ' | ' + markdown_link(author[field]['path'].split('/')[-1], author[field]['path'], task) + ' |\n'
                        text += '\nBoth source routes remain scientifically unknown; these selectors do not authorize execution.\n\n'
                if outcomes.get('reproduction_contract') is not None and continuous is None:
                    text += ('- ' + markdown_link('Reproduction proposal (inspection only)' if unavailable else
                                                 'Original-finding reproduction contract',
                                                 outcomes['reproduction_contract']['path'], task) + '\n')
                if unavailable:
                    text += ('- ' + markdown_link('Primary outcome pairing decision' if neutral_unavailable_reason(outcomes)
                                                 else 'Primary and retained secondary scope decision',
                                                 outcomes['root_scope_decision']['path'], task) + '\n')
                if gap:
                    text += '- ' + markdown_link('Source declaration gap record', outcomes['source_declaration_gap']['path'], task) + '\n'
                elif continuous is None:
                    text += ('- ' + markdown_link('Primary-outcome unavailability record' if unavailable else
                                                  'Paired outcome protocols', outcomes['outcomes']['path'], task) + '\n')
                text += '- ' + markdown_link('Preserved definition before dual outcomes', outcomes['previous_specification']['path'], task) + '\n\n'
                if continuous is not None:
                    text += ('| Outcome | Information condition | Assessment | Episode protocol | Participant result |\n'
                             '| --- | --- | --- | --- | --- |\n')
                    for cell in outcomes['cells']:
                        text += ('| ' + markdown_text(readable_label(cell['outcome'])) + ' | '
                                 + markdown_text(readable_label(cell['condition']))
                                 + ' | Continuous measurement | Not instantiated | Not attempted |\n')
                elif gap:
                    text += ('| Outcome | Information condition | Paired protocol | Scientific outcome |\n'
                             '| --- | --- | --- | --- |\n')
                    for cell in outcomes['cells']:
                        text += ('| ' + markdown_text(readable_label(cell['outcome'])) + ' | '
                                 + markdown_text(readable_label(cell['condition'])) + ' | Not established | Unknown |\n')
                else:
                    text += ('| Outcome | Information condition | Endpoint eligibility | Protocol status | Declared availability | Scientific outcome |\n'
                             '| --- | --- | --- | --- | --- | --- |\n')
                    for cell in outcomes['cells']:
                        text += ('| ' + markdown_text(readable_label(cell['outcome'])) + ' | '
                                 + markdown_text(readable_label(cell['condition'])) + ' | '
                                 + markdown_text(cell['eligibility']) + ' | '
                                 + markdown_text(cell['pairing_status']) + ' | '
                                 + ('unavailable' if unavailable else 'specified' if cell['condition_available'] else 'unresolved')
                                 + ' | Unknown |\n')
                text += ('\nAuthor-baseline replay and historical reconstruction attempts retain their original scopes. '
                         'They are not promoted to qualified AI reproductions or improvements by these contracts.\n\n')
            if row.get('paper_improvement'):
                improvement = row['paper_improvement']
                if improvement.get('role') == RETAINED_POLICY_ROLE:
                    if continuous_paper_selection(row['paper_outcomes']) is not None:
                        text += ('## Retained original registration policy\n\n'
                                 'This original contract preserves its registration scope. The shared continuous policy above governs both current outcomes; '
                                 'this retained audit does not set current measurement thresholds.\n\n')
                    elif row['paper_outcomes']['candidate_interface'] is None:
                        text += ('## Retained predecessor improvement policy\n\n'
                                 'This original contract preserves the predecessor scientific instructions and source scope. '
                                 'The selected primary policy above governs current improvement.\n\n')
                    else:
                        text += ('## Retained author-source policy\n\n'
                                 'This original registration contract remains attached to the author-source reproduction and calibration routes. '
                                 'The selected current policy above defines the offline candidate interface; the retained author restrictions do not govern that candidate.\n\n')
                elif row.get('paper_outcomes', {}).get('availability') == 'unavailable':
                    if neutral_unavailable_reason(row['paper_outcomes']):
                        text += ('## Retained improvement contract\n\n'
                                 'This preserved contract retains the declared coverage described above. '
                                 'Complete primary-outcome pairing remains unavailable, so the contract cannot admit a primary outcome under this marker.\n\n')
                    else:
                        text += ('## Retained secondary improvement policy\n\n'
                                 'This preserved policy remains source evidence for a different or narrower scientific question. '
                                 'It is unavailable for primary outcome admission and does not define primary paper success.\n\n')
                else:
                    text += ('## Current paper-improvement objective\n\n'
                             '**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. '
                             'Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.\n\n')
                text += (
                         '**Disposition:** ' + markdown_text(improvement['disposition']) + '. '
                         + markdown_text(improvement.get('disposition_reason', '')) + '\n\n'
                         '- ' + markdown_link('Retained original improvement contract' if improvement.get('role') == RETAINED_POLICY_ROLE
                                              else 'Source-grounded improvement contract', improvement['contract']['path'], task) + '\n'
                         '- ' + (markdown_link('Preserved historical task definition', improvement['historical_specification']['path'], task)
                                 if improvement['historical_specification'] else
                                 markdown_link('Initial source-paper task registration (no predecessor)', improvement['initial_registration']['path'], task)) + '\n\n'
                         'Within the existing improvement contract, historical graders and pilot scores retain their calibration role. '
                         'They are not automatically qualified reproductions or improvements. '
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
