"""Real-ledger and adversarial controls for source maintenance, no science runs."""
import copy
import ast
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('workflow_source_pins', ROOT / 'scripts/maintenance/workflow_source_pins.py')
ci = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ci)


class PinControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = 'benchmarks/neural/NEURAL-001/task.json'
        self.body = b'{"id":"NEURAL-001","track":"neural"}\n'
        self.write(self.source, self.body)
        self.write(ci.CPU_SOURCE, b'import resource\nresource.setrlimit(resource.RLIMIT_CPU, (120, 121))\n')
        self.write('benchmarks/registry.json', ci.encoded({'schema_version': 1, 'kind': 'neuroscience_benchmark_registry', 'tasks': [{'id': 'NEURAL-OTHER'}]}))
        self.make_workflow()

    def write(self, name, body):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)

    def make_workflow(self, *, scalar=False, extra=''):
        pin = {'path': self.source, **ci.identity(self.body)}
        token = repr(pin['sha256']) if scalar else repr(pin)
        body = ('jobs:\n  generated-numerical-regressions:\n    run: |\n'
                '      ulimit -t 121\n      ulimit -S -t 120\n      pin = ' + token + '\n' + extra).encode()
        self.write(ci.CPU_WORKFLOW, body)
        self.ledger = {'schema': 'workflow-source-pins/v1', 'baseline_commit': '0' * 40,
                       'sources': {self.source: {'bytes': len(self.body)}}, 'reviewed_updates': [],
                       'workflows': [{'path': ci.CPU_WORKFLOW, **ci.identity(body),
                                      'occurrences': [{'offset': next(ci.SHA.finditer(body)).start(), 'source': self.source}]}]}
        self.save_ledger()

    def save_ledger(self):
        self.write(ci.LEDGER, ci.encoded(self.ledger))

    def literal_group(self):
        self.source = 'pkg/member.py'
        self.body = b'pass\n'
        self.write(self.source, self.body)
        pin = {'path': self.source, **ci.identity(self.body)}
        extra = ('      rows = [' + repr(pin) + ']\n      packages = [\'pkg\']\n'
                 '      assert len(rows) == 1 > 0\n'
                 "      assert sum(row['bytes'] for row in rows) == 5 <= 33554432\n"
                 "      print({'verified_bytes': 5})\n      PY\n")
        self.make_workflow(extra=extra)
        body = (self.root / ci.CPU_WORKFLOW).read_bytes()
        self.ledger['workflows'][0]['occurrences'] = [{'offset': m.start(), 'source': self.source} for m in ci.SHA.finditer(body)]
        self.save_ledger()

    def mutate_workflow(self, old, new, *, accept_snapshot=False):
        body = (self.root / ci.CPU_WORKFLOW).read_bytes().replace(old, new)
        self.write(ci.CPU_WORKFLOW, body)
        if accept_snapshot:
            self.ledger['workflows'][0].update(ci.identity(body))
            self.save_ledger()

    def change(self, newpath, body):
        self.write(newpath, body)
        return {'schema': 'workflow-pin-changes/v1', 'reason': 'Reviewed fixture source correction',
                'updates': [{'previous': {'path': self.source, **ci.identity(self.body)},
                             'current': {'path': newpath, **ci.identity(body)}}]}

    def register_history(self, newpath):
        old = {'path': self.source, **ci.identity(self.body)}
        previous = {'path': newpath, **ci.identity(self.body)}
        registry = {'schema_version': 1, 'kind': 'neuroscience_benchmark_registry', 'tasks': [
            {'id': 'NEURAL-001', 'original_specification': old,
             'specification_revision': {'version': 'neural-understanding/v1', 'previous_specification': previous}}]}
        self.write('benchmarks/registry.json', ci.encoded(registry))

    def test_real_repository_complete_coverage(self):
        result = ci.audit(ROOT)
        self.assertGreaterEqual(result['source_occurrences'], 839)
        self.assertGreaterEqual(result['complete_literal_package_groups'], 42)
        self.assertFalse(result['benchmark_execution'])

    def test_all_existing_jobs_depend_on_shared_preflight(self):
        for path in sorted((ROOT / '.github/workflows').glob('*.yml')):
            if path.name == 'source-maintenance-preflight.yml':
                continue
            with self.subTest(workflow=path.name):
                jobs = path.read_text().split('\njobs:\n', 1)[1]
                blocks = re.findall(r'^  ([\w-]+):\n(.*?)(?=^  [\w-]+:|\Z)', jobs, re.M | re.S)
                dependencies = {}
                for name, body in blocks:
                    if name == 'source-preflight':
                        self.assertIn('uses: ./.github/workflows/source-maintenance-preflight.yml', body)
                    else:
                        needs = re.search(r'^    needs: ([\w-]+)$', body, re.M)
                        self.assertIsNotNone(needs)
                        dependencies[name] = needs[1]
                for name in dependencies:
                    visited = set()
                    while name != 'source-preflight':
                        self.assertNotIn(name, visited)
                        visited.add(name)
                        name = dependencies[name]

    def test_source_panel_ci_declares_lazy_test_dependencies(self):
        # Inspect imports inside test methods too: a developer interpreter can
        # otherwise hide a missing h5py wheel in the selected CI environment.
        self.assert_ci_dependencies('benchmarks/paper/PAPER-paper-method-013/implementations/source-panel-v1/tests')

    def test_smc_ci_declares_original_evaluator_dependencies(self):
        directory = 'benchmarks/paper/PAPER-SMC-RNN-2024/implementations/source-matched-nlb-v1'
        self.assert_ci_dependencies(directory,
                                    extra_sources=('third_party/nlb_tools_0_0_3/evaluation.py',),
                                    local_modules=('native_guard',))

    def assert_ci_dependencies(self, directory, *, extra_sources=(), local_modules=()):
        sources = sorted((ROOT / directory).glob('test_*.py'))
        self.assertTrue(sources)
        sources.extend(ROOT / directory / name for name in extra_sources)
        for name in local_modules:
            self.assertTrue((ROOT / directory / (name + '.py')).is_file())
        distributions = {'sklearn': 'scikit-learn'}
        required = set()
        for path in sources:
            for node in ast.walk(ast.parse(path.read_text())):
                names = ([item.name for item in node.names] if isinstance(node, ast.Import)
                         else [node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
                required.update(distributions.get(name.split('.')[0], name.split('.')[0]) for name in names
                                if name.split('.')[0] not in sys.stdlib_module_names
                                and name.split('.')[0] not in local_modules)
        jobs = []
        for path in (ROOT / '.github/workflows').glob('*.yml'):
            workflow = path.read_text().split('\njobs:\n', 1)[1]
            for name, body in re.findall(
                    r'^  ([\w-]+):\n(.*?)(?=^  [\w-]+:|\Z)', workflow, re.M | re.S):
                jobs.extend((name, body) for _ in range(
                    self.discovery_enrollment_count(body, directory)))
        self.assertEqual(len(jobs), 1, 'Package needs exactly one generated CI enrollment')
        name, body = jobs[0]
        declared = set(re.findall(r'^\s+([a-zA-Z0-9_-]+)==[^\s]+ --hash=sha256:', body, re.M))
        self.assertTrue(required <= declared,
                        f'{name}: undeclared generated test dependencies: {sorted(required - declared)}')

    @staticmethod
    def discovery_enrollment_count(body, directory):
        """Count exact literal discovery targets in the supported CI forms."""
        count = 0
        for line in body.splitlines():
            line = line.strip()
            # Parse one-line Python calls, not comments, strings or a nearby
            # directory reference. Dynamic and multiline targets fail closed.
            try:
                statement = ast.parse(line)
            except SyntaxError:
                statement = None
            if statement is not None:
                for node in ast.walk(statement):
                    if not (isinstance(node, ast.Call)
                            and isinstance(node.func, ast.Attribute)
                            and node.func.attr == 'discover'
                            and isinstance(node.func.value, ast.Attribute)
                            and node.func.value.attr == 'defaultTestLoader'
                            and isinstance(node.func.value.value, ast.Name)
                            and node.func.value.value.id == 'unittest'):
                        continue
                    target = (node.args[0] if node.args else
                              next((item.value for item in node.keywords
                                    if item.arg == 'start_dir'), None))
                    if isinstance(target, ast.Constant) and target.value == directory:
                        count += 1

            # Preserve the existing timeout/python -m unittest discover form.
            # Only literal start-directory arguments count; shell variables,
            # comments and other commands are not inferred as enrollments.
            try:
                words = shlex.split(line, comments=True)
            except ValueError:
                continue
            if words and words[0] == 'timeout':
                words = words[1:]
                while words and words[0].startswith('--') and '=' in words[0]:
                    words = words[1:]
                if not words or not re.fullmatch(r'\d+(?:\.\d+)?[smhd]?', words[0]):
                    continue
                words = words[1:]
            if not words or not re.fullmatch(r'python(?:3(?:\.\d+)?)?', words[0]):
                continue
            words = words[1:]
            while words and re.fullmatch(r'-[ISB]+', words[0]):
                words = words[1:]
            if words[:3] != ['-m', 'unittest', 'discover']:
                continue
            arguments = words[3:]
            targets = []
            for index, argument in enumerate(arguments):
                if argument in ('-s', '--start-directory') and index + 1 < len(arguments):
                    targets.append(arguments[index + 1])
                elif argument.startswith('--start-directory='):
                    targets.append(argument.split('=', 1)[1])
            if targets == [directory]:
                count += 1
        return count

    def assert_fixture_ci_dependencies(self, bodies, *, declared=True):
        directory = 'generated/package'
        self.write(directory + '/test_dependencies.py',
                   b'def lazy_import():\n    import numpy\n')
        workflow = 'name: generated\njobs:\n'
        for index, body in enumerate(bodies):
            workflow += f'  generated-{index}:\n    steps:\n      - run: |\n'
            if declared:
                workflow += '          numpy==1.0 --hash=sha256:' + '0' * 64 + '\n'
            workflow += ''.join('          ' + line + '\n' for line in body.splitlines())
        self.write(ci.CPU_WORKFLOW, workflow.encode())
        with patch.dict(globals(), {'ROOT': self.root}):
            self.assert_ci_dependencies(directory)

    def test_ci_dependency_selection_requires_enrollment(self):
        with self.assertRaisesRegex(AssertionError, 'exactly one generated CI enrollment'):
            self.assert_fixture_ci_dependencies(['print("no discovery")'])

    def test_ci_dependency_selection_rejects_duplicate_enrollments(self):
        call = "suite = unittest.defaultTestLoader.discover('generated/package', pattern='test_*.py')"
        for bodies in ([call + '\n' + call], [call, call]):
            with self.subTest(jobs=len(bodies)):
                with self.assertRaisesRegex(AssertionError, 'exactly one generated CI enrollment'):
                    self.assert_fixture_ci_dependencies(bodies)

    def test_ci_dependency_selection_accepts_exact_python(self):
        call = "suite = unittest.defaultTestLoader.discover('generated/package', pattern='test_*.py')"
        self.assert_fixture_ci_dependencies([call])
        with self.assertRaisesRegex(AssertionError, 'undeclared generated test dependencies'):
            self.assert_fixture_ci_dependencies([call], declared=False)

    def test_ci_dependency_selection_accepts_exact_shell(self):
        call = ("timeout --signal=TERM --kill-after=5s 120s python -I -B "
                "-m unittest discover -s 'generated/package' -p 'test_*.py' -v")
        self.assert_fixture_ci_dependencies([call])

    def test_ci_dependency_selection_rejects_descendant(self):
        for call in (
                "suite = unittest.defaultTestLoader.discover('generated/package/dependency-builders/antlr', pattern='test_*.py')",
                "python -I -S -B -m unittest discover -s 'generated/package/child' -p 'test_*.py'"):
            with self.subTest(call=call):
                with self.assertRaisesRegex(AssertionError, 'exactly one generated CI enrollment'):
                    self.assert_fixture_ci_dependencies([call])

    def test_ci_dependency_selection_ignores_unrelated_references(self):
        unrelated = (
            "source_pin = {'path': 'generated/package/dependency-builders/antlr/test_build_antlr.py'}\n"
            "directory = 'somewhere/else'\n"
            "suite = unittest.defaultTestLoader.discover(directory, pattern='test_*.py')\n"
            "other = unittest.defaultTestLoader.discover('somewhere/else', pattern='test_*.py')\n"
            "# unittest.defaultTestLoader.discover('generated/package')\n"
            'quoted = "unittest.defaultTestLoader.discover(\'generated/package\')"\n'
            'python -I -B -m unittest discover -s "$directory" -p "test_*.py"')
        with self.assertRaisesRegex(AssertionError, 'exactly one generated CI enrollment'):
            self.assert_fixture_ci_dependencies([unrelated])
        exact = "suite = unittest.defaultTestLoader.discover('generated/package', pattern='test_*.py')"
        self.assert_fixture_ci_dependencies([exact, unrelated])

    def test_fixture_passes(self):
        self.assertEqual(ci.audit(self.root)['source_files'], 1)

    def test_stale_source_bytes_fail(self):
        self.write(self.source, self.body.replace(b'001', b'002'))
        with self.assertRaisesRegex(ci.InvalidSource, 'hash or length'):
            ci.audit(self.root)

    def test_changed_workflow_fails_before_index_reuse(self):
        self.mutate_workflow(b'pin =', b'changed =')
        with self.assertRaisesRegex(ci.InvalidSource, 'hash or length'):
            ci.audit(self.root)

    def test_unclassified_occurrence_fails_even_with_new_snapshot(self):
        self.mutate_workflow(b'pin =', b"extra = '" + b'1' * 64 + b"'\n      pin =", accept_snapshot=True)
        with self.assertRaisesRegex(ci.InvalidSource, 'occurrence coverage'):
            ci.audit(self.root)

    def test_cannot_label_local_pin_external(self):
        self.ledger['workflows'][0]['occurrences'][0] = {'offset': self.ledger['workflows'][0]['occurrences'][0]['offset'], 'external': 'pypi-wheel'}
        self.save_ledger()
        with self.assertRaisesRegex(ci.InvalidSource, 'explicit pip'):
            ci.audit(self.root)

    def test_symlink_rejected(self):
        target = self.root / self.source
        target.unlink()
        target.symlink_to(self.root / ci.CPU_SOURCE)
        with self.assertRaisesRegex(ci.InvalidSource, 'Symlink'):
            ci.audit(self.root)

    def test_hardlink_rejected(self):
        os.link(self.root / self.source, self.root / 'alias')
        with self.assertRaisesRegex(ci.InvalidSource, 'Single-link'):
            ci.audit(self.root)

    def test_old_parent_cpu_limits_fail(self):
        self.mutate_workflow(b'ulimit -t 121\n      ulimit -S -t 120', b'ulimit -t 120', accept_snapshot=True)
        row = self.ledger['workflows'][0]
        row['occurrences'][0]['offset'] = next(ci.SHA.finditer((self.root / ci.CPU_WORKFLOW).read_bytes())).start()
        self.save_ledger()
        with self.assertRaisesRegex(ci.InvalidSource, 'cannot admit'):
            ci.audit(self.root)

    def test_history_redirect_preserves_hash_and_unrelated_current_reader(self):
        self.make_workflow(extra='      current_reader = ' + repr(self.source) + '\n')
        history = 'benchmarks/neural/NEURAL-001/historical/task.pre-understanding.v1.json'
        self.register_history(history)
        changes = self.change(history, self.body)
        ledger, bodies = ci.propose(self.root, changes)
        self.assertIn(('current_reader = ' + repr(self.source)).encode(), bodies[ci.CPU_WORKFLOW])
        self.assertIn(history, ledger['sources'])
        self.assertEqual(next(ci.SHA.finditer(bodies[ci.CPU_WORKFLOW])).group().decode(), ci.identity(self.body)['sha256'])

    def test_arbitrary_history_destination_fails(self):
        history = 'benchmarks/neural/NEURAL-001/historical/arbitrary.json'
        self.register_history(history)
        with self.assertRaisesRegex(ci.InvalidSource, 'Unrecognized historical'):
            ci.propose(self.root, self.change(history, self.body))

    def test_history_requires_registered_original(self):
        history = 'benchmarks/neural/NEURAL-001/historical/task.pre-understanding.v1.json'
        with self.assertRaisesRegex(ci.InvalidSource, 'Unregistered historical'):
            ci.propose(self.root, self.change(history, self.body))

    def test_canonical_task_cannot_be_rehashed(self):
        with self.assertRaisesRegex(ci.InvalidSource, 'historical redirect'):
            ci.propose(self.root, self.change(self.source, self.body.replace(b'001', b'002')))

    def test_explicit_same_size_scalar_wrapper_update(self):
        self.source = 'tests/wrapper.py'
        self.body = b'pass\n'
        self.write(self.source, self.body)
        self.make_workflow(scalar=True)
        changes = self.change(self.source, b'# ok\n')
        ledger, bodies = ci.propose(self.root, changes)
        self.assertEqual(ledger['reviewed_updates'], [changes])
        self.assertIn(ci.identity(b'# ok\n')['sha256'].encode(), bodies[ci.CPU_WORKFLOW])

    def test_scalar_size_change_needs_manual_review(self):
        self.source = 'tests/wrapper.py'
        self.body = b'pass\n'
        self.write(self.source, self.body)
        self.make_workflow(scalar=True)
        with self.assertRaisesRegex(ci.InvalidSource, 'non-dictionary'):
            ci.propose(self.root, self.change(self.source, b'pass # longer\n'))

    def test_digest_only_cli_flag_accepts_changed_descriptor_size(self):
        self.source = 'pkg/SOURCE.json'
        self.body = b'{}\n'
        self.write(self.source, self.body)
        self.make_workflow(scalar=True)
        self.mutate_workflow(b'pin = ', b'verify --expected-sha256 ', accept_snapshot=True)
        body = (self.root / ci.CPU_WORKFLOW).read_bytes()
        self.ledger['workflows'][0]['occurrences'][0]['offset'] = next(ci.SHA.finditer(body)).start()
        self.save_ledger()
        ledger, bodies = ci.propose(self.root, self.change(self.source, b'{"reviewed": true}\n'))
        self.assertEqual(ci.audit(self.root, ledger=ledger, bodies=bodies)['source_bytes'], 19)

    def test_stale_explicit_previous_identity_fails(self):
        changes = self.change(self.source, self.body)
        changes['updates'][0]['previous']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ci.InvalidSource, 'Stale or unbound'):
            ci.propose(self.root, changes)

    def test_complete_namespace_rejects_extra_member(self):
        self.literal_group()
        self.write('pkg/extra.py', b'# extra\n')
        with self.assertRaisesRegex(ci.InvalidSource, 'namespace mismatch'):
            ci.audit(self.root)

    def test_stale_aggregate_is_rejected(self):
        self.literal_group()
        self.mutate_workflow(b'verified_bytes\': 5', b'verified_bytes\': 6', accept_snapshot=True)
        with self.assertRaisesRegex(ci.InvalidSource, 'byte total is stale'):
            ci.audit(self.root)

    def test_dictionary_update_preserves_aggregate_guards(self):
        self.literal_group()
        ledger, bodies = ci.propose(self.root, self.change(self.source, b'pass # extended\n'))
        self.assertIn(b'verified_bytes\': 16', bodies[ci.CPU_WORKFLOW])
        self.assertEqual(ci.audit(self.root, ledger=ledger, bodies=bodies)['source_bytes'], 16)

    def test_invalid_provenance_schema_rejected(self):
        for field, value in [('baseline_commit', 'erased'), ('reviewed_updates', None)]:
            with self.subTest(field=field):
                ledger = copy.deepcopy(self.ledger)
                ledger[field] = value
                with self.assertRaises(ci.InvalidSource):
                    ci.audit(self.root, ledger=ledger)

    def test_conflicting_update_receipt_rejected(self):
        change = self.change(self.source, self.body)
        change['updates'][0]['current']['sha256'] = '1' * 64
        self.ledger['reviewed_updates'] = [change]
        self.save_ledger()
        with self.assertRaisesRegex(ci.InvalidSource, 'history disagrees'):
            ci.audit(self.root)

    def test_cli_reviewed_plan_apply_and_stale_replay(self):
        self.literal_group()
        changes = self.change(self.source, b'pass # extended\n')
        request, plan, report = (self.root / name for name in ('request.json', 'plan.json', 'report.json'))
        request.write_bytes(ci.encoded(changes))
        with patch.object(ci.sys, 'argv', ['pins', '--root', str(self.root), '--plan', str(request), '--output', str(plan)]):
            ci.main()
        with patch.object(ci.sys, 'argv', ['pins', '--root', str(self.root), '--apply', str(plan), '--output', str(report)]):
            ci.main()
        self.assertEqual(json.loads(report.read_text())['status'], 'passed')
        with patch.object(ci.sys, 'argv', ['pins', '--root', str(self.root), '--apply', str(plan), '--output', str(report)]):
            with self.assertRaises(SystemExit):
                ci.main()


if __name__ == '__main__':
    unittest.main()
