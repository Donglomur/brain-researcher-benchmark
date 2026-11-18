"""Generated source/provenance controls; never the five genuine runtime methods."""
import argparse
from copy import deepcopy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('_current_cpu_setup_generated_controls', HERE/'current_setup.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)
PROFILE = setup.read_json(HERE/'current_profile.json', setup.PROFILE_SHA256, 65536)
LEGACY = None
FIXTURE_BYTES = 0


def generated_receipt():
    # Invented qualification data for pure predicate controls, never execution.
    versions = dict(PROFILE['external_versions'])
    for project, row in PROFILE['source_distributions'].items():
        versions[project] = row['version'] or '0.0.dev1+g61c8a7b.d20261118'
    known = dict(PROFILE['known_wheel_sha256'])
    known.update(PROFILE['preserved_inherited_wheel_sha256'])
    builds = {}
    for project in setup.SOURCE_PROJECTS:
        row = {'status':'success', 'backend':'setuptools.build_meta', 'receipt_sha256':'1'*64,
               'wheel_sha256':'2'*64, 'version':versions[project]}
        if project == 'antlr4-python3-runtime':
            row['source_sdist_sha256'] = 'f224469b4168294902bb1efa80a8bf7855f24c99aef99cbefc1bcd3cce77881b'
        else:
            row['source_commit'] = PROFILE['source_distributions'][project]['commit']
        builds[project] = row
    distributions = {project:{'version':version,
        'wheel_sha256':builds[project]['wheel_sha256'] if project in builds else known[project],
        'files':{'generated.py':{'bytes':1,'sha256':'3'*64}}} for project,version in versions.items()}
    receipt = {'schema':'nuclr-installed-current-runtime/v1', 'condition':setup.CONDITION,
        'status':'qualified_installation', 'profile_sha256':setup.PROFILE_SHA256,
        'historical_environment_qualified':False, 'scientific_result':False,
        'distributions':distributions, 'builds':builds,
        'environment':{'python_version':'3.11.18','implementation':'CPython','system':'Linux','machine':'x86_64',
                       'python_executable_sha256':'4'*64, 'runner_identity_sha256':'5'*64,
                       'glibc':['glibc','2.39'],'linked_hdf5_version':'generated-not-qualified'}}
    for key in ('complete_artifact_roster_verified','wheel_record_and_abi_verified',
                'complete_installed_source_identity_verified','genuine_source_builds_verified',
                'frontend_cli_verified','runtime_dependencies_verified','brainsets_complete98_git_context_verified',
                'no_module_stubs','network_egress_disabled','owned_resource_guards_verified'):
        receipt[key] = True
    for key in ('installation_receipt_sha256','source_materialization_receipt_sha256','frontend_receipt_sha256',
                'resource_admission_sha256','runtime_artifact_manifest_sha256'):
        receipt[key] = '6'*64
    return receipt


class CurrentSetupSourceControls(unittest.TestCase):
    def test_current74_profile_and_distinct_build_setuptools(self):
        expected = setup.validate_receipt(PROFILE, generated_receipt())
        self.assertEqual(len(expected), 74)
        self.assertEqual(expected['setuptools'], '68.2.2')
        self.assertEqual(expected['numpy'], '2.4.6')
        self.assertEqual(expected['torch'], '2.12.1+cpu')
        self.assertEqual(PROFILE['build_environments']['default']['setuptools'], '80.9.0')
        self.assertEqual(PROFILE['build_environments']['brainsets']['setuptools-scm'], '10.3.4')
        self.assertIsNone(PROFILE['source_distributions']['brainsets']['version'])
        self.assertEqual(PROFILE['source_distributions']['temporaldata']['module_version'], '0.1.1')
        self.assertFalse(PROFILE['qualified'])

    def test_missing_external_qualifications_and_build_only_receipt_refused(self):
        for key in ('complete_artifact_roster_verified', 'genuine_source_builds_verified',
                    'brainsets_complete98_git_context_verified', 'network_egress_disabled', 'owned_resource_guards_verified'):
            value = generated_receipt(); value[key] = False
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                setup.validate_receipt(PROFILE, value)
        value = generated_receipt(); value['schema'] = 'nuclr-backend-direct-build/v1'
        with self.assertRaises(RuntimeError): setup.validate_receipt(PROFILE, value)

    def test_wrong_original_source_artifact_or_distribution_refused(self):
        mutations = [lambda d:d['builds']['brainsets'].__setitem__('source_commit','0'*40),
                     lambda d:d['builds']['antlr4-python3-runtime'].__setitem__('source_sdist_sha256','0'*64),
                     lambda d:d['distributions']['numpy'].__setitem__('wheel_sha256','0'*64),
                     lambda d:d['distributions']['torch'].__setitem__('version','2.12.1'),
                     lambda d:d['distributions'].pop('narwhals'),
                     lambda d:d['distributions'].__setitem__('torch-brain',d['distributions'].pop('pytorch-brain')),
                     lambda d:d.__setitem__('scientific_result',True)]
        for index, change in enumerate(mutations):
            value = generated_receipt(); change(value)
            with self.subTest(index=index), self.assertRaises((RuntimeError, KeyError)):
                setup.validate_receipt(PROFILE, value)

    def test_receipt_requires_out_of_band_hash_before_any_import(self):
        global FIXTURE_BYTES
        data = b'{"schema":"invented-fixture"}'
        with tempfile.TemporaryDirectory(prefix='source-control-',dir=HERE.parent) as directory:
            path = Path(directory)/'receipt.json'; path.write_bytes(data); FIXTURE_BYTES += len(data)
            with mock.patch.object(setup.importlib,'import_module',side_effect=AssertionError('native import forbidden')):
                with self.assertRaisesRegex(RuntimeError,'pinned'):
                    setup.read_json(path,'0'*64,1024)
                self.assertEqual(setup.read_json(path,hashlib.sha256(data).hexdigest(),1024), {'schema':'invented-fixture'})
                with self.assertRaisesRegex(RuntimeError,'bounded'):
                    setup.read_json(path,hashlib.sha256(data).hexdigest(),1)

    def test_exact_four_inherited_functions_and_five_explicit_methods(self):
        legacy = setup.load_frozen(LEGACY, setup.LOCAL_PINS['legacy'][1], '_nuclr_current_control_original')
        try:
            calls = []
            cls = setup._current_class(legacy, lambda c:calls.append(c))
            for method in setup.INHERITED:
                self.assertIs(getattr(cls,method),getattr(legacy.OriginalRuntimeControls,method))
            self.assertEqual(set(unittest.TestLoader().getTestCaseNames(cls)),set(setup.METHODS))
            suite = unittest.TestSuite(cls(method) for method in setup.METHODS)
            self.assertEqual(suite.countTestCases(),5)
            self.assertEqual([test._testMethodName for test in suite],list(setup.METHODS))
            cls.setUpClass()
            self.assertEqual(calls,[cls])
            # None of the five real test bodies, original fixtures or constructors run.
            self.assertFalse(hasattr(cls,'runtime'))
        finally:
            sys.modules.pop('_nuclr_current_control_original',None)

    def test_actual_authentication_platform_failure_precedes_target_import(self):
        with mock.patch.object(setup.platform,'machine',return_value='generated_wrong_cpu'), \
             mock.patch.object(setup.importlib,'import_module',side_effect=AssertionError('native import forbidden')):
            with self.assertRaisesRegex(RuntimeError,'observed platform differs'):
                setup.authenticate_installed(PROFILE,generated_receipt(),None)

    def test_sparse_metadata_preserves_offsets_duplicates_gaps_and_configuration(self):
        clocks = [('sb003_20200103',[[0.125,0.125,40.125],[40.125,60.125,80.125],[3600.5,3610.5]])]
        metadata = setup.manifest_from_clocks(clocks)
        self.assertEqual(metadata['sessions'][0]['frames'],8)
        rows = metadata['sessions'][0]['experiments']
        self.assertEqual([r['source_offset_seconds'] for r in rows],[0,3600,7200])
        self.assertEqual([r['shifted_first_second'] for r in rows],[0.125,40.125,3600.5])
        self.assertEqual([r['gap_from_previous_seconds'] for r in rows],[None,0.0,3520.375])
        self.assertEqual([(r['row_start'],r['row_stop']) for r in rows],[(0,3),(3,6),(6,8)])
        config = setup.configuration()
        self.assertEqual(config['batch_size'],2); self.assertEqual(config['num_workers'],0)
        self.assertEqual(config['checkpoint_epochs'],list(range(30)))
        self.assertIsNone(config['split']); self.assertIsNone(config['limit_observation_time'])
        with self.assertRaises(RuntimeError): setup.manifest_from_clocks([('bad',[[2,1]])])

    def test_frozen_loader_handles_dataclass_and_refuses_changed_source(self):
        global FIXTURE_BYTES
        body = b'from dataclasses import dataclass\n@dataclass\nclass Control:\n    value: str\n'
        with tempfile.TemporaryDirectory(prefix='source-control-',dir=HERE.parent) as directory:
            path=Path(directory)/'fixture.py';path.write_bytes(body);FIXTURE_BYTES+=len(body)
            with self.assertRaisesRegex(RuntimeError,'frozen source differs'):
                setup.load_frozen(path,'0'*64,'_never_registered')
            module=setup.load_frozen(path,hashlib.sha256(body).hexdigest(),'_generated_dataclass_control')
            try:self.assertEqual(module.Control('invented').value,'invented')
            finally:sys.modules.pop('_generated_dataclass_control',None)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--legacy',type=Path,default=HERE.parent/'official-serialization-v1/hosted_original_runtime.py')
    args=parser.parse_args();LEGACY=args.legacy
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CurrentSetupSourceControls))
    print(json.dumps({'scope':'generated_source_controls_only','tests':result.testsRun,'fixture_cumulative_bytes':FIXTURE_BYTES,
                      'native_suite_executed':False,'actual_runtime_qualified':False,'skips':len(result.skipped)}))
    raise SystemExit(0 if result.wasSuccessful() and result.testsRun==8 and not result.skipped else 1)
