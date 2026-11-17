"""Full-cohort metadata and inert capture controls; no arrays, Docker or models."""
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SPEC=importlib.util.spec_from_file_location('reve_opaque_adapter',Path(__file__).resolve().parents[1]/'adapter.py')
a=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(a)
m=a.materials_module()
CREATED=0

def write(path,value):
    global CREATED
    raw=m.canonical(value)+b'\n';CREATED+=len(raw)
    if CREATED>8*1024**2:raise AssertionError('generated-write allocation exceeded')
    path.write_bytes(raw);os.chmod(path,0o600);return a.pin(raw)

def fixtures():
    records=[];targets=[];ordinal={'train':0,'val':0,'test':0}
    for person in range(1,110):
        split=m.split_for(person)
        for run in m.RUNS:
            extra=int((split=='val' and ordinal[split]<24) or (split=='test' and ordinal[split]<3))
            n=15+extra;ordinal[split]+=1
            ids=[f'S{person:03d}R{run:02d}-event{i:03d}' for i in range(n)]
            records.append({'participant':person,'run':run,'split':split,'signal':f'S{person:03d}R{run:02d}.npy',
                            'shape':[n,64,800],'event_ids':ids,'sha256':'a'*64})
            targets.extend({'participant':person,'run':run,'split':split,'event_id':eid,
                            'label':person%2+(0 if run in (4,8,12) else 2)} for eid in ids)
    panel={'schema':'reve-original-physionet-inputs-v1','source_commit':m.SOURCE_COMMIT,'profile':m.PROFILE,
           'source_identity':'b'*64,'units':'uV','dtype':'float64','sampling_hz':200,'channels':m.CHANNELS,
           'historical_recipe_verified':False,'records':records,'counts':a.COUNTS,'observed_epoch_count':9837,
           'published_epoch_count':9837,'published_epoch_count_matches':True,'targets_identity':m.identity(targets)}
    panel['panel_identity']=m.identity(panel);m.validate_panel(panel)
    mapping=m.mapping_document(panel)
    labels=m.project_targets(panel,{'panel_identity':panel['panel_identity'],'targets':targets})
    hashes={row['signal']:'c'*64 for row in mapping['records']}
    docs=[m.make_manifest(panel,labels,condition,mapping,hashes) for condition in ('paper_data','paper_data_code')]
    infos=a.pair_info(*docs,docs[0]['materials_identity'],docs[1]['materials_identity'],panel['panel_identity'])
    return panel,mapping,docs,infos

PANEL,MAP,DOCS,INFOS=fixtures()

def resources():
    return {'setup_seconds':2,'producer_seconds':3,'capture_seconds':2,'cleanup_seconds':2,
            'memory_bytes':134217728,'cpu_nanos':1000000000,'pids':16,'scratch_bytes':4096,
            'max_files':2,'max_directories':1,'max_file_bytes':a.RESULT_CAP,'max_output_bytes':2*a.RESULT_CAP,
            'manifest_bytes':65536,'max_cli_calls':64,'max_cli_bytes':1048576,'inventory_bytes':65536,
            'source_read_bytes':20*1024**3,'host_write_bytes':4*1024**2}

def bundle_pair(root):
    packets=[]
    for info in INFOS:
        sizes={row['signal']:row['shape'][0]*64*800*8+128 for row in info['records']}
        packets.append(a.packet_mount(info,root/info['condition'],info['manifest_pin'],sizes))
    programs=[{'path':str(root/('program'+str(i))),'kind':'directory','purpose':'program',
               'files':{'solution.py':a.pin(b'generated source, never executed')}} for i in range(2)]
    files={'encoder.safetensors':a.ENCODER,**{name:a.pin(name.encode()) for name in ('encoder-config.json','encoder-runtime.py','ENCODER_SOURCE.json')}}
    common=a.common_mount(root/'common',files)
    return a.paired_requests(INFOS,packets,programs,common,phase_ids=['generated_A','generated_B'],image='sha256:'+'d'*64,
        exposure_pins=[a.pin(b'exposureA'),a.pin(b'exposureB')],origin=time.monotonic(),deadline=time.monotonic()+120,resources=resources())

def repin(doc):
    doc['data_identity']=a.digest(doc['data']);doc.pop('materials_identity',None);doc['materials_identity']=a.digest(doc);return doc

class MetadataControls(unittest.TestCase):
    def test_complete_original_pair(self):
        self.assertEqual(len(INFOS[0]['test_ids']),1803)
        self.assertEqual(DOCS[0]['data'],DOCS[1]['data'])
        self.assertEqual(sum(r['shape'][0] for r in INFOS[0]['records']),9837)
    def test_changed_label_breaks_pair(self):
        doc=deepcopy(DOCS[1]);doc['data']['records'][0]['labels'][0]^=1;repin(doc)
        with self.assertRaises(a.Refusal):a.pair_info(DOCS[0],doc,DOCS[0]['materials_identity'],doc['materials_identity'],PANEL['panel_identity'])
    def test_public_test_label_is_rejected(self):
        doc=deepcopy(DOCS[0]);doc['data']['records'][-1]['labels']=[0];repin(doc)
        with self.assertRaises(a.Refusal):a.packet_info(doc,doc['materials_identity'],PANEL['panel_identity'])
    def test_public_test_subject_is_rejected(self):
        doc=deepcopy(DOCS[0]);doc['data']['records'][-1]['participant']=109;repin(doc)
        with self.assertRaises(a.Refusal):a.packet_info(doc,doc['materials_identity'],PANEL['panel_identity'])
    def test_missing_query_is_rejected(self):
        doc=deepcopy(DOCS[0]);doc['data']['records'].pop();repin(doc)
        with self.assertRaises(a.Refusal):a.packet_info(doc,doc['materials_identity'],PANEL['panel_identity'])
    def test_changed_selected_panel_is_rejected(self):
        with self.assertRaises(a.Refusal):a.packet_info(DOCS[0],DOCS[0]['materials_identity'],'0'*64)
    def test_condition_code_omission_is_rejected(self):
        doc=deepcopy(DOCS[1]);doc['official_code']=None;repin(doc)
        with self.assertRaises(a.Refusal):a.packet_info(doc,doc['materials_identity'],PANEL['panel_identity'])
    def test_grouped_test_rows_are_rejected(self):
        doc=deepcopy(DOCS[0]);doc['data']['records'][-1]['shape'][0]=2;repin(doc)
        with self.assertRaises(a.Refusal):a.packet_info(doc,doc['materials_identity'],PANEL['panel_identity'])
    def test_historical_recipe_cannot_be_promoted(self):
        doc=deepcopy(DOCS[0]);doc['historical_recipe_verified']=True;repin(doc)
        with self.assertRaises(a.Refusal):a.packet_info(doc,doc['materials_identity'],PANEL['panel_identity'])
    def test_paired_requests_share_assets_and_resource_operands(self):
        pair=bundle_pair(Path('/generated-only'))
        self.assertEqual(pair[0]['mounts']['/common'],pair[1]['mounts']['/common'])
        self.assertEqual(pair[0]['request']['resources'],pair[1]['request']['resources'])
        self.assertEqual([p['request']['role'] for p in pair],['A','B'])
        self.assertNotIn('official-code.tar.gz',pair[0]['mounts']['/input']['files'])
        self.assertIn('official-code.tar.gz',pair[1]['mounts']['/input']['files'])
        self.assertFalse(pair[0]['runtime_qualified']);self.assertFalse(pair[0]['scientific_budget_adopted'])
    def test_missing_encoder_runtime_is_rejected(self):
        with self.assertRaises(a.Refusal):a.common_mount('/generated',{'encoder.safetensors':a.ENCODER})
    def test_changed_encoder_is_rejected(self):
        pair=bundle_pair(Path('/generated-only'));files=deepcopy(pair[0]['mounts']['/common']['files']);files['encoder.safetensors']['sha256']='0'*64
        with self.assertRaises(a.Refusal):a.common_mount('/generated',files)
    def test_half_packet_read_grant_is_rejected(self):
        pair=bundle_pair(Path('/generated-only'));b=pair[0];r=resources();r['source_read_bytes']=b['minimum_input_hash_reads']
        with self.assertRaises(a.Refusal):a.request(INFOS[0],b['mounts']['/input'],b['mounts']['/candidate'],b['mounts']['/common'],
            phase_id='bad',image=b['request']['image'],exposure_pin=b['request']['exposure'],origin=0,deadline=100,resources=r)
    def test_run_refuses_before_provider_or_packet_read(self):
        with patch.object(a,'transport_package',side_effect=AssertionError('provider constructed')),patch.object(a,'packet_info',side_effect=AssertionError('packet read')):
            with self.assertRaises(a.RuntimeUnavailable):a.run(qualified=True,backend=object(),gpu=True)
    def test_extra_geometry_fields_are_rejected(self):
        doc=deepcopy(DOCS[0]);doc['data']['geometry']['test_labels']=[1];repin(doc)
        with self.assertRaises(a.Refusal):a.packet_info(doc,doc['materials_identity'],PANEL['panel_identity'])
    def test_foreign_coordinate_convention_is_rejected(self):
        doc=deepcopy(DOCS[0]);doc['data']['geometry']['coordinate_convention']='foreign private data';repin(doc)
        with self.assertRaises(a.Refusal):a.packet_info(doc,doc['materials_identity'],PANEL['panel_identity'])
    def test_foreign_limit_text_is_rejected(self):
        doc=deepcopy(DOCS[0]);doc['limits'].append('foreign private data');repin(doc)
        with self.assertRaises(a.Refusal):a.packet_info(doc,doc['materials_identity'],PANEL['panel_identity'])
    def test_foreign_cached_provider_module_is_rejected(self):
        a.transport_package()
        with patch.dict(sys.modules,{'_reve_existing_owned_transport.engine':SimpleNamespace(__file__='/foreign/engine.py')}):
            with self.assertRaises(a.Refusal):a.transport_package()

class CaptureControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='reve-opaque-composition-');cls.root=Path(cls.temp.name).resolve()
        cls.p,cls.contract,cls.bounds=a.transport_package();cls.bundle=bundle_pair(cls.root)[0];phase=cls.bundle['request']
        cls.deadline=phase['clock']['phase_deadline'];cls.info=INFOS[0]
        cls.control=cls.root/'control';cls.quarantine=cls.root/'quarantine'
        cls.control.mkdir(mode=0o700);cls.quarantine.mkdir(mode=0o700)
        cls.provider=cls.p.Provider(cls.control,cls.quarantine,'/usr/bin/false',cls.root/'absent.sock',
            a.pin((a.TRANSPORT/'SOURCE_MANIFEST.json').read_bytes()),{'e'*64:str(cls.root/'never-read.json')},30*1024**3,8*1024**2)
        cls.phase_dir=cls.quarantine/phase['phase_id'];cls.phase_dir.mkdir()
        cls.private=cls.root/'private';cls.private.mkdir(mode=0o700)
        cls.packet_metadata=cls.root/'packet_metadata';cls.packet_metadata.mkdir()
        write(cls.private/'panel.json',PANEL);write(cls.private/'map.json',MAP);write(cls.packet_metadata/'materials.json',DOCS[0])
        ids=cls.info['test_ids'];cls.values={eid:[i,i+1,-i,i/4096] for i,eid in enumerate(sorted(ids),1)}
        cls.result={'schema':'reve-candidate-predictions-v1','materials_identity':cls.info['materials_identity'],
                    'predictions':[{'event_id':eid,'scores':cls.values[eid]} for eid in reversed(ids)]}
        result_pin=write(cls.phase_dir/'RESULT.json',cls.result)
        request_sha=a.pin(cls.p.encoded(phase))['sha256']
        envelope={'schema':'osl_transport_output_manifest_v1','phase_id':phase['phase_id'],'request_sha256':request_sha,'files':{'RESULT.json':result_pin}}
        envelope_pin=write(cls.phase_dir/'OUTPUTS.json',envelope)
        cli={'phase':'image','returncode':0,'error_type':None,'observed_retained_bytes':0,'seconds':0,
             'client_reaped':True,'cleanup_complete':True,'cleanup_before_original_cutoff':True,
             'owned_group_absence_observed':True,'leader_exited_with_group_alive':False,'group_probe_or_cleanup_error':None}
        cls.receipt={'schema':'osl_owned_phase_receipt_v1','phase_id':phase['phase_id'],'request_sha256':request_sha,
            **{k:phase[k] for k in ('action','role','image','source','exposure')},'status':'captured',
            'all_native_resources_closed':True,'cli_reaped':True,'producer_closed_before_capture':True,'error':None,'oom':False,
            'deadline_exceeded':False,'retired_resources':[{'kind':kind,'name':name,'closed':True,'absence_observed':True,'creation_outcome_unknown':False}
                 for kind,name in [('container','producer'),('container','holder'),('volume','output')]],
            'natural_exit':{'Status':'exited','Running':False,'Dead':False,'Pid':0,'ExitCode':0,'OOMKilled':False},
            'command_metadata':[cli],'enforced_resource_limits':phase['resources'],
            'input_before':cls.bounds.mount_identity(cls.bundle['mounts']),'input_after':cls.bounds.mount_identity(cls.bundle['mounts']),
            'timing':{'original_deadline':cls.deadline},'qualification_inherited':False,'scientific_qualification':False,
            'output_inventory':{'complete':True,'files':{'RESULT.json':result_pin,'OUTPUTS.json':envelope_pin}},'quarantine_root':str(cls.phase_dir)}
        c=cls.control/phase['phase_id'];c.mkdir()
        receipt_pin=write(c/'RECEIPT.json',cls.receipt)
        cls.returned={'receipt':cls.receipt,'receipt_pin':receipt_pin}
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_real_observer_and_original_private_restore(self):
        global CREATED
        # Explicit test-only replacement of the closed installation gate, plus
        # an inert phase result. Neither replacement exists in a public API.
        with patch.object(a,'_require_installation',return_value=None),patch.object(self.p.Provider,'execute_phase',return_value=self.returned) as execute:
            captured=a._compose_owned_phase(self.provider,self.bundle,self.deadline,lambda *args:None,self.info)
        execute.assert_called_once();self.assertFalse(captured['runtime_qualification'])
        out=self.private/'restored.json'
        result=a.restore_private(captured,panel_path=self.private/'panel.json',mapping_path=self.private/'map.json',
            materials_path=self.packet_metadata/'materials.json',output=out,expected_panel_identity=PANEL['panel_identity'],
            expected_mapping_identity=MAP['mapping_identity'],expected_materials_identity=self.info['materials_identity'])
        CREATED+=out.stat().st_size;self.assertLess(CREATED,8*1024**2)
        restored=json.loads(out.read_bytes())['predictions']
        self.assertEqual(restored,[{'event_id':r['source_event_id'],'scores':self.values[r['event_id']]} for r in MAP['records']])
        self.assertEqual(result['test_predictions'],1803)
    def test_arbitrary_backend_is_rejected(self):
        with patch.object(a,'_require_installation',return_value=None):
            with self.assertRaises(a.Refusal):a._compose_owned_phase(object(),self.bundle,self.deadline,lambda *args:None,self.info)
    def test_internal_dispatch_also_refuses_before_execute(self):
        with patch.object(self.p.Provider,'execute_phase',side_effect=AssertionError('native dispatch')):
            with self.assertRaises(a.RuntimeUnavailable):a._compose_owned_phase(self.provider,self.bundle,self.deadline,lambda *args:None,self.info)
    def test_wrong_material_condition_refused_before_observe(self):
        with patch.object(self.p.Provider,'observe',side_effect=AssertionError('unbound observation')):
            with self.assertRaises(a.Refusal):a._collect_observed(self.provider,self.bundle,self.returned,self.deadline,INFOS[1])
    def test_collection_reads_debit_whole_provider(self):
        before=self.provider.read_used
        result=a._collect_observed(self.provider,self.bundle,self.returned,self.deadline,self.info)
        self.assertEqual(self.provider.read_used-before,self.returned['receipt_pin']['bytes']+result['collection_metadata_read_bytes'])
        self.assertEqual(result['collection_metadata_read_bytes'],sum(v['bytes'] for v in self.receipt['output_inventory']['files'].values()))
    def test_collection_respects_remaining_read_ceiling(self):
        before=self.provider.read_used;size=self.returned['receipt_pin']['bytes']
        remaining=size+sum(v['bytes'] for v in self.receipt['output_inventory']['files'].values())-5
        with patch.object(self.provider,'read_limit',before+remaining):
            with self.assertRaises(ValueError):a._collect_observed(self.provider,self.bundle,self.returned,self.deadline,self.info)
        self.assertGreater(self.provider.read_used,before+size)
    def test_independent_observer_disagreement_is_rejected(self):
        changed=deepcopy(self.receipt);changed['role']='B'
        with patch.object(self.p.Provider,'observe',return_value={'receipt':changed}):
            with self.assertRaises(a.Refusal):a._collect_observed(self.provider,self.bundle,self.returned,self.deadline,self.info)
    def assert_bad_receipt(self,mutate):
        changed=deepcopy(self.receipt);mutate(changed);returned={'receipt':changed,'receipt_pin':self.returned['receipt_pin']}
        with patch.object(self.p.Provider,'observe',return_value={'receipt':changed}):
            with self.assertRaises((a.Refusal,ValueError)):a._collect_observed(self.provider,self.bundle,returned,self.deadline,self.info)
    def test_partial_cleanup_is_rejected(self):self.assert_bad_receipt(lambda r:r.update(all_native_resources_closed=False))
    def test_duplicate_resource_closure_is_rejected(self):self.assert_bad_receipt(lambda r:r['retired_resources'].__setitem__(1,deepcopy(r['retired_resources'][0])))
    def test_wrong_role_is_rejected(self):self.assert_bad_receipt(lambda r:r.update(role='B'))
    def test_wrong_image_is_rejected(self):self.assert_bad_receipt(lambda r:r.update(image='sha256:'+'0'*64))
    def test_changed_mount_identity_is_rejected(self):self.assert_bad_receipt(lambda r:r.update(input_after={}))
    def test_failed_cli_is_rejected(self):self.assert_bad_receipt(lambda r:r['command_metadata'][0].update(returncode=1))
    def test_qualification_promotion_is_rejected(self):self.assert_bad_receipt(lambda r:r.update(qualification_inherited=True))
    def test_oom_is_rejected(self):self.assert_bad_receipt(lambda r:r.update(oom=True))
    def test_changed_result_material_identity_is_rejected(self):
        result=deepcopy(self.result);result['materials_identity']=DOCS[1]['materials_identity']
        with self.assertRaises(a.Refusal):a.admit_result(result,self.info)
    def test_duplicate_prediction_is_rejected(self):
        result=deepcopy(self.result);result['predictions'][-1]=result['predictions'][0]
        with self.assertRaises(a.Refusal):a.admit_result(result,self.info)
    def test_missing_prediction_is_rejected(self):
        result=deepcopy(self.result);result['predictions'].pop()
        with self.assertRaises(a.Refusal):a.admit_result(result,self.info)
    def test_nonfinite_score_is_rejected(self):
        result=deepcopy(self.result);result['predictions'][0]['scores'][0]=float('nan')
        with self.assertRaises(a.Refusal):a.admit_result(result,self.info)
    def test_boolean_class_is_rejected(self):
        result=deepcopy(self.result);result['predictions'][0]={'event_id':result['predictions'][0]['event_id'],'prediction':True}
        with self.assertRaises(a.Refusal):a.admit_result(result,self.info)

if __name__=='__main__':
    try:program=unittest.main(exit=False,verbosity=2)
    finally:print(json.dumps({'generated_logical_bytes_created_and_reclaimed':CREATED,'authentic_arrays':0,'Docker_calls':0,'models':0}))
    raise SystemExit(0 if program.result.wasSuccessful() else 1)
