"""Generated producer/reader controls; no original archive or native execution."""
import dataclasses
import hashlib
import importlib.util
import itertools
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import producer as p
import reader as r

WORK = 256*1024**2
OUTPUT = 256*1024
META = 512*1024
FIXTURES = 0
WRITTEN = 0


def source_fixture():
    path = HERE.parent/'original-protected-layout-v1/test_layout.py'
    spec = importlib.util.spec_from_file_location('producer_generated_source_fixture',path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0,str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(path.parent))
    geometry,data,row = module.fixture()
    data['geometry'] = geometry
    data['input_receipts'] = {'data_processed/p1_1/fr_matrix.npy':{
        'bytes':128+data['fr'].nbytes,'sha256':'1'*64,'scope':'generated_control'}}
    population,units = p.O.smooth_targets(data['fr'])
    def array_pin(a):
        return {'shape':list(a.shape),'dtype':a.dtype.str,'sha256_c_order':p.array_sha(a)}
    preparation = {'scope':'generated_control','sessions':[{
        'session':geometry['id'],'geometry':geometry,'input_receipts':data['input_receipts'],
        'prepared_population_response':array_pin(population),'prepared_unit_responses':array_pin(units)}],
        'population_weights':{'schema':'generated-population-weights/v1','rows':[{'session':'p1_1','count':3}],
                              'authentic_header_receipts':False}}
    census,geometries = module.wrapper(geometry,row)
    plan = p.StorePlan(p.encoded(census),p.encoded(geometries),p.encoded(preparation),'generated_prefix_control',3)
    return geometry,data,row,plan


def physical(root,plan,data):
    global FIXTURES,WRITTEN
    assert FIXTURES < 3
    FIXTURES += 1
    value = p.prepare_generated(root,plan,{'p1_1':data},working_limit=WORK,output_limit=OUTPUT,metadata_limit=META)
    WRITTEN += value['written_bytes']
    assert WRITTEN <= 3*OUTPUT
    return value


class ProducerControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.geometry,cls.data,cls.row,cls.plan = source_fixture()

    def test_complete4209_lineage_recovers_original_targets_and_sharing(self):
        pbase,units = p.O.smooth_targets(self.data['fr'])
        perm = np.random.RandomState(20).permutation(np.arange(self.geometry['time_bins'],dtype='<i8'))
        features,classes,jobs,requests = {},{},0,0
        for job,expected in zip(p.O.iter_jobs(self.data),p.L.iter_job_layout(self.row,self.geometry)):
            proof = p.derive_lineage(job,expected,self.geometry,self.row['support_classes'][expected['response_class']],pbase,units,perm)
            f,c = expected['feature_key_sha256'],expected['response_class']
            self.assertEqual(features.setdefault(f,proof['feature_array_sha256']),proof['feature_array_sha256'])
            self.assertEqual(classes.setdefault(c,proof['target_sha256']),proof['target_sha256'])
            jobs += 1; requests += len(proof['labels'])
        self.assertEqual(jobs,4209)
        self.assertEqual(requests,self.row['source_requests'])
        self.assertEqual(len(classes),len(self.row['support_classes']))
        census,geometry,_,layout = p._plan(self.plan,WORK)
        self.assertEqual(len(features),layout['distinct_features'])

    def test_physical_prefix_roundtrip_cache_and_exact_private_targets(self):
        with tempfile.TemporaryDirectory(dir=HERE) as folder:
            root = Path(folder)/'store'
            produced = physical(root,self.plan,self.data)
            reader = r.StoreReader(root,expected_store_sha256=produced['store']['sha256'],read_limit=8*1024**2,working_limit=WORK)
            try:
                self.assertEqual(reader.scope,'generated_prefix_control')
                self.assertFalse(reader.metadata['complete_original_store'])
                self.assertEqual(reader.weights['rows'][0]['count'],3)
                for session in reader.iter_sessions():
                    store = p.C.FileStore(session.root,session.specs,read_limit=8*1024**2,working_limit=16*1024**2,max_objects=100)
                    cache = p.C.BundleCache(store,payload_limit=512*1024,entry_limit=30,metadata_limit=512*1024,bundle_byte_limit=65536)
                    originals = list(itertools.islice(p.O.iter_jobs(self.data),3))
                    count = 0
                    for item,original in zip(session.iter_jobs(include_targets=True),originals):
                        x = store.load(item['view_job'].feature_id)
                        self.assertEqual(x.tobytes(),original['x'].tobytes())
                        self.assertEqual(item['targets'].tobytes(),original['y'].tobytes())
                        self.assertEqual(item['qid'].tobytes(),original['qid'].tobytes())
                        self.assertFalse(item['targets'].flags.writeable)
                        self.assertEqual(item['feature_path'],session.root/item['feature_spec']['relative_path'])
                        for label in np.unique(item['qid']):
                            raw = cache.get(item['view_job'],float(label))
                            actual = p.C.B.assemble_request(x,raw,item['view_job'].context,byte_limit=65536,working_limit=16*1024**2)
                            train,query = original['qid'] != label,original['qid'] == label
                            for got,want in zip(actual[:3],(original['x'][train],original['y'][train],original['x'][query])):
                                self.assertEqual(got.tobytes(),want.tobytes())
                        count += 1
                    self.assertEqual(count,3)
            finally:
                reader.close()
            self.assertTrue(reader.closed)

    def test_default_reader_never_opens_targets_or_features_and_bounds_io(self):
        with tempfile.TemporaryDirectory(dir=HERE) as folder:
            root = Path(folder)/'store'
            produced = physical(root,self.plan,self.data)
            reader = r.StoreReader(root,expected_store_sha256=produced['store']['sha256'],read_limit=8*1024**2,working_limit=WORK)
            seen = []
            original = reader._read
            def capture(relative,*args):
                seen.append(relative)
                self.assertNotIn('/private/',relative)
                return original(relative,*args)
            try:
                with mock.patch.object(reader,'_read',side_effect=capture):
                    for session in reader.iter_sessions():
                        items = list(session.iter_jobs())
                        self.assertEqual(len(items),3)
                        self.assertTrue(all('targets' not in item for item in items))
                        allowed = {session.prefix+session._specs[oid].relative_path
                                   for c in session._classes.values() for oid in (c['qid_object'],c['time_object'])}
                        self.assertTrue(all(path in allowed for path in seen if '/objects/' in path))
                        chosen = (items[2]['context'],items[0]['context'])
                        selected = list(session.iter_jobs(contexts=chosen))
                        self.assertEqual([x['context'] for x in selected],[items[0]['context'],items[2]['context']])
                        self.assertEqual(list(session.iter_jobs(contexts=())),[])
                        absent = dict(items[0]['context']); absent['layer'] = 2
                        with mock.patch.object(session,'_candidate_array',side_effect=AssertionError('selector opened arrays')):
                            with self.assertRaises(ValueError):
                                list(session.iter_jobs(contexts=(absent,)))
                        self.assertTrue(reader.failed)
            finally:
                reader.close()
            with mock.patch.object(r.os,'open',side_effect=AssertionError('body open before work admission')):
                with self.assertRaises(ValueError):
                    r.StoreReader(root,expected_store_sha256=produced['store']['sha256'],read_limit=1,working_limit=1)

    def test_mutated_private_recovery_map_poisoned_before_reuse(self):
        with tempfile.TemporaryDirectory(dir=HERE) as folder:
            root = Path(folder)/'store'
            produced = physical(root,self.plan,self.data)
            reader = r.StoreReader(root,expected_store_sha256=produced['store']['sha256'],read_limit=8*1024**2,working_limit=WORK)
            try:
                for session in reader.iter_sessions():
                    items = list(session.iter_jobs(include_targets=True))
                    cid = items[0]['support_class_sha256']
                    path = session.root/session._classes[cid]['source_rows']['path']
                    raw = path.read_bytes()
                    path.chmod(0o600)
                    path.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
                    path.chmod(0o400)
                    with self.assertRaises(ValueError):
                        next(session.iter_jobs(include_targets=True))
                    self.assertTrue(reader.failed)
            finally:
                reader.close()

    def test_generated_plan_cannot_promote_to_original_scope(self):
        forged = dataclasses.replace(self.plan,scope='original_full_source',generated_job_limit=None)
        with self.assertRaises(ValueError):
            p._plan(forged,WORK)

    def test_output_cap_refuses_before_any_metadata_bytes(self):
        with tempfile.TemporaryDirectory(dir=HERE) as folder:
            root = Path(folder)/'short'
            with self.assertRaises(ValueError):
                p.prepare_generated(root,self.plan,{'p1_1':self.data},working_limit=WORK,output_limit=64,metadata_limit=META)
            self.assertFalse((root/'STORE.json').exists())
            self.assertEqual(list(root.iterdir()),[])

    def test_original_admission_refuses_before_archive_constructor(self):
        raw = b'{}\n'
        with mock.patch.object(p.I,'ArchiveInputs',side_effect=AssertionError('authentic archive constructor reached')):
            with self.assertRaises(ValueError):
                p.prepare_original('/unused-output',{name:'/unused/'+name for name in ('data_processed.zip','DNN.zip','transcription.zip')},
                    census_path='/unused-census',preparation_path='/unused-preparation',admission_bytes=raw,
                    expected_admission_sha256=hashlib.sha256(raw).hexdigest(),read_limit=1,working_limit=WORK,
                    output_limit=1,metadata_limit=META)


if __name__ == '__main__':
    try:
        unittest.main(verbosity=2)
    finally:
        print({'generated_physical_fixtures':FIXTURES,'generated_store_bytes_written':WRITTEN,
               'gross_fixture_cap_bytes':3*OUTPUT,'authentic_array_reads':0,'models_native_runs':0})
