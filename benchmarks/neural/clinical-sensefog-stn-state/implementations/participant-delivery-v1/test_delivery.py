"""Generated full-census bridge controls; no clinical inputs or model evaluation."""
import copy
import importlib.util
import math
from pathlib import Path
import unittest


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


d = load('sensefog_delivery', Path(__file__).with_name('sensefog_delivery.py'))
f = load('packet_fixtures', Path(__file__).resolve().parent.parent / 'signal-packets-v1/test_packets.py')


def policy():
    return {'schema': 'sensefog_score_policy_v1', 'task': d.TASK,
            'classes': ['freezing', 'walking'], 'finite_probability_floor': .01,
            'bootstrap_replicates': 20, 'bootstrap_seed': 1}


def make(*, h=6, substrate='original_authorized_support', paired=True, **overrides):
    g, m, a = f.fixture(h=h)
    reader, calls = f.reader_for(g)
    options = dict(substrate=substrate, include_paired=paired, max_cases=12,
                   max_packet_values=100, max_total_values=5000, max_output_bytes=1000000)
    options.update(overrides)
    bundle = d.prepare_delivery(g, policy(), m, a, reader, **options)
    return g, bundle, calls


def responses(bundle):
    return [{'schema': 'sensefog_probability_response_v1',
             'request_token': r['request_token'], 'request_sha256': d.canonical_sha256(r),
             'probabilities': [.75, .25]} for r in bundle['public_requests']]


def collect(bundle, rows=None, digest=None, **kwargs):
    options = dict(expected_delivery_sha256=digest or d.canonical_sha256(bundle), max_output_bytes=1000000)
    options.update(kwargs)
    return d.collect_responses(bundle, responses(bundle) if rows is None else rows, **options)


class DeliveryChecks(unittest.TestCase):
    def test_full_census_roundtrip_into_actual_primary_and_paired_scorer(self):
        grid, bundle, _ = make()
        output = collect(bundle, list(reversed(responses(bundle))))
        self.assertEqual(len(output['predictions']['rows']), 12)
        self.assertEqual(len(output['paired_predictions']['rows']), 24)
        targets = {'schema': 'sensefog_protected_targets_v1', 'task': d.TASK,
                   'grid_sha256': d.canonical_sha256(grid), 'label_protocol_sha256': 'a' * 64,
                   'rows': [{'case_id': 'q%d' % i, 'participant': 'p%d' % i,
                             'status': 'evaluable', 'label': 'freezing'} for i in range(12)]}
        result = d._score.score(grid, policy(), targets, output['predictions'], max_cases=12,
                                paired_predictions=output['paired_predictions'])
        self.assertAlmostEqual(result['primary']['score'], -math.log(.75))
        self.assertEqual(len(result['primary']['participant_folds']), 12)
        self.assertEqual(result['paired_diagnostics']['equal_transform_mean_delta_nats'], 0)
        self.assertEqual(len(result['paired_diagnostics']['transforms']), 20)
        self.assertFalse(output['readiness'])

    def test_public_projection_and_packet_bytes_preserved(self):
        _, bundle, _ = make()
        for request, binding in zip(bundle['public_requests'], bundle['response_bindings']):
            self.assertEqual(set(request), {'schema', 'request_token', 'class_order', 'observation_status', 'observation'})
            for forbidden in ('case_id', 'participant', 'multiple', 'grid_sha256', 'label', 'segment_id'):
                self.assertNotIn('"' + forbidden + '"', d.canonical_bytes(request).decode())
            self.assertEqual(binding['request_sha256'], d.canonical_sha256(request))
            role = 'lag_authorized_support' if binding['kind'] == 'paired' else bundle['substrate']
            row = next(r for r in bundle['private_manifest'] if r['case_id'] == binding['case_id']
                       and r['role'] == role and r['multiple'] == binding['multiple'])
            self.assertEqual(row['packet_sha256'], d.canonical_sha256(request['observation']))
        self.assertEqual(len({r['request_token'] for r in bundle['public_requests']}), 36)

    def test_all_unavailable_history_stays_in_original_census(self):
        _, bundle, _ = make(h=None)
        self.assertEqual(len(bundle['public_requests']), 12)
        self.assertTrue(all(r['observation'] is None and r['observation_status'] == 'unavailable'
                            for r in bundle['public_requests']))
        output = collect(bundle)
        self.assertEqual(len(output['predictions']['rows']), 12)
        self.assertEqual(output['paired_predictions']['rows'], [])
        self.assertEqual(len(bundle['private_manifest']), 264)

    def test_core_only_is_separate_and_cannot_substitute_in_paired_comparison(self):
        _, bundle, _ = make(h=None, substrate='original_core', paired=False)
        self.assertTrue(all(r['observation'] is not None for r in bundle['public_requests']))
        self.assertIsNone(collect(bundle)['paired_predictions'])
        with self.assertRaisesRegex(ValueError, 'same complete-support'):
            make(substrate='original_core', paired=True)

    def test_missing_duplicate_extra_and_unknown_responses_refuse_whole_condition(self):
        _, bundle, _ = make()
        for mutate in (lambda x: x.pop(), lambda x: x.append(copy.deepcopy(x[0])),
                       lambda x: x.__setitem__(1, copy.deepcopy(x[0])),
                       lambda x: x[0].update(request_token='f' * 32)):
            rows = responses(bundle); mutate(rows)
            with self.assertRaises(ValueError): collect(bundle, rows)

    def test_failed_invalid_and_class_order_unbound_outputs_refused(self):
        _, bundle, _ = make()
        for mutate in (lambda r: r.update(probabilities=None),
                       lambda r: r.update(probabilities=[True, 0]),
                       lambda r: r.update(probabilities=[math.nan, 0]),
                       lambda r: r.update(probabilities=[.4, .4]),
                       lambda r: r.update(probabilities=[1]),
                       lambda r: r.update(request_sha256='0' * 64),
                       lambda r: r.update(label='freezing')):
            rows = responses(bundle); mutate(rows[0])
            with self.assertRaises(ValueError): collect(bundle, rows)

    def test_frozen_bundle_refuses_private_swap_packet_and_policy_mutations(self):
        _, bundle, _ = make()
        frozen = d.canonical_sha256(bundle)
        for mutate in (lambda x: x['response_bindings'][0].update(case_id='q1'),
                       lambda x: x['public_requests'][0]['observation']['channels'][0]['values'].__setitem__(0, 0),
                       lambda x: x['policy']['classes'].reverse(),
                       lambda x: x['response_bindings'].pop()):
            changed = copy.deepcopy(bundle); mutate(changed)
            with self.assertRaisesRegex(ValueError, 'frozen delivery changed'):
                collect(changed, responses(bundle), digest=frozen)

    def test_output_caps_refuse_complete_operation(self):
        _, bundle, _ = make()
        with self.assertRaisesRegex(ValueError, 'whole collected output'):
            collect(bundle, max_output_bytes=1)
        with self.assertRaisesRegex(ValueError, 'whole output'):
            make(max_output_bytes=1)
        with self.assertRaises(ValueError): make(max_cases=11)

    def test_callback_cannot_change_frozen_policy(self):
        g, m, a = f.fixture(); pol = policy(); reader, _ = f.reader_for(g)
        def mutate(*args):
            pol['classes'].reverse()
            return reader(*args)
        bundle = d.prepare_delivery(g, pol, m, a, mutate, substrate='original_core',
                                    include_paired=False, max_cases=12, max_packet_values=100,
                                    max_total_values=5000, max_output_bytes=1000000)
        self.assertEqual(bundle['policy']['classes'], ['freezing', 'walking'])


if __name__ == '__main__':
    unittest.main()
