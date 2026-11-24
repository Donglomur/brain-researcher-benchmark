"""Invented full32 delivery controls; no authentic input, model, or host issuer."""
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
TASK = Path(os.environ.get('N092_BASE_TASK', str(HERE.parent.parent)))
SOURCE = TASK / 'implementations/registered-runtime-stable-deviance-v1/programme/source'
sys.path.insert(0, str(HERE))
import observed_text as transport
sys.path.insert(0, str(SOURCE))
import numpy as np
from analysis import reconstruct, numeric_report
from score import evaluate


def fixture():
    metadata, counts, expected = {}, {}, {}
    for number in range(32):
        sid, mouse = str(1000 + number), str(2000 + number)
        expected[sid] = mouse
        units = [str(100 * number + i) for i in range(12)]
        areas = [area for area in transport.AREAS for _ in range(2)]
        states = [('REST', 'LOW'), ('RUN', 'LOW'), ('REST', 'HIGH'), ('RUN', 'HIGH')]
        rows = []
        for i, phase in enumerate(('FIT', 'VALIDATION', 'QUERY', 'QUERY', 'QUERY', 'QUERY')):
            run, pupil = states[(i - 2) % 4]
            rows.append({'id': 'drifting_gratings:' + str(i), 'onset': 10.0 * i,
                         'condition_key': 'same exact stimulus',
                         'block': {'FIT': 2, 'VALIDATION': 5, 'QUERY': 7}[phase],
                         'run_bin': run, 'pupil_bin': pupil if number < 26 else 'MISSING',
                         'split': phase})
        baseline = [math.nextafter(3.0, math.inf)] * len(units)
        metadata[sid] = {
            'schema': 'neuropixels_session_v1', 'task_id': 'NEURAL-092',
            'session_id': sid, 'mouse_id': mouse, 'unit_ids': units, 'areas': areas,
            'baseline_rates': baseline, 'exposure_seconds': 1.9, 'rows': rows,
            'support': {'invented': True}, 'state_policy': {'source': 'FIT only'},
            'unit_metadata': [{'unit_id': uid, 'area': area, 'FITbaseline': baseline[i],
                               'presence_ratio': .99, 'isi_violations': .1,
                               'amplitude_cutoff': .05}
                              for i, (uid, area) in enumerate(zip(units, areas))]}
        counts[sid] = [[(q + 1) * (i % 5 + 1) + number % 3 for i in range(12)]
                       for q in range(4)]
    return metadata, counts, expected


def render(metadata, counts, expected, **kwargs):
    bounds = {'max_page_bytes': 4096, 'max_total_bytes': 1000000, 'count_chunk_units': 5}
    bounds.update(kwargs)
    return transport.render_panel(metadata, counts, expected, **bounds)


def independent_roundtrip(delivery):
    """Program arm reads only exactly the text bytes available to direct arm."""
    metadata, counts = {}, {}
    for page in delivery.pages:
        for raw in page.splitlines():
            value = json.loads(raw)
            kind = value['kind']
            if kind == 'protocol':
                continue
            sid = value['session_id']
            if kind == 'session':
                metadata[sid] = value['metadata']
                for key in ('unit_ids', 'areas', 'baseline_rates', 'unit_metadata', 'rows'):
                    metadata[sid][key] = []
                counts[sid] = []
            elif kind == 'unit':
                assert value['index'] == len(metadata[sid]['unit_ids'])
                for key, field in [('unit_ids', 'unit_id'), ('areas', 'area'),
                                   ('baseline_rates', 'baseline_rate'),
                                   ('unit_metadata', 'unit_metadata')]:
                    metadata[sid][key].append(value[field])
            elif kind == 'trial':
                assert value['index'] == len(metadata[sid]['rows'])
                metadata[sid]['rows'].append(value['row'])
            elif kind == 'counts':
                query = [r for r in metadata[sid]['rows'] if r['split'] == 'QUERY']
                index = value['query_index']
                assert value['query_id'] == query[index]['id']
                if index == len(counts[sid]):
                    counts[sid].append([])
                start = value['unit_start']
                assert start == len(counts[sid][index])
                assert value['unit_ids'] == metadata[sid]['unit_ids'][start:start + len(value['counts'])]
                counts[sid][index].extend(value['counts'])
            else:
                raise AssertionError('unexpected observation field')
    return metadata, counts


def answers(metadata, counts):
    return {sid: numeric_report(reconstruct(meta, np.array(counts[sid], dtype=np.int64)))
            for sid, meta in metadata.items()}


def response(delivery, values, arm='restricted_observation'):
    return transport.encode({'arm': arm,
                             'observation_sha256': json.loads(delivery.manifest)['observation_sha256'],
                             'sessions': values})


class ObservedDelivery(unittest.TestCase):
    def setUp(self):
        self.metadata, self.counts, self.expected = fixture()

    def test_full_panel_lossless_text_with_original_units_counts_and_float_precision(self):
        delivery = render(self.metadata, self.counts, self.expected)
        restored, counts = independent_roundtrip(delivery)
        self.assertEqual(restored, self.metadata)
        self.assertEqual(counts, self.counts)
        manifest = json.loads(delivery.manifest)
        self.assertEqual(len(manifest['sessions']), 32)
        self.assertEqual(sum(s['count_cells'] for s in manifest['sessions']), 32 * 4 * 12)
        self.assertTrue(all(len(page) <= 4096 for page in delivery.pages))
        self.assertLessEqual(sum(map(len, delivery.pages)) + len(delivery.manifest), 1000000)
        self.assertFalse(manifest['host_barrier_or_no_tools_enforced'])

    def test_actual_original_reconstruction_and_full32_scorer_unchanged_after_transport(self):
        delivery = render(self.metadata, self.counts, self.expected)
        restored, counts = independent_roundtrip(delivery)
        original_answers = answers(self.metadata, self.counts)
        text_answers = answers(restored, counts)
        self.assertEqual(original_answers, text_answers)
        emitted = []
        for arm in transport.ARMS:
            submission, receipt = transport.collect_responses(
                delivery, arm, response(delivery, text_answers, arm), max_response_bytes=1000000)
            self.assertEqual(receipt['endpoint'], 'later_observed_reconstruction')
            self.assertFalse(receipt['score_computed'])
            emitted.append(submission)
        self.assertEqual(*emitted)
        accepted = json.loads(emitted[0])
        observed = []
        def load(sid):
            observed.append(sid)
            return np.array(self.counts[sid], dtype=np.int64)
        scored = evaluate(accepted['sessions'], self.metadata, load)
        self.assertEqual(observed, list(self.expected))
        self.assertLess(scored['primary_running_reconstruction_error']['primary_mean_absolute_error']['value'], 1e-14)
        self.assertEqual(scored['separate_pupil_reconstruction_error']['primary_mean_absolute_error']['status'],
                         'undefined_required_session')
        self.assertFalse(scored['scientific_or_runtime_qualification'])

    def test_changed_observed_counts_change_text_and_original_required_answer(self):
        first = render(self.metadata, self.counts, self.expected)
        original = answers(self.metadata, self.counts)
        self.counts['1000'][1][0] += 5
        second = render(self.metadata, self.counts, self.expected)
        self.assertNotEqual(json.loads(first.manifest)['observation_sha256'],
                            json.loads(second.manifest)['observation_sha256'])
        self.assertNotEqual(original['1000'], answers(self.metadata, self.counts)['1000'])

    def test_missing_last_session_or_replaced_mouse_rejected(self):
        self.counts.pop('1031')
        with self.assertRaises(ValueError):
            render(self.metadata, self.counts, self.expected)
        self.metadata, self.counts, self.expected = fixture()
        self.metadata['1031']['mouse_id'] = 'wrong'
        with self.assertRaises(ValueError):
            render(self.metadata, self.counts, self.expected)

    def test_final_count_cell_and_unit_axis_fail_without_partial_delivery(self):
        self.counts['1031'][-1].pop()
        with self.assertRaises(ValueError):
            render(self.metadata, self.counts, self.expected)
        self.metadata, self.counts, self.expected = fixture()
        self.metadata['1031']['unit_metadata'][-1]['unit_id'] = 'wrong'
        with self.assertRaises(ValueError):
            render(self.metadata, self.counts, self.expected)

    def test_noninteger_and_out_of_domain_count_rejected(self):
        for bad in (True, 1.0, -1, 2**63):
            with self.subTest(bad=bad):
                self.counts['1000'][0][0] = bad
                with self.assertRaises(ValueError):
                    render(self.metadata, self.counts, self.expected)

    def test_selected_capacity_refuses_instead_of_truncating(self):
        with self.assertRaises(ValueError):
            render(self.metadata, self.counts, self.expected, max_page_bytes=100)
        delivery = render(self.metadata, self.counts, self.expected)
        text_bytes = sum(map(len, delivery.pages))
        with self.assertRaisesRegex(ValueError, 'manifest plus'):
            render(self.metadata, self.counts, self.expected, max_total_bytes=text_bytes)

    def test_complete_response_admission_retains_nulls_and_rejects_missing_axes(self):
        delivery = render(self.metadata, self.counts, self.expected)
        values = answers(self.metadata, self.counts)
        self.assertTrue(all(v is None for v in values['1031']['pupil']['areas'].values()))
        variants = []
        missing = copy.deepcopy(values); missing.pop('1031'); variants.append(missing)
        missing = copy.deepcopy(values); missing['1031'].pop('pupil'); variants.append(missing)
        missing = copy.deepcopy(values); missing['1031']['running']['matched'].pop(transport.PAIRS[-1]); variants.append(missing)
        for incomplete in variants:
            with self.assertRaises(ValueError):
                transport.collect_responses(delivery, 'restricted_observation',
                                            response(delivery, incomplete), max_response_bytes=1000000)

    def test_changed_page_wrong_observation_wrong_arm_and_oversize_response_refused(self):
        delivery = render(self.metadata, self.counts, self.expected)
        raw = response(delivery, answers(self.metadata, self.counts))
        corrupted = transport.Delivery(delivery.manifest, (delivery.pages[0] + b' ',) + delivery.pages[1:])
        with self.assertRaises(ValueError):
            transport.collect_responses(corrupted, 'restricted_observation', raw, max_response_bytes=1000000)
        with self.assertRaises(ValueError):
            transport.collect_responses(delivery, 'program_from_text', raw, max_response_bytes=1000000)
        with self.assertRaises(ValueError):
            transport.collect_responses(delivery, 'restricted_observation', raw, max_response_bytes=len(raw) - 1)
        value = json.loads(raw); value['observation_sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            transport.collect_responses(delivery, 'restricted_observation', transport.encode(value), max_response_bytes=1000000)

    def test_json_duplicates_nonfinite_numbers_and_boolean_answers_refused(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}'):
            with self.assertRaises(ValueError):
                transport.decode(raw)
        delivery = render(self.metadata, self.counts, self.expected)
        values = answers(self.metadata, self.counts)
        values['1031']['running']['areas']['VISp'] = True
        with self.assertRaises(ValueError):
            transport.collect_responses(delivery, 'restricted_observation', response(delivery, values),
                                        max_response_bytes=1000000)

    def test_original_source_dependency_hashes_remain_exact(self):
        bindings = json.loads((HERE / 'SOURCE_BINDINGS.json').read_text())
        for item in bindings['original_dependencies']:
            raw = (TASK / item['task_relative_path']).read_bytes()
            self.assertEqual(len(raw), item['bytes'])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), item['sha256'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
