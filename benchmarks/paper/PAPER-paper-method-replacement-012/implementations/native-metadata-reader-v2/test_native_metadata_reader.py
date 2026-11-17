"""Generated metadata-only controls; no authentic output or neural array reads."""
from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import reader

FIXTURE_LIMIT = 4 * 1024**2
GENERATED_FILE_BYTES = 0
GENERATED_WRITE_CALLS = 0
HELPER_SHA256 = '428ac5555647eac596d801d7a80df8fdb6bdbc5b27b8bdc88f88f7848cd3c598'
HOLDS = [
    'Invalid current E/I inductive split remains refused.',
    'Transductive resample command conflicts with pinned single-split script.',
    'Conference-era artifact equality, native references and protected candidates unqualified.',
]


def write_generated(path, body):
    global GENERATED_FILE_BYTES, GENERATED_WRITE_CALLS
    if GENERATED_FILE_BYTES + len(body) > FIXTURE_LIMIT:
        raise AssertionError('cumulative generated-file allocation exceeded')
    Path(path).write_bytes(body)
    GENERATED_FILE_BYTES += len(body)
    GENERATED_WRITE_CALLS += 1


def completion_for(native, manifest, joined):
    return {'schema': 'nuclr-native-preparation-complete-v1',
            'manifest_sha256': native.digest(manifest),
            'joined_panels_sha256': native.digest(joined),
            'scientific_qualification': False}


def original_generated_projection_helper(native):
    """Load only the pinned original fixture function, never its array helpers/tests."""
    path = Path(__file__).resolve().parents[1] / 'native-inputs-v1/test_native_inputs.py'
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != HELPER_SHA256:
        raise AssertionError('original generated projection helper source changed')
    functions = [node for node in ast.parse(body).body
                 if isinstance(node, ast.FunctionDef) and node.name == 'generated_projections']
    if len(functions) != 1:
        raise AssertionError('one pinned generated projection helper required')
    namespace = {'dependencies': SimpleNamespace(load_dependencies=native.load_dependencies),
                 'hashlib': hashlib}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace['generated_projections']


class SavedMetadataControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.native = reader.frozen_native()
        cls.source = cls.native.load_dependencies()
        definition = cls.native.profile()
        vocabulary = ['EC'] + sorted(cls.source.splits.LABELS['11class']) + ['IN', 'Lamp5-invented']
        sessions, neurons = [], []
        for sid, spec in definition['sessions'].items():
            sessions.append({'session_id': sid, 'neurons': spec['neurons'],
                             'experiments': [{'experiment_id': exp} for exp in spec['experiments']],
                             'historical_experiment_order_verified': False,
                             'order_policy': cls.native.ORDER_POLICY})
            for index in range(spec['neurons']):
                label = vocabulary[index % len(vocabulary)]
                matched = None if index % 7 == 1 else index
                subject = sid.split('_')[0]
                neurons.append({'id': f'{sid}_u{index}', 'session_id': sid, 'subject_id': subject,
                                'source_neuron_index': index, 'ttype': label,
                                'ei_class': label if label in ('EC', 'IN') else 'IN',
                                'subclass': 'unknown' if label in ('EC', 'IN') else label.split('-')[0],
                                'source_unique_id': matched,
                                'source_unique_id_missing': 'NaN_unmatched' if matched is None else None,
                                'repeated_cell_id': None if matched is None else f'{subject}:UniqueID:{matched}',
                                'repeated_cell_namespace': 'subject_scoped_source_match; global namespace unspecified'})
        projections = original_generated_projection_helper(cls.native)(neurons)
        joined = cls.native.join_projections(sessions, neurons, projections)
        assets = [{'source_member': row['name'], 'relative_path': 'native/' + row['name'],
                   'bytes': row['bytes'],
                   'sha256': hashlib.sha256(('GENERATED-NOT-SOURCE:' + row['name']).encode()).hexdigest()}
                  for row in definition['required_members']]
        manifest = {'schema': cls.native.SCHEMA, 'source_profile_sha256': cls.native.PROFILE_SHA256,
                    'order_adoption_sha256': cls.native.ORDER_ADOPTION_SHA256,
                    'split_archive_sha256': cls.source.splits.ARCHIVE_SHA256,
                    'metadata_archive_sha256': definition['metadata_archive']['sha256'],
                    'raw_archive_sha256': hashlib.sha256(b'GENERATED-NOT-SOURCE').hexdigest(),
                    'dependencies': cls.source.pins, 'order_policy': cls.native.ORDER_POLICY,
                    'sessions': sessions, 'neurons': neurons, 'assets': assets,
                    'subjects': 4, 'session_count': 17, 'subrecordings': 69, 'neuron_observations': 10153,
                    'historical_order_verified': False, 'scientific_qualification': False,
                    'input_preparation_crops_or_samples': False, 'remaining_holds': HOLDS,
                    'downstream_sampler_configuration': None,
                    'downstream_observation_limit_seconds': None, 'downstream_device_count': None,
                    'fixture_role': 'generated_metadata_control_not_authentic_assets'}
        cls.original_order = [list(row['ordered_ids']) for row in joined]
        # This is the production writer's exact sorted-key canonical serialization,
        # followed by JSON decoding, kept entirely in memory.
        cls.bodies = {'native-manifest.json': cls.native.canonical(manifest) + b'\n',
                      'joined-panels.json': cls.native.canonical(joined) + b'\n',
                      'COMPLETE.json': cls.native.canonical(completion_for(cls.native, manifest, joined)) + b'\n'}
        cls.manifest = reader.decode(cls.bodies['native-manifest.json'])
        cls.joined = reader.decode(cls.bodies['joined-panels.json'])
        cls.completion = reader.decode(cls.bodies['COMPLETE.json'])
        cls.file_digests = {name: hashlib.sha256(body).hexdigest() for name, body in cls.bodies.items()}

    def setUp(self):
        root = os.environ.get('NUCLR_READER_CONTROL_ROOT')
        self.temporary = tempfile.TemporaryDirectory(dir=root, prefix='generated-reader-')
        self.root = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)
        for name in ('NativeArray', 'inspect_session', 'session_neurons', 'prepare_source', 'read_prepared_block'):
            guard = patch.object(self.native, name, side_effect=AssertionError('neural array/preparation access prohibited'))
            guard.start()
            self.addCleanup(guard.stop)

    def validate(self, manifest=None, joined=None):
        manifest = self.manifest if manifest is None else manifest
        joined = self.joined if joined is None else joined
        return reader.validate_documents(manifest, joined, completion_for(self.native, manifest, joined))

    def changed_joined(self, index=0):
        changed = list(self.joined)
        changed[index] = deepcopy(changed[index])
        return changed

    def test_full_saved_roundtrip_preserves_all_nine_source_orders(self):
        self.assertEqual((len(self.manifest['sessions']), len(self.manifest['neurons']),
                          len(self.manifest['assets']), len(self.joined)), (17, 10153, 257, 9))
        self.assertEqual(sum(len(s['experiments']) for s in self.manifest['sessions']), 69)
        self.assertTrue(any(list(row['projection']['label_map']) != expected
                            for row, expected in zip(self.joined, self.original_order)))
        # Witness the old failure without rerunning its existing test suite.
        old_rejoin = self.native.join_projections(self.manifest['sessions'], self.manifest['neurons'],
                                                  [row['projection'] for row in self.joined])
        self.assertNotEqual(old_rejoin, self.joined)
        binding = self.validate()
        self.assertEqual([row['ordered_ids'] for row in binding.joined], self.original_order)
        self.assertEqual(binding.reader_policy, reader.READER_POLICY)
        self.assertIs(binding.manifest, self.manifest)
        self.assertEqual(self.native.canonical(binding.joined) + b'\n', self.bodies['joined-panels.json'])
        self.assertFalse(binding.manifest['scientific_qualification'])
        self.assertEqual(binding.manifest['fixture_role'], 'generated_metadata_control_not_authentic_assets')

    def test_source_row_list_controls_order_without_mutating_input(self):
        projection = self.joined[0]['projection']
        before = self.native.canonical(projection)
        sorted_map_order = list(projection['label_map'])
        restored = reader.restore_source_order(projection)
        self.assertEqual(list(restored['label_map']), [row['id'] for row in projection['metadata']])
        self.assertNotEqual(list(restored['label_map']), sorted_map_order)
        self.assertEqual(list(projection['label_map']), sorted_map_order)
        self.assertEqual(self.native.canonical(projection), before)
        self.assertEqual(self.native.canonical(restored), before)

    def test_missing_duplicate_and_changed_projection_metadata_ids_refuse(self):
        for mutation in ('missing', 'duplicate', 'changed'):
            with self.subTest(mutation=mutation):
                changed = self.changed_joined()
                rows = changed[0]['projection']['metadata']
                if mutation == 'missing': rows.pop()
                elif mutation == 'duplicate': rows[0] = dict(rows[-1])
                else: rows[0]['id'] = 'sb025_20191004_u999999'
                with self.assertRaisesRegex(ValueError, 'cover label map exactly once'):
                    self.validate(joined=changed)

    def test_changed_projection_identity_fields_refuse(self):
        changed = self.changed_joined()
        changed[0]['projection']['metadata'][0]['source_neuron_index'] += 1
        with self.assertRaisesRegex(ValueError, 'column identity differs'):
            self.validate(joined=changed)

    def test_saved_ordered_ids_tamper_refuses(self):
        changed = self.changed_joined()
        changed[0]['ordered_ids'][0:2] = changed[0]['ordered_ids'][0:2][::-1]
        with self.assertRaisesRegex(ValueError, 'native panel rows'):
            self.validate(joined=changed)

    def test_saved_native_address_tamper_refuses(self):
        changed = self.changed_joined()
        changed[0]['ordered_native_addresses'][0]['column'] += 1
        with self.assertRaisesRegex(ValueError, 'native panel rows'):
            self.validate(joined=changed)

    def test_saved_joined_metadata_row_tamper_refuses(self):
        changed = self.changed_joined()
        changed[0]['metadata'][0]['id'] = changed[0]['metadata'][1]['id']
        with self.assertRaisesRegex(ValueError, 'native panel rows'):
            self.validate(joined=changed)

    def test_missing_duplicate_and_changed_native_neuron_ids_refuse(self):
        for mutation in ('missing', 'duplicate', 'changed'):
            with self.subTest(mutation=mutation):
                manifest = dict(self.manifest, neurons=list(self.manifest['neurons']))
                if mutation == 'missing': manifest['neurons'].pop()
                elif mutation == 'duplicate': manifest['neurons'][0] = dict(manifest['neurons'][-1])
                else: manifest['neurons'][0] = dict(manifest['neurons'][0], id='sb025_20191004_u999999')
                with self.assertRaises(ValueError):
                    self.validate(manifest=manifest)

    def test_file_digest_cannot_replace_canonical_completion_digest(self):
        bad = dict(self.completion, manifest_sha256=self.file_digests['native-manifest.json'])
        self.assertNotEqual(bad['manifest_sha256'], self.completion['manifest_sha256'])
        with self.assertRaisesRegex(ValueError, 'canonical completion binding'):
            reader.validate_documents(self.manifest, self.joined, bad)

    def test_bound_metadata_constructor_and_addresses_use_no_arrays(self):
        reads = []
        def generated_read(path, maximum, expected):
            name = Path(path).name
            self.assertIn(name, self.bodies)
            self.assertEqual(expected, self.file_digests[name])
            self.assertLessEqual(len(self.bodies[name]), maximum)
            reads.append(name)
            return self.bodies[name]
        # Only the file-read boundary is injected with generated serialized bytes.
        # Actual file hashing is checked below on a small physical JSON fixture.
        with patch.object(reader, 'read_bound', generated_read):
            binding = reader.NativeInputs(self.root, file_sha256=self.file_digests)
        self.assertCountEqual(reads, reader.DOCUMENTS)
        ids = ['sb025_20191004_u10', 'sb025_20191004_u2', 'sb028_20191107_u0']
        self.assertEqual(binding.native_addresses(ids), [('sb025_20191004',10),
                                                       ('sb025_20191004',2), ('sb028_20191107',0)])
        with self.assertRaises(ValueError): binding.native_addresses(ids + ids[:1])
        self.assertEqual(binding.file_sha256, self.file_digests)
        self.assertFalse(binding.manifest['historical_order_verified'])

    def test_incomplete_marker_and_missing_trusted_file_digest_refuse(self):
        with patch.object(reader, 'read_bound', side_effect=AssertionError('must refuse before reading')):
            with self.assertRaisesRegex(ValueError, 'all three trusted'):
                reader.NativeInputs(self.root, file_sha256={'COMPLETE.json': '0'*64})
            write_generated(self.root/'INCOMPLETE.json', b'{}\n')
            with self.assertRaisesRegex(ValueError, 'partial preparation'):
                reader.NativeInputs(self.root, file_sha256=self.file_digests)

    def test_small_physical_file_hash_is_distinct_from_document_hash(self):
        path = self.root/'generated.json'
        body = b'{"z":2,"a":1}\n'
        write_generated(path, body)
        actual = hashlib.sha256(body).hexdigest()
        canonical_digest = self.native.digest(reader.decode(body))
        self.assertNotEqual(actual, canonical_digest)
        self.assertEqual(reader.read_bound(path, 64, actual), body)
        with self.assertRaisesRegex(ValueError, 'exact metadata file digest'):
            reader.read_bound(path, 64, canonical_digest)
        with self.assertRaises(ValueError): reader.read_bound(path, len(body)-1, actual)
        changed = body + b' '
        write_generated(path, changed)
        self.assertEqual(reader.decode(changed), reader.decode(body))
        with self.assertRaisesRegex(ValueError, 'exact metadata file digest'):
            reader.read_bound(path, 64, actual)

    def test_duplicate_and_nonfinite_json_refuse(self):
        for body in (b'{"id":1,"id":2}', b'{"x":NaN}', b'{"x":Infinity}'):
            with self.subTest(body=body), self.assertRaises(ValueError): reader.decode(body)

    def test_invalid_ei_remains_present_and_unselectable(self):
        invalid = [row for row in self.joined if not row['topology_audit']['matches_registered_topology']]
        self.assertEqual(len(invalid), 1)
        projection = reader.restore_source_order(invalid[0]['projection'])
        self.assertEqual((projection['label_level'], projection['panel']), ('ei', 'inductive_zero_shot'))
        with self.assertRaises(ValueError):
            self.source.splits.select_readout_panel([projection], 'ei', 'inductive_zero_shot')
        changed = self.changed_joined(self.joined.index(invalid[0]))
        changed[self.joined.index(invalid[0])]['topology_audit']['matches_registered_topology'] = True
        with self.assertRaises(ValueError): self.validate(joined=changed)

    def test_historical_claims_and_original_holds_cannot_be_promoted(self):
        cases = [dict(self.manifest, historical_order_verified=True),
                 dict(self.manifest, scientific_qualification=True),
                 dict(self.manifest, remaining_holds=[]),
                 {k:v for k,v in self.manifest.items() if k != 'downstream_device_count'}]
        for manifest in cases:
            with self.subTest(keys=set(manifest)-set(self.manifest)), self.assertRaises(ValueError):
                self.validate(manifest=manifest)


def tearDownModule():
    print(json.dumps({'generated_fixture_file_bytes': GENERATED_FILE_BYTES,
                      'generated_fixture_write_calls': GENERATED_WRITE_CALLS,
                      'cumulative_fixture_cap_bytes': FIXTURE_LIMIT,
                      'full_metadata_roundtrip_in_memory': True,
                      'authentic_array_or_model_execution': False,
                      'existing_full_suite_replayed': False}))


if __name__ == '__main__':
    unittest.main()
