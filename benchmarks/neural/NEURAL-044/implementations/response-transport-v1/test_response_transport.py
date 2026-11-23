"""Generated protocol/lifecycle controls; no real recordings or model fitting."""
import copy
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'registered-runtime' / 'source'
sys.path.insert(0, str(SOURCE))
from alm.contracts import Refusal
from alm.response_comparison_v2 import SCHEMA, FEATURES, RECIPE, UNITS
from alm import response_transport_v1 as transport

LIMITS = dict(wall_seconds=3, cpu_seconds=3, memory_bytes=2**26,
              output_bytes=8192, model_calls=1, model_tokens=1)
COMMITMENT = 'd' * 64


def packet():
    return {'task': 'NEURAL-044', 'case_id': 'a' * 64,
        'training_features': [[0.0] * 8, [1.0] * 8, [2.0] * 8],
        'training_responses': [0.0, 1.0, 2.0],
        'query_features': [[3.0] * 8, [4.0] * 8],
        'ids': ['1' * 64, '2' * 64],
        'training_unit_ids': ['e' * 64, 'f' * 64, 'e' * 64],
        'prohibited_inputs': ['held_mouse_response', 'held_mouse_stimulation_signals'],
        'claim': 'held_mouse_response_prediction', 'comparison_schema': SCHEMA,
        'feature_names': FEATURES.copy(), 'response_units': UNITS,
        'source_digest': 'b' * 64, 'disposition_digest': 'c' * 64,
        'reference_recipe': copy.deepcopy(RECIPE)}


def answer(public, digest):
    return {'schema': transport.TRANSPORT_SCHEMA, 'packet_digest': digest,
            'case_id': public['case_id'], 'ids': public['ids'], 'responses': [0.0, 1.0]}


GOOD_CHILD = """
import json,sys
r=json.load(sys.stdin)
p=r['public_packet']
assert set(p)=={'task','case_id','training_features','training_responses','query_features',
 'ids','training_unit_ids','prohibited_inputs','claim','comparison_schema','feature_names',
 'response_units','source_digest','disposition_digest','reference_recipe'}
assert 'private' not in r and 'cohort' not in r and 'other_cases' not in r
print(json.dumps({'schema':r['schema'],'packet_digest':r['packet_digest'],
 'case_id':p['case_id'],'ids':p['ids'],'responses':[0.0]*len(p['ids'])}))
"""


class ProtocolTests(unittest.TestCase):
    def test_same_packet_identity_for_both_arms(self):
        p = packet()
        fixed, digest1 = transport.make_request(p, 'frozen_program', LIMITS, COMMITMENT, 8192)
        adaptive, digest2 = transport.make_request(p, 'case_adaptive', LIMITS, COMMITMENT, 8192)
        a, b = json.loads(fixed), json.loads(adaptive)
        self.assertEqual(digest1, digest2)
        self.assertEqual(a['public_packet'], b['public_packet'])
        self.assertEqual(a['limits'], b['limits'])
        self.assertEqual(len(a['public_packet']['ids']), 2)
        self.assertNotEqual(a['arm'], b['arm'])

    def test_private_extra_fields_and_invalid_public_inputs_refuse_before_launch(self):
        mutations = [
            lambda p: p.update(responses=[99, 99]),
            lambda p: p.update(source_ids=['mouse-name']),
            lambda p: p.update(private={'responses': [99, 99]}),
            lambda p: p.update(ids=['1' * 64, '1' * 64]),
            lambda p: p.update(training_unit_ids=['e' * 64] * 3),
            lambda p: p['training_features'][0].__setitem__(0, True),
            lambda p: p['query_features'][0].__setitem__(0, float('nan')),
            lambda p: p['training_responses'].__setitem__(0, 10**400),
            lambda p: p.update(query_features=[[0.0] * 7, [0.0] * 7]),
            lambda p: p.update(reference_recipe={**RECIPE, 'alpha': 2}),
            lambda p: p.update(response_units='arbitrary'),
        ]
        for change in mutations:
            with self.subTest(index=mutations.index(change)):
                p = packet(); change(p)
                with patch.object(transport.subprocess, 'Popen') as launch:
                    with self.assertRaises(Refusal):
                        transport.run_case(p, 'frozen_program', LIMITS, COMMITMENT,
                            [sys.executable, '-c', 'pass'], Path.cwd(), max_input_bytes=8192)
                    launch.assert_not_called()

    def test_output_vector_case_and_packet_bindings(self):
        p = packet(); pin = transport.validate_public(p)
        good = answer(p, pin)
        submission = transport.parse_answer(json.dumps(good).encode() + b'\n', p, pin)
        self.assertEqual(set(submission), {'case_id', 'ids', 'responses'})
        mutations = [lambda a: a.update(packet_digest='0'*64),
            lambda a: a.update(case_id='0'*64), lambda a: a.update(ids=a['ids'][::-1]),
            lambda a: a.update(responses=[0.0]), lambda a: a.update(responses=[True, 0.0]),
            lambda a: a.update(responses=[float('nan'), 0.0]),
            lambda a: a.update(extra='unused')]
        for change in mutations:
            with self.subTest(index=mutations.index(change)):
                value = copy.deepcopy(good); change(value)
                with self.assertRaises(Refusal):
                    transport.parse_answer(json.dumps(value).encode() + b'\n', p, pin)

    def test_json_duplicate_keys_trailing_output_and_invalid_utf8(self):
        p = packet(); pin = transport.validate_public(p)
        good = json.dumps(answer(p, pin)).encode()
        for raw in (good, good+b'\n\n', good+b'\n'+good+b'\n',
                    b'{"schema":1,"schema":2}\n', b'\xff\n'):
            with self.subTest(raw=raw[:30]), self.assertRaises(Refusal):
                transport.parse_answer(raw, p, pin)

    def test_input_cap_and_limits(self):
        for limits, cap in ((LIMITS, 1), ({**LIMITS, 'output_bytes': True}, 8192),
                            ({**LIMITS, 'other': 1}, 8192)):
            with self.assertRaises(Refusal):
                transport.make_request(packet(), 'frozen_program', limits, COMMITMENT, cap)


class ProcessTests(unittest.TestCase):
    def invoke(self, code, limits=None, **options):
        return transport.run_case(packet(), 'frozen_program', limits or LIMITS,
            COMMITMENT, [sys.executable, '-I', '-S', '-B', '-c', code], Path.cwd(),
            max_input_bytes=8192, **options)

    def test_one_fresh_process_per_exchange_with_no_readiness_claim(self):
        first = self.invoke(GOOD_CHILD)
        second = self.invoke(GOOD_CHILD)
        self.assertNotEqual(first['receipt']['participant_pid'], second['receipt']['participant_pid'])
        self.assertEqual(first['submission']['responses'], [0.0, 0.0])
        self.assertFalse(first['receipt']['provider_verified'])
        self.assertFalse(first['receipt']['scientific_qualification'])
        self.assertEqual(first['receipt']['participant_exit_code'], 0)
        self.assertGreater(first['receipt']['input_bytes'], 0)

    def test_valid_prefix_from_failed_child_is_not_accepted(self):
        with self.assertRaisesRegex(Refusal, 'completed full exchange'):
            self.invoke(GOOD_CHILD + '\nraise SystemExit(7)\n')

    def test_stdout_and_stderr_are_bounded(self):
        with self.assertRaisesRegex(Refusal, 'total output cap'):
            self.invoke("import sys;sys.stdin.read();sys.stdout.write('x'*100000)")
        with self.assertRaisesRegex(Refusal, 'stderr cap'):
            self.invoke("import sys;sys.stdin.read();sys.stderr.write('x'*65)", stderr_limit=64)

    def test_deadline_retires_owned_child(self):
        created = []; original = subprocess.Popen
        def launch(*args, **kwargs):
            proc = original(*args, **kwargs); created.append(proc); return proc
        before = time.monotonic()
        with patch.object(transport.subprocess, 'Popen', side_effect=launch):
            with self.assertRaisesRegex(Refusal, 'wall deadline'):
                self.invoke('import sys,time;sys.stdin.read();time.sleep(10)',
                            {**LIMITS, 'wall_seconds': 1})
        self.assertIsNotNone(created[0].poll())
        self.assertLess(time.monotonic() - before, 2.5)

    def test_catchable_interrupt_retires_child_and_restores_handlers(self):
        created = []; original = subprocess.Popen
        old = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
        def launch(*args, **kwargs):
            proc = original(*args, **kwargs); created.append(proc); return proc
        with patch.object(transport.subprocess, 'Popen', side_effect=launch):
            with self.assertRaisesRegex(Refusal, 'interrupted by signal'):
                self.invoke('import sys,os,signal,time;sys.stdin.read();'
                            'os.kill(os.getppid(),signal.SIGTERM);time.sleep(10)')
        self.assertIsNotNone(created[0].poll())
        self.assertEqual(old, {s: signal.getsignal(s) for s in old})

    def test_signal_during_acquisition_cannot_escape_child_ownership(self):
        created = []; original = subprocess.Popen
        def launch(*args, **kwargs):
            proc = original(*args, **kwargs); created.append(proc)
            os.kill(os.getpid(), signal.SIGTERM)
            return proc
        with patch.object(transport.subprocess, 'Popen', side_effect=launch):
            with self.assertRaisesRegex(Refusal, 'launch interrupted'):
                self.invoke('import time;time.sleep(10)')
        self.assertIsNotNone(created[0].poll())


class AmendmentTests(unittest.TestCase):
    def test_detached_snapshot_survives_postvalidation_caller_mutation(self):
        public = packet()
        original = transport.validate_public
        def validate_then_mutate(snapshot):
            pin = original(snapshot)
            public['private'] = {'responses': [999, 999]}
            public['training_features'][0][0] = 999.0
            return pin
        with patch.object(transport, 'validate_public', side_effect=validate_then_mutate):
            raw, pin = transport.make_request(public, 'frozen_program', LIMITS, COMMITMENT, 8192)
        sent = json.loads(raw)['public_packet']
        self.assertNotIn('private', sent)
        self.assertEqual(sent['training_features'][0][0], 0.0)
        self.assertEqual(pin, transport.digest(sent))
        self.assertEqual(pin, original(sent))

    def test_fixed_recipe_rejects_boolean_numeric_type_substitution(self):
        for key, value in [('alpha', True), ('fit_intercept', 1),
                           ('minimum_eligible_mice', 3.0)]:
            with self.subTest(key=key):
                public = packet()
                public['reference_recipe'][key] = value
                with self.assertRaisesRegex(Refusal, 'type-sensitive recipe'):
                    transport.make_request(public, 'frozen_program', LIMITS, COMMITMENT, 8192)

    def test_late_answer_validation_refuses_and_retires_owned_child(self):
        created = []; original_launch = subprocess.Popen
        original_parse = transport.parse_answer
        def launch(*args, **kwargs):
            proc = original_launch(*args, **kwargs); created.append(proc); return proc
        def delayed_validation(*args):
            answer = original_parse(*args)
            time.sleep(1.05)
            return answer
        with patch.object(transport.subprocess, 'Popen', side_effect=launch), \
             patch.object(transport, 'parse_answer', side_effect=delayed_validation):
            with self.assertRaisesRegex(Refusal, 'answer validation deadline'):
                transport.run_case(packet(), 'frozen_program', {**LIMITS, 'wall_seconds': 1},
                    COMMITMENT, [sys.executable, '-I', '-S', '-B', '-c', GOOD_CHILD],
                    Path.cwd(), max_input_bytes=8192)
        self.assertIsNotNone(created[0].poll())


class LimitBindingTests(unittest.TestCase):
    def test_postvalidation_caller_mutation_cannot_change_sent_limits(self):
        limits = LIMITS.copy()
        original_limits = limits.copy()
        validate = transport.validate_public
        def validate_then_mutate(public):
            pin = validate(public)
            limits['output_bytes'] = True
            limits['unvalidated_extra'] = 1
            return pin
        with patch.object(transport, 'validate_public', side_effect=validate_then_mutate):
            raw, _ = transport.make_request(packet(), 'frozen_program', limits,
                                             COMMITMENT, 8192)
        self.assertEqual(json.loads(raw)['limits'], original_limits)

    def test_output_cap_uses_delivered_limits_after_caller_mutation(self):
        limits = {**LIMITS, 'output_bytes': 512}
        make_request = transport.make_request
        def request_then_mutate(*args, **kwargs):
            result = make_request(*args, **kwargs)
            limits['output_bytes'] = 8192
            return result
        # Leading JSON whitespace is valid protocol data, but still consumes the
        # transmitted output cap. The larger caller cap would accept this answer.
        code = "import sys;sys.stdout.write(' '*1024)\n" + GOOD_CHILD
        created = []
        original_launch = subprocess.Popen
        def launch(*args, **kwargs):
            proc = original_launch(*args, **kwargs)
            created.append(proc)
            return proc
        with patch.object(transport, 'make_request', side_effect=request_then_mutate), \
             patch.object(transport.subprocess, 'Popen', side_effect=launch):
            with self.assertRaisesRegex(Refusal, 'total output cap'):
                transport.run_case(packet(), 'frozen_program', limits, COMMITMENT,
                    [sys.executable, '-I', '-S', '-B', '-c', code], Path.cwd(),
                    max_input_bytes=8192, stderr_limit=0)
        self.assertEqual(len(created), 1)
        self.assertIsNotNone(created[0].poll())

    def test_deadline_uses_delivered_limits_before_launch(self):
        limits = {**LIMITS, 'wall_seconds': 1}
        make_request = transport.make_request
        def request_then_mutate(*args, **kwargs):
            result = make_request(*args, **kwargs)
            limits['wall_seconds'] = 3
            return result
        calls = 0
        def clock():
            nonlocal calls
            calls += 1
            return 0.0 if calls == 1 else 1.5
        with patch.object(transport, 'make_request', side_effect=request_then_mutate), \
             patch.object(transport.time, 'monotonic', side_effect=clock), \
             patch.object(transport.subprocess, 'Popen', wraps=subprocess.Popen) as launch:
            with self.assertRaisesRegex(Refusal, 'deadline before participant launch'):
                transport.run_case(packet(), 'frozen_program', limits, COMMITMENT,
                    [sys.executable, '-I', '-S', '-B', '-c', GOOD_CHILD], Path.cwd(),
                    max_input_bytes=8192)
            launch.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
