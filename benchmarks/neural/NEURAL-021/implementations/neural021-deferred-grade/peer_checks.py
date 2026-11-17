"""Independent generated checks; no authentic inputs or runtime qualification.

The author's complete92 fixture supplies invented files and binding overlays.
Independent mutations re-pin the entire affected chain, so semantic refusals
cannot be explained merely by stale content hashes. Production source is frozen.
"""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

HERE = Path(__file__).resolve().parent
Q = HERE
raw = (Q / 'test_grade_completed.py').read_bytes()
spec = importlib.util.spec_from_loader('author_generated_controls', loader=None)
a = importlib.util.module_from_spec(spec)
a.__file__ = str(Q / 'test_grade_completed.py')
exec(compile(raw, a.__file__, 'exec'), a.__dict__)
c, g = a.c, a.g
RESULTS = []
PEAK = 0


def read(path):
    return c.parse(Path(path).read_bytes())


def refresh_outer(request, external):
    data = c.encoded(external)
    assert len(data) <= 8192
    request['external'] = a.row(Path(request['external']['path']), data + b' ' * (8192 - len(data)), raw=True)
    outer = read(request['outer_review']['path'])
    outer['external'] = c.only_pin(request['external'])
    request['outer_review'] = a.row(Path(request['outer_review']['path']), outer)
    refresh_authority(request)


def refresh_authority(request):
    authority = read(request['authority']['path'])
    authority['external'] = c.only_pin(request['external'])
    authority['outer_review'] = c.only_pin(request['outer_review'])
    request['authority'] = a.row(Path(request['authority']['path']), authority)


def refresh_infer(request, mutate_submission=None, mutate_native=None):
    root = Path(read(request['selection']['path'])['output'])
    native = read(root / 'infer/NATIVE.json')
    complete = read(root / 'COMPLETE.json')
    seal = read(root / 'SUBMISSION_COMMITTED.json')
    external = read(request['external']['path'])
    if mutate_submission:
        submission = read(root / 'infer/submission.json')
        mutate_submission(submission)
        pin = a.put(root / 'infer/submission.json', submission)
        native['outputs']['submission.json'] = pin
        complete['outputs']['submission.json'] = pin
        seal['outputs']['submission.json'] = pin
        external['outputs']['submission.json'] = pin
        handoff = read(root / 'GRADE_HANDOFF.json')
        handoff['submission'].update(pin)
        complete['grade_handoff'] = a.put(root / 'GRADE_HANDOFF.json', handoff)
    if mutate_native:
        mutate_native(native)
    native_pin = a.put(root / 'infer/NATIVE.json', native)
    complete['native']['infer'] = native_pin
    seal['infer_native'] = native_pin
    complete['outputs_commitment'] = a.put(root / 'SUBMISSION_COMMITTED.json', seal)
    external['complete'] = a.put(root / 'COMPLETE.json', complete)
    refresh_outer(request, external)


class IndependentChecks(unittest.TestCase):
    def check_refusal(self, label, change, expected):
        global PEAK
        with tempfile.TemporaryDirectory(prefix='neural021-peer-invented-') as directory:
            tmp = Path(directory).resolve()
            request, bodies, target = a.fixture(tmp, 'perfect')
            change(request)
            budget = a.MeteredBudget(target)
            with self.assertRaises(ValueError) as raised:
                g.evaluate(request, a.ADAPTER, c, bodies, a.SCIENCE, budget)
            self.assertIn(expected, str(raised.exception))
            self.assertEqual(budget.observed_target_captures, 0)
            self.assertEqual(budget.target_captures, 0)
            PEAK = max(PEAK, sum(p.stat().st_size for p in tmp.rglob('*') if p.is_file()))
            RESULTS.append(dict(control=label, outcome='refused_before_target', target_captures=0,
                                reason=str(raised.exception), read_reservations=budget.reads))

    def test_final_query_numeric_domain_with_complete_repinned_chain(self):
        def change(request):
            def bad(submission):
                submission['predictions'][-1]['velocity_m_s'][-1][-1] = 1000001
            refresh_infer(request, mutate_submission=bad)
        self.check_refusal('q0091_t29_axis1_out_of_domain', change, 'finite numeric velocities')

    def test_exact_holder_name_with_complete_repinned_chain(self):
        def change(request):
            def bad(native):
                native['closures'][1]['name'] += '-replacement'
            refresh_infer(request, mutate_native=bad)
        self.check_refusal('renamed_infer_holder', change, 'exact three distinct owned resources')

    def test_worker_end_clock_with_repinned_authority(self):
        def change(request):
            external = read(request['external']['path'])
            external['argv'][16] = '1885.0'
            refresh_outer(request, external)
        self.check_refusal('changed_original_worker_end', change, 'clock invocation')

    def test_outer_worker_source_with_repinned_authority(self):
        def change(request):
            outer = read(request['outer_review']['path'])
            outer['worker_source']['sha256'] = 'f' * 64
            request['outer_review'] = a.row(Path(request['outer_review']['path']), outer)
            refresh_authority(request)
        self.check_refusal('outer_review_wrong_worker_source', change, 'independent natural original observer exit')

    def test_existing_output_never_opens_targets(self):
        self.check_refusal('occupied_score_path', lambda request: a.put(Path(request['output']), b'occupied', raw=True),
                           'fresh existing-parent result')

    def test_cli_failed_tiny_read_profile_keeps_bootstrap_cost(self):
        with tempfile.TemporaryDirectory(prefix='neural021-peer-cli-') as directory:
            path = Path(directory).resolve() / 'request.json'
            request = dict(producer_root=str(a.PRODUCER_ROOT), science_root=str(a.SCIENCE_ROOT),
                           limits=dict(a.LIMITS, reads=1))
            pin = a.put(path, request)
            argv = [sys.executable, '-I', '-S', '-B', str(Q / 'grade_completed.py'), 'grade',
                    '--source-sha256', a.ADAPTER['sha256'], '--producer-root', str(a.PRODUCER_ROOT),
                    '--science-root', str(a.SCIENCE_ROOT), '--request', str(path),
                    '--request-bytes', str(pin['bytes']), '--request-sha256', pin['sha256']]
            p = subprocess.run(argv, cwd=tempfile.gettempdir(), capture_output=True, text=True, timeout=20)
            self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
            failure = json.loads(p.stderr)
            self.assertEqual(failure['reason'], 'whole grading read ceiling')
            self.assertGreater(failure['read_reservations'], 1000000)
            self.assertEqual(failure['protected_target_captures'], 0)
            self.assertGreaterEqual(failure['elapsed_seconds'], 0)
            self.assertGreaterEqual(failure['cpu_seconds'], 0)
            self.assertFalse(failure['physical_IO_or_peak_RSS_measured'])
            RESULTS.append(dict(control='cli_invalid_tiny_read_profile', outcome='refused_with_bootstrap_cost',
                                exit_code=p.returncode, failure=failure))


if __name__ == '__main__':
    origin = time.monotonic()
    suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(a.GradeTests),
                               unittest.defaultTestLoader.loadTestsFromTestCase(IndependentChecks)])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps(dict(schema='neural021_peer_generated_controls_v1', methods=result.testsRun,
        failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped), expected_failures=len(result.expectedFailures),
        unexpected_successes=len(result.unexpectedSuccesses), author_methods=5, independent_methods=6,
        independent_controls=RESULTS, seconds=time.monotonic() - origin,
        author_fixture_source_read_bytes=a.SOURCE_READS + len(raw),
        source_counter_excludes_child_CLI_and_independent_generated_reads=True,
        generated_write_bytes=a.GENERATED_WRITES, fixture_peak_logical_bytes=max(PEAK, a.FIXTURE_PEAK),
        authentic_inputs_read=0, native_or_model_calls=0, scientific_qualification=False,
        generated_binding_overlays=True, unchanged_observer_interface_scorer=True,
        physical_IO_and_aggregate_peak_RSS_not_measured=True), sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() and not result.skipped and not result.expectedFailures
                            and not result.unexpectedSuccesses and result.testsRun == 11 else 1)
