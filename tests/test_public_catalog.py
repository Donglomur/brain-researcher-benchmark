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

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


catalog = module('public_catalog_tests_builder', ROOT / 'tools/build_public_catalog.py')
cli = module('public_catalog_tests_cli', ROOT / 'tools/neurobench.py')


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, sort_keys=True) + '\n').encode()
    path.write_bytes(raw)
    return len(raw), hashlib.sha256(raw).hexdigest()


def fixture(root):
    for track in ('paper', 'neural'):
        for index in range(1, 101):
            identifier = f'{track.upper()}-{index:03d}'
            spec = {key: {} for key in catalog.COMMON}
            spec.update(schema_version=1, id=identifier, title='Invented public metadata ' + identifier,
                        track=track, status='specification_only', primary_outputs=[],
                        admission={'runnable': False, 'research_qualified': False})
            # A public draft can have no frozen endpoint; navigation is still valid.
            write(root / f'benchmarks/manifests/{track}/{identifier}.json', spec)
    previous, previous_pin = None, None
    paper, neural = 100, 100
    for snapshot, (p_count, n_count) in enumerate(((4, 1), (5, 10), (7, 6), (0, 1))):
        parent = root / f'benchmarks/neuroscience/expansion-{snapshot:02d}'
        before = {'paper': paper, 'neural': neural, 'total': paper + neural}
        rows = []
        for track, number in (('paper', p_count), ('neural', n_count)):
            for index in range(number):
                identifier = f'{track.upper()}-EXP-{snapshot}-{index}'
                title = 'Invented expansion ' + identifier
                spec = {'id': identifier, 'title': title, 'track': track, 'status': 'held_draft',
                        'paper': {'url': 'https://example.org/paper'},
                        'data': {'url': 'https://example.org/data?token=omit-this-query'}}
                row = {'id': identifier, 'title': title, 'track': track, 'stage': 'registered_construction_draft'}
                if snapshot == 1 and track == 'neural' and index < 3:
                    row['contract_candidate_id'] = 'HOLD-' + identifier
                    spec['id'] = row['contract_candidate_id']
                    del spec['track']
                if snapshot == 3:
                    spec['candidate_id'] = spec.pop('id')
                name = f'tasks/{identifier}.json'
                size, digest = write(parent / name, spec)
                if snapshot == 0:
                    row.update(path=name, bytes=size, sha256=digest)
                else:
                    row.update(specification=name, specification_sha256=digest)
                    if snapshot > 1:
                        row['specification_bytes'] = size
                rows.append(row)
        paper += p_count
        neural += n_count
        registry = {'tasks': rows, 'predecessor_registered_drafts': before,
                    'registered_draft_totals': {'paper': paper, 'neural': neural, 'total': paper + neural},
                    'new_held_reserves': [{'id': 'RESERVE-NEVER-COUNT', 'track': 'paper'}]}
        if snapshot == 0:
            registry['baseline_registered_contracts'] = registry.pop('predecessor_registered_drafts')
            registry['programme_totals'] = {'paper': paper, 'neural': neural,
                'registered_contracts_and_drafts': paper + neural, 'scientifically_qualified': 0, 'submission_ready': 0}
            del registry['registered_draft_totals']
        if previous is not None:
            registry['predecessor'] = f'../{previous.parent.name}/registry.json'
            if snapshot > 1:
                registry['predecessor_bytes'], registry['predecessor_sha256'] = previous_pin
        if snapshot == 2:
            registry['mandatory_shared_contract'] = 'tasks/COMMON_TASK_AND_COUNT_CONTRACT.json'
            registry['mandatory_interpretation'] = 'tasks/REGISTRATION_INTERPRETATION.json'
            for field in ('mandatory_shared_contract', 'mandatory_interpretation'):
                write(parent / registry[field], {'not_a_task': True})
        previous = parent / 'registry.json'
        previous_pin = write(previous, registry)
    write(root / 'benchmarks/neuroscience/neural-001/manifest.json',
          {'id': 'NEURAL-001', 'status': 'declared_passed_historically',
           'admission': {'runnable': True},
           'verification': {'status': 'passed', 'receipt_path': 'private-ledger-sentinel/receipt.json'},
           'entrypoints': {'score': {'argv': ['python3', 'private-ledger-sentinel/score.py']}}})
    (root / 'components/generated-source-component').mkdir(parents=True)
    (root / 'benchmarks/README.md').write_text('# Benchmark sources\n')


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
                self.assertIn('**Declared specification status:** ' + catalog.markdown_text(row['declared_specification_status']), page)
                self.assertIn('not a new self-contained runnable package', page)
                self.assertEqual('**Specification alias:**' in page, row['specification_alias'])
                self.assertEqual('Existing implementation folder' in page, bool(row['runtime_manifest']))
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
            with self.assertRaisesRegex(ValueError, 'missing|Unexpected|misplaced'):
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
            self.assertFalse((self.root / 'benchmarks/neural').exists())
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
        page.unlink()
        task.rmdir()
        task.write_text('not a directory')
        with self.assertRaisesRegex(ValueError, 'ordinary directory'):
            catalog.generate(self.root, catalog=result)
        self.assertEqual((self.root / catalog.OUTPUT / 'catalog.json').read_bytes(), before)
        task.unlink()
        task.mkdir()
        page.write_bytes(original)
        for parent in (task, task.parent):
            saved = self.root / 'saved-output-directory'
            parent.rename(saved)
            parent.symlink_to(saved, target_is_directory=True)
            with self.subTest(parent=parent), self.assertRaisesRegex(ValueError, 'ordinary directory'):
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
                         ['status'], ['check'], ['show', 'NEURAL-001'], ['show', 'NEURAL-EXP-3-0']):
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
        with self.assertRaisesRegex(ValueError, 'escapes'):
            catalog.validate(changed, self.root)

    def test_changed_expansion_spec_or_predecessor_pin_refuses(self):
        spec_path = next((self.root / 'benchmarks/neuroscience/expansion-03/tasks').glob('*.json'))
        spec_path.write_text(spec_path.read_text() + ' ')
        with self.assertRaisesRegex(ValueError, 'digest mismatch'):
            catalog.discover(self.root)

    def test_legacy_roster_mode_remains_separate(self):
        build = self.root / 'docs/neuroscience-benchmarks/build'
        write(build / 'paper_100.json', {'tasks': []})
        with self.assertRaisesRegex(ValueError, 'Incomplete legacy roster pair'):
            cli.public_metadata_mode(self.root)
        write(build / 'neural_100.json', {'tasks': []})
        self.assertFalse(cli.public_metadata_mode(self.root))


class PublishedInventoryTests(unittest.TestCase):
    def test_actual_public_catalog_is_complete_without_counting_components(self):
        # Full deterministic regeneration runs once via the separate --check
        # command. This inexpensive inventory test does not rescan large specs.
        result = catalog.load(ROOT)
        expected = {path.stem for path in ROOT.glob('benchmarks/manifests/*/*.json')}
        for path in ROOT.glob('benchmarks/neuroscience/expansion*/registry.json'):
            expected.update(row['id'] for row in json.loads(path.read_text())['tasks'])
        self.assertEqual({row['id'] for row in result['tasks']}, expected)
        self.assertEqual(result['counts']['total'], 234)
        self.assertEqual(result['counts']['paper'], 116)
        self.assertEqual(result['counts']['neural'], 118)
        self.assertEqual(result['counts']['runtime_manifests'], 95)


if __name__ == '__main__':
    unittest.main()
