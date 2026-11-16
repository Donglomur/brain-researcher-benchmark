"""New package/API relocation checks only, using invented full170 inputs."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_train_only import fixture, install


def load(path):
    spec = importlib.util.spec_from_file_location('portable_marmoset_adapter', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RelocationTests(unittest.TestCase):
    def test_package_closure_without_private_dependencies(self):
        source = json.loads((HERE / 'SOURCE.json').read_text())
        self.assertEqual({r['path'] for r in source['files']}, {
            'train_only.py', 'test_train_only.py', 'test_relocation.py',
            'README.md', 'SPECIFICATION.md', 'ATTRIBUTION.md'})
        for row in source['files']:
            self.assertEqual(Path(row['path']).name, row['path'])
            body = (HERE / row['path']).read_bytes()
            self.assertEqual((len(body), hashlib.sha256(body).hexdigest()), (row['bytes'], row['sha256']))
            for forbidden in (b'/Us' + b'ers/', b'/ho' + b'me/', b'authoring/' + b'delivery-',
                              b'benchmark-engineering-' + b'evidence'):
                self.assertNotIn(forbidden, body)
        self.assertFalse(source['scientifically_qualified'])
        self.assertFalse(source['complete_candidate_packet'])

    def test_full_api_from_unrelated_directory_and_single_source_copy(self):
        policy, bodies, expected = fixture('nm_to_wn_source_only')
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder); component = base / 'portable'; component.mkdir()
            shutil.copyfile(HERE / 'train_only.py', component / 'train_only.py')
            module = load(component / 'train_only.py')
            root = base / 'invented-original'; root.mkdir(); install(root, policy, bodies)
            before = Path.cwd()
            try:
                os.chdir(base)
                result = module.prepare_training(policy,
                    policy_sha256=hashlib.sha256(module.canonical(policy)).hexdigest(),
                    source_root=root, read_byte_budget=1000000, output_byte_budget=1000000)
            finally:
                os.chdir(before)
            self.assertEqual((result['selected_cells'], result['preparations'], len(result['packets'])), (170, 2, 4))
            self.assertEqual(len({i for p in result['packets'] for i in p['cell_ids']}), 170)
            for packet in result['packets']:
                self.assertEqual(packet['stimulus'], 'NM')
                values = [x[0] for x in struct.iter_unpack('<i', packet['counts'])]
                self.assertEqual(values, expected[(packet['dataset'], 'NM', packet['seed'])])
            self.assertEqual((result['protected_response_reads'], result['original_sta_reads']), (0, 0))

    def test_portable_authority_refusal_before_any_file_open(self):
        policy, _, _ = fixture()
        with tempfile.TemporaryDirectory() as folder:
            copied = Path(folder) / 'train_only.py'; shutil.copyfile(HERE / 'train_only.py', copied)
            module = load(copied)
            for expected in (None, '0' * 64):
                with patch.object(module.os, 'open', side_effect=AssertionError('opened before policy authority')):
                    with self.assertRaises(module.InputError):
                        module.prepare_training(policy, policy_sha256=expected, source_root='unavailable',
                                                read_byte_budget=1000000, output_byte_budget=1000000)


if __name__ == '__main__':
    unittest.main()
