"""Real-ledger and adversarial controls for source maintenance, no science runs."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import re
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
