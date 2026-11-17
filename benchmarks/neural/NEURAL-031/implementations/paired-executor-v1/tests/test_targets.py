"""Generated target-format/semantic controls, never an authentic-source receipt."""
from contextlib import contextmanager
import copy
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import stat
import tempfile
import unittest
import warnings
import zipfile

import numpy as np

PATH = Path(__file__).resolve().parents[1] / 'targets.py'
SPEC = importlib.util.spec_from_file_location('_neural031_test_target_bridge', PATH)
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)
CREATED_BYTES = 0
RECLAIMED_BYTES = 0


@contextmanager
def temporary_files():
    global RECLAIMED_BYTES
    with tempfile.TemporaryDirectory(prefix='generated-neural031-targets-') as directory:
        root = Path(directory)
        try:
            yield root
        finally:
            RECLAIMED_BYTES += sum(len(os.readlink(p).encode()) if p.is_symlink() else p.stat().st_size
                                   for p in root.rglob('*') if p.is_symlink() or p.is_file())


def fixture_write(path, body):
    global CREATED_BYTES
    path.write_bytes(body)
    CREATED_BYTES += len(body)


def fixture():
    """Real roster metadata with invented measurements; not source authority."""
    source = bridge.sources()
    ep = bridge.endpoint()
    columns = {key: [] for key in bridge.TARGET_KEYS}
    census = []
    request_index = 0
    for member_index, member in enumerate(source['members']):
        count = 43 if member_index < 9 else 42
        requests = 29 if member_index < 18 else 28
        for local_row in range(count):
            rowid = len(census)
            requested = local_row < requests
            observed = requested and request_index % 18 != 0
            new = rowid % 5 == 0
            value = (rowid % 9) / 4 if observed else math.nan
            columns['rowid'].append(rowid)
            columns['mouse'].append(ep.MICE.index(member['mouse_id_from_path']))
            columns['y'].append(value)
            columns['request'].append(int(requested))
            columns['observed'].append(int(observed))
            columns['baseline_new'].append(int(new))
            columns['compartment'].append(int(member['compartment_from_path'] == 'basal'))
            census.append({'rowid': rowid, 'member_index0': member_index, 'source_row0': local_row,
                'source_member': member['name'], 'mouse_id': member['mouse_id_from_path'],
                'FOV': member['fov_from_path'], 'session': member['session_from_path'],
                'compartment': member['compartment_from_path'], 'dendrite_id': local_row // 7,
                'baseline_new': new, 'request': requested, 'target_observed': observed,
                'baseline_reasons': [] if requested else ['baseline_absent'],
                'target_reasons': [] if observed else
                    (['followup_nonfinite', 'ratio_nonfinite'] if requested else ['not_requested']),
                'local_missing': rowid % 7 == 0, 'coincident_missing': rowid % 11 == 0})
            request_index += int(requested)
    arrays = {key: np.asarray(values, dtype='<f8' if key == 'y' else '<i8')
              for key, values in columns.items()}
    support = {'schema': 'neural031_ordinary_public_support_v1', 'candidate_id': 'NEURAL-031',
               'folds': [], 'request_rows': 774, 'query_targets_included': False}
    for fold in range(20):
        rowids = np.flatnonzero((arrays['mouse'] == fold) & (arrays['request'] == 1)).tolist()
        views = {view: {kind: {'bytes': 1, 'sha256': hashlib.sha256(
            f'GENERATED-UNAUTHENTICATED/{fold}/{view}/{kind}'.encode()).hexdigest()}
            for kind in ('data', 'manifest')} for view in ep.VIEWS}
        support['folds'].append({'fold': fold, 'rowids': rowids, 'views': views})
    assert request_index == 774 and int(arrays['observed'].sum()) == 731
    return arrays, census, support


def archive(arrays):
    buffer = io.BytesIO()
    np.savez(buffer, **arrays)
    return buffer.getvalue()


class TargetBridgeTests(unittest.TestCase):
    def setUp(self):
        self.arrays, self.census, self.support = fixture()

    @classmethod
    def tearDownClass(cls):
        print(json.dumps({'scope': 'generated_fixture_file_accounting',
            'created_bytes': CREATED_BYTES, 'reclaimed_bytes': RECLAIMED_BYTES,
            'retained_fixture_bytes': CREATED_BYTES - RECLAIMED_BYTES,
            'authentic_operands_opened': False, 'production_source_authority_mocked': False}))

    def build(self):
        return bridge.build_unbound_target(np, self.arrays, self.census, self.support)

    def test_complete_native_format_to_json_preserves_ratios_zero_and_unavailable(self):
        values = bridge.decode_legacy_npz(np, archive(self.arrays))
        census = bridge.decode_census(b''.join(bridge.encoded(row) for row in self.census))
        target = bridge.build_unbound_target(np, values, census, self.support)
        self.assertEqual(len(target['rows']), 1143)
        self.assertEqual(sum(row['request'] for row in target['rows']), 774)
        self.assertEqual(sum(row['observed'] for row in target['rows']), 731)
        self.assertEqual(sum(row['request'] and not row['observed'] for row in target['rows']), 43)
        self.assertEqual(sum(row['y'] is None for row in target['rows']), 412)
        self.assertTrue(any(row['observed'] and row['y'] == 0 for row in target['rows']))
        for row in target['rows']:
            if row['observed']:
                self.assertEqual(row['y'], self.arrays['y'][row['rowid']])
        raw = bridge.encoded(target)
        self.assertNotIn(b'NaN', raw)
        self.assertLess(len(raw), 524288)
        self.assertEqual(json.loads(raw), target)

    def test_bridge_connects_to_unchanged_equal_mouse_scorer(self):
        target = self.build()
        bundle = {'schema': 'neural031_ordinary_submission_bundle_v1',
                  'candidate_id': 'NEURAL-031', 'outputs': []}
        for fold in self.support['folds']:
            for view in ('baseline', 'neural'):
                bundle['outputs'].append({'schema': 'neural031_ordinary_prediction_v1',
                    'candidate_id': 'NEURAL-031', 'fold': fold['fold'], 'view': view,
                    'input_manifest': fold['views'][view]['manifest'],
                    'rows': [{'row_id': rowid, 'prediction': 1.0} for rowid in fold['rowids']]})
        scored = bridge.endpoint().score(self.support, bundle, target)
        self.assertEqual(scored['primary'], 0.0)
        self.assertEqual((scored['raw_rows'], scored['request_rows'], scored['scored_rows'], scored['unavailable_rows']),
                         (1143, 774, 731, 43))

    def test_source_row_mouse_compartment_and_baseline_new_mismatches_fail(self):
        for column, value in [('rowid', 1), ('mouse', 1), ('compartment', 1), ('baseline_new', 0)]:
            original = self.arrays[column][0]
            self.arrays[column][0] = value
            with self.subTest(column=column), self.assertRaises(ValueError):
                self.build()
            self.arrays[column][0] = original

    def test_all_source_identity_fields_are_bound(self):
        changes = {'source_member': 'invented', 'mouse_id': 'JW306', 'FOV': 'other',
                   'session': 'Later', 'compartment': 'basal', 'source_row0': 1, 'member_index0': 1}
        for key, value in changes.items():
            old = self.census[0][key]
            self.census[0][key] = value
            with self.subTest(field=key), self.assertRaises(ValueError):
                self.build()
            self.census[0][key] = old

    def test_census_order_gap_duplicate_or_omitted_member_fails(self):
        original = copy.deepcopy(self.census)
        cases = ('swap', 'duplicate_local', 'skip_member', 'omit')
        for case in cases:
            self.census = copy.deepcopy(original)
            if case == 'swap':
                self.census[0], self.census[1] = self.census[1], self.census[0]
            elif case == 'duplicate_local':
                self.census[1]['source_row0'] = 0
            elif case == 'skip_member':
                self.census[43]['member_index0'] = 2
            else:
                self.census.pop()
            with self.subTest(case=case), self.assertRaises(ValueError):
                self.build()

    def test_unavailable_target_requires_nan_and_observed_zero_is_distinct(self):
        missing = int(np.flatnonzero(self.arrays['observed'] == 0)[0])
        observed = int(np.flatnonzero(self.arrays['observed'] == 1)[0])
        for value in (0., 1., math.inf, -math.inf):
            self.arrays['y'][missing] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.build()
        self.arrays['y'][missing] = math.nan
        self.arrays['y'][observed] = 0.
        self.assertEqual(self.build()['rows'][observed]['y'], 0.)

    def test_observed_ratio_negative_nan_or_infinite_fails(self):
        row = int(np.flatnonzero(self.arrays['observed'])[0])
        for value in (-1., math.nan, math.inf, -math.inf):
            self.arrays['y'][row] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.build()

    def test_binary_flags_and_exact_dtypes_required(self):
        for column in ('request', 'observed', 'baseline_new', 'compartment'):
            original = self.arrays[column]
            for value in (-1, 2):
                self.arrays[column] = original.copy()
                self.arrays[column][0] = value
                with self.subTest(column=column, value=value), self.assertRaises(ValueError):
                    self.build()
            self.arrays[column] = original.astype(np.float64)
            with self.subTest(column=column, dtype='float'), self.assertRaises(ValueError):
                self.build()
            self.arrays[column] = original

    def test_census_booleans_and_reasons_must_agree(self):
        original = copy.deepcopy(self.census[0])
        changes = [('request', 1), ('target_observed', True), ('baseline_new', False),
                   ('baseline_reasons', ['baseline_absent']), ('target_reasons', []),
                   ('target_reasons', ['not_requested']), ('target_reasons', ['invented']),
                   ('target_reasons', ['followup_nonfinite', 'followup_nonfinite'])]
        for key, value in changes:
            self.census[0] = copy.deepcopy(original)
            self.census[0][key] = value
            with self.subTest(field=key, value=value), self.assertRaises(ValueError):
                self.build()

    def test_public_support_swapped_fold_omission_and_extra_request_fail(self):
        original = copy.deepcopy(self.support)
        for mutation in ('swap_fold', 'omit_request', 'extra_request'):
            self.support = copy.deepcopy(original)
            if mutation == 'swap_fold':
                a, b = self.support['folds'][:2]
                a['rowids'], b['rowids'] = b['rowids'], a['rowids']
            elif mutation == 'omit_request':
                self.support['folds'][0]['rowids'].pop()
            else:
                self.support['folds'][0]['rowids'].append(1142)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.build()

    def test_jsonl_duplicate_keys_nonstandard_constants_and_blank_rows_fail(self):
        good = b''.join(bridge.encoded(row) for row in self.census)
        bodies = [good.replace(b'"rowid":0', b'"rowid":0,"rowid":0', 1),
                  good.replace(b'"dendrite_id":0', b'"dendrite_id":NaN', 1),
                  b'\n' + good, good.replace(b'\n', b'\n\n', 1)]
        for body in bodies:
            with self.subTest(prefix=body[:40]), self.assertRaises(ValueError):
                bridge.decode_census(body)

    def test_npz_extra_missing_duplicate_object_shape_and_dtype_fail(self):
        mutations = []
        missing = dict(self.arrays); missing.pop('y'); mutations.append(archive(missing))
        extra = dict(self.arrays, surprise=np.zeros(1)); mutations.append(archive(extra))
        for values in (np.zeros(1142), np.zeros((1143, 1)), np.zeros(1143, dtype=np.float32),
                       np.asarray(['forbidden'] * 1143, dtype=object)):
            modified = dict(self.arrays, y=values); mutations.append(archive(modified))
        duplicate = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(archive(self.arrays))) as source, zipfile.ZipFile(duplicate, 'w') as dest:
            for item in source.infolist():
                dest.writestr(item.filename, source.read(item))
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                dest.writestr('y.npy', source.read('y.npy'))
        mutations.append(duplicate.getvalue())
        for body in mutations:
            with self.subTest(bytes=len(body)), self.assertRaises(ValueError):
                bridge.decode_legacy_npz(np, body)

    def test_numpy_header_shape_bomb_refused_before_allocation(self):
        small = io.BytesIO()
        np.lib.format.write_array_header_1_0(small, {'descr': '<f8', 'fortran_order': False, 'shape': (10**12,)})
        bad = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(archive(self.arrays))) as source, zipfile.ZipFile(bad, 'w') as dest:
            for item in source.infolist():
                dest.writestr(item.filename, small.getvalue() if item.filename == 'y.npy' else source.read(item))
        with self.assertRaises(ValueError):
            bridge.decode_legacy_npz(np, bad.getvalue())

    def test_generated_support_cannot_create_production_source_authority(self):
        with temporary_files() as root:
            support = root / 'generated-support.json'
            fixture_write(support, bridge.encoded(self.support))
            with self.assertRaisesRegex(ValueError, 'independent source'):
                bridge.prepare_targets(root/'not-opened-targets.npz', root/'not-opened-census.jsonl',
                                       support, root/'output')
            self.assertFalse((root/'output').exists())

    def test_private_writes_are_bounded_exclusive_and_owner_only(self):
        global CREATED_BYTES
        with temporary_files() as root:
            path = root / 'private.json'
            body = b'{"generated":true}\n'
            self.assertEqual(bridge._write_private(path, body, 128), bridge.pin(body))
            CREATED_BYTES += len(body)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            with self.assertRaises(FileExistsError):
                bridge._write_private(path, body, 128)
            with self.assertRaises(ValueError):
                bridge._write_private(root/'too-large.json', body, 1)

    def test_source_symlinks_and_wrong_hashes_refused(self):
        global CREATED_BYTES
        with temporary_files() as root:
            path = root/'fixture'
            fixture_write(path, b'generated')
            symlink = root/'link'
            symlink.symlink_to('fixture')
            CREATED_BYTES += len(b'fixture')
            with self.assertRaises(OSError):
                bridge.read_pinned(symlink, bridge.pin(b'generated'), 128)
            with self.assertRaises(ValueError):
                bridge.read_pinned(path, bridge.pin(b'different'), 128)


if __name__ == '__main__':
    unittest.main(verbosity=2)
