"""Public source navigation tests; no data, receipts or candidate execution."""
from contextlib import redirect_stdout
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


catalog = module('public_catalog_tests_builder', ROOT / 'src/neurobench/catalog.py')
cli = module('public_catalog_tests_cli', ROOT / 'src/neurobench/cli.py')


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, sort_keys=True) + '\n').encode()
    path.write_bytes(raw)
    return len(raw), hashlib.sha256(raw).hexdigest()


def fixture(root):
    """Current registry with moved definitions and deliberately stale history locators."""
    rows = []
    source_commit = 'a' * 40

    def add(identifier, track, spec, classification, history=None):
        directory = catalog.task_directory(identifier, track)
        size, digest = write(root / directory / 'task.json', spec)
        pin = {'path': directory + '/task.json', 'bytes': size, 'sha256': digest}
        row = catalog.task_row(identifier, spec.get('title', 'Invented task ' + identifier), track, pin,
                               'canonical_source_specification' if classification == 'canonical' else 'registered_construction_draft',
                               history, spec)
        row.update(registration_class=classification,
                   original_specification={**pin, 'path': f'former-source/{identifier}.json'})
        rows.append(row)
        return row

    for track in ('paper', 'neural'):
        for index in range(1, 101):
            identifier = f'{track.upper()}-{index:03d}'
            spec = {key: {} for key in catalog.COMMON}
            spec.update(schema_version=1, id=identifier, title='Invented public metadata ' + identifier,
                        track=track, status='specification_only', primary_outputs=[],
                        admission={'runnable': False, 'research_qualified': False})
            add(identifier, track, spec, 'canonical')
    historical = []
    for snapshot, (p_count, n_count) in enumerate(((4, 1), (5, 10), (7, 6), (0, 1))):
        history = f'docs/provenance/registrations/expansion-{snapshot:02d}.json'
        size, digest = write(root / history, {'tasks': [{'path': 'private-ledger-sentinel/missing-old-task.json'}],
                                            'predecessor': 'old-layout/missing-registry.json'})
        historical.append({'path': history, 'original_path': f'benchmarks/neuroscience/expansion-{snapshot:02d}/registry.json',
                           'bytes': size, 'sha256': digest})
        for track, number in (('paper', p_count), ('neural', n_count)):
            for index in range(number):
                identifier = f'{track.upper()}-EXP-{snapshot}-{index}'
                spec = {'id': identifier, 'title': 'Invented expansion ' + identifier,
                        'track': track, 'status': 'held_draft',
                        'paper': {'url': 'https://example.org/paper'},
                        'data': {'url': 'https://example.org/data?token=omit-this-query'}}
                if snapshot == 0 and track == 'paper' and index == 0:
                    spec['status'] = {'stage': 'registered_construction_draft', 'runnable': False,
                                      'scientifically_qualified': False, 'submission_ready': False}
                if snapshot == 1 and track == 'neural' and index < 3:
                    spec['id'] = 'HOLD-' + identifier
                    del spec['track']
                if snapshot == 3:
                    spec['candidate_id'] = spec.pop('id')
                add(identifier, track, spec, 'expansion', history)
    by_id = {row['id']: row for row in rows}
    document_path = 'benchmarks/neural/NEURAL-003/docs/rights.md'
    (root / document_path).parent.mkdir(parents=True)
    (root / document_path).write_text('# Invented task rights and scientific scope\n')
    by_id['NEURAL-003']['documentation'] = [{'label': 'Rights and scientific scope', 'path': document_path}]
    runtime_path = 'benchmarks/neural/NEURAL-001/implementations/legacy/manifest.json'
    size, digest = write(root / runtime_path,
          {'id': 'NEURAL-001', 'status': 'declared_passed_historically',
           'admission': {'runnable': True},
           'verification': {'status': 'passed', 'receipt_path': 'private-ledger-sentinel/receipt.json'},
           'entrypoints': {'score': {'argv': ['python3', 'private-ledger-sentinel/score.py']}}})
    by_id['NEURAL-001'].update(runtime_manifest={'path': runtime_path, 'bytes': size, 'sha256': digest},
                             runtime_package=str(Path(runtime_path).parent),
                             runtime_manifest_status='declared_passed_historically')
    definitions = [
        ('legacy-n001', ['NEURAL-001'], [], 'task', str(Path(runtime_path).parent), 'Preserved partial legacy declaration.'),
        ('NEURAL-001', ['NEURAL-002'], [], 'task', 'benchmarks/neural/NEURAL-002/implementations/alternative',
         'Package-local ID coincides with another registered ID; this alternative source is assigned only to NEURAL-002.'),
        ('shared-family', ['NEURAL-001', 'PAPER-001'], [], 'shared', 'benchmarks/shared/invented-family', 'Partial shared family source.'),
        ('PAPER-001-programme', ['PAPER-001'], [], 'task', 'benchmarks/paper/PAPER-001/implementations/programme', 'Prospective programme with no legacy runtime declaration.'),
        ('related-background', [], ['NEURAL-003'], 'shared', 'benchmarks/shared/related-background', 'Background classification differs from the registered threshold task.'),
        ('unresolved-source', [], [], 'unresolved', 'docs/provenance/unresolved/source', 'Ownership is unresolved; excluded from task implementation coverage.'),
        ('unbound-family', [], [], 'shared', 'benchmarks/shared/unbound-family', 'Retained scientific family with no registered owner or related-task assignment.'),
    ]
    implementations = []
    for identifier, owners, related, scope, path, notes in definitions:
        folder = root / path
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'README.md').write_text('# Invented implementation artifact\n')
        implementations.append({'id': identifier, 'owner_ids': owners, 'related_task_ids': related,
                                'scope': scope, 'role': 'scientific source', 'path': path,
                                'original_path': 'former-implementations/' + identifier,
                                'source_commit': source_commit, 'scope_notes': notes})
    component = 'benchmarks/shared/generated-source-component'
    (root / component).mkdir(parents=True)
    shared = []
    for name in ('COMMON_TASK_AND_COUNT_CONTRACT', 'REGISTRATION_INTERPRETATION'):
        path = 'benchmarks/shared/contracts/' + name + '.json'
        write(root / path, {'not_a_task': True})
        shared.append({'kind': name.lower(), 'path': path})
    (root / 'benchmarks/README.md').write_text('# Benchmark sources\n')
    write(root / catalog.REGISTRY,
          {'schema_version': 1, 'kind': 'neuroscience_benchmark_registry', 'source_commit': source_commit,
           'source_counts': {'paper': 116, 'neural': 118, 'total': 234, 'canonical_specifications': 200,
                             'expansion_drafts': 34, 'runtime_manifests': 1, 'linked_runtime_manifests': 1,
                             'source_components': 1},
           'tasks': sorted(rows, key=lambda row: row['id']), 'historical_registries': historical,
           'shared_contracts': shared, 'implementations': implementations,
           'components': [{'name': 'generated-source-component', 'kind': 'source_component', 'path': component}]})


class PublicCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        fixture(self.root)

    def test_clean_public_roster_covers_all_ids_and_preserves_aliases(self):
        result = catalog.generate(self.root)
        self.assertFalse((self.root / 'docs/neuroscience-benchmarks/build').exists())
        self.assertEqual({k: result['counts'][k] for k in ('paper', 'neural', 'total')},
                         {'paper': 116, 'neural': 118, 'total': 234})
        self.assertEqual(len({row['id'] for row in result['tasks']}), 234)
        self.assertEqual(sum(row['specification_alias'] for row in result['tasks']), 3)
        self.assertNotIn('RESERVE-NEVER-COUNT', {row['id'] for row in result['tasks']})
        self.assertEqual(result['counts']['runtime_manifests'], 1)
        self.assertEqual(result['counts']['source_components'], 1)
        self.assertEqual(len(result['shared_contracts']), 2)
        self.assertTrue(all('token=' not in link['url'] for row in result['tasks'] for link in row['external_links']))

    def test_deterministic_regeneration_and_all_markdown_links_exist(self):
        first = catalog.generate(self.root)
        before = catalog.render(first)
        self.assertEqual(catalog.render(catalog.generate(self.root, check=True)), before)
        self.assertEqual(catalog.render(catalog.generate(self.root)), before)
        for path in catalog.source_links(first):
            self.assertTrue((self.root / path).exists(), path)
        for name, raw in before.items():
            if name.endswith('.md'):
                for target in re.findall(r'\]\(([^)]+)\)', raw.decode()):
                    self.assertTrue((self.root / catalog.OUTPUT / unquote(target)).exists(), (name, target))
        target = self.root / catalog.OUTPUT / 'paper.md'
        target.write_text(target.read_text() + 'stale\n')
        with self.assertRaisesRegex(ValueError, 'stale'):
            catalog.generate(self.root, check=True)

    def test_track_directories_group_the_original_roster_and_expansions(self):
        result = catalog.generate(self.root)
        for track, expansion in (('paper', 16), ('neural', 18)):
            folder = self.root / 'benchmarks' / track
            rows = [row for row in result['tasks'] if row['track'] == track]
            self.assertEqual({path.name for path in folder.iterdir() if path.is_dir()},
                             {row['id'] for row in rows})
            index = (folder / 'README.md').read_text()
            self.assertIn('Original canonical specifications (100)', index)
            self.assertIn(f'Expansion drafts ({expansion})', index)
            for row in rows:
                self.assertEqual(row['task_directory'], f"benchmarks/{track}/{row['id']}")
                page = (self.root / row['task_directory'] / 'README.md').read_text()
                self.assertIn(row['specification']['sha256'], page)
                self.assertIn('Unknown', page)
                self.assertIn('**Declared specification status:** ' + catalog.markdown_text(catalog.status_summary(row['declared_specification_status'])), page)
                self.assertIn('authoritative registered definition', page)
                self.assertEqual('**Specification alias:**' in page, row['specification_alias'])
                self.assertEqual('Legacy declaration package' in page, bool(row['runtime_manifest']))
                self.assertNotIn('token=', page)
        for name, raw in catalog.render_tracks(result).items():
            page = self.root / name
            for target in re.findall(r'\]\(([^)]+)\)', raw.decode()):
                if not target.startswith(('http://', 'https://')):
                    self.assertTrue((page.parent / unquote(target)).exists(), (name, target))

    def test_track_checks_detect_missing_stale_and_misplaced_entries(self):
        result = catalog.generate(self.root)
        task = self.root / result['tasks'][0]['task_directory']
        page = task / 'README.md'
        original = page.read_bytes()
        page.unlink()
        with self.assertRaisesRegex(ValueError, 'missing'):
            catalog.generate(self.root, check=True, catalog=result)
        page.write_bytes(original + b'stale\n')
        with self.assertRaisesRegex(ValueError, 'stale'):
            catalog.generate(self.root, check=True, catalog=result)
        page.write_bytes(original)
        wrong_track = 'paper' if result['tasks'][0]['track'] == 'neural' else 'neural'
        misplaced = self.root / 'benchmarks' / wrong_track / task.name
        task.rename(misplaced)
        for check in (True, False):
            with self.assertRaisesRegex(ValueError, 'missing|Missing|Unexpected|misplaced'):
                catalog.generate(self.root, check=check, catalog=result)
        self.assertFalse(task.exists())

    def test_unsafe_task_output_ids_refuse_before_writes(self):
        result = catalog.discover(self.root)
        for identifier in ('../escape', '/absolute', 'two/parts', 'two\\parts', '.', '..',
                           'README.md', 'rEaDmE.Md', 'A' * 201):
            changed = copy.deepcopy(result)
            changed['tasks'][0]['id'] = identifier
            with self.subTest(identifier=identifier), self.assertRaisesRegex(ValueError, 'Unsafe'):
                catalog.generate(self.root, catalog=changed)
            self.assertFalse((self.root / catalog.OUTPUT).exists())
            self.assertFalse((self.root / 'benchmarks/neural/README.md').exists())
        changed = copy.deepcopy(result)
        changed['tasks'][0]['task_directory'] = 'benchmarks/paper/elsewhere'
        with self.assertRaisesRegex(ValueError, 'does not match'):
            catalog.generate(self.root, catalog=changed)
        changed = copy.deepcopy(result)
        changed['tasks'][1]['id'] = changed['tasks'][0]['id'].lower()
        changed['tasks'][1]['task_directory'] = catalog.task_directory(changed['tasks'][1]['id'], changed['tasks'][1]['track'])
        with self.assertRaisesRegex(ValueError, 'Ambiguous'):
            catalog.generate(self.root, catalog=changed)
        self.assertFalse((self.root / catalog.OUTPUT).exists())

    def test_output_aliases_and_conflicting_types_refuse_without_other_writes(self):
        result = catalog.generate(self.root)
        task = self.root / result['tasks'][0]['task_directory']
        page = task / 'README.md'
        before = (self.root / catalog.OUTPUT / 'catalog.json').read_bytes()
        original = page.read_bytes()
        for kind in ('dangling_symlink', 'directory', 'hardlink'):
            page.unlink()
            if kind == 'dangling_symlink':
                page.symlink_to(self.root / 'absent-target')
            elif kind == 'directory':
                page.mkdir()
            else:
                target = self.root / 'unrelated-output-target'
                target.write_bytes(b'preserve me')
                page.hardlink_to(target)
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'ordinary single-link'):
                catalog.generate(self.root, catalog=result)
            self.assertEqual((self.root / catalog.OUTPUT / 'catalog.json').read_bytes(), before)
            if kind == 'directory':
                page.rmdir()
            else:
                page.unlink()
            page.write_bytes(original)
        saved_task = self.root / 'saved-task-definition'
        task.rename(saved_task)
        task.write_text('not a directory')
        with self.assertRaises((ValueError, NotADirectoryError)):
            catalog.generate(self.root, catalog=result)
        self.assertEqual((self.root / catalog.OUTPUT / 'catalog.json').read_bytes(), before)
        task.unlink()
        saved_task.rename(task)
        for parent in (task, task.parent):
            saved = self.root / 'saved-output-directory'
            parent.rename(saved)
            parent.symlink_to(saved, target_is_directory=True)
            with self.subTest(parent=parent), self.assertRaisesRegex(ValueError, 'ordinary directory|symlinks'):
                catalog.generate(self.root, catalog=result)
            parent.unlink()
            saved.rename(parent)
        self.assertEqual((self.root / catalog.OUTPUT / 'catalog.json').read_bytes(), before)

    def test_regeneration_preserves_additional_authored_task_files(self):
        result = catalog.generate(self.root)
        authored = self.root / result['tasks'][0]['task_directory'] / 'notes.txt'
        authored.write_bytes(b'Unrelated authored task material.\n')
        before = authored.read_bytes()
        catalog.generate(self.root, catalog=result)
        catalog.generate(self.root, check=True, catalog=result)
        self.assertEqual(authored.read_bytes(), before)

    def test_public_cli_never_follows_private_verification_paths(self):
        catalog.generate(self.root)
        original_stat = Path.stat
        def guarded_stat(path, *args, **kwargs):
            self.assertNotIn('private-ledger-sentinel', str(path))
            return original_stat(path, *args, **kwargs)
        with patch.object(Path, 'stat', guarded_stat), \
             patch.object(cli, 'verified_runtime', side_effect=AssertionError('No verification traversal')), \
             patch.object(cli, 'verified_program_runtime', side_effect=AssertionError('No verification traversal')), \
             patch.object(cli.subprocess, 'run', side_effect=AssertionError('No process execution')):
            for args in (['list'], ['list', '--track', 'paper'], ['list', '--track', 'neural'],
                         ['status'], ['check'], ['show', 'NEURAL-001'], ['show', 'NEURAL-EXP-3-0'],
                         ['implementations', 'NEURAL-001'], ['implementations', 'PAPER-001']):
                with self.subTest(args=args), redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(cli.main(args, root=self.root), 0)
                result = json.loads(output.getvalue())
                if args[0] == 'list':
                    self.assertEqual(len(result), 234 if len(args) == 1 else (116 if args[-1] == 'paper' else 118))
                    self.assertTrue(all(row['local_scoring_adapter_verified'] is None for row in result))
                if args[0] in ('status', 'check'):
                    self.assertIsNone(result['research_qualified'])
                    self.assertIsNone(result['submission_ready'])
                    self.assertIsNone(result['local_score_adapters_verified'])
                    self.assertEqual(result['scientific_readiness'], 'unknown')
                    self.assertEqual(result['runtime_manifests_present'], 1)

    def test_implementation_view_exposes_programmes_without_legacy_runtimes(self):
        catalog.generate(self.root)
        with patch.object(cli.subprocess, 'run', side_effect=AssertionError('No process execution')):
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(cli.main(['implementations', 'PAPER-001'], root=self.root), 0)
            result = json.loads(output.getvalue())
            records = {record['id']: record for record in result['implementations']}
            self.assertEqual(set(records), {'PAPER-001-programme', 'shared-family'})
            self.assertEqual(records['PAPER-001-programme']['path'],
                             'benchmarks/paper/PAPER-001/implementations/programme')
            self.assertIn('no legacy runtime', records['PAPER-001-programme']['scope_notes'])
            self.assertEqual(records['shared-family']['owner_ids'], ['NEURAL-001', 'PAPER-001'])
            self.assertEqual(result['scientific_readiness'], 'unknown')
            self.assertEqual(result['related_sources'], [])
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(cli.main(['show', 'PAPER-001'], root=self.root), 0)
            shown = json.loads(output.getvalue())
            self.assertIsNone(shown['runtime'])
            self.assertEqual(shown['sources'], result)

    def test_implementation_view_keeps_related_source_separate_and_does_not_infer_owners(self):
        catalog.generate(self.root)
        result = cli.public_metadata_command('implementations', self.root, task_id='NEURAL-003')
        self.assertEqual(result['implementations'], [])
        self.assertEqual([r['id'] for r in result['related_sources']], ['related-background'])
        self.assertEqual(result['related_sources'][0]['owner_ids'], [])
        self.assertEqual(result['documentation'][0]['label'], 'Rights and scientific scope')
        empty = cli.public_metadata_command('implementations', self.root, task_id='PAPER-100')
        self.assertEqual(empty['implementations'], [])
        self.assertEqual(empty['related_sources'], [])
        # A package-local ID equal to another task ID never makes it that task's source.
        different_owner = cli.public_metadata_command('implementations', self.root, task_id='NEURAL-002')
        self.assertEqual([r['id'] for r in different_owner['implementations']], ['NEURAL-001'])
        with self.assertRaisesRegex(ValueError, 'Specification not yet built'):
            cli.public_metadata_command('implementations', self.root, task_id='UNKNOWN')

    def test_implementation_metadata_cannot_assert_verified_scientific_readiness(self):
        registry = json.loads((self.root / catalog.REGISTRY).read_text())
        artifact = next(row for row in registry['implementations'] if row['id'] == 'PAPER-001-programme')
        artifact.update(status='ready', scientific_readiness='qualified')
        write(self.root / catalog.REGISTRY, registry)
        with patch.object(cli, 'verified_runtime', side_effect=AssertionError('No receipt traversal')), \
             patch.object(cli, 'verified_program_runtime', side_effect=AssertionError('No receipt traversal')):
            result = cli.public_metadata_command('implementations', self.root, task_id='PAPER-001')
        record = next(row for row in result['implementations'] if row['id'] == 'PAPER-001-programme')
        self.assertEqual(record['declared_source_status'], 'ready')
        self.assertEqual(record['scientific_readiness'], 'unknown')
        self.assertEqual(result['scientific_readiness'], 'unknown')

    def test_duplicate_missing_and_escaped_source_links_refuse(self):
        result = catalog.generate(self.root)
        duplicate = copy.deepcopy(result)
        duplicate['tasks'].append(copy.deepcopy(duplicate['tasks'][0]))
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            catalog.validate(duplicate, self.root)
        changed = copy.deepcopy(result)
        changed['tasks'][0]['specification']['path'] = 'missing.json'
        with self.assertRaisesRegex(ValueError, 'Missing'):
            catalog.validate(changed, self.root)
        changed['tasks'][0]['specification']['path'] = '../outside.json'
        with self.assertRaisesRegex(ValueError, 'normalized|escapes'):
            catalog.validate(changed, self.root)

    def test_changed_task_and_historical_registry_bodies_refuse(self):
        registry = json.loads((self.root / catalog.REGISTRY).read_text())
        task = registry['tasks'][-1]
        path = self.root / task['specification']['path']
        original = path.read_bytes()
        path.write_bytes(original + b' ')
        with self.assertRaisesRegex(ValueError, 'Task specification pin mismatch'):
            catalog.discover(self.root)
        path.write_bytes(original)
        history = self.root / registry['historical_registries'][0]['path']
        history.write_bytes(history.read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'Historical registry pin mismatch'):
            catalog.discover(self.root)

    def test_all_explicit_artifacts_and_related_sources_are_linked_without_id_inference(self):
        result = catalog.generate(self.root)
        by_id = {row['id']: row for row in result['tasks']}
        self.assertEqual(result['counts']['implementation_artifacts'], 7)
        self.assertEqual(result['counts']['tasks_with_implementation_artifacts'], 3)
        self.assertEqual(result['counts']['tasks_with_related_scientific_sources'], 1)
        self.assertEqual(result['counts']['unresolved_implementation_artifacts'], 1)
        self.assertNotIn('NEURAL-001', by_id['NEURAL-001']['implementation_ids'])
        self.assertEqual(by_id['NEURAL-002']['implementation_ids'], ['NEURAL-001'])
        self.assertEqual(by_id['PAPER-001']['implementation_ids'], ['PAPER-001-programme', 'shared-family'])
        self.assertIsNone(by_id['PAPER-001']['runtime_manifest'])
        self.assertEqual(by_id['NEURAL-003']['implementation_ids'], [])
        self.assertEqual(by_id['NEURAL-003']['related_implementation_ids'], ['related-background'])
        related_page = (self.root / by_id['NEURAL-003']['task_directory'] / 'README.md').read_text()
        self.assertIn('Related scientific source (different or narrower scope)', related_page)
        self.assertIn('not assigned implementations', related_page)
        self.assertIn('## Task documentation', related_page)
        self.assertIn('[Rights and scientific scope](docs/rights.md)', related_page)
        for artifact in result['implementations']:
            for identifier in artifact['owner_ids'] + artifact.get('related_task_ids', []):
                page = (self.root / by_id[identifier]['task_directory'] / 'README.md').read_text()
                self.assertIn(catalog.markdown_text(artifact['scope_notes']), page)
        self.assertEqual(result['source_counts']['runtime_manifests'], 1)
        self.assertEqual(result['counts']['total'], 234)

    def test_shared_index_uses_readable_labels_without_changing_relationships_or_packages(self):
        registry = json.loads((self.root / catalog.REGISTRY).read_text())
        family_pages = {self.root / record['path'] / 'README.md': (self.root / record['path'] / 'README.md').read_bytes()
                        for record in registry['implementations'] if record['path'].startswith('benchmarks/shared/')}
        result = catalog.generate(self.root)
        shared = self.root / 'benchmarks/shared/README.md'
        body = shared.read_text()
        for heading in ('Assigned source', 'Related source only', 'Unbound scientific families', 'Unresolved ownership'):
            self.assertIn('## ' + heading, body)
        self.assertIn('[Invented family](invented-family)', body)
        self.assertIn('[Unbound family](unbound-family)', body)
        self.assertIn('no registered task owner', body)
        by_id = {row['id']: row for row in result['tasks']}
        task = (self.root / by_id['PAPER-001']['task_directory'] / 'README.md').read_text()
        self.assertIn('[Programme](implementations/programme)', task)
        self.assertNotIn('[PAPER-001-programme]', task)
        self.assertIn('PAPER-001-programme', by_id['PAPER-001']['implementation_ids'])
        for path, previous in family_pages.items():
            self.assertEqual(path.read_bytes(), previous)
        for target in re.findall(r'\]\(([^)]+)\)', body):
            self.assertTrue((shared.parent / unquote(target)).exists(), target)
        shared.write_text(body + 'stale\n')
        with self.assertRaisesRegex(ValueError, 'stale'):
            catalog.generate(self.root, check=True, catalog=result)

    def test_structured_declared_status_is_readable_without_qualification_promotion(self):
        result = catalog.generate(self.root)
        row = next(row for row in result['tasks'] if row['id'] == 'PAPER-EXP-0-0')
        self.assertIsInstance(row['declared_specification_status'], dict)
        self.assertIs(row['declared_specification_status']['runnable'], False)
        page = (self.root / row['task_directory'] / 'README.md').read_text()
        self.assertIn('**Declared specification status:** Registered construction draft', page)
        self.assertIn('| Runnable | No |', page)
        self.assertIn('| Scientifically qualified | No |', page)
        self.assertIn('**Scientific and submission readiness:** Unknown', page)
        self.assertIn('do not establish current execution or scientific qualification', page)
        self.assertNotIn("{'stage':", page)
        self.assertNotIn('False', page)
        self.assertEqual(list(catalog.declared_status_fields({'nested': {'ready': True}})), [('Nested / Ready', 'Yes')])

    def test_unknown_owners_related_ids_and_scope_mismatches_refuse(self):
        registry_path = self.root / catalog.REGISTRY
        original = json.loads(registry_path.read_text())
        mutations = [
            ('owner', lambda row: row.update(owner_ids=['UNKNOWN']), 'Unknown implementation owner'),
            ('related', lambda row: row.update(related_task_ids=['UNKNOWN']), 'Unknown related task ID'),
            ('overlap', lambda row: row.update(related_task_ids=row['owner_ids']), 'distinct'),
            ('task-no-owner', lambda row: row.update(owner_ids=[]), 'exactly one owner'),
            ('task-two-owners', lambda row: row.update(owner_ids=['NEURAL-001', 'NEURAL-002']), 'exactly one owner'),
            ('unresolved-owned', lambda row: row.update(scope='unresolved'), 'must not claim'),
            ('unknown-scope', lambda row: row.update(scope='assumed'), 'Unknown implementation scope'),
            ('no-notes', lambda row: row.update(scope_notes=''), 'scope_notes'),
            ('missing-artifact', lambda row: row.update(path='missing/artifact'), 'Missing public source'),
        ]
        for name, mutation, expected in mutations:
            changed = copy.deepcopy(original)
            mutation(changed['implementations'][0])
            write(registry_path, changed)
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, expected):
                catalog.discover(self.root)
        write(registry_path, original)
        result = catalog.discover(self.root)
        result['tasks'][0]['implementation_ids'].append('ORPHAN')
        with self.assertRaisesRegex(ValueError, 'Orphan'):
            catalog.validate(result, self.root)

    def test_registry_is_the_only_discovery_input(self):
        write(self.root / 'benchmarks/neuroscience/misleading-PAPER-001/manifest.json',
              {'id': 'PAPER-001', 'admission': {'runnable': True}})
        write(self.root / 'benchmarks/manifests/paper/UNREGISTERED.json',
              {'id': 'UNREGISTERED', 'track': 'paper'})
        result = catalog.discover(self.root)
        self.assertEqual(result['counts']['total'], 234)
        self.assertEqual(result['counts']['runtime_manifests'], 1)
        self.assertEqual(result['counts']['implementation_artifacts'], 7)
        (self.root / catalog.REGISTRY).unlink()
        with self.assertRaisesRegex(ValueError, 'Missing public source link'):
            catalog.discover(self.root)

    def test_registry_id_cannot_replace_a_task_definition_or_silently_reclassify_it(self):
        path = self.root / catalog.REGISTRY
        original = json.loads(path.read_text())
        mutations = [
            ('specification-id', lambda row: row.update(specification_id='OTHER'), 'identity mismatch'),
            ('alias', lambda row: row.update(specification_alias=True), 'alias'),
            ('original-hash', lambda row: row['original_specification'].update(sha256='0' * 64), 'preserved original'),
            ('classification', lambda row: row.update(registration_class='expansion'), 'lineage'),
            ('cross-task-documentation', lambda row: row.update(documentation=[{'label': 'Wrong task', 'path': 'benchmarks/neural/NEURAL-003/docs/rights.md'}]), 'exact task folder'),
            ('track', lambda row: row.update(track='paper', task_directory='benchmarks/paper/' + row['id']), 'task.json'),
        ]
        for name, mutate, expected in mutations:
            changed = copy.deepcopy(original)
            mutate(changed['tasks'][0])
            write(path, changed)
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, expected):
                catalog.discover(self.root)
        write(path, original)
        # Current task hashes are read through the registry, even when a stale generated catalog exists.
        catalog.generate(self.root)
        task = self.root / original['tasks'][0]['specification']['path']
        task.write_bytes(task.read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'pin mismatch'):
            catalog.load(self.root)

    def test_legacy_ledgers_never_replace_the_current_registry(self):
        build = self.root / 'docs/neuroscience-benchmarks/build'
        write(build / 'paper_100.json', {'tasks': []})
        self.assertTrue(cli.public_metadata_mode(self.root))
        write(build / 'neural_100.json', {'tasks': []})
        self.assertTrue(cli.public_metadata_mode(self.root))
        (self.root / catalog.REGISTRY).unlink()
        with self.assertRaises((ValueError, FileNotFoundError)):
            cli.public_metadata_mode(self.root)


class PublishedInventoryTests(unittest.TestCase):
    def test_actual_public_catalog_is_complete_without_counting_components(self):
        # Read current authoritative definitions; generated catalogs cannot hide stale source.
        result = catalog.load(ROOT)
        registry = json.loads((ROOT / catalog.REGISTRY).read_text())
        expected = {row['id'] for row in registry['tasks']}
        self.assertEqual({row['id'] for row in result['tasks']}, expected)
        self.assertEqual(result['counts']['total'], 234)
        self.assertEqual(result['counts']['paper'], 116)
        self.assertEqual(result['counts']['neural'], 118)
        self.assertEqual(result['counts']['runtime_manifests'], 95)


if __name__ == '__main__':
    unittest.main()
