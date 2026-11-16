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
import stat
from urllib.parse import quote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
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


def registered_counts(value):
    # The first public registry predates the later `total` field. Its separate
    # scientific-readiness counters are deliberately not catalog evidence.
    total = value['total'] if 'total' in value else value['registered_contracts_and_drafts']
    result = {'paper': value['paper'], 'neural': value['neural'], 'total': total}
    need(all(type(number) is int and number >= 0 for number in result.values()), 'Invalid registration counts')
    return result


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
    collect(doc.get('input_assets', {}).get('routes', []), 'source')
    collect(doc.get('sources'), 'source')
    return [{'kind': kind, 'url': url} for kind, url in sorted(found)]


def task_row(identifier, title, track, pin, stage, registry, doc):
    need(isinstance(identifier, str) and identifier and isinstance(title, str) and title,
         'Task ID and title must be nonempty strings')
    need(track in ('paper', 'neural'), 'Unknown task track')
    return {'id': identifier, 'title': title, 'track': track,
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


def discover(root=ROOT):
    root = Path(root).resolve()
    reader = Reader(root)
    # Resolve the append-only registry chain before reading the larger canonical
    # specifications. Held reserves and shared condition files are not task rows.
    registry_docs = {}
    for path in sorted(root.glob('benchmarks/neuroscience/expansion*/registry.json')):
        doc, pin = reader.read(path)
        predecessor = doc.get('predecessor')
        previous = public_path(root, (path.parent / predecessor).relative_to(root).as_posix()) if predecessor else None
        registry_docs[path] = (doc, pin, previous)
    ordered, remaining, previous = [], dict(registry_docs), None
    while remaining:
        choices = [path for path, (_, _, parent) in remaining.items() if parent == previous]
        need(len(choices) == 1, 'Expansion registries must form one complete unbranched chain')
        path = choices[0]
        doc, pin, _ = remaining.pop(path)
        if previous is not None:
            predecessor_pin = registry_docs[previous][1]
            for key, field in [('predecessor_bytes', 'bytes'), ('predecessor_sha256', 'sha256')]:
                if key in doc:
                    need(doc[key] == predecessor_pin[field], 'Expansion predecessor pin mismatch')
        ordered.append((path, doc, pin))
        previous = path

    expansion = []
    shared = []
    for path, registry, registry_pin in ordered:
        for row in registry['tasks']:
            relative = row.get('specification', row.get('path'))
            spec_path = public_path(root, (path.parent / relative).relative_to(root).as_posix())
            doc, pin = reader.read(spec_path)
            expected_sha = row.get('specification_sha256', row.get('sha256'))
            expected_size = row.get('specification_bytes', row.get('bytes'))
            need(expected_sha == pin['sha256'], 'Expansion task specification digest mismatch')
            if expected_size is not None:
                need(expected_size == pin['bytes'], 'Expansion task specification size mismatch')
            identity = doc.get('id', doc.get('candidate_id', doc.get('task_id')))
            need(identity in (row['id'], row.get('contract_candidate_id')) and identity is not None,
                 'Expansion row/specification identity mismatch')
            need(doc.get('track') is None or doc['track'] == row['track'], 'Expansion track mismatch')
            expansion.append(task_row(row['id'], row['title'], row['track'], pin,
                                      row.get('stage', 'registered_construction_draft'), registry_pin['path'], doc))
        for field in ('mandatory_shared_contract', 'mandatory_interpretation'):
            if field in registry:
                linked = public_path(root, (path.parent / registry[field]).relative_to(root).as_posix())
                shared.append({'kind': field, 'path': linked.relative_to(root).as_posix()})

    tasks = []
    for path in sorted(root.glob('benchmarks/manifests/*/*.json')):
        doc, pin = reader.read(path)
        need(COMMON.issubset(doc), 'Incomplete delivery schema: ' + pin['path'])
        need(doc['id'] == path.stem and doc['track'] == path.parent.name,
             'Misnamed or wrong-track canonical specification')
        need(doc['schema_version'] == 1 and isinstance(doc['status'], str) and doc['status'],
             'Unsupported canonical source schema or missing declared status: ' + pin['path'])
        # A browse index reports declared source status. It does not adopt source
        # admission flags or require every held draft to contain a usable endpoint.
        tasks.append(task_row(doc['id'], doc['title'], doc['track'], pin,
                              'canonical_source_specification', None, doc))
    need(counts(tasks) == {'paper': 100, 'neural': 100, 'total': 200},
         'Expected exactly 200 canonical specifications: 100 per track')
    cumulative = list(tasks)
    index = 0
    for _, registry, _ in ordered:
        before = counts(cumulative)
        expected_before = registry.get('predecessor_registered_drafts', registry.get('baseline_registered_contracts'))
        if isinstance(expected_before, dict):
            need(before == registered_counts(expected_before), 'Expansion predecessor task counts disagree')
        number = len(registry['tasks'])
        cumulative.extend(expansion[index:index + number])
        index += number
        expected_after = registry.get('registered_draft_totals', registry.get('programme_totals'))
        if isinstance(expected_after, dict):
            need(counts(cumulative) == registered_counts(expected_after), 'Expansion cumulative task counts disagree')
    tasks = sorted(cumulative, key=lambda row: row['id'])
    need(len({row['id'] for row in tasks}) == len(tasks), 'Duplicate registered task ID')
    by_id = {row['id']: row for row in tasks}

    runtime_seen, unmapped = set(), []
    for path in sorted(root.glob('benchmarks/neuroscience/*/manifest.json')):
        doc, pin = reader.read(path)
        identifier = doc['id']
        need(identifier not in runtime_seen, 'Duplicate runtime manifest task ID')
        runtime_seen.add(identifier)
        if identifier in by_id:
            by_id[identifier].update(runtime_manifest=pin, runtime_package=path.parent.relative_to(root).as_posix(),
                                     runtime_manifest_status=doc.get('status'))
        else:
            unmapped.append({'id': identifier, 'manifest': pin,
                             'classification': 'unmapped_runtime_source_not_an_additional_registered_task'})

    components = []
    for prefix, kind in [('components', 'source_component'),
                         ('benchmarks/scientific_components', 'scientific_source_component'),
                         ('benchmarks/scientific_contracts', 'scientific_contract_collection')]:
        for path in sorted((root / prefix).glob('*')):
            if path.is_dir():
                public_path(root, path.relative_to(root).as_posix())
                components.append({'name': path.name, 'kind': kind, 'path': path.relative_to(root).as_posix()})
    result = {'schema_version': 1, 'kind': 'public_neuroscience_source_catalog',
              'counts': {**counts(tasks), 'canonical_specifications': 200,
                         'expansion_drafts': len(expansion), 'runtime_manifests': len(runtime_seen),
                         'linked_runtime_manifests': len(runtime_seen) - len(unmapped),
                         'source_components': len(components)},
              'scientific_readiness': 'unknown', 'submission_readiness': 'unknown',
              'counting_note': 'Registered questions, runtime manifests, source components and subcases are distinct. '
                               'No receipts, data, candidate code or private construction ledger were followed. '
                               'Readiness is not assessed by this catalog.',
              'registry_chain': [pin for _, _, pin in ordered], 'shared_contracts': shared,
              'tasks': tasks, 'unmapped_runtime_sources': unmapped, 'components': components}
    validate(result, root)
    return result


def source_links(catalog):
    for row in catalog['tasks']:
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
    for row in tasks:
        need(row['scientific_readiness'] == row['submission_readiness'] == 'unknown'
             and row['local_scoring_adapter_verified'] is None
             and row['local_program_runner_verified'] is None, 'Catalog must not manufacture task qualification')
    for relative in source_links(catalog):
        public_path(Path(root), relative)
    return catalog


def load(root=ROOT):
    path = Path(root) / OUTPUT / 'catalog.json'
    if not path.is_file():
        return discover(root)
    return validate(json.loads(path.read_text()), root)


def markdown_link(label, path):
    relative = posixpath.relpath(path, OUTPUT)
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
        f"The checkout also contains {c['runtime_manifests']} one-level runtime manifests and "
        f"{c['source_components']} [supporting source components/collections](components.md). "
        'Participants, conditions, folds, seeds and controls are nested task units, not additional benchmarks.\n\n'
        'The [machine-readable catalog](catalog.json) includes exact specification pins and links to existing public files. '
        'External citations are copied from public specifications; their availability was not rechecked.\n\n'
        'Regenerate with `python3 tools/build_public_catalog.py`; verify with '
        '`python3 tools/build_public_catalog.py --check`, from the repository root.\n\n'
        'Expansion registries are cumulative overlays, in this order:\n\n' +
        ''.join('- ' + markdown_link(row['path'].split('/')[-2], row['path']) + '\n' for row in catalog['registry_chain']) +
        '\nShared scope and interpretation documents:\n\n' +
        ''.join('- ' + markdown_link(row['kind'], row['path']) + '\n' for row in catalog['shared_contracts'])).encode()
    for track in ('paper', 'neural'):
        rows = [row for row in catalog['tasks'] if row['track'] == track]
        text = f'# {track.title()} tasks ({len(rows)})\n\n[Catalog](README.md)\n\n' + intro
        text += '| ID | Scientific question / title | Source stage | Included runtime source |\n| --- | --- | --- | --- |\n'
        for row in rows:
            title = row['title'].replace('\\', '\\\\').replace('[', '\\[').replace(']', '\\]').replace('|', '\\|').replace('\n', ' ').replace('\r', ' ')
            identifier = row['id'].replace('|', '\\|')
            runtime = markdown_link('manifest', row['runtime_manifest']['path']) if row['runtime_manifest'] else 'not included'
            text += '| ' + identifier + ' | ' + markdown_link(title, row['specification']['path']) + ' | ' + row['registration_stage'] + ' | ' + runtime + ' |\n'
        files[track + '.md'] = text.encode()
    text = '# Supporting source components\n\n[Catalog](README.md)\n\n' + intro
    text += 'These packages and shared contracts are not additional registered benchmark IDs. No task association is inferred from a folder name.\n\n'
    text += '| Component | Classification |\n| --- | --- |\n'
    for row in catalog['components']:
        text += '| ' + markdown_link(row['name'], row['path']) + ' | ' + row['kind'] + ' |\n'
    if catalog['unmapped_runtime_sources']:
        text += '\nRuntime sources without a registered ID match:\n\n'
        for row in catalog['unmapped_runtime_sources']:
            text += '- ' + markdown_link(row['id'], row['manifest']['path']) + '\n'
    files['components.md'] = text.encode()
    return files


def generate(root=ROOT, check=False, catalog=None):
    root = Path(root)
    result = discover(root) if catalog is None else validate(catalog, root)
    contents = render(result)
    target = root / OUTPUT
    if check:
        need(target.is_dir() and {p.name for p in target.iterdir()} == set(contents),
             'Public catalog files are missing or unexpected; regenerate')
        for name, raw in contents.items():
            need((target / name).read_bytes() == raw, 'Public catalog is stale: ' + name)
    else:
        target.mkdir(parents=True, exist_ok=True)
        for name, raw in contents.items():
            (target / name).write_bytes(raw)
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
