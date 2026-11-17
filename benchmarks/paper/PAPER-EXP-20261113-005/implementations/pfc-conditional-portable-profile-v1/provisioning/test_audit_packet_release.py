"""Invented complete-shape and file-boundary controls; no authentic inputs."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
import uuid

import audit_packet_release as audit


def fixture():
    hashed = lambda s: hashlib.sha256(s.encode()).hexdigest()
    animals = sorted(hashed('invented-animal-' + str(i)) for i in range(68))
    records = [{'id': hashed('invented-record-' + str(i)), 'animal': animals[i % 68], 'task': 'Passive'} for i in range(99)]
    units = [{'id': str(uuid.UUID(int=i + 1, version=4)), 'recording': records[i % 99]['id'],
              'animal': records[i % 99]['animal'], 'task': 'Passive', 'category': i % 8,
              'labels': [0] * 12} for i in range(19186)]
    families = [{'key': k, 'labels': ['1|deep']} for k in audit.FAMILIES]
    contexts = []
    encodings = {'deepRois': 'laydepth', 'nolayRois': 'nolays', 'layeredRois': 'lays', 'deepSupRois': 'laydepth'}
    for k in audit.CONTEXTS:
        r, p, s = k.split('/')
        contexts.append({'key': k, 'family': audit.FAMILIES.index('/'.join((r, p, encodings[s]))),
                         'indices': [0], 'hierarchy': [0.5] if r == 'gaoRois' and s in ('deepRois', 'nolayRois') else None})
    return {'schema': 'PFC_FULL99_FIXED_MAP_PACKET_V1', 'units': units, 'families': families,
            'contexts': contexts, 'animals': animals, 'records': records,
            'historical_diagnostics': {'source_comparison_report': {'bytes': 10, 'sha256': '0' * 64},
                'comparisons': 1, 'shuffle_differences': 0, 'dependent_roi_gao_differences': 0,
                'unavailable_comparisons': 0, 'logical_qe_difference': 'Separate and unchanged',
                'source_geometry_views': 48, 'source_geometry_recomputed': False,
                'historical_equivalence': False, 'full_paper_reproduction': False,
                'interpretation': audit.DIAGNOSTIC_TEXT}}


class ReleaseBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = fixture()

    def mutated(self, action):
        value = copy.deepcopy(self.base)
        action(value)
        with self.assertRaises(audit.Refusal):
            audit.inspect_content(value)

    def test_complete_invented_panel_and_json_roundtrip(self):
        result = audit.inspect_content(audit.decode(json.dumps(self.base).encode()))
        self.assertTrue(result['content_boundary_passed'])
        self.assertEqual((result['units'], result['recordings'], result['animals']), (19186, 99, 68))
        self.assertTrue(result['owner_derived_report_digest_present'])

    def test_nested_unknown_answer_fields_refused(self):
        for field in ('units', 'records', 'families', 'contexts'):
            with self.subTest(field=field):
                self.mutated(lambda x: x[field][0].update({'private_answer': 1}))
        self.mutated(lambda x: x.update({'reference': {}}))

    def test_historical_extra_field_and_report_path_refused(self):
        self.mutated(lambda x: x['historical_diagnostics'].update({'private_owner': '/private/path'}))
        self.mutated(lambda x: x['historical_diagnostics']['source_comparison_report'].update({'path': '/private/path'}))

    def test_freeform_historical_prose_refused(self):
        self.mutated(lambda x: x['historical_diagnostics'].update({'interpretation': '/private/report.json'}))
        self.mutated(lambda x: x['historical_diagnostics'].update({'full_paper_reproduction': True}))

    def test_complete_scope_and_unit_duplicates(self):
        self.mutated(lambda x: x['units'].pop())
        self.mutated(lambda x: x['records'].pop())
        self.mutated(lambda x: x['units'][1].update({'id': x['units'][0]['id']}))

    def test_nonopaque_or_unjoined_identities_refused(self):
        self.mutated(lambda x: x['units'][0].update({'id': 'original-source-unit-42'}))
        self.mutated(lambda x: x['units'][0].update({'recording': '0' * 64}))
        self.mutated(lambda x: x['records'][0].update({'animal': '/private/subject'}))

    def test_anatomical_paths_and_wrong_family_order(self):
        self.mutated(lambda x: x['families'][0].update({'labels': ['/private/owner']}))
        self.mutated(lambda x: x['families'].reverse())

    def test_membership_and_category_domain(self):
        self.mutated(lambda x: x['units'][0].update({'category': True}))
        self.mutated(lambda x: x['units'][0]['labels'].__setitem__(0, -1))
        self.mutated(lambda x: x['units'][0]['labels'].__setitem__(0, 1))

    def test_context_parent_and_hierarchy_domain(self):
        self.mutated(lambda x: x['contexts'][0].update({'family': 0}))
        self.mutated(lambda x: x['contexts'][0].update({'hierarchy': [True]}))
        self.mutated(lambda x: x['contexts'][0].update({'hierarchy': [float('inf')]}))

    def test_explicit_nonfinite_hierarchy_states_are_retained(self):
        value = copy.deepcopy(self.base)
        value['contexts'][0]['hierarchy'] = ['NaN']
        self.assertTrue(audit.inspect_content(value)['content_boundary_passed'])

    def test_duplicate_json_and_nonfinite_constants_refused(self):
        for body in (b'{"schema":1,"schema":2}', b'{"v":NaN}', b'{"v":Infinity}'):
            with self.subTest(body=body), self.assertRaises(audit.Refusal):
                audit.decode(body)

    def test_exact_reader_identity_and_no_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory).resolve() / 'invented.json'
            body = b'{"invented":true}'
            p.write_bytes(body)
            before = set(p.parent.iterdir())
            self.assertEqual(audit.read_exact(p, len(body), hashlib.sha256(body).hexdigest()), body)
            self.assertEqual(before, set(p.parent.iterdir()))
            with self.assertRaises(audit.Refusal):
                audit.read_exact(p, len(body), '0' * 64)
            with self.assertRaises(audit.Refusal):
                audit.read_exact(p, len(body) - 1, hashlib.sha256(body).hexdigest())

    def test_file_aliases_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            p = root / 'file'; p.write_bytes(b'x')
            linked = root / 'linked'; linked.symlink_to(p)
            with self.assertRaises(audit.Refusal):
                audit.read_exact(linked, 1, hashlib.sha256(b'x').hexdigest())
            linked.unlink(); os.link(p, linked)
            with self.assertRaises(audit.Refusal):
                audit.read_exact(p, 1, hashlib.sha256(b'x').hexdigest())

    def test_main_audit_cannot_accept_an_arbitrary_valid_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory).resolve() / 'invented.json'
            p.write_text('{}')
            with self.assertRaises(audit.Refusal):
                audit.audit_packet(p)


if __name__ == '__main__':
    unittest.main(verbosity=2)
