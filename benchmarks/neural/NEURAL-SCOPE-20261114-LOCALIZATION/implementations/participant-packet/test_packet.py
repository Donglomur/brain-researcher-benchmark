"""Generated full-grid input controls; no source payloads or private labels."""
import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import packet as p


def opaque(text):
    return hashlib.sha256(text.encode()).hexdigest()[:32]


def npy(shape, values, dtype='<f8', fortran=False, version=1):
    header = repr({'descr': dtype, 'fortran_order': fortran, 'shape': tuple(shape)}).encode()
    start = 10 if version == 1 else 12
    header += b' ' * ((-start - len(header) - 1) % 64) + b'\n'
    return (b'\x93NUMPY' + bytes((version, 0))
            + struct.pack('<H' if version == 1 else '<I', len(header)) + header
            + b''.join(struct.pack('<' + p.DTYPES[dtype][0], value) for value in values))


def artifact(role, shape, raw, dtype='<f8'):
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw),
            'role': role, 'shape': shape, 'dtype': dtype}


def fixture():
    definitions = [('waveforms', [2, 3, 3], list(range(18)), '<f8'),
                   ('template', [3, 3], list(range(9)), '<f8'),
                   ('probe_geometry', [3, 2], [0, 0, 10, 30, 50, 90], '<f8'),
                   ('observed_support', [3], [1, 1, 0], '|b1')]
    bodies, artifacts, inputs = {}, [], {}
    for role, shape, values, dtype in definitions:
        raw = npy(shape, values, dtype)
        desc = artifact(role, shape, raw, dtype)
        bodies[desc['sha256']] = raw
        artifacts.append(desc)
        inputs[role] = desc['sha256']
    cells = [opaque('cell' + str(i)) for i in range(11)]
    conditions = [opaque('condition' + str(i)) for i in range(16)]
    realizations = [opaque('realization' + str(i)) for i in range(5)]
    neural = {'schema': 'localization-normalized-neural-v1', 'task_id': 'NEURAL-SCOPE-20261114-LOCALIZATION',
              'axis_names': ['z', 'x'], 'coordinate_unit': 'um', 'cells': cells,
              'conditions': conditions, 'realizations': realizations, 'artifacts': artifacts, 'cases': []}
    for cell in cells:
        for condition in conditions:
            for realization in realizations:
                cid = opaque(cell + condition + realization)
                requests = [{'request_id': opaque(cid + 'spike' + str(i)), 'kind': 'spike', 'array_index': i}
                            for i in range(2)]
                requests.append({'request_id': opaque(cid + 'template'), 'kind': 'template', 'array_index': 0})
                neural['cases'].append({'case_id': cid, 'cell_id': cell, 'condition_id': condition,
                    'realization_id': realization, 'sampling_frequency_hz': 30000, 'voltage_unit': 'uV',
                    'sample_offsets': [-1, 0, 1], 'channel_ids': [opaque('channel' + str(i)) for i in range(3)],
                    'inputs': dict(inputs), 'requests': requests})
    return neural, bodies


def replace_role(neural, bodies, role, raw, dtype=None):
    old = next(a for a in neural['artifacts'] if a['role'] == role)
    new = artifact(role, old['shape'], raw, dtype or old['dtype'])
    neural['artifacts'].remove(old)
    neural['artifacts'].append(new)
    bodies[new['sha256']] = raw
    for case in neural['cases']:
        case['inputs'][role] = new['sha256']


def source(folder, bodies):
    root = Path(folder) / 'source'
    (root / 'inputs').mkdir(parents=True)
    for digest, raw in bodies.items():
        (root / 'inputs' / (digest + '.npy')).write_bytes(raw)
    return root


def stage(neural, root, destination, **changes):
    kwargs = {'expected_manifest_sha256': hashlib.sha256(p.canonical(neural)).hexdigest(),
              'total_input_byte_budget': 1000000, 'maximum_artifact_bytes': 100000}
    kwargs.update(changes)
    return p.stage(neural, root, destination, **kwargs)


class PacketTests(unittest.TestCase):
    def test_full880_exact_copy_projection_and_private_sentinel_exclusion(self):
        neural, bodies = fixture()
        with tempfile.TemporaryDirectory() as temp:
            root = source(temp, bodies)
            (root / 'private-reference.json').write_text('{"coordinate_um":[999,999]}')
            (root / 'inputs' / 'unrequested.npy').write_bytes(b'private sentinel')
            output = Path(temp) / 'packet'
            receipt = stage(neural, root, output)
            public = json.loads((output / 'manifest.json').read_bytes())
            self.assertEqual((receipt['cases'], receipt['requests'], receipt['artifact_count']), (880, 2640, 4))
            self.assertEqual(receipt['artifact_bytes'], sum(map(len, bodies.values())))
            self.assertEqual(public, p.load_neutral().project(neural))
            self.assertEqual(set(x.name for x in output.iterdir()), {'manifest.json', 'inputs'})
            self.assertEqual(set(x.name for x in (output / 'inputs').iterdir()), {h + '.npy' for h in bodies})
            for digest, body in bodies.items():
                self.assertEqual((output / 'inputs' / (digest + '.npy')).read_bytes(), body)
            self.assertNotIn('cells', public)
            self.assertTrue(all('cell_id' not in c and 'realization_id' not in c for c in public['cases']))
            self.assertFalse(any(receipt['access_mode_qualification'].values()))
            self.assertEqual(hashlib.sha256((output / 'manifest.json').read_bytes()).hexdigest(),
                             receipt['participant_manifest_sha256'])
            with self.assertRaises(p.PacketError):
                stage(neural, root, output)

    def test_npy_storage_order_and_numeric_dtypes_preserved(self):
        for dtype in ('<f4', '<f8', '<i4', '<i8'):
            for fortran in (False, True):
                for version in (1, 2):
                    values = [1, 3, 7, 2, 4, 8] if fortran else [1, 2, 3, 4, 7, 8]
                    raw = npy([3, 2], values, dtype, fortran, version)
                    desc = artifact('probe_geometry', [3, 2], raw, dtype)
                    self.assertEqual(p.validate_array(raw, desc), [(1, 2), (3, 4), (7, 8)])
                    raw = npy([2, 3, 3], range(18), dtype, fortran, version)
                    self.assertIsNone(p.validate_array(raw, artifact('waveforms', [2, 3, 3], raw, dtype)))

    def test_complete_case_request_and_unit_gate_before_destination_creation(self):
        neural, bodies = fixture()
        for mutation in ('case', 'request', 'unit', 'owner_field', 'duplicate_request'):
            candidate = copy.deepcopy(neural)
            if mutation == 'case': candidate['cases'].pop()
            elif mutation == 'request': candidate['cases'][0]['requests'].pop()
            elif mutation == 'unit': candidate['cases'][0]['voltage_unit'] = 'mV'
            elif mutation == 'owner_field': candidate['reference_coordinates'] = [1, 2]
            else: candidate['cases'][0]['requests'][1]['request_id'] = candidate['cases'][0]['requests'][0]['request_id']
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                output = Path(temp) / 'packet'
                with self.assertRaises(p.PacketError):
                    stage(candidate, Path(temp) / 'source-does-not-exist', output)
                self.assertFalse(output.exists())

    def test_identity_and_complete_byte_allocations_refused_before_source_access(self):
        neural, _ = fixture()
        for changed in ({'expected_manifest_sha256': '0' * 64}, {'total_input_byte_budget': 1},
                        {'maximum_artifact_bytes': 1}):
            with tempfile.TemporaryDirectory() as temp:
                output = Path(temp) / 'packet'
                with self.assertRaises(p.PacketError):
                    stage(neural, Path(temp) / 'absent', output, **changed)
                self.assertFalse(output.exists())

    def test_changed_or_missing_body_never_publishes_manifest(self):
        neural, bodies = fixture()
        for mutation in ('missing', 'changed', 'trailing'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                root = source(temp, bodies)
                h = neural['cases'][0]['inputs']['waveforms']
                path = root / 'inputs' / (h + '.npy')
                if mutation == 'missing': path.unlink()
                elif mutation == 'changed': path.write_bytes(bytes(len(bodies[h])))
                else: path.write_bytes(bodies[h] + b'x')
                output = Path(temp) / 'packet'
                with self.assertRaises(p.PacketError): stage(neural, root, output)
                self.assertFalse((output / 'manifest.json').exists())

    def test_authenticated_nonfinite_wrong_header_and_noncanonical_bool_refused(self):
        for role, raw, dtype in [
            ('waveforms', npy([2, 3, 3], [float('nan')] + [0] * 17), '<f8'),
            ('template', npy([3, 3], [float('inf')] + [0] * 8), '<f8'),
            ('probe_geometry', npy([3, 2], [0, 1, 2, 3, 4, float('-inf')]), '<f8'),
            ('observed_support', npy([3], [0, 1, 2], '|b1'), '|b1'),
            ('waveforms', npy([2, 3, 3], [1] * 18, '|b1'), '|b1'),
            ('waveforms', npy([3, 2, 3], [0] * 18), '<f8'),
            ('waveforms', npy([2, 3, 3], [0] * 18) + b'x', '<f8')]:
            neural, bodies = fixture()
            replace_role(neural, bodies, role, raw, dtype)
            with self.subTest(role=role, dtype=dtype), tempfile.TemporaryDirectory() as temp:
                root = source(temp, bodies)
                output = Path(temp) / 'packet'
                with self.assertRaises(p.PacketError): stage(neural, root, output)
                self.assertFalse((output / 'manifest.json').exists())

    def test_contact_mapping_consistency_and_matching_permutation(self):
        for consistent in (False, True):
            neural, bodies = fixture()
            raw = npy([3, 2], [50, 90, 10, 30, 0, 0], '<f8')
            desc = artifact('probe_geometry', [3, 2], raw)
            neural['artifacts'].append(desc)
            bodies[desc['sha256']] = raw
            neural['cases'][0]['inputs']['probe_geometry'] = desc['sha256']
            if consistent: neural['cases'][0]['channel_ids'].reverse()
            with tempfile.TemporaryDirectory() as temp:
                root = source(temp, bodies)
                output = Path(temp) / 'packet'
                if consistent:
                    self.assertEqual(stage(neural, root, output)['cases'], 880)
                else:
                    with self.assertRaisesRegex(p.PacketError, 'channel/coordinate'):
                        stage(neural, root, output)
                    self.assertFalse((output / 'manifest.json').exists())

    def test_symlinked_source_roles_and_special_file_refused(self):
        neural, bodies = fixture()
        for mutation in ('body_link', 'inputs_link', 'source_link', 'fifo'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                root = source(temp, bodies)
                h = neural['cases'][0]['inputs']['waveforms']
                path = root / 'inputs' / (h + '.npy')
                if mutation == 'body_link':
                    saved = Path(temp) / 'body'; path.rename(saved); path.symlink_to(saved)
                elif mutation == 'inputs_link':
                    saved = Path(temp) / 'bodies'; (root / 'inputs').rename(saved); (root / 'inputs').symlink_to(saved)
                elif mutation == 'source_link':
                    link = Path(temp) / 'link'; link.symlink_to(root); root = link
                else:
                    path.unlink(); os.mkfifo(path)
                with self.assertRaises(p.PacketError): stage(neural, root, Path(temp) / 'packet')

    def test_duplicate_header_keys_and_object_dtype_refused(self):
        for header in ("{'descr':'<f8','shape':(3,2),'shape':(3,2),'fortran_order':False}",
                       "{'descr':'|O','shape':(3,2),'fortran_order':False}",
                       "{'descr':'<f8','shape':(3,2),'fortran_order':0}"):
            encoded = header.encode() + b'\n'
            raw = b'\x93NUMPY\x01\x00' + struct.pack('<H', len(encoded)) + encoded + bytes(48)
            with self.assertRaises(p.PacketError):
                p.validate_array(raw, artifact('probe_geometry', [3, 2], raw))

    def test_cli_writes_external_receipt_and_never_overwrites(self):
        neural, bodies = fixture()
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = source(temp, bodies)
            raw = json.dumps(neural, indent=2).encode()
            manifest = base / 'owner.json'; manifest.write_bytes(raw)
            args = ['--manifest', str(manifest), '--manifest-sha256', hashlib.sha256(raw).hexdigest(),
                    '--manifest-bytes', str(len(raw)), '--source-root', str(root),
                    '--destination', str(base / 'packet'), '--receipt', str(base / 'receipt.json'),
                    '--total-input-byte-budget', '1000000', '--maximum-artifact-bytes', '100000']
            p.main(args)
            receipt = json.loads((base / 'receipt.json').read_text())
            self.assertEqual(receipt['status'], 'COMPLETE_PACKET')
            self.assertEqual(receipt['source_manifest_file_sha256'], hashlib.sha256(raw).hexdigest())
            with self.assertRaises(FileExistsError): p.main(args)


if __name__ == '__main__':
    unittest.main()
