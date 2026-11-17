"""Generated detection controls; only the pinned public filename roster is read."""
import copy
import hashlib
import os
from pathlib import Path
import unittest

import interface as api


def opaque(text):
    return hashlib.sha256(text.encode()).hexdigest()[:24]


class Fixture:
    def __init__(self):
        path = os.environ.get('NEURAL010_RECORDS_FILE') or Path(__file__).parent / 'fixtures/CHBMIT_RECORDS.txt'
        self.records = Path(path).read_bytes()
        api.scorer().source_roster(self.records)
        self.panel = {'schema_version': 1, 'task_id': 'NEURAL-009', 'records': []}
        self.metadata = {'schema': 'neural010-target-free-metadata-v1', 'records': []}
        self.provenance = {'records': []}
        labels = ['FP1-F7', 'F7-T7', 'FP1-F7']  # Duplicate channel labels remain ordered.
        montage = hashlib.sha256(api.encoded(sorted(labels))).hexdigest()
        for source in self.records.decode('ascii').splitlines():
            folder = source.split('/')[0]
            person = 'chb01' if folder == 'chb21' else folder
            rid, pid = opaque(source), opaque(person)
            projection = {'bytes': 4096, 'sha256': hashlib.sha256(('projection:' + source).encode()).hexdigest()}
            source_pin = {'bytes': 8192, 'sha256': hashlib.sha256(('source:' + source).encode()).hexdigest()}
            self.panel['records'].append({'recording_id': rid, 'patient_id': pid, 'duration_seconds': 1000,
                'observed_intervals': [[0, 1000]], 'path': 'signals/' + rid + '.h5', **projection})
            self.metadata['records'].append({'recording_id': rid, 'patient_id': pid, 'duration_seconds': 1000,
                'montage_id': montage, 'channel_count': 3, 'channel_labels': labels[:],
                'source_edf': source_pin, 'target_free_projection': projection})
            self.provenance['records'].append({'recording_id': rid, 'source_path': source, 'source_edf': source_pin,
                'header': {'private_marker': 'NEVER_PARTICIPANT_HEADER'},
                'annotation_evidence': {'private_marker': 'NEVER_PARTICIPANT_ANNOTATION'}})
        self.operand_bytes = {k: api.encoded(getattr(self, k)) for k in ('panel', 'metadata', 'provenance')}
        self.preparation_pins = {k: api.pin(v) for k, v in self.operand_bytes.items()}
        self.prepared = self.project()
        self.support = self.prepared['support']
        self.people = sorted({r['patient_id'] for r in self.panel['records']})
        self.method = hashlib.sha256(b'fixed generated threshold rule, no fitting').hexdigest()
        self.mode = 'frozen_program'
        self.queries, self.submissions = {}, {}
        # A fixed detector sees generated observations, never annotations. This
        # list is an engineering fixture, not source EEG or a scientific proxy.
        observation = [0] * 100 + [2] * 10 + [0] * 890
        events, start = [], None
        for index, value in enumerate(observation + [0]):
            if value > 1 and start is None:
                start = index
            if value <= 1 and start is not None:
                events.append([start, index]); start = None
        for person in self.people:
            query = api.make_query(self.support, held_person=person, mode=self.mode,
                                   method_sha256=self.method, fold_state_sha256='0' * 64)
            self.queries[person] = query
            self.submissions[person] = api.encoded({'schema': 'neural010-detection-submission-v1',
                'query_sha256': api.pin(query)['sha256'],
                'records': [{'recording_id': row['recording_id'], 'events': copy.deepcopy(events)}
                            for row in api.parse(query)['records']]})
        panel = api.parse(self.prepared['scientific_panel'])
        self.references = {}
        for arm in ('matched_no_eeg', 'signal_reference', 'montage_only'):
            ev = [[500, 510]] if arm == 'signal_reference' else []
            self.references[arm] = api.encoded({'schema': 'neural010-scientific-events-v2',
                'panel_sha256': api.pin(self.prepared['scientific_panel'])['sha256'], 'arm': arm,
                'records': [{'recording_id': row['recording_id'], 'events': copy.deepcopy(ev)}
                            for row in panel['records']]})
        self.reference_pins = {k: api.pin(v) for k, v in self.references.items()}
        self.assessment = api.encoded({'schema_version': 1, 'task_id': 'NEURAL-009',
            'panel_sha256': self.preparation_pins['panel']['sha256'],
            'records': [{'recording_id': r['recording_id'], 'events': [[100, 110]]}
                        for r in self.panel['records']]})
        self.assessment_pin = api.pin(self.assessment)
        self.target_reads = 0

    def project(self, **changed):
        bodies = dict(self.operand_bytes, **changed)
        return api.project_preparation(records_bytes=self.records,
            panel_bytes=bodies['panel'], metadata_bytes=bodies['metadata'], provenance_bytes=bodies['provenance'],
            expected={key: api.pin(raw) for key, raw in bodies.items()})

    def freeze(self):
        return api.freeze_candidate(support_bytes=self.support, queries=self.queries,
            submissions=self.submissions, mode=self.mode, method_sha256=self.method)

    def read_targets(self):
        self.target_reads += 1
        return self.assessment

    def grade_args(self):
        return dict(records_bytes=self.records, panel_bytes=self.prepared['scientific_panel'],
            support_bytes=self.support, queries=self.queries, submissions=self.submissions,
            frozen=self.freeze(), mode=self.mode, method_sha256=self.method,
            reference_bytes=self.references, operator_reference_pins=self.reference_pins,
            original_panel_pin=self.preparation_pins['panel'], original_assessment_pin=self.assessment_pin,
            assessment_loader=self.read_targets)

    def training(self, person):
        return api.encoded({'schema': 'neural010-detector-view-v1', 'task_id': 'NEURAL-010',
            'outer_person': person, 'inner_person': None, 'role': 'training',
            'records': [dict(r, events=[[100, 110]]) for r in self.metadata['records']
                        if r['patient_id'] != person]})


class DetectionInterfaceTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()

    def test_generated_detector_to_unchanged_scientific_scorer(self):
        out = api.grade_frozen(**self.f.grade_args())
        self.assertEqual((out['recordings'], out['biological_patients'], self.f.target_reads), (686, 23, 1))
        self.assertEqual(out['primary']['mean'], 1)
        self.assertEqual(out['observed_seconds'], 686000)
        self.assertEqual(out['patients'][opaque('chb01')]['candidate']['observed_seconds'], 75000)
        self.assertEqual(set(out['patients'][opaque('chb01')]), set(api.scorer().ARMS))
        self.assertFalse(out['detection_interface']['independent_reference_matching_or_competence_established'])
        self.assertFalse(out['detection_interface']['qualified_provider_or_process_isolation'])

    def test_allowlist_preserves_channels_but_removes_source_and_annotation_leaks(self):
        support = self.f.support.decode()
        for marker in ('source_path', 'source_edf', 'annotation', 'NEVER_PARTICIPANT', '.edf', 'projection_path'):
            self.assertNotIn(marker, support)
        self.assertEqual(api.parse(self.f.support)['records'][0]['channel_labels'], ['FP1-F7', 'F7-T7', 'FP1-F7'])
        for raw in self.f.queries.values():
            self.assertNotIn(b'events', raw)
            self.assertNotIn(b'NEVER_PARTICIPANT', raw)

    def test_alias_substitution_and_source_membership_refused(self):
        original = copy.deepcopy(self.f.panel)
        meta = copy.deepcopy(self.f.metadata)
        altered_ids = {r['recording_id'] for r in self.f.provenance['records'] if r['source_path'].startswith('chb21/')}
        for doc in (original, meta):
            for row in doc['records']:
                if row['recording_id'] in altered_ids:
                    row['patient_id'] = opaque('chb21')
        with self.assertRaisesRegex(ValueError, 'aliases'):
            self.f.project(panel=api.encoded(original), metadata=api.encoded(meta))
        provenance = copy.deepcopy(self.f.provenance)
        provenance['records'][0]['source_path'] = provenance['records'][1]['source_path']
        with self.assertRaisesRegex(ValueError, 'source membership'):
            self.f.project(provenance=api.encoded(provenance))

    def test_source_channel_ceiling_preserves_duplicate_multiset(self):
        metadata = copy.deepcopy(self.f.metadata)
        row = metadata['records'][0]
        row['channel_labels'] = ['FP1-F7'] * 512
        row['channel_count'] = 512
        row['montage_id'] = hashlib.sha256(api.encoded(sorted(row['channel_labels']))).hexdigest()
        prepared = self.f.project(metadata=api.encoded(metadata))
        projected = next(r for r in api.parse(prepared['support'])['records'] if r['recording_id'] == row['recording_id'])
        self.assertEqual(projected['channel_labels'], ['FP1-F7'] * 512)

    def test_actual_preparer_training_shape_excludes_all_held_person_aliases(self):
        person = opaque('chb01')
        train = self.f.training(person)
        projected = api.parse(api.project_training_view(train, api.pin(train), self.f.support, held_person=person))
        self.assertEqual(len(projected['records']), 611)
        self.assertEqual(len({r['patient_id'] for r in projected['records']}), 22)
        self.assertTrue(all(r['patient_id'] != person for r in projected['records']))
        self.assertNotIn('source_edf', projected['records'][0])
        damaged = api.parse(train)
        damaged['records'][0] = dict(next(r for r in self.f.metadata['records'] if r['patient_id'] == person), events=[])
        raw = api.encoded(damaged)
        with self.assertRaisesRegex(ValueError, 'training support'):
            api.project_training_view(raw, api.pin(raw), self.f.support, held_person=person)

    def test_missing_fold_and_missing_record_are_not_empty_predictions(self):
        person = self.f.people[0]
        submission = self.f.submissions.pop(person)
        with self.assertRaisesRegex(ValueError, '23 complete'):
            self.f.freeze()
        self.f.submissions[person] = submission
        broken = api.parse(submission); broken['records'].pop()
        self.f.submissions[person] = api.encoded(broken)
        with self.assertRaisesRegex(ValueError, 'record count'):
            self.f.freeze()
        self.assertEqual(self.f.target_reads, 0)

    def test_query_method_mode_and_output_binding_cannot_be_reselected(self):
        person = self.f.people[0]
        good = self.f.queries[person]
        for field, value in [('mode', 'typed_viewer'), ('method_sha256', 'f' * 64), ('held_person', self.f.people[1])]:
            damaged = api.parse(good); damaged[field] = value
            self.f.queries[person] = api.encoded(damaged)
            with self.assertRaisesRegex(ValueError, 'frozen query'):
                self.f.freeze()
        self.f.queries[person] = good
        bad = api.parse(self.f.submissions[person]); bad['query_sha256'] = 'f' * 64
        self.f.submissions[person] = api.encoded(bad)
        with self.assertRaisesRegex(ValueError, 'query binding'):
            self.f.freeze()

    def test_event_policy_used_for_both_modes_without_new_matching_rule(self):
        person = self.f.people[0]
        submission = api.parse(self.f.submissions[person])
        rid = submission['records'][0]['recording_id']
        submission['records'][0]['events'] = [[0, 301], [500, 510], [599, 610]]
        self.f.submissions[person] = api.encoded(submission)
        expected = [[0.0, 300.0], [300.0, 301.0], [500.0, 610.0]]
        rows = api.parse(self.f.freeze()['candidate'])['records']
        self.assertEqual(next(r['events'] for r in rows if r['recording_id'] == rid), expected)
        self.f.mode = 'typed_viewer'
        for p in self.f.people:
            query = api.make_query(self.f.support, held_person=p, mode=self.f.mode,
                                  method_sha256=self.f.method, fold_state_sha256='0' * 64)
            self.f.queries[p] = query
            out = api.parse(self.f.submissions[p]); out['query_sha256'] = api.pin(query)['sha256']
            self.f.submissions[p] = api.encoded(out)
        rows = api.parse(self.f.freeze()['candidate'])['records']
        self.assertEqual(next(r['events'] for r in rows if r['recording_id'] == rid), expected)

    def test_changed_freeze_and_every_invalid_reference_precede_target_read(self):
        args = self.f.grade_args()
        bad = dict(args); bad['frozen'] = dict(args['frozen'], candidate=b'{}')
        with self.assertRaisesRegex(ValueError, 'candidate freeze'):
            api.grade_frozen(**bad)
        for arm in self.f.references:
            damaged = api.parse(self.f.references[arm]); damaged['records'].pop()
            raw = api.encoded(damaged)
            bad = dict(args, reference_bytes=dict(self.f.references, **{arm: raw}),
                       operator_reference_pins=dict(self.f.reference_pins, **{arm: api.pin(raw)}))
            with self.assertRaisesRegex(ValueError, 'all stream records'):
                api.grade_frozen(**bad)
        self.assertEqual(self.f.target_reads, 0)

    def test_candidate_cannot_replace_independently_pinned_reference(self):
        args = self.f.grade_args()
        value = api.parse(self.f.references['matched_no_eeg'])
        value['records'][0]['events'] = [[100, 110]]
        args['reference_bytes'] = dict(self.f.references, matched_no_eeg=api.encoded(value))
        with self.assertRaisesRegex(ValueError, 'operator reference identity'):
            api.grade_frozen(**args)
        self.assertEqual(self.f.target_reads, 0)

    def test_target_free_support_and_original_panel_cannot_be_swapped(self):
        args = self.f.grade_args()
        args['original_panel_pin'] = {'bytes': 12, 'sha256': 'f' * 64}
        with self.assertRaisesRegex(ValueError, 'original preparation panel identity'):
            api.grade_frozen(**args)
        self.assertEqual(self.f.target_reads, 0)

    def test_true_target_hash_and_original_panel_binding_required(self):
        args = self.f.grade_args()
        damaged = api.parse(self.f.assessment); damaged['panel_sha256'] = 'f' * 64
        self.f.assessment = api.encoded(damaged)
        with self.assertRaisesRegex(ValueError, 'operand identity'):
            api.grade_frozen(**args)
        self.assertEqual(self.f.target_reads, 1)
        args['original_assessment_pin'] = api.pin(self.f.assessment)
        with self.assertRaisesRegex(ValueError, 'assessment binding'):
            api.grade_frozen(**args)

    def test_extra_fields_bool_endpoints_duplicate_json_and_nonfinite_refused(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}'):
            with self.assertRaises(ValueError):
                api.parse(raw)
        person = self.f.people[0]
        original = self.f.submissions[person]
        for payload in ([[True, 110]], [[100, 100]], [[-1, 2]], [[100, 110], [105, 120]]):
            damaged = api.parse(original); damaged['records'][0]['events'] = payload
            self.f.submissions[person] = api.encoded(damaged)
            with self.assertRaises(ValueError):
                self.f.freeze()
        damaged = api.parse(original); damaged['matched_no_eeg'] = []
        self.f.submissions[person] = api.encoded(damaged)
        with self.assertRaisesRegex(ValueError, 'exact fields'):
            self.f.freeze()


if __name__ == '__main__':
    unittest.main()
