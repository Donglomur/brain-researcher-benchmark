#!/usr/bin/env python3
"""Build a deterministic navigation catalog from published metadata only.

Never follow runtime verification receipts, data paths, private ledgers or
candidate entrypoints. Catalog membership is not execution qualification.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import posixpath
import re
import stat
from urllib.parse import quote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = 'benchmarks/catalog'
COMMON = {'schema_version', 'id', 'track', 'title', 'status', 'primary_outputs',
          'input_assets', 'evaluation', 'resources', 'holds',
          'next_implementation_action', 'provenance', 'admission'}
READ_LIMIT = 24 * 1024 * 1024


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
        raw = path.read_bytes()
        need(len(raw) == info.st_size, 'Public metadata changed during read')
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
        need(isinstance(original, dict) and isinstance(original.get('path'), str)
             and all(original.get(key) == row['specification'][key] for key in ('bytes', 'sha256')),
             'Task definition differs from its preserved original identity')
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
              'scientific_readiness': 'unknown', 'submission_readiness': 'unknown',
              'counting_note': 'Registered task definitions, implementation artifacts and legacy runtime declarations are distinct. '
                               'An ownership link is not equivalence to the complete registered scientific contract or execution qualification. '
                               'No receipts, data, candidate code or private construction ledger were followed.',
              'registry_chain': historical, 'shared_contracts': shared, 'tasks': tasks,
              'unmapped_runtime_sources': [], 'components': components,
              'implementations': sorted(implementations, key=lambda record: record['id'])}
    validate(result, root)
    return result


def source_links(catalog):
    yield catalog['registry']['path']
    for implementation in catalog['implementations']:
        yield implementation['path']
    for row in catalog['tasks']:
        for document in row.get('documentation', []):
            yield document['path']
        yield row['specification']['path']
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


def render(catalog):
    c = catalog['counts']
    files = {'catalog.json': (json.dumps(catalog, indent=2, ensure_ascii=False) + '\n').encode()}
    intro = ('This is a public source inventory, not a list of qualified benchmarks. '
             'Scientific and submission readiness are **unknown here**. Runtime manifests '
             'and source components do not establish successful execution. Registered IDs '
             'may alias earlier contract identifiers; they do not count independent studies or datasets.\n\n')
    files['README.md'] = (f'# Neuroscience task catalog\n\n{intro}'
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
        text += '| ID | Scientific question / title | Source stage | Implementation artifacts | Legacy runtime declaration |\n| --- | --- | --- | --- | --- |\n'
        for row in rows:
            title = row['title'].replace('\\', '\\\\').replace('[', '\\[').replace(']', '\\]').replace('|', '\\|').replace('\n', ' ').replace('\r', ' ')
            identifier = row['id'].replace('|', '\\|')
            runtime = markdown_link('manifest', row['runtime_manifest']['path']) if row['runtime_manifest'] else 'not included'
            text += '| ' + markdown_link(identifier, task_directory(row['id'], track) + '/README.md') + ' | ' + markdown_link(title, row['specification']['path']) + ' | ' + row['registration_stage'] + ' | ' + str(len(row['implementation_ids'])) + ' | ' + runtime + ' |\n'
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
        'paper': ('Paper research', 'Reproduce a defined neuroscience result, then evaluate prospective improvement. '
                  'Compare paper + data with paper + data + official code under matched budgets.'),
        'neural': ('Neural-data understanding', 'Interpret neural and behavioral observations and make predictions. '
                   'Compare a prediction program written in advance with case-by-case investigation.'),
    }
    for track, (title, description) in descriptions.items():
        base = f'benchmarks/{track}'
        rows = [row for row in catalog['tasks'] if row['track'] == track]
        groups = [('Original canonical specifications', [row for row in rows if row['registration_class'] == 'canonical']),
                  ('Expansion drafts', [row for row in rows if row['registration_class'] == 'expansion'])]
        text = f'# {title}\n\n[All benchmarks](../README.md) · [Other track](../' + ('neural' if track == 'paper' else 'paper') + '/README.md)\n\n'
        text += description + '\n\n'
        text += (f"**{len(rows)} registered task drafts: {len(groups[0][1])} original specifications + "
                 f"{len(groups[1][1])} expansion drafts.** Scientific and submission readiness remain **unknown**.\n\n"
                 'Each task folder contains its authoritative `task.json` and explicitly assigned source artifacts or links to shared families. '
                 'Implementation scope notes distinguish complete definitions from narrower or alternative source. '
                 'A folder and its source do not establish a qualified runnable benchmark. Conditions, aliases and '
                 'implementation artifacts do not add independent benchmarks.\n\n')
        for heading, group in groups:
            text += f'## {heading} ({len(group)})\n\n'
            text += '| Task | Scientific question / title | Implementation artifacts | Legacy runtime declaration |\n| --- | --- | --- | --- |\n'
            for row in group:
                task = task_directory(row['id'], track)
                runtime = markdown_link('manifest', row['runtime_manifest']['path'], base) if row['runtime_manifest'] else 'not linked'
                text += ('| ' + markdown_link(row['id'], task + '/README.md', base) + ' | '
                         + markdown_text(row['title']) + ' | ' + str(len(row['implementation_ids'])) + ' | ' + runtime + ' |\n')
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
            if isinstance(row['declared_specification_status'], (dict, list)):
                text += ('## Declared status fields\n\n'
                         'These values are copied from the task definition. They do not establish current execution or scientific qualification.\n\n'
                         '| Field | Declared value |\n| --- | --- |\n')
                for field, value in declared_status_fields(row['declared_specification_status']):
                    text += '| ' + markdown_text(field) + ' | ' + markdown_text(value) + ' |\n'
                text += '\n'
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
