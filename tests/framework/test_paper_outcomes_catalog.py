"""Generated metadata-only controls for dual outcomes, lineage and CLI reads."""
from contextlib import redirect_stdout
import copy
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


initial = module('outcomes_initial_catalog_fixture', ROOT / 'tests/framework/test_initial_paper_catalog.py')
examples = module('outcomes_receipt_fixture', ROOT / 'tests/framework/test_paper_reproduction.py')
binding = module('outcomes_catalog_binding', ROOT / 'src/neurobench/paper_outcomes_binding.py')
catalog, cli, builder = initial.catalog, initial.cli, initial.builder
engine = binding.engine()


def unresolved_contract(improvement):
    return {
        'schema_version': 'paper-reproduction/v1', 'task_id': improvement['task_id'],
        'objective': 'recreate_original_findings_same_task', 'eligibility': 'source_unresolved',
        'eligibility_reason': 'Generated metadata fixture with an unresolved original finding.',
        'source_paper': copy.deepcopy(improvement['source_paper']),
        'evidence': copy.deepcopy(improvement['evidence']),
        'same_task': {**copy.deepcopy(improvement['same_task']), **{
            key: {'status': 'unresolved', 'description': 'Unresolved generated ' + key, 'evidence_ids': []}
            for key in ('full_panel', 'permitted_observations')}},
        'findings': [{
            'id': 'original', 'kind': 'scalar', 'description': 'Unresolved generated original finding',
            'status': 'unresolved', 'expected': None, 'units': 'unresolved', 'aggregation': 'unresolved',
            'evidence_ids': [], 'categories': [],
            'tolerance': {'status': 'unresolved', 'absolute': None, 'rationale': 'No invented tolerance.', 'evidence_ids': []},
            'uncertainty': {'kind': 'unresolved', 'method': 'unresolved', 'independent_unit': 'unresolved',
                            'minimum_independent_units': None, 'confidence_level': None, 'statistic': None,
                            'operator': None, 'threshold': None, 'rationale': 'No invented interval.', 'evidence_ids': []},
        }],
        'panel_rule': 'all_declared_findings_and_companions',
        'blocking_issues': ['Generated fixture has no source-native original finding.'],
    }


class PaperOutcomesCatalogTests(unittest.TestCase):
    def setUp(self):
        self.fixture = initial.InitialPaperCatalogTests('test_117th_paper_preserves_original_116_and_canonical_100')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.selected = 'PAPER-001'
        reproduction, improvement, outcomes, result, _ = examples.fixture()
        for doc in (reproduction, improvement, outcomes, result):
            doc['task_id'] = self.selected
        examples.refreeze(reproduction, improvement, outcomes, result)
        initial.put(self.root, 'benchmarks/paper/PAPER-001/improvement.v1.json', improvement)
        builder.write_or_check(self.root, validator=initial.engine.contract_validate)
        previous_raw = (self.root / builder.REGISTRY).read_bytes()
        previous = json.loads(previous_raw)
        self.previous_rows = {row['id']: copy.deepcopy(row) for row in previous['tasks']}
        self.original_initial = (self.root / initial.REGISTRATION).read_bytes()
        self.original_first = (self.root / initial.DIRECTORY / 'task.json').read_bytes()
        self.original_registry = (self.root / builder.SNAPSHOT).read_bytes()
        self.write(binding.SNAPSHOT, previous_raw)
        registry = copy.deepcopy(previous)
        registry['paper_outcomes'] = {
            'schema_version': binding.VERSION, 'coverage_required': True, 'registered_count': 117,
            'pre_outcomes_registry': binding.pin(binding.SNAPSHOT, previous_raw),
        }
        registry['historical_registries'].append(registry['paper_outcomes']['pre_outcomes_registry'])
        for row in registry['tasks']:
            if row['track'] != 'paper':
                continue
            home = row['task_directory']
            raw = (self.root / home / 'task.json').read_bytes()
            old = json.loads(raw)
            contract = json.loads((self.root / home / 'improvement.v1.json').read_bytes())
            previous_pin = self.write(home + '/' + binding.HISTORY, raw)
            projected = binding.project_task(old, row, contract)
            row['specification'] = self.write(home + '/task.json', binding.encode(projected))
            if row['id'] == self.selected:
                repro, descriptor = copy.deepcopy(reproduction), copy.deepcopy(outcomes)
            else:
                repro = unresolved_contract(contract)
                descriptor = {
                    'schema_version': 'paper-outcomes/v1', 'task_id': row['id'],
                    'original_task_sha256': row['specification']['sha256'],
                    'contracts': {'reproduction': engine.contract_digest(repro),
                                  'improvement': engine.contract_digest(contract)},
                    'pairing': {outcome: {'status': 'unresolved', 'rationale': 'Generated protocol unresolved.', 'protocol': None}
                                for outcome in ('reproduction', 'improvement')},
                }
            descriptor['original_task_sha256'] = row['specification']['sha256']
            row['paper_outcomes'] = {
                'schema_version': binding.VERSION, 'previous_specification': previous_pin,
                'reproduction_contract': self.write(home + '/reproduction.v1.json', repro),
                'outcomes': self.write(home + '/outcomes.v1.json', descriptor),
            }
            if row['id'] == self.selected:
                self.reproduction, self.outcomes, self.result = repro, descriptor, result
        self.save_registry(registry)

    def write(self, relative, value):
        raw = value if isinstance(value, bytes) else binding.encode(value)
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return binding.pin(relative, raw)

    def registry(self):
        return json.loads((self.root / builder.REGISTRY).read_bytes())

    def save_registry(self, value):
        self.write(builder.REGISTRY, value)

    def row(self, registry, identifier=None):
        return next(row for row in registry['tasks'] if row['id'] == (identifier or self.selected))

    def repin_descriptor(self, mutate):
        registry = self.registry()
        row = self.row(registry)
        relative = row['paper_outcomes']['outcomes']['path']
        descriptor = json.loads((self.root / relative).read_bytes())
        mutate(descriptor)
        row['paper_outcomes']['outcomes'] = self.write(relative, descriptor)
        self.save_registry(registry)

    def receipt_file(self, receipt=None):
        receipt = examples.receipt_for(self.outcomes, self.result) if receipt is None else receipt
        relative = 'receipt.json'
        self.write(relative, receipt)
        return self.root / relative

    def unavailable_view(self, *, proposal=False):
        """Authenticate a generated exact-ID marker through the real shared helper.

        The full fixture above covers the catalog's old lineage adapter. This
        fixture isolates the public CLI/render boundary after helper validation;
        its source decisions are synthetic metadata, not empirical findings.
        """
        identifier = 'PAPER-FIND-013'
        home = 'benchmarks/paper/' + identifier
        prior = copy.deepcopy(self.previous_rows[self.selected])
        prior.update(id=identifier, task_directory=home)
        old = json.loads((self.root / self.previous_rows[self.selected]['task_directory'] / binding.HISTORY).read_bytes())
        old['id'] = identifier
        old_raw = binding.encode(old)
        prior['specification'] = binding.pin(home + '/task.json', old_raw)
        improvement = json.loads((self.root / self.previous_rows[self.selected]['task_directory'] / 'improvement.v1.json').read_bytes())
        improvement['task_id'] = identifier
        prior['specification_revision']['improvement_contract'] = self.write(home + '/improvement.v1.json', improvement)
        scope = {'schema_version': binding.SCOPE_VERSION, 'entries': {
            task: {'task_id': task, 'primary_goal': 'Generated primary empirical finding',
                   'primary_scope': 'Generated primary population and finding panel',
                   'retained_secondary_scope': 'Generated separate secondary prediction',
                   'remaining_source_limits': ['Generated unresolved source fixture'],
                   'primary_same_task_improvement': 'unavailable_until_independently_justified',
                   'paired_bundle_status': 'unavailable_primary_secondary_scope_mismatch',
                   'scientific_outcome': 'unknown'} for task in binding.SCOPE_IDS}}
        scope_pin = self.write(binding.SCOPE_PATH, scope)
        snapshot = {'schema_version': 1, 'kind': 'neuroscience_benchmark_registry', 'tasks': [prior]}
        # A separate fixture root is unnecessary: exact pins authenticate this
        # replacement snapshot, and no original full-roster assertions use it.
        snapshot_pin = self.write(binding.SNAPSHOT, snapshot)
        row = copy.deepcopy(prior)
        projected = binding.project_task(old, prior, improvement, scope['entries'][identifier])
        row['specification'] = self.write(home + '/task.json', projected)
        marker = {
            'schema_version': binding.UNAVAILABLE, 'task_id': identifier,
            'original_task_sha256': row['specification']['sha256'], 'status': 'unavailable',
            'reason_code': 'primary_secondary_scope_mismatch',
            'reason': 'The generated primary panel and secondary prediction are distinct.',
            'primary_scope': scope['entries'][identifier]['primary_scope'],
            'retained_secondary_improvement': {
                'path': 'improvement.v1.json',
                'raw_sha256': row['specification_revision']['improvement_contract']['sha256'],
                'contract_digest': engine.contract_digest(improvement),
                'scope_description': scope['entries'][identifier]['retained_secondary_scope']},
            'root_scope_decision': {'path': binding.SCOPE_PATH, 'raw_sha256': scope_pin['sha256'],
                                    'task_entry_id': identifier}}
        row['paper_outcomes'] = {'schema_version': binding.VERSION,
                                 'previous_specification': self.write(home + '/' + binding.HISTORY, old_raw)}
        reproduction = None
        if proposal:
            reproduction = unresolved_contract(improvement)
            reproduction['same_task']['target']['description'] = scope['entries'][identifier]['primary_scope']
            repro_pin = self.write(home + '/reproduction.v1.json', reproduction)
            row['paper_outcomes']['reproduction_contract'] = repro_pin
            marker['reproduction_proposal'] = {'path': 'reproduction.v1.json', 'raw_sha256': repro_pin['sha256'],
                                               'contract_digest': engine.contract_digest(reproduction)}
        row['paper_outcomes']['outcomes'] = self.write(home + '/outcomes.v1.json', marker)
        registry = {'tasks': [row], 'paper_outcomes': {
            'schema_version': binding.VERSION, 'coverage_required': True, 'registered_count': 1,
            'pre_outcomes_registry': snapshot_pin, 'scope_decisions': scope_pin}}
        reader = catalog.Reader(self.root)
        read_pin = lambda pin, label: catalog.checked_pin(reader, pin, label)
        previous = binding.coverage(registry, read_pin)
        bound = binding.context(row, projected, previous, read_pin)
        view = {'id': identifier, 'track': 'paper', 'specification': row['specification'],
                'paper_outcomes': binding.public_summary(row, bound),
                'paper_improvement': {'contract': row['specification_revision']['improvement_contract'],
                                      'disposition': improvement['disposition']}}
        return view, reproduction, marker

    def test_distinct_task_counts_four_unknown_cells_and_preserved_lineage(self):
        result = catalog.discover(self.root)
        self.assertEqual({key: result['counts'][key] for key in ('paper', 'neural', 'total')},
                         {'paper': 117, 'neural': 118, 'total': 235})
        self.assertEqual(result['paper_outcome_counts']['covered'], 117)
        self.assertEqual(result['paper_outcome_counts']['reproduction_eligibility'],
                         {'eligible': 1, 'source_unresolved': 116})
        self.assertEqual((self.root / builder.SNAPSHOT).read_bytes(), self.original_registry)
        self.assertEqual((self.root / initial.REGISTRATION).read_bytes(), self.original_initial)
        self.assertEqual((self.root / initial.DIRECTORY / binding.HISTORY).read_bytes(), self.original_first)
        smc = self.row(result, initial.IDENTIFIER)
        self.assertIsNone(smc['paper_improvement']['historical_specification'])
        self.assertNotEqual(smc['specification'], smc['original_specification'])
        for task in (row for row in result['tasks'] if row['track'] == 'paper'):
            self.assertEqual(len(task['paper_outcomes']['cells']), 4)
            self.assertTrue(all(cell['scientific_outcome'] == 'unknown' and cell['receipt'] is None
                                for cell in task['paper_outcomes']['cells']))

    def test_current_raw_identity_is_not_a_canonical_json_digest(self):
        registry = self.registry()
        doc = json.loads((self.root / self.row(registry)['specification']['path']).read_bytes())
        canonical = engine.contract_digest(doc)
        self.assertNotEqual(canonical, self.row(registry)['specification']['sha256'])
        self.repin_descriptor(lambda value: value.update(original_task_sha256=canonical))
        with self.assertRaisesRegex(ValueError, 'raw current task identity'):
            catalog.discover(self.root)

    def test_rehashed_arbitrary_current_document_is_rejected(self):
        registry = self.registry()
        row = self.row(registry)
        path = row['specification']['path']
        doc = json.loads((self.root / path).read_bytes())
        doc['input_assets'] = {'invented': 'different observation'}
        row['specification'] = self.write(path, doc)
        self.save_registry(registry)
        self.repin_descriptor(lambda value: value.update(original_task_sha256=row['specification']['sha256']))
        with self.assertRaisesRegex(ValueError, 'deterministic dual-outcome projection'):
            catalog.discover(self.root)

    def test_stale_reproduction_and_cross_task_descriptor_refuse(self):
        registry = self.registry()
        path = self.root / self.row(registry)['paper_outcomes']['reproduction_contract']['path']
        raw = path.read_bytes()
        path.write_bytes(raw + b' ')
        with self.assertRaisesRegex(ValueError, 'pin mismatch'):
            catalog.discover(self.root)
        path.write_bytes(raw)
        self.repin_descriptor(lambda value: value.update(task_id='PAPER-002'))
        with self.assertRaisesRegex(ValueError, 'Invalid paper outcome contracts'):
            catalog.discover(self.root)

    def test_previous_current_archive_is_bound_to_snapshot(self):
        registry = self.registry()
        row = self.row(registry)
        path = row['paper_outcomes']['previous_specification']['path']
        raw = (self.root / path).read_bytes() + b' '
        row['paper_outcomes']['previous_specification'] = self.write(path, raw)
        self.save_registry(registry)
        with self.assertRaisesRegex(ValueError, 'immutable prior registry'):
            catalog.discover(self.root)

    def test_initial_original_cannot_be_rehashed_to_current_dual_projection(self):
        registry = self.registry()
        row = self.row(registry, initial.IDENTIFIER)
        row['original_specification'] = copy.deepcopy(row['specification'])
        self.save_registry(registry)
        with self.assertRaisesRegex(ValueError, 'changed prior original_specification'):
            catalog.discover(self.root)

    def test_rehashed_initial_snapshot_still_must_bind_first_definition(self):
        registry = self.registry()
        current = self.row(registry, initial.IDENTIFIER)
        registration = json.loads(self.original_initial)
        registration['specification'] = copy.deepcopy(current['specification'])
        initial_pin = self.write(initial.REGISTRATION, registration)
        current['specification_revision']['initial_registration'] = initial_pin
        registry['historical_registries'] = [initial_pin if item['path'] == initial.REGISTRATION else item
                                            for item in registry['historical_registries']]
        prior = json.loads((self.root / binding.SNAPSHOT).read_bytes())
        self.row(prior, initial.IDENTIFIER)['specification_revision']['initial_registration'] = initial_pin
        prior['historical_registries'] = [initial_pin if item['path'] == initial.REGISTRATION else item
                                         for item in prior['historical_registries']]
        snapshot_pin = self.write(binding.SNAPSHOT, prior)
        registry['paper_outcomes']['pre_outcomes_registry'] = snapshot_pin
        registry['historical_registries'] = [snapshot_pin if item['path'] == binding.SNAPSHOT else item
                                            for item in registry['historical_registries']]
        self.save_registry(registry)
        with self.assertRaisesRegex(ValueError, 'preserved snapshot'):
            catalog.discover(self.root)

    def test_complete_coverage_missing_neural_and_boolean_count_refuse(self):
        original = self.registry()
        mutations = [
            lambda value: self.row(value).pop('paper_outcomes'),
            lambda value: value['paper_outcomes'].update(registered_count=True),
            lambda value: self.row(value, 'NEURAL-001').update(paper_outcomes=copy.deepcopy(self.row(value)['paper_outcomes'])),
            lambda value: value.pop('paper_outcomes'),
            lambda value: value['historical_registries'].pop(),
        ]
        for mutate in mutations:
            changed = copy.deepcopy(original)
            mutate(changed)
            self.save_registry(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                catalog.discover(self.root)
        self.save_registry(original)

    def test_sidecar_paths_are_fixed_to_their_current_task(self):
        registry = self.registry()
        self.row(registry)['paper_outcomes']['outcomes']['path'] = 'benchmarks/paper/PAPER-002/outcomes.v1.json'
        self.save_registry(registry)
        with self.assertRaisesRegex(ValueError, 'Invalid paper outcomes pin'):
            catalog.discover(self.root)

    def test_cli_default_contract_and_explicit_outcomes_do_not_execute(self):
        with patch.object(cli, 'read', side_effect=AssertionError('permissive reread')), \
             patch.object(cli.subprocess, 'run', side_effect=AssertionError('unexpected execution')):
            original = cli.paper_contract(self.selected, self.root)
            self.assertEqual(original, cli.paper_contract(self.selected, self.root, outcome='improvement'))
            self.assertEqual(cli.paper_contract(self.selected, self.root, outcome='reproduction'), self.reproduction)
            report = cli.paper_outcomes(self.selected, self.root)
            self.assertEqual(report['summary']['task_count'], 1)
            self.assertEqual(report['summary']['paired_metadata_admitted'], {'reproduction': False, 'improvement': False})
            for argv in (['paper-contract', self.selected, '--outcome', 'reproduction'], ['paper-outcomes', self.selected]):
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(cli.main(argv, root=self.root), 0)

    def test_cli_admits_declared_mismatch_without_scientific_success(self):
        result = copy.deepcopy(self.result)
        result['findings'][0]['value'] = 82.0
        result['findings'][0]['uncertainty']['interval'] = [81.9, 82.1]
        receipt = examples.receipt_for(self.outcomes, result)
        output = io.StringIO()
        with redirect_stdout(output), patch.object(cli.subprocess, 'run', side_effect=AssertionError('unexpected execution')):
            code = cli.main(['check-paper-outcome', self.selected, '--receipt', str(self.receipt_file(receipt))], root=self.root)
        response = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertIs(response['metadata_admitted'], True)
        self.assertIs(response['criterion_satisfied'], False)
        self.assertEqual(response['scientific_outcome'], 'unknown')

    def test_cli_rejects_author_and_historical_roles_without_promotion(self):
        for role in ('author_baseline_calibration', 'historical_attempt', 'software_control'):
            receipt = examples.receipt_for(self.outcomes, self.result)
            receipt['actor_role'] = role
            output = io.StringIO()
            with self.subTest(role=role), redirect_stdout(output):
                code = cli.main(['check-paper-outcome', self.selected, '--receipt', str(self.receipt_file(receipt))], root=self.root)
            response = json.loads(output.getvalue())
            self.assertEqual(code, 2)
            self.assertIsNone(response['criterion_satisfied'])
            self.assertEqual(response['scientific_outcome'], 'unknown')

    def test_receipt_reader_rejects_nonfinite_duplicates_and_oversize(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e9999}', b' ' * (2 * 1024 * 1024 + 1)):
            path = self.receipt_file(raw)
            with self.subTest(size=len(raw)), self.assertRaises(ValueError):
                cli._outcome_receipt(path, engine)

    def test_receipt_reader_rejects_symlinks_and_hardlink_aliases(self):
        target = self.receipt_file()
        linked = self.root / 'linked.json'
        linked.symlink_to(target)
        with self.assertRaises(ValueError):
            cli._outcome_receipt(linked, engine)
        linked.unlink()
        linked.hardlink_to(target)
        for path in (target, linked):
            with self.subTest(path=path.name), self.assertRaises(ValueError):
                cli._outcome_receipt(path, engine)

    def test_receipt_read_is_bounded_and_detects_file_change(self):
        target = self.receipt_file()
        real_open = Path.open
        reads = []

        class Stream:
            def __init__(self, handle, change):
                self.handle, self.change = handle, change

            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.handle.close()
                if self.change:
                    with real_open(target, 'ab') as changed:
                        changed.write(b' ')

            def read(self, size=-1):
                reads.append(size)
                return self.handle.read(size)

        for change in (False, True):
            def tracked(path, *args, **kwargs):
                handle = real_open(path, *args, **kwargs)
                return Stream(handle, change) if path == target else handle
            with patch.object(Path, 'open', tracked):
                if change:
                    with self.assertRaisesRegex(ValueError, 'changed during bounded read'):
                        cli._outcome_receipt(target, engine)
                else:
                    self.assertEqual(cli._outcome_receipt(target, engine)['task_id'], self.selected)
        self.assertEqual(reads, [2 * 1024 * 1024 + 1] * 2)

    def test_catalog_renders_both_outcomes_and_exact_previous_definition(self):
        discovered = catalog.discover(self.root)
        rendered = catalog.render(discovered)
        page = catalog.render_tracks(discovered)['benchmarks/paper/' + initial.IDENTIFIER + '/README.md'].decode()
        self.assertIn('Separate paper outcomes', page)
        self.assertIn('Preserved definition before dual outcomes', page)
        self.assertIn('Initial source-paper task registration (no predecessor)', page)
        self.assertNotIn('historical/task.pre-improvement', page)
        self.assertIn('Reproduction eligibility', rendered['paper.md'].decode())
        paths = set(catalog.source_links(discovered))
        self.assertIn(initial.DIRECTORY + '/' + binding.HISTORY, paths)
        self.assertIn(initial.DIRECTORY + '/reproduction.v1.json', paths)
        self.assertIn(initial.DIRECTORY + '/outcomes.v1.json', paths)

    def test_public_catalog_cannot_gain_receipts_or_scientific_success(self):
        discovered = catalog.discover(self.root)
        self.row(discovered)['paper_outcomes']['cells'][0]['receipt'] = {'metadata_admitted': True}
        with self.assertRaisesRegex(ValueError, 'four unscored outcome conditions'):
            catalog.validate(discovered, self.root)

    def test_unavailable_primary_refuses_before_receipt_or_secondary_reads(self):
        view, _, marker = self.unavailable_view()
        with patch.object(catalog, 'load', return_value={'tasks': [view]}), \
             patch.object(cli, 'public_catalog_module', return_value=catalog), \
             patch.object(cli.subprocess, 'run', side_effect=AssertionError('unexpected execution')):
            report = cli.paper_outcomes(view['id'], self.root)
            self.assertEqual(report['descriptor'], marker)
            self.assertEqual(report['summary']['availability'], 'unavailable')
            self.assertIsNone(report['binding']['reproduction_contract'])
            self.assertTrue(all(cell['scientific_outcome'] == 'unknown' and cell['receipt'] is None
                                and cell['endpoint_eligible'] is False for cell in report['summary']['cells']))
            with patch.object(cli, '_program_pin', side_effect=AssertionError('unexpected secondary read')), \
                 patch.object(cli, '_outcome_receipt', side_effect=AssertionError('unexpected receipt read')):
                for command in (lambda: cli.paper_contract(view['id'], self.root),
                                lambda: cli.compare_paper(view['id'], self.root / 'absent.json', self.root),
                                lambda: cli.check_paper_outcome(view['id'], self.root / 'absent.json', self.root)):
                    with self.assertRaisesRegex(ValueError, 'Current .* admission is unavailable'):
                        command()
                with self.assertRaisesRegex(ValueError, 'No reproduction proposal'):
                    cli.paper_contract(view['id'], self.root, outcome='reproduction')

    def test_unavailable_primary_allows_only_explicit_proposal_inspection(self):
        view, reproduction, _ = self.unavailable_view(proposal=True)
        with patch.object(catalog, 'load', return_value={'tasks': [view]}), \
             patch.object(cli, 'public_catalog_module', return_value=catalog):
            self.assertEqual(cli.paper_contract(view['id'], self.root, outcome='reproduction'), reproduction)
            self.assertEqual(cli.paper_outcomes(view['id'], self.root)['summary']['scientific_outcomes'],
                             {'reproduction': 'unknown', 'improvement': 'unknown'})
            with self.assertRaisesRegex(ValueError, 'Current complete-primary paired-outcome admission is unavailable'):
                cli.check_paper_outcome(view['id'], self.root / 'absent.json', self.root)

    def test_unavailable_primary_render_and_counts_keep_secondary_separate(self):
        discovered = catalog.discover(self.root)
        view, _, _ = self.unavailable_view(proposal=True)
        current = self.row(discovered)
        current.update(view)
        current['task_directory'] = 'benchmarks/paper/' + view['id']
        # The authenticated marker changes only the public outcome view in this
        # rendering fixture; unrelated historical display fields stay intact.
        current['paper_improvement'].update({
            'disposition_reason': 'Generated secondary contract',
            'historical_specification': {'path': current['task_directory'] + '/historical/task.pre-improvement.v1.json'}})
        discovered['paper_outcome_counts'] = catalog.paper_outcome_counts(discovered['tasks'])
        self.assertEqual(discovered['paper_outcome_counts']['primary_unavailable'], 1)
        self.assertEqual(discovered['paper_outcome_counts']['reproduction_eligibility']['unavailable'], 1)
        self.assertEqual(discovered['paper_outcome_counts']['improvement_disposition']['unavailable'], 1)
        count_text = catalog.paper_count_text(discovered)
        self.assertIn('Outcome metadata covers **117/117 paper tasks**', count_text)
        self.assertIn('contract declarations and unavailability records', count_text)
        self.assertIn('completion of both outcomes requires separate qualifying execution evidence', count_text)
        self.assertIn('Complete primary-outcome pairing is unavailable for **1 tasks**', count_text)
        self.assertNotIn('Dual-outcome contracts cover', count_text)
        page = catalog.render_tracks(discovered)[current['task_directory'] + '/README.md'].decode()
        self.assertIn('Current complete-primary paired-outcome admission is unavailable', page)
        self.assertIn('Reproduction proposal (inspection only)', page)
        self.assertIn('Retained secondary improvement policy', page)
        self.assertIn('Primary and retained secondary scope decision', page)
        self.assertNotIn('## Current paper-improvement objective', page)
        self.assertIn(binding.SCOPE_PATH, set(catalog.source_links(discovered)))

    def test_cli_selects_engine_from_bound_reproduction_version(self):
        adapter = catalog.companion_module('paper_outcomes_binding')
        companion = catalog.companion_module
        with patch.object(cli, 'public_catalog_module', return_value=catalog), \
             patch.object(catalog, 'companion_module', side_effect=lambda name: adapter if name == 'paper_outcomes_binding' else companion(name)), \
             patch.object(adapter, 'engine', wraps=adapter.engine) as route:
            cli.paper_outcomes(self.selected, self.root)
        self.assertTrue(any(call.args and call.args[0] == self.reproduction for call in route.call_args_list))
        with self.assertRaisesRegex(ValueError, 'Unsupported reproduction contract version'):
            adapter.engine({'schema_version': 'paper-reproduction/v999'})


if __name__ == '__main__':
    unittest.main()
