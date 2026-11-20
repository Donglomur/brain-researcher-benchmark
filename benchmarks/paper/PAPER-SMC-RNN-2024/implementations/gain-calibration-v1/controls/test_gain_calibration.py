"""Focused gain-calibration controls; fresh external ARTIFACT_DIR is required.

Uses generated tiny arrays and explicit external owner/original-validation
boundaries. Does not qualify original-data calibration, inference or deployment.
"""
from __future__ import annotations
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import types
import unittest

HERE=Path(__file__).absolute().parent
ROOT=HERE.parent
RESULTS={}
SOURCE_IDENTITIES={}
SOURCE_READ_BYTES=0
ART=None
MODULES={}


def load(name,path):
    global SOURCE_READ_BYTES
    raw=path.read_bytes();SOURCE_READ_BYTES+=len(raw)
    SOURCE_IDENTITIES[str(path.relative_to(ROOT))]={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    module=types.ModuleType('_gain_controls_'+name);module.__file__=str(path)
    exec(compile(raw,str(path),'exec'),module.__dict__)
    return module


class GainCalibrationControls(unittest.TestCase):
    def test_01_canonical_metric_grid_and_source_precision(self):
        result=MODULES['selection_controls'].exercise_selection(self,MODULES['selector'],MODULES['transform'],
            MODULES['oracle'],HERE/'fixtures'/'evaluation.py')
        self.assertEqual(importlib.metadata.version('h5py'),'3.11.0')
        with self.assertRaisesRegex(ValueError,'selected scientific dependency versions'):
            MODULES['selector'].load_original_evaluator(HERE/'fixtures'/'evaluation.py')
        result['production_loader_refused_in_local_h5py_3_11_environment']=True
        result['production_dependency_guard_changed']=False
        result['named_source_read_bytes']+=18292
        RESULTS[self._testMethodName]=result

    def test_02_identity_and_all_rate_field_transform(self):
        RESULTS[self._testMethodName]=MODULES['transform_controls'].exercise_transform(
            self,MODULES['transform'],ART/'transform')

    def test_03_frozen_lineage_barrier_and_target_free_submission(self):
        RESULTS[self._testMethodName]=MODULES['core_controls'].exercise_core(self,
            MODULES['core'],MODULES['selector'],MODULES['transform'],ART/'lineage',HERE/'fixtures'/'evaluation.py')

    def test_04_whole_selection_owner_and_child_bounds(self):
        result=MODULES['runtime_controls'].exercise_host(self,MODULES['host'],MODULES['core_controls'].isolated)
        result['child']=MODULES['child_controls'].exercise_child(self,MODULES['child'],
            MODULES['core_controls'].isolated,ART/'child',MODULES['core'].source_identity())
        RESULTS[self._testMethodName]=result


def main():
    global ART
    value=os.environ.get('ARTIFACT_DIR','');path=Path(value)
    if not value or not path.is_absolute() or str(path)!=value or '..' in path.parts:
        raise ValueError('fresh canonical absolute ARTIFACT_DIR is required')
    if any(p.is_symlink() for p in (path,*path.parents)) or os.path.lexists(path) or not path.parent.is_dir():
        raise ValueError('fresh ordinary ARTIFACT_DIR with existing parent required')
    if path.is_relative_to(ROOT) or any((p/'.git').exists() for p in (path,*path.parents)):
        raise ValueError('ARTIFACT_DIR must be outside the component and every Git root')
    path.mkdir(mode=0o700);ART=path
    roster={'core':ROOT/'gain_core.py','selector':ROOT/'gain_selector.py','transform':ROOT/'gain_transform.py',
        'host':ROOT/'selector-runtime'/'gain_selector_host.py','child':ROOT/'selector-runtime'/'gain_selector_child.py',
        'oracle':HERE/'canonical_oracle.py','selection_controls':HERE/'selection_controls.py',
        'transform_controls':HERE/'transform_controls.py','core_controls':HERE/'core_controls.py',
        'runtime_controls':HERE/'runtime_controls.py','child_controls':HERE/'child_controls.py'}
    for name,file in roster.items():MODULES[name]=load(name,file)
    program=unittest.main(module=__name__,exit=False,verbosity=2)
    outcome=program.result
    files=[p for p in ART.rglob('*') if p.is_file()]
    extents=sum(p.stat().st_size for p in files)
    # The largest conservative write allowances include production rewrites and
    # failed copied HDF5 outputs. No fixture is deleted or reused between methods.
    # Count known rewrite/copy allowances even if a method fails before returning
    # its detailed receipt. All partial generated files remain available.
    rewritten=[ART/'transform'/'gain-nine-eighths.h5',ART/'lineage'/'baseline'/'prediction.h5']
    generated_write_charge=extents+2*sum(p.stat().st_size for p in rewritten if p.is_file())
    report={'schema':'smc_gain_calibration_generated_controls_v1',
        'tests_run':outcome.testsRun,'failures':len(outcome.failures),'errors':len(outcome.errors),
        'successful':outcome.wasSuccessful(),'method_results':RESULTS,
        'source_identities':SOURCE_IDENTITIES,'module_source_read_bytes':SOURCE_READ_BYTES,
        'fixture_file_count':len(files),'fixture_serialized_extent_bytes':extents,
        'fixture_cumulative_write_charge_bytes':generated_write_charge,
        'source_runtime_versions':{name:importlib.metadata.version(name) for name in ('numpy','h5py','scipy','scikit-learn')},
        'logical_read_work_bound_bytes':8912896,'original_data_accessed':False,
        'model_or_native_execution':False,'production_dependency_admission':False,
        'scientific_improvement':False,'physical_runtime_qualification':False}
    raw=(json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    if len(raw)>65536:raise ValueError('control report cap')
    (ART/'CONTROL_RESULT.json').write_bytes(raw)
    summary={'tests_run':outcome.testsRun,'failures':len(outcome.failures),'errors':len(outcome.errors),
        'successful':outcome.wasSuccessful(),'fixture_cumulative_write_charge_bytes':generated_write_charge,
        'report_bytes':len(raw),'report_sha256':hashlib.sha256(raw).hexdigest()}
    print('CONTROL_RESULT '+json.dumps(summary,sort_keys=True),flush=True)
    return 0 if outcome.wasSuccessful() else 1


if __name__=='__main__':raise SystemExit(main())
