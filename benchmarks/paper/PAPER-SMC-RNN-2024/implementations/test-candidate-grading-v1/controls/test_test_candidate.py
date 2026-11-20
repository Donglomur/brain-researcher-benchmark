"""Focused TEST candidate controls; generated authority is not a scientific result.

Run once with a fresh absolute ARTIFACT_DIR under the runner home, external to
this component and every Git checkout. Only these five methods are selected.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parent.parent
SOURCE_GUARDS={'SOURCE.json': {'bytes': 479, 'sha256': '55aa4b39c888edddf7cb668f95cc05fa3f2c5c7d7e9f94d93c58553f8915af4e'}, 'TEST_PROFILE.json': {'bytes': 3348, 'sha256': 'ea9dca30997ff6f5a4993ac2fe554e864b7ff2c08e3a2cfb2c902fe1a76a0ce8'}, 'test_core.py': {'bytes': 23670, 'sha256': '4775201d4916f7f25d643caf2136b2e4d87f2a3dde2b1d6f8afea75a0b24a334'}, 'transform/test_transform.py': {'bytes': 8104, 'sha256': '84f7222915dfb5ce24764507a9c9213a84e70009977bc5731419d6243796d156'}, 'grader/SOURCE.json': {'bytes': 878, 'sha256': '6e406e9d5c35d9347fde188f26e65401766b5abce5570f8fceda4029e5e558f0'}, 'grader/gain_transform.py': {'bytes': 19658, 'sha256': 'b78a4eaae4b5ea1af893ed133e9973c71f131bccadb62cb7b93aa7e13cfc5dda'}, 'grader/reference_panel.json': {'bytes': 3665, 'sha256': '209a15e2189499a9e68264df5c9f81057dd919564d98a46fb64d75b3f39af2f3'}, 'grader/scorer.py': {'bytes': 15050, 'sha256': '48638a595755138b32ff9c228804fd8c19c9ff874cd254f135fc5245ee9a25f8'}, 'grader/test_pair_child.py': {'bytes': 3851, 'sha256': '55be6ca4da6b62bf76c6fabf365e1d698a38e52d66bdd9ba77e07c1532d03a0a'}, 'grader/test_pair_grade.py': {'bytes': 30351, 'sha256': '8e39f087935d26ab8869a697dc20d76f409db4fa5bf27bbbddb1c49ec4983e2c'}, 'runtime/SOURCE.json': {'bytes': 627, 'sha256': '9a6dc413eec1be17ffab2f36098f32c5b8d863044bc45b95b598f431d65b14b3'}, 'runtime/bounded_capture.py': {'bytes': 7749, 'sha256': '0a9274a1b08b00ee778143aa5ba35e4a3bf6b27dd6e8ea8838428b0652c0949f'}, 'runtime/label_policy.py': {'bytes': 2169, 'sha256': '9c87d897215caead93206ecaa09ec2a33717609fd84a6e374d8e63f4daa330ef'}, 'runtime/owned_exit.py': {'bytes': 8088, 'sha256': 'd1d4aa36bf3893ee07e16f7086fd123c08d81ec47278efd6be3091c862c59426'}, 'runtime/test_pair_grade_host.py': {'bytes': 54568, 'sha256': '227b25e946d9f9015d77fcea6deaae5aab814c03da33d152c04366b21cbedc27'}, 'controls/fixtures/gain-kernel/SOURCE.json': {'bytes': 604, 'sha256': '34bcd3a7dc56440e58694f3275bbb59d6f46a7ddc0e3a248c10cd98399c1b44c'}, 'controls/fixtures/gain-kernel/METHOD.json': {'bytes': 3001, 'sha256': '5c10c138ccfc86fd43fd2eb8f681ce1aaf3c51235335e17b31a055b5efa647f4'}, 'controls/fixtures/gain-kernel/gain_core.py': {'bytes': 22880, 'sha256': '324ae0db0b5ffb0c7694d6d4a63eaefe133a727797d58f0c6d643222a0e402c3'}, 'controls/fixtures/gain-kernel/gain_selector.py': {'bytes': 13947, 'sha256': 'ed39f6c96c449c0b3061b2aca31f879e35833537e80963f30fa425806fd83216'}, 'controls/fixtures/gain-kernel/gain_transform.py': {'bytes': 19658, 'sha256': 'b78a4eaae4b5ea1af893ed133e9973c71f131bccadb62cb7b93aa7e13cfc5dda'}, 'controls/fixtures/gain-kernel/selector-runtime/SOURCE.json': {'bytes': 884, 'sha256': '0104cd632c855e624d076965669f1103128a569b116562181d516761839c8076'}, 'controls/fixtures/gain-kernel/selector-runtime/bounded_capture.py': {'bytes': 7749, 'sha256': '0a9274a1b08b00ee778143aa5ba35e4a3bf6b27dd6e8ea8838428b0652c0949f'}, 'controls/fixtures/gain-kernel/selector-runtime/gain_selector_child.py': {'bytes': 7908, 'sha256': 'd964c68af82faf1ac5ac1b30180e50124e46c4ed99880e5892d4ae161b290aa9'}, 'controls/fixtures/gain-kernel/selector-runtime/gain_selector_host.py': {'bytes': 53183, 'sha256': '7ab6d64e5fb9d1db12c0ef6f5ac08a0821a5f38cb4e5309c278aa015d9ff8509'}, 'controls/fixtures/gain-kernel/selector-runtime/label_policy.py': {'bytes': 2169, 'sha256': '9c87d897215caead93206ecaa09ec2a33717609fd84a6e374d8e63f4daa330ef'}, 'controls/fixtures/gain-kernel/selector-runtime/owned_exit.py': {'bytes': 8088, 'sha256': 'd1d4aa36bf3893ee07e16f7086fd123c08d81ec47278efd6be3091c862c59426'}, 'controls/transform_wiring.py': {'bytes': 6030, 'sha256': '3737a09fa5ba9949607e445631e32706301db7fd76c346e70366fe5934d93685'}, 'controls/binding_controls.py': {'bytes': 14276, 'sha256': '56f6e27c14a0c6d352445e4bd56203322b83d78ab4d9dbe4586ae631c0a59d71'}, 'controls/paired_grade_controls.py': {'bytes': 14760, 'sha256': '1a84644fbfb177e034771cb26ce4a96a36e26577381c770e75f8ad4e62a39b5f'}, 'controls/metric_assertions.py': {'bytes': 2900, 'sha256': '0002345a84a90d9ff57aab9c8d70fb9a0752fd657998a8c851add02523734ff1'}, 'controls/scale_proof_controls.py': {'bytes': 15330, 'sha256': 'e8ee265bec8761939d7c2967cde64aae2a20d5e3991ee7bd7db3ec543adacd55'}, 'controls/host_controls.py': {'bytes': 40988, 'sha256': '7780d5de0892b802e1082b1be50adc811549f996dd45e876a181f6cf16f8b048'}, 'controls/fixtures/evaluation.py': {'bytes': 18292, 'sha256': '05f49d3cdf7720ae68e0fb76113a9e450e9df3813c6c6837689f23a9be278476'}}
ART=None
OUTCOMES={}
SOURCE_IDENTITIES={}
SOURCE_AUTH_READS=0
MODULE_READS=0
MODULES={}
GENERATED_WRITE_LIMIT=3145728
CAMPAIGN_READ_WORK_LIMIT=33554432

def identity(raw):return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def descriptor(path):
    raw=path.read_bytes()
    return {'path':str(path),**identity(raw)}
def load(relative):
    global MODULE_READS
    if relative in MODULES:return MODULES[relative]
    path=ROOT/relative;raw=path.read_bytes();MODULE_READS+=len(raw)
    if identity(raw)!=SOURCE_GUARDS[relative]:raise ValueError('selected source changed: '+relative)
    name='smc_test_candidate_control_'+str(len(MODULES))
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module
    exec(compile(raw,str(path),'exec'),module.__dict__)
    MODULES[relative]=module
    return module

def extent(root):return sum(p.stat().st_size for p in root.rglob('*') if p.is_file())

class TestCandidateControls(unittest.TestCase):
    def tearDown(self):self.assertLessEqual(extent(ART),GENERATED_WRITE_LIMIT)
    def test_01_test_valid_checkpoint_and_candidate_lineage(self):
        helper=load('controls/binding_controls.py');wiring=load('controls/transform_wiring.py')
        gain=ROOT/'controls/fixtures/gain-kernel'
        OUTCOMES['binding']=helper.exercise_bindings(self,load('test_core.py'),load('grader/gain_transform.py'),
            wiring.isolated,ART/'binding',descriptor(gain/'SOURCE.json'),descriptor(gain/'selector-runtime/SOURCE.json'))
    def test_02_target_free_test_transform_wiring(self):
        helper=load('controls/transform_wiring.py')
        OUTCOMES['transform']=helper.exercise_transform_wiring(self,load('transform/test_transform.py'),
            descriptor(ROOT/'controls/fixtures/gain-kernel/SOURCE.json'),ART/'transform')
    def test_03_independent_all_eight_field_scale_proof(self):
        helper=load('controls/scale_proof_controls.py')
        OUTCOMES['scale']=helper.exercise_scaled_pair(self,load('grader/test_pair_grade.py'),
            load('grader/gain_transform.py'),ART/'scale')
    def test_04_both_snapshots_before_targets_and_four_metric_roles(self):
        helper=load('controls/paired_grade_controls.py');wiring=load('controls/transform_wiring.py')
        OUTCOMES['pair']=helper.exercise_pair(self,load('grader/test_pair_grade.py'),load('test_core.py'),
            load('controls/metric_assertions.py'),wiring.isolated,ART/'pair',ROOT/'controls/fixtures/evaluation.py')
    def test_05_bounded_host_custody_and_one_paired_child(self):
        helper=load('controls/host_controls.py')
        OUTCOMES['host']=helper.exercise_host(self,load('runtime/test_pair_grade_host.py'),load('grader/test_pair_child.py'),ART)

def main():
    global ART,SOURCE_AUTH_READS,GENERATED_WRITE_LIMIT,CAMPAIGN_READ_WORK_LIMIT
    raw=os.environ.get('ARTIFACT_DIR')
    if not raw:raise ValueError('ARTIFACT_DIR is required')
    ART=Path(raw)
    if not ART.is_absolute() or ART!=ART.resolve() or any(p.is_symlink() for p in (ART,*ART.parents)):
        raise ValueError('ARTIFACT_DIR must be canonical absolute without links')
    home=Path.home().resolve()
    if not ART.is_relative_to(home) or ART==home:raise ValueError('ARTIFACT_DIR must be a fresh child of the runner home')
    if ART.exists() or not ART.parent.is_dir():raise ValueError('fresh ARTIFACT_DIR with existing parent required')
    if ART.is_relative_to(ROOT) or ROOT.is_relative_to(ART):raise ValueError('ARTIFACT_DIR must be external to component')
    for ancestor in (ART.parent,*ART.parent.parents):
        if (ancestor/'.git').exists():raise ValueError('ARTIFACT_DIR must be outside Git checkouts')
    for relative,expected in SOURCE_GUARDS.items():
        path=ROOT/relative;raw=path.read_bytes();SOURCE_AUTH_READS+=len(raw)
        if identity(raw)!=expected:raise ValueError('source guard mismatch: '+relative)
        SOURCE_IDENTITIES[relative]=expected
    own=Path(__file__).read_bytes();SOURCE_AUTH_READS+=len(own)
    SOURCE_IDENTITIES['controls/'+Path(__file__).name]=identity(own)
    ART.mkdir(mode=0o700)
    full_roster=unittest.defaultTestLoader.getTestCaseNames(TestCandidateControls)
    if len(full_roster)!=5:raise AssertionError('exactly five changed-source methods')
    requested=[arg for arg in sys.argv[1:] if arg!='-v']
    failed_selection=['TestCandidateControls.'+full_roster[i] for i in (0,4)]
    if requested:
        if requested!=failed_selection:raise ValueError('only the explicitly selected two-method retry is supported')
        suite=unittest.defaultTestLoader.loadTestsFromNames(requested,sys.modules[__name__])
        selected_roster=[full_roster[i] for i in (0,4)]
        GENERATED_WRITE_LIMIT=1048576
        CAMPAIGN_READ_WORK_LIMIT=16777216
    else:
        suite=unittest.defaultTestLoader.loadTestsFromTestCase(TestCandidateControls)
        selected_roster=full_roster
    if suite.countTestCases()!=len(selected_roster):raise AssertionError('selected method count changed')
    result=unittest.TextTestRunner(verbosity=2 if '-v' in sys.argv else 1).run(suite)
    deleted=OUTCOMES.get('pair',{}).get('deleted_generated_snapshot_bytes',0)
    host=OUTCOMES.get('host',{}).get('accounting',{})
    host_extent=extent(ART/'host-fixtures') if (ART/'host-fixtures').exists() else 0
    host_extra=max(0,host.get('generated_write_bytes',0)-host_extent)
    # On failure partial fixture extents remain; precharged method ceilings also
    # retain writes not recoverable from a helper that did not return its counter.
    partial_charge=0 if result.wasSuccessful() else GENERATED_WRITE_LIMIT
    report={'schema':'smc_test_candidate_source_controls_v1','tests_run':result.testsRun,
        'successful':result.wasSuccessful(),'failures':len(result.failures),'errors':len(result.errors),
        'method_roster':full_roster,'selected_method_roster':selected_roster,'full_suite_discovery_count':len(full_roster),
        'source_identities':SOURCE_IDENTITIES,'outcomes':OUTCOMES,
        'source_auth_read_bytes':SOURCE_AUTH_READS,'module_load_read_bytes':MODULE_READS,
        'generated_extent_bytes':extent(ART),'deleted_generated_snapshot_bytes':deleted,
        'host_cumulative_over_extent_bytes':host_extra,
        'partial_fixture_conservative_charge_bytes':partial_charge,
        'generated_write_charge_bytes':0,'generated_write_cap_bytes':GENERATED_WRITE_LIMIT,
        'whole_campaign_read_work_upper_bytes':CAMPAIGN_READ_WORK_LIMIT,
        'original_array_or_checkpoint_or_target_used':False,'native_or_Docker_execution':False,
        'production_runtime_admission':False,'inference_or_benchmark_result':False,
        'old_source_test_methods_executed':0,
        'limitations':['fixed historical metadata and prior native completion are explicit generated authority',
          'tiny geometry is supported only at generic verifier seam; full production guards remain unchanged',
          'actual local h5py3.11 fails the unchanged selected3.10 production guards',
          'paired numerical evaluator and selected-runtime reports are explicit external boundaries',
          'no authentic original TEST delivery, checkpoint-body identity or physical owner qualification']}
    for _ in range(5):
        body=(json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
        charge=max(partial_charge,report['generated_extent_bytes']+deleted+host_extra+len(body))
        if charge==report['generated_write_charge_bytes']:break
        report['generated_write_charge_bytes']=charge
    body=(json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    if report['generated_write_charge_bytes']>GENERATED_WRITE_LIMIT:raise AssertionError('generated fixture write budget exceeded')
    with (ART/'CONTROL_RESULT.json').open('xb') as handle:handle.write(body)
    print(json.dumps({'tests_run':result.testsRun,'successful':result.wasSuccessful(),'failures':len(result.failures),
      'errors':len(result.errors),'generated_write_charge_bytes':report['generated_write_charge_bytes'],
      'control_result':str(ART/'CONTROL_RESULT.json'),'control_result_identity':identity(body)},sort_keys=True))
    return 0 if result.wasSuccessful() else 1
if __name__=='__main__':raise SystemExit(main())
