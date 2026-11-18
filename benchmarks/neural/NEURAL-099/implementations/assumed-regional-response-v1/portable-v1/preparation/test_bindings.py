"""Tiny generated metadata/source fixtures; never execute native preparation."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import bindings
import prepare_counts
from test_launch_preparation import fixture,save,fixture_contract_pins


class BindingTests(unittest.TestCase):
    def setUp(self):
        for module in (bindings,prepare_counts):
            selected=patch.object(module,'CONTRACT_PINS',fixture_contract_pins())
            selected.start();self.addCleanup(selected.stop)

    def test_factory_returns_only_required_portable_roles_and_no_authority_token(self):
        with tempfile.TemporaryDirectory() as temporary:
            path,coordinator,value=fixture(Path(temporary))
            self.assertEqual(set(value),{'schema','profile','coordinator','modules','inputs'})
            self.assertEqual(set(value['inputs']),{'schema','timing','support','cohort','protocol'})
            self.assertEqual(len(value['modules'])+1,6)
            self.assertEqual(bindings.resolve_path(path,value['coordinator']['path']),coordinator)
            self.assertTrue(all(set(pin)=={'bytes','sha256'} for pin in value['modules'].values()))
            self.assertNotIn(str(Path(temporary)),json.dumps(value))
            self.assertFalse(path.exists())
            copied=bindings.validate_binding(value);copied['profile']['source_files']=1
            self.assertEqual(value['profile']['source_files'],26)

    def test_factory_uses_actual_nondefault_binding_location(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);_,coordinator,_=fixture(root)
            target=root/'nested/deeper/BINDING.json'
            value=bindings.create_binding(root,root/'local/schema.json',root/'local/timing.json',binding_path=target)
            self.assertEqual(bindings.resolve_path(target,value['coordinator']['path']),coordinator)
            self.assertEqual(bindings.resolve_path(target,value['inputs']['schema']['path']),(root/'local/schema.json').resolve())
            self.assertFalse(target.exists())

    def test_exact_fields_relative_locators_and_integer_pin_types_are_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            _,_,original=fixture(Path(temporary))
            changes=[]
            value=deepcopy(original);value['inputs'].pop('protocol');changes.append(value)
            value=deepcopy(original);value['inputs']['history']=dict(value['inputs']['timing']);changes.append(value)
            value=deepcopy(original);value['coordinator']['path']='/absolute/source.py';changes.append(value)
            value=deepcopy(original);value['modules']['runtime_io']['bytes']=True;changes.append(value)
            value=deepcopy(original);value['modules']['runtime_io']['path']='elsewhere.py';changes.append(value)
            value=deepcopy(original);value['inputs']['schema']['sha256']='ABC';changes.append(value)
            for value in changes:
                with self.assertRaises(ValueError):bindings.validate_binding(value)

    def test_strict_json_and_bounded_metadata_refuse(self):
        for body in (b'{"a":1,"a":2}',b'{"a":NaN}',b'{"a":Infinity}',b'{"a":1e400}'):
            with self.assertRaises(ValueError):bindings.strict_json(body)
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);path,_,_=fixture(root)
            schema=root/'local/schema.json';schema.write_bytes(b'x'*33)
            with patch.object(bindings,'MAX_METADATA_BYTES',32),self.assertRaises(ValueError):
                bindings.create_binding(root,schema,root/'local/timing.json',binding_path=path)
            schema.write_bytes(b'{"a":1,"a":2}')
            with self.assertRaises(ValueError):
                bindings.create_binding(root,schema,root/'local/timing.json',binding_path=path)

    def test_coordinator_intake_agrees_with_factory_before_module_or_data_access(self):
        class MetadataAccepted(Exception):pass
        with tempfile.TemporaryDirectory() as temporary:
            path,coordinator,original=fixture(Path(temporary))
            def arguments(raw):
                return ['--binding',str(path),'--binding-bytes',str(len(raw)),
                        '--binding-sha256',hashlib.sha256(raw).hexdigest(),
                        '--raw-root','/unused-generated','--output','/unused-generated-output',
                        '--execute-authenticated-preparation']
            raw=save(path,original)
            with patch.object(prepare_counts,'__file__',str(coordinator)), \
                 patch.object(prepare_counts,'_load_modules',side_effect=MetadataAccepted) as load:
                with self.assertRaises(MetadataAccepted):prepare_counts.main(arguments(raw))
                load.assert_called_once_with(original['modules'])
            value=deepcopy(original);value['inputs']['root_history']=dict(value['inputs']['protocol'])
            raw=save(path,value)
            with patch.object(prepare_counts,'__file__',str(coordinator)), \
                 patch.object(prepare_counts,'_load_modules',side_effect=AssertionError('No source load expected')):
                with self.assertRaises(ValueError):prepare_counts.main(arguments(raw))

    def test_changed_protocol_fails_factory_and_runtime_even_with_its_new_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);path,coordinator,original=fixture(root)
            body=b'{"changed_protocol":true}\n'
            (root/'contract/PROTOCOL.json').write_bytes(body)
            with self.assertRaisesRegex(ValueError,'selected published contract: protocol'):
                bindings.create_binding(root,root/'local/schema.json',root/'local/timing.json',binding_path=path)
            changed=deepcopy(original)
            changed['inputs']['protocol'].update(bytes=len(body),sha256=hashlib.sha256(body).hexdigest())
            raw=save(path,changed)
            args=['--binding',str(path),'--binding-bytes',str(len(raw)),
                  '--binding-sha256',hashlib.sha256(raw).hexdigest(),
                  '--raw-root','/unused-generated','--output','/unused-generated-output',
                  '--execute-authenticated-preparation']
            with patch.object(prepare_counts,'__file__',str(coordinator)), \
                 patch.object(prepare_counts,'_load_modules',side_effect=AssertionError('No module access expected')):
                with self.assertRaisesRegex(ValueError,'selected published contract: protocol'):
                    prepare_counts.main(args)


if __name__=='__main__':unittest.main(verbosity=2)
