"""Generated software controls; the only source input is public RECORDS metadata."""
import copy
import hashlib
import json
import os
from pathlib import Path
import unittest

import scorer


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def opaque(value):
    return hashlib.sha256(value.encode()).hexdigest()[:24]


class ScientificScorerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = os.environ.get('NEURAL010_RECORDS_FILE')
        if not path:
            raise RuntimeError('Provide pinned public RECORDS metadata through NEURAL010_RECORDS_FILE')
        cls.records = Path(path).read_bytes()
        scorer.source_roster(cls.records)

    def setUp(self):
        rows = []
        for source in self.records.decode('ascii').splitlines():
            folder = source.split('/')[0]
            person = 'chb01' if folder == 'chb21' else folder
            rows.append({'recording_id': opaque(source), 'patient_id': opaque(person),
                         'source_record': source, 'duration_seconds': 1000, 'montage_id': 'a' * 64})
        self.panel = {'schema': 'neural010-scientific-panel-v2', 'records': rows}
        panel_hash = scorer.digest(encoded(self.panel))
        self.streams = {}
        for arm in scorer.ARMS:
            events = [[100, 110]] if arm == 'candidate' else [[500, 510]] if arm == 'signal_reference' else []
            self.streams[arm] = {'schema': 'neural010-scientific-events-v2', 'arm': arm,
                                 'panel_sha256': panel_hash,
                                 'records': [{'recording_id': row['recording_id'], 'events': copy.deepcopy(events)} for row in rows]}
        self.targets = {'schema': 'neural010-scientific-targets-v2', 'panel_sha256': panel_hash,
                        'records': [{'recording_id': row['recording_id'], 'events': [[100, 110]]} for row in rows]}
        self.target_reads = 0

    def operands(self):
        panel = encoded(self.panel)
        streams = {arm: encoded(value) for arm, value in self.streams.items()}
        targets = encoded(self.targets)
        pins = {'panel': scorer.digest(panel), 'targets': scorer.digest(targets),
                **{arm: scorer.digest(raw) for arm, raw in streams.items()}}

        def target_loader():
            self.target_reads += 1
            return targets

        return {'records_bytes': self.records, 'panel_bytes': panel, 'stream_bytes': streams,
                'target_loader': target_loader, 'expected_sha256': pins}

    def rebind_panel(self):
        pin = scorer.digest(encoded(self.panel))
        for value in (*self.streams.values(), self.targets):
            value['panel_sha256'] = pin

    def test_absolute_four_arm_outcomes_and_observed_day_units(self):
        out = scorer.evaluate(**self.operands())
        self.assertEqual(self.target_reads, 1)
        self.assertEqual(out['primary']['mean'], 1)
        self.assertEqual(out['primary']['n'], 23)
        self.assertEqual(out['primary']['standard_error'], 0)
        self.assertEqual(out['observed_seconds'], 686000)
        self.assertEqual(len(out['false_alarm_localization']), 686 * 4)
        for arms in out['patients'].values():
            self.assertEqual(set(arms), set(scorer.ARMS))
            self.assertEqual(arms['candidate']['event_f1'], 1)
            self.assertEqual(arms['matched_no_eeg']['event_f1'], 0)
            self.assertAlmostEqual(arms['signal_reference']['false_alarms_per_24_observed_hours'], 86.4)

    def test_equal_person_macro_not_record_or_folder_weighting(self):
        by_id = {r['recording_id']: r for r in self.panel['records']}
        for arm, person in (('candidate', 'chb01'), ('matched_no_eeg', 'chb02')):
            for row in self.streams[arm]['records']:
                row['events'] = [[100, 110]] if by_id[row['recording_id']]['patient_id'] == opaque(person) else []
        out = scorer.evaluate(**self.operands())
        self.assertEqual(out['primary']['mean'], 0)
        self.assertEqual(out['primary']['positive'], 1)
        self.assertEqual(out['primary']['negative'], 1)
        self.assertEqual(out['primary']['zero'], 21)
        self.assertEqual(out['patients'][opaque('chb01')]['candidate']['observed_seconds'], 75000)
        self.assertEqual(out['patients'][opaque('chb02')]['candidate']['observed_seconds'], 36000)

    def test_negative_contrast_is_valid(self):
        for row in self.streams['candidate']['records']:
            row['events'] = []
        for row in self.streams['matched_no_eeg']['records']:
            row['events'] = [[100, 110]]
        self.assertEqual(scorer.evaluate(**self.operands())['primary']['mean'], -1)

    def test_single_person_montage_retains_undefined_support(self):
        row = self.panel['records'][0]
        row['montage_id'] = 'b' * 64
        self.targets['records'][0]['events'] = []
        for value in self.streams.values():
            value['records'][0]['events'] = []
        self.rebind_panel()
        out = scorer.evaluate(**self.operands())
        cell = out['montages']['b' * 64]
        self.assertTrue(cell['single_patient_support'])
        delta = cell['candidate_minus_comparator']['matched_no_eeg']['event_f1']
        self.assertEqual(delta['n'], 0)
        self.assertIsNone(delta['mean'])
        self.assertEqual(delta['undefined_person_ids'], [row['patient_id']])
        self.assertEqual(out['primary']['n'], 23)

    def test_invalid_streams_never_open_targets(self):
        for arm in scorer.ARMS:
            with self.subTest(arm=arm):
                args = self.operands()
                value = copy.deepcopy(self.streams[arm])
                value['records'].pop()
                args['stream_bytes'][arm] = encoded(value)
                args['expected_sha256'][arm] = scorer.digest(args['stream_bytes'][arm])
                with self.assertRaisesRegex(ValueError, 'all stream records'):
                    scorer.evaluate(**args)
        self.assertEqual(self.target_reads, 0)

    def test_operator_reference_pin_cannot_be_replaced_by_candidate(self):
        args = self.operands()
        altered = copy.deepcopy(self.streams['matched_no_eeg'])
        altered['records'][0]['events'] = [[100, 110]]
        args['stream_bytes']['matched_no_eeg'] = encoded(altered)
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            scorer.evaluate(**args)
        self.assertEqual(self.target_reads, 0)

    def test_wrong_person_alias_and_collapsed_people_rejected(self):
        for corruption in ('alias', 'collapse'):
            original = copy.deepcopy(self.panel)
            with self.subTest(corruption=corruption):
                for row in self.panel['records']:
                    if corruption == 'alias' and row['source_record'].startswith('chb21/'):
                        row['patient_id'] = opaque('chb21')
                    if corruption == 'collapse' and row['source_record'].startswith('chb02/'):
                        row['patient_id'] = opaque('chb01')
                with self.assertRaises(ValueError):
                    scorer.evaluate(**self.operands())
                self.panel = original
        self.assertEqual(self.target_reads, 0)

    def test_substituted_source_record_rejected_despite_matching_count(self):
        self.panel['records'][0]['source_record'] = self.panel['records'][1]['source_record']
        with self.assertRaisesRegex(ValueError, 'source membership'):
            scorer.evaluate(**self.operands())
        self.assertEqual(self.target_reads, 0)

    def test_duplicate_and_nonfinite_json_rejected(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}'):
            with self.assertRaises(ValueError):
                scorer.parse(raw, scorer.digest(raw))

    def test_noncanonical_boolean_and_wrong_arm_streams_rejected(self):
        for events in ([[100, 110], [120, 130]], [[True, 110]]):
            self.streams['candidate']['records'][0]['events'] = events
            with self.assertRaises(ValueError):
                scorer.evaluate(**self.operands())
        self.streams['candidate']['records'][0]['events'] = [[100, 110]]
        self.streams['matched_no_eeg']['arm'] = 'candidate'
        with self.assertRaisesRegex(ValueError, 'arm identity'):
            scorer.evaluate(**self.operands())
        self.assertEqual(self.target_reads, 0)

    def test_missing_person_reference_events_refuses_full_primary(self):
        selected = {r['recording_id'] for r in self.panel['records'] if r['patient_id'] == opaque('chb02')}
        for row in self.targets['records']:
            if row['recording_id'] in selected:
                row['events'] = []
        with self.assertRaisesRegex(ValueError, 'every person'):
            scorer.evaluate(**self.operands())

    def test_event_policy_boundaries_preserved(self):
        policy = scorer.event_policy()
        self.assertEqual(policy.canonical([[0, 10], [100, 110]], 1000), [[0., 10.], [100., 110.]])
        self.assertEqual(policy.canonical([[0, 10], [99, 110]], 1000), [[0., 110.]])
        self.assertEqual(policy.canonical([[0, 301]], 1000), [[0., 300.], [300., 301.]])
        self.assertEqual(policy.count_events([[100, 110]], [[70, 71]], 1000)['true_positive_events'], 1)
        self.assertEqual(policy.count_events([[100, 110]], [[170, 171]], 1000)['false_alarm_events'], 1)


if __name__ == '__main__':
    unittest.main()
