"""Inert generated-source checks; never execute the actual coordinator."""

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import bindings
import launch_preparation as launcher


def fixture_contract_pins():
    body=b'{"generated":true}\n'
    return {name:{'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
            for name in ('support','cohort','protocol')}


def fixture(root, source=b'MARKER = "verified"\n'):
    root=root.resolve()
    prep,contract,local=root/'preparation',root/'contract',root/'local'
    for directory in (prep,contract,local):directory.mkdir(parents=True)
    coordinator=prep/'prepare_counts.py';coordinator.write_bytes(source)
    for name in bindings.MODULES:(prep/(name+'.py')).write_bytes(b'INERT = True\n')
    for name in ('DECLARED_SUPPORT.json','COHORT_BINDING.json','PROTOCOL.json'):
        (contract/name).write_text('{"generated":true}\n')
    for name in ('schema.json','timing.json'):(local/name).write_text('{"generated":true}\n')
    path=local/'BINDING.json'
    value=bindings.create_binding(root,local/'schema.json',local/'timing.json',binding_path=path)
    return path,coordinator,value


def save(path,value):
    raw=json.dumps(value,sort_keys=True,separators=(',',':')).encode()
    path.write_bytes(raw)
    return raw


def write_binding(directory, source, *, digest=None, size=None):
    binding,coordinator,value=fixture(directory,source)
    if size is not None:value['coordinator']['bytes']=size
    if digest is not None:value['coordinator']['sha256']=digest
    raw=save(binding,value)
    return binding, coordinator, raw


class LauncherTests(unittest.TestCase):
    def setUp(self):
        selected=patch.object(bindings,'CONTRACT_PINS',fixture_contract_pins())
        selected.start();self.addCleanup(selected.stop)

    def test_verified_bytes_execute_after_file_change_without_reread_and_keep_argv(self):
        source = (b'import sys\nMARKER = "verified"\n'
                  b'OBSERVED_FILE = __file__\nOBSERVED_NAME = __name__\n'
                  b'OBSERVED_ARGV = list(sys.argv)\n')
        with tempfile.TemporaryDirectory() as temporary:
            binding, coordinator, raw_binding = write_binding(Path(temporary), source)
            argv = ['launch_preparation.py', '--binding', str(binding),
                    '--binding-bytes', str(len(raw_binding)), '--binding-sha256',
                    hashlib.sha256(raw_binding).hexdigest(), '--raw-root', 'inert',
                    '--output', 'inert-output', '--execute-authenticated-preparation']
            read_once = launcher._verified_bytes
            reads = []
            def authenticate_then_change(path, size, digest):
                reads.append(str(path))
                body = read_once(path, size, digest)
                if str(path) == str(coordinator):
                    coordinator.write_bytes(b'raise AssertionError("Coordinator was reopened")\n')
                return body
            with patch.object(launcher, '_verified_bytes', side_effect=authenticate_then_change), \
                 patch.object(sys, 'argv', argv):
                observed = launcher.main()
                self.assertEqual(sys.argv, argv)
            self.assertEqual(reads, [str(binding), str(coordinator)])
            self.assertEqual(observed['MARKER'], 'verified')
            self.assertEqual(observed['OBSERVED_FILE'], str(coordinator))
            self.assertEqual(observed['OBSERVED_NAME'], '__main__')
            self.assertEqual(observed['OBSERVED_ARGV'], argv)

    def test_binding_and_coordinator_size_or_hash_mismatches_refuse_before_execution(self):
        source = b'raise AssertionError("Unverified code executed")\n'
        for bad_part in ('binding_size', 'binding_hash', 'coordinator_size', 'coordinator_hash'):
            with self.subTest(bad_part=bad_part), tempfile.TemporaryDirectory() as temporary:
                binding, _, raw = write_binding(
                    Path(temporary), source,
                    size=len(source) + 1 if bad_part == 'coordinator_size' else None,
                    digest='0' * 64 if bad_part == 'coordinator_hash' else None)
                expected_size = len(raw) + (bad_part == 'binding_size')
                expected_digest = ('0' * 64 if bad_part == 'binding_hash'
                                   else hashlib.sha256(raw).hexdigest())
                with self.assertRaises(launcher.LaunchError):
                    launcher.launch(binding, expected_size, expected_digest)

    def test_binding_relocates_and_ignores_process_working_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);original=base/'original';moved=base/'relocated'
            path,_,value=fixture(original)
            raw=save(path,value);original.rename(moved)
            elsewhere=base/'elsewhere';elsewhere.mkdir()
            previous=os.getcwd()
            try:
                os.chdir(elsewhere)
                observed=launcher.launch(moved/'local/BINDING.json',len(raw),hashlib.sha256(raw).hexdigest())
            finally:os.chdir(previous)
            self.assertEqual(observed['MARKER'],'verified')
            rebuilt=bindings.create_binding(moved,moved/'local/schema.json',moved/'local/timing.json',
                                             binding_path=moved/'local/BINDING.json')
            self.assertEqual(rebuilt,value)

    def test_duplicate_nonfinite_and_invalid_role_bindings_never_execute(self):
        with tempfile.TemporaryDirectory() as temporary:
            path,_,original=fixture(Path(temporary),b'raise AssertionError("Bad binding executed")\n')
            bad=[]
            for role in ('schema','profile','inputs','modules'):
                value=deepcopy(original)
                if role=='schema':value[role]='legacy'
                elif role=='profile':value[role]['source_files']=True
                elif role=='inputs':value[role]['root_history']=dict(value[role]['protocol'])
                else:value[role]['runtime_io']['path']='../other.py'
                bad.append(json.dumps(value).encode())
            encoded=json.dumps(original).encode()
            bad += [encoded[:-1]+b',"profile":NaN}',encoded[:-1]+b',"schema":"duplicate"}']
            for raw in bad:
                path.write_bytes(raw)
                with self.assertRaises(launcher.LaunchError):
                    launcher.launch(path,len(raw),hashlib.sha256(raw).hexdigest())


if __name__ == '__main__':
    unittest.main()
