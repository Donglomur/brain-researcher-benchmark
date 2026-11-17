"""Generated selected-store controls; no original payload or candidate execution."""
import dataclasses
import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import producer as s
import reader as r
p=s.p
WORK=256*1024**2
WRITTEN=0

def fixture():
    path=HERE.parent/'original-protected-layout-v1/test_layout.py'
    spec=importlib.util.spec_from_file_location('selected_store_generated_fixture',path)
    module=importlib.util.module_from_spec(spec)
    sys.path.insert(0,str(path.parent))
    try:spec.loader.exec_module(module)
    finally:sys.path.remove(str(path.parent))
    geometry,data,row=module.fixture();data['geometry']=geometry
    data['input_receipts']={'data_processed/p1_1/fr_matrix.npy':{'bytes':128+data['fr'].nbytes,'sha256':'1'*64,'scope':'generated'}}
    population,units=p.O.smooth_targets(data['fr'])
    def ap(a):return {'shape':list(a.shape),'dtype':a.dtype.str,'sha256_c_order':p.array_sha(a)}
    prep={'scope':'generated_control','sessions':[{'session':geometry['id'],'geometry':geometry,
        'input_receipts':data['input_receipts'],'prepared_population_response':ap(population),'prepared_unit_responses':ap(units)}],
        'population_weights':{'schema':'generated-population-weights/v1','rows':[{'session':'p1_1','count':3}],
                              'authentic_header_receipts':False}}
    census,geometries=module.wrapper(geometry,row)
    plan=p.StorePlan(p.encoded(census),p.encoded(geometries),p.encoded(prep),'generated_prefix_control',3)
    return geometry,data,row,plan

def physical(root,plan,data):
    global WRITTEN
    value=s.prepare_generated(root,plan,{'p1_1':data},working_limit=WORK,output_limit=256*1024,metadata_limit=512*1024)
    WRITTEN+=value['written_bytes'];assert WRITTEN<=512*1024
    return value

class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.geometry,cls.data,cls.row,cls.plan=fixture()

    def test_selected_kernels_match_original4209_schedule_byte_for_byte(self):
        expected=[];visited=0
        for job in p.O.iter_jobs(self.data):
            visited+=1
            if job['field']=='population' and job['layer']==5 and job['lag_index'] in s.LAGS:
                expected.append(job)
        actual=list(s.iter_selected_jobs(self.data))
        self.assertEqual(visited,4209);self.assertEqual(len(expected),len(actual),3)
        pop,units=p.O.smooth_targets(self.data['fr'])
        permutation=np.random.RandomState(20).permutation(np.arange(self.geometry['time_bins'],dtype='<i8'))
        for got,want,planned in zip(actual,expected,s.selected_layout(self.row,self.geometry)):
            for key in s.CONTEXT_KEYS:self.assertEqual(got[key],want[key])
            for key in ('x','y','qid','time_indices'):self.assertEqual(got[key].tobytes(),want[key].tobytes())
            proof=p.derive_lineage(got,planned,self.geometry,self.row['support_classes'][planned['response_class']],pop,units,permutation)
            self.assertEqual(proof['base_kind'],'population')
        _,_,_,layout=s.selected_plan(self.plan,WORK)
        self.assertEqual(layout['counts']['features'],1);self.assertEqual(layout['counts']['response_classes'],3)
        self.assertEqual(layout['counts']['array_files'],layout['counts']['candidate_objects']+4)

    def test_selected_physical_store_cache_exact_targets_and_bound_only(self):
        with tempfile.TemporaryDirectory(dir=HERE) as temp:
            root=Path(temp)/'store';out=physical(root,self.plan,self.data)
            reader=r.StoreReader(root,expected_store_sha256=out['store']['sha256'],read_limit=8*1024**2,working_limit=WORK)
            try:
                self.assertEqual(reader.scope,s.GENERATED_SCOPE)
                self.assertFalse(reader.metadata['complete_selected_store'])
                self.assertFalse(reader.metadata['complete_original_store'])
                for session in reader.iter_sessions():
                    store=p.C.FileStore(session.root,session.specs,read_limit=8*1024**2,working_limit=16*1024**2,max_objects=100)
                    cache=p.C.BundleCache(store,payload_limit=512*1024,entry_limit=30,metadata_limit=512*1024,bundle_byte_limit=65536)
                    actual=list(session.iter_jobs(include_targets=True));expected=list(s.iter_selected_jobs(self.data))
                    self.assertEqual(len(actual),3);self.assertEqual(set(session._manifest['bases']),{'population'})
                    for item,job in zip(actual,expected):
                        x=store.load(item['view_job'].feature_id)
                        self.assertEqual(x.tobytes(),job['x'].tobytes())
                        self.assertEqual(item['targets'].tobytes(),job['y'].tobytes())
                        self.assertFalse(item['targets'].flags.writeable)
                        for held in np.unique(item['qid']):
                            raw=cache.get(item['view_job'],float(held))
                            operands=p.C.B.assemble_request(x,raw,item['view_job'].context,byte_limit=65536,working_limit=16*1024**2)
                            train,query=job['qid']!=held,job['qid']==held
                            for got,want in zip(operands[:3],(job['x'][train],job['y'][train],job['x'][query])):
                                self.assertEqual(got.tobytes(),want.tobytes())
                    chosen=list(session.iter_jobs(contexts=(actual[2]['context'],actual[0]['context'])))
                    self.assertEqual([x['context']['lag_index'] for x in chosen],[17,19])
                    self.assertEqual(list(session.iter_jobs(contexts=())),[])
            finally:reader.close()
            layout=out['metadata']['layout']
            self.assertEqual(out['files'],layout['file_count'])
            self.assertLessEqual(out['written_bytes'],layout['logical_output_upper_bytes'])

    def test_default_reader_no_targets_and_foreign_coordinate_pre_array_refusal(self):
        with tempfile.TemporaryDirectory(dir=HERE) as temp:
            root=Path(temp)/'store';out=physical(root,self.plan,self.data)
            reader=r.StoreReader(root,expected_store_sha256=out['store']['sha256'],read_limit=8*1024**2,working_limit=WORK)
            try:
                for session in reader.iter_sessions():
                    read=reader._read
                    def capture(relative,*args):
                        self.assertNotIn('/private/',relative)
                        return read(relative,*args)
                    with mock.patch.object(reader,'_read',side_effect=capture):items=list(session.iter_jobs())
                    self.assertTrue(all('targets' not in item for item in items))
                    absent=dict(items[0]['context']);absent['layer']=4
                    with mock.patch.object(session,'_candidate_array',side_effect=AssertionError('map read before selector refusal')):
                        with self.assertRaises(ValueError):list(session.iter_jobs(contexts=(absent,)))
                    self.assertTrue(reader.failed)
            finally:reader.close()
            with mock.patch.object(r.p.L,'parse',side_effect=AssertionError('metadata parse before work budget')):
                with self.assertRaises(ValueError):r.StoreReader(root,expected_store_sha256=out['store']['sha256'],read_limit=1,working_limit=1)

    def test_generated_metadata_cannot_promote_to_original_selected_scope(self):
        forged=dataclasses.replace(self.plan,scope='original_full_source',generated_job_limit=None)
        with self.assertRaises(ValueError):s.selected_plan(forged,WORK)

    def test_aggregate_publication_guard_precedes_success_marker(self):
        _,_,_,layout=s.selected_plan(self.plan,WORK)
        bound=layout['sessions'][0]
        class MetadataOnlyOutput:
            def __init__(self,*args):self.written=self.charged=self.files=0
            def write(self,name,raw):
                if name=='STORE.json':raise AssertionError('published before aggregate file-count admission')
                self.written+=len(raw);self.charged+=len(raw);self.files+=1
                return {'path':name,**p.pin(raw)}
        class MetadataOnlySession:
            def __init__(self,*args):pass
            def run(self,data):return {'path':'unused'}, {'counts':bound['counts'],'array_bytes':bound['canonical_array_bytes']}
        with mock.patch.object(s.p,'_Output',MetadataOnlyOutput),mock.patch.object(s,'_SessionWriter',MetadataOnlySession):
            with self.assertRaisesRegex(ValueError,'before publication'):
                s.prepare_generated('/unused',self.plan,{'p1_1':{}},working_limit=WORK,
                                    output_limit=256*1024,metadata_limit=512*1024)

    def test_original_admission_refuses_before_payload_or_output(self):
        raw=b'{}\n'
        with mock.patch.object(s.I,'ArchiveInputs',side_effect=AssertionError('original archive reached')):
            with self.assertRaises(ValueError):s.prepare_original('/unused',
                {k:'/unused/'+k for k in ('data_processed.zip','DNN.zip','transcription.zip')},
                census_path='/unused-census',preparation_path='/unused-preparation',admission_bytes=raw,
                expected_admission_sha256=hashlib.sha256(raw).hexdigest(),read_limit=1,working_limit=WORK,
                output_limit=1,metadata_limit=512*1024)

if __name__=='__main__':
    try:unittest.main(verbosity=2)
    finally:print({'generated_store_bytes_written':WRITTEN,'physical_fixture_gross_cap':512*1024,
                   'authentic_array_reads':0,'native_runs':0,'models_fitted':0})
