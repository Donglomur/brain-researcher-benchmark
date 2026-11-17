"""Generated fixed-provider controls; all subprocess creation is forbidden."""
import hashlib
import io
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import fixed_provider as p
worker=p._source(HERE/'time_worker.py',p.WORKER_SHA)
WORK=32*1024**2

def config(jobs=1,requests=3):
    return {'schema':'language-fixed-time-provider/v1','scope':p.GENERATED,'candidate_sha256':p.WORKER_SHA,
        'provider_source_sha256':p.identity(),'store_sha256':'1'*64,'schedule_sha256':'2'*64,'condition':'paper_data',
        'python':{'path':'/unused/generated-python','bytes':1,'sha256':'3'*64,'version':sys.version.split()[0]},
        'caps':{'working_bytes':WORK,'bundle_bytes':65536,'feature_read_bytes':65536,'runtime_read_bytes':32768,
            'stdin_bytes':65536,'stdout_bytes':65536,'stderr_bytes':65536,'response_bytes':65536,
            'journal_bytes':131072,'max_jobs':jobs,'max_requests':requests,'job_seconds':2,
            'cleanup_seconds':1,'run_seconds':60,'stderr_per_job_bytes':128}}

class FakeExecutor:
    def __init__(self):self.calls=[];self.closed=True;self.bad=False
    def __call__(self,frame,maximum,deadline):
        self.calls.append(frame)
        times=worker.read_frame(io.BytesIO(frame));raw=worker.encode_prediction(times)
        assert len(raw)<=maximum
        receipt={'schema':'language-fixed-job-process/v1','generated':True,'pid':None,
            'natural_exit_zero':True,'owned_group_absent':self.closed,'pipes_closed':True,
            'stdin_bytes':len(frame),'stdout_bytes':len(raw),'stderr_bytes':0,'source_sha256':p.WORKER_SHA,
            'exec_reset':False,'containment_qualified':False}
        if self.bad:raw=b'bad'
        return {'stdout':raw,'stderr':b'','receipt':receipt}

def fixture(root):
    q=np.array([3,-2,9,-2,3,9,9,-2,3],dtype='<f8')
    t=np.array([0,1,2,5,8,13,21,34,55],dtype='<i8')
    y=np.arange(len(q),dtype='<f8').reshape(-1,1)
    x=np.arange(len(q)*30,dtype='<f8').reshape(-1,30)
    f=io.BytesIO();np.save(f,x,allow_pickle=False);raw=f.getvalue()
    path=root/'feature.npy';path.write_bytes(raw);path.chmod(0o400)
    spec={'bytes':len(raw),'sha256':p.sha(raw),'fortran_order':False}
    return q,t,y,path,spec

def request(q,t,y,held,spec,context):
    raw=p.B.HEADER.pack(p.B.MAGIC,1,0,len(q),int(np.count_nonzero(q!=held)),1,float(held))
    raw+=q.tobytes()+t.tobytes()+y[q!=held].astype('<f8').tobytes()
    desc=p.B.make_descriptor(raw,p.J._source_context(context),feature_sha256=spec['sha256'],feature_bytes=spec['bytes'],
        feature_fortran_order=False,byte_limit=65536,working_limit=WORK)
    return raw,desc

class FixedProviderControls(unittest.TestCase):
    def setUp(self):
        self.forbid=patch.object(p.subprocess,'Popen',side_effect=AssertionError('Native child forbidden in generated controls'))
        self.forbid.start()
    def tearDown(self):self.forbid.stop()

    def test_two_jobs_six_derived_requests_one_worker_per_job_exact_rows_and_journal(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            root=Path(tmp);q,t,y,path,spec=fixture(root);fake=FakeExecutor()
            provider=p.FixedProvider(config(2,6),None,evidence_root=root/'evidence',executor=fake)
            for context in p.J.ENDPOINT.contexts()[:2]:
                handle=provider.prepare_feature(path,spec,rows=len(q))
                for held in np.unique(q):
                    raw,desc=request(q,t,y,held,spec,context)
                    prediction,closure=provider.run_request(handle,raw,desc)
                    value=np.load(io.BytesIO(prediction),allow_pickle=False)
                    np.testing.assert_array_equal(value[:,0],((t[q==held]%17)-8)/8)
                    self.assertEqual(closure['transport_sha256'],p.sha(prediction))
                    self.assertEqual(closure['request_sha256'],desc.public_id)
                    self.assertTrue(closure['owned_processes_absent'])
                provider.release_feature(handle)
            result=provider.finish();provider.close();provider.close()
            self.assertEqual(result['worker_executions'],2);self.assertEqual(result['derived_responses'],6)
            self.assertTrue(result['generated']);self.assertFalse(result['native_containment_qualified'])
            self.assertFalse(result['scientific_qualification']);self.assertEqual(len(fake.calls),2)
            expected_frame=struct.pack('<8sQ',b'LNGTIME1',len(t))+t.tobytes()
            self.assertEqual(fake.calls,[expected_frame,expected_frame])
            lines=[p.parse(r) for r in (root/'evidence/JOBS.jsonl').read_bytes().splitlines()]
            self.assertEqual([r['kind'] for r in lines].count('worker_closed'),2)
            derived=[r for r in lines if r['kind']=='derived_requests_complete']
            self.assertEqual([r['derived_responses'] for r in derived],[3,3])
            self.assertTrue(all(r['per_request_processes'] is False for r in derived))
            self.assertEqual(result['journal_sha256'],p.sha((root/'evidence/JOBS.jsonl').read_bytes()))

    def test_response_and_feature_values_never_enter_fixed_worker_or_change_predictions(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            root=Path(tmp);q,t,y,path,spec=fixture(root);records=[]
            for index,values in enumerate((y,y*999-200)):
                if index:
                    changed=io.BytesIO();np.save(changed,np.full((len(q),30),99999.,dtype='<f8'),allow_pickle=False)
                    path=root/'changed-feature.npy';path.write_bytes(changed.getvalue());path.chmod(0o400)
                    spec={'bytes':len(changed.getvalue()),'sha256':p.sha(changed.getvalue()),'fortran_order':False}
                fake=FakeExecutor();provider=p.FixedProvider(config(),None,evidence_root=root/('e'+str(index)),executor=fake)
                handle=provider.prepare_feature(path,spec,rows=len(q));outputs=[]
                for held in np.unique(q):
                    raw,desc=request(q,t,values,held,spec,p.J.ENDPOINT.contexts()[0])
                    outputs.append(provider.run_request(handle,raw,desc)[0])
                provider.release_feature(handle);provider.finish();records.append((fake.calls,outputs))
            self.assertEqual(records[0],records[1])

    def test_changed_maps_after_first_request_fail_before_second_worker_and_poison(self):
        for changed in ('time','qid'):
            with self.subTest(changed=changed),tempfile.TemporaryDirectory(dir=HERE) as tmp:
                root=Path(tmp);q,t,y,path,spec=fixture(root);fake=FakeExecutor()
                provider=p.FixedProvider(config(),None,evidence_root=root/'e',executor=fake)
                handle=provider.prepare_feature(path,spec,rows=len(q));c=p.J.ENDPOINT.contexts()[0]
                raw,d=request(q,t,y,-2,spec,c);provider.run_request(handle,raw,d)
                q2,t2=q.copy(),t.copy()
                if changed=='time':t2+=1
                else:q2[[0,2]]=q2[[2,0]]
                raw,d=request(q2,t2,y,3,spec,c)
                with self.assertRaisesRegex(ValueError,'Identical full public'):provider.run_request(handle,raw,d)
                self.assertTrue(provider.failed);self.assertEqual(len(fake.calls),1);provider.close()

    def test_wrong_first_or_duplicate_held_request_cannot_advance_producer(self):
        for duplicate in (False,True):
            with self.subTest(duplicate=duplicate),tempfile.TemporaryDirectory(dir=HERE) as tmp:
                root=Path(tmp);q,t,y,path,spec=fixture(root);fake=FakeExecutor()
                provider=p.FixedProvider(config(),None,evidence_root=root/'e',executor=fake)
                handle=provider.prepare_feature(path,spec,rows=len(q));c=p.J.ENDPOINT.contexts()[0]
                if duplicate:
                    raw,d=request(q,t,y,-2,spec,c);provider.run_request(handle,raw,d)
                raw,d=request(q,t,y,-2 if duplicate else 3,spec,c)
                with self.assertRaises(ValueError):provider.run_request(handle,raw,d)
                self.assertEqual(len(fake.calls),int(duplicate));self.assertTrue(provider.failed);provider.close()

    def test_actual_scope_refuses_injected_executor_or_missing_admission_before_outputs(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            root=Path(tmp);c=config(42,5685);c['scope']=p.ORIGINAL
            with self.assertRaisesRegex(ValueError,'rejects injected'):
                p.FixedProvider(c,None,evidence_root=root/'e1',executor=FakeExecutor())
            with self.assertRaisesRegex(ValueError,'root control admission'):
                p.FixedProvider(c,None,evidence_root=root/'e2')
            self.assertFalse((root/'e1').exists());self.assertFalse((root/'e2').exists())

    def test_changed_global_programme_or_source_identity_refuses(self):
        for key in ('candidate_sha256','provider_source_sha256'):
            with self.subTest(key=key),tempfile.TemporaryDirectory(dir=HERE) as tmp:
                c=config();c[key]='0'*64
                with self.assertRaises(ValueError):p.FixedProvider(c,None,evidence_root=Path(tmp)/'e',executor=FakeExecutor())

    def test_pipe_reservations_precede_executor_and_partial_counts_cannot_finish(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            root=Path(tmp);q,t,y,path,spec=fixture(root);fake=FakeExecutor();c=config();c['caps']['stdout_bytes']=1
            provider=p.FixedProvider(c,None,evidence_root=root/'e',executor=fake)
            handle=provider.prepare_feature(path,spec,rows=len(q));raw,d=request(q,t,y,-2,spec,p.J.ENDPOINT.contexts()[0])
            with self.assertRaisesRegex(ValueError,'stdout_bytes exhausted'):provider.run_request(handle,raw,d)
            self.assertEqual(fake.calls,[]);self.assertTrue(provider.failed)
            with self.assertRaises(ValueError):provider.finish()
            provider.close()

    def test_unclosed_worker_or_changed_transport_cannot_emit_derived_prediction(self):
        for bad in ('closure','bytes'):
            with self.subTest(bad=bad),tempfile.TemporaryDirectory(dir=HERE) as tmp:
                root=Path(tmp);q,t,y,path,spec=fixture(root);fake=FakeExecutor()
                if bad=='closure':fake.closed=False
                else:fake.bad=True
                provider=p.FixedProvider(config(),None,evidence_root=root/'e',executor=fake)
                handle=provider.prepare_feature(path,spec,rows=len(q));raw,d=request(q,t,y,-2,spec,p.J.ENDPOINT.contexts()[0])
                with self.assertRaises(ValueError):provider.run_request(handle,raw,d)
                self.assertEqual(provider.requests,0);self.assertTrue(provider.failed);provider.close()

    def test_exact_feature_hash_and_small_working_bound_fail_before_worker(self):
        for bad in ('hash','working'):
            with self.subTest(bad=bad),tempfile.TemporaryDirectory(dir=HERE) as tmp:
                root=Path(tmp);q,t,y,path,spec=fixture(root);fake=FakeExecutor();c=config()
                if bad=='hash':spec['sha256']='0'*64
                else:c['caps']['working_bytes']=16*1024**2
                provider=p.FixedProvider(c,None,evidence_root=root/'e',executor=fake)
                with self.assertRaises(ValueError):provider.prepare_feature(path,spec,rows=len(q))
                self.assertEqual(fake.calls,[]);provider.close()

    def test_runtime_source_read_cap_precedes_worker_source_read(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            c=config();c['caps']['runtime_read_bytes']=1
            with patch.object(p,'read_regular',side_effect=AssertionError('Read beyond admission')):
                with self.assertRaisesRegex(ValueError,'runtime_read_bytes exhausted'):
                    p.FixedProvider(c,None,evidence_root=Path(tmp)/'e',executor=FakeExecutor())

    def test_response_output_admission_precedes_row_gather_allocation(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            root=Path(tmp);q,t,y,path,spec=fixture(root);c=config();c['caps']['response_bytes']=1
            fake=FakeExecutor();provider=p.FixedProvider(c,None,evidence_root=root/'e',executor=fake)
            handle=provider.prepare_feature(path,spec,rows=len(q));raw,d=request(q,t,y,-2,spec,p.J.ENDPOINT.contexts()[0])
            np.unique(q)  # Complete NumPy's lazy helper import before instrumentation.
            original=np.frombuffer
            def guarded(value,*args,**kwargs):
                if provider.active is not None and value is provider.active.get('payload'):
                    raise AssertionError('Row gather before response output admission')
                return original(value,*args,**kwargs)
            try:
                with patch.object(np,'frombuffer',side_effect=guarded):
                    with self.assertRaisesRegex(ValueError,'response_bytes exhausted'):provider.run_request(handle,raw,d)
                self.assertEqual(provider.requests,0);self.assertEqual(len(fake.calls),1)
            finally:provider.close()

    def test_worker_source_working_admission_precedes_read(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            c=config();c['caps']['working_bytes']=1024
            with patch.object(p,'read_regular',side_effect=AssertionError('Unadmitted source allocation')):
                with self.assertRaisesRegex(ValueError,'Worker source workspace'):
                    p.FixedProvider(c,None,evidence_root=Path(tmp)/'e',executor=FakeExecutor())

    def test_broken_job_release_cannot_claim_completed_roster_and_close_is_idempotent(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            root=Path(tmp);q,t,y,path,spec=fixture(root);provider=p.FixedProvider(config(),None,evidence_root=root/'e',executor=FakeExecutor())
            handle=provider.prepare_feature(path,spec,rows=len(q))
            with self.assertRaises(ValueError):provider.release_feature(handle)
            self.assertTrue(provider.failed);self.assertEqual(provider.jobs,0)
            provider.close();provider.close();self.assertTrue(provider.journal.closed)

    def test_failed_request_retirement_preserves_primary_error_for_collector(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            root=Path(tmp);q,t,y,path,spec=fixture(root);provider=p.FixedProvider(config(),None,evidence_root=root/'e',executor=FakeExecutor())
            handle=provider.prepare_feature(path,spec,rows=len(q));raw,d=request(q,t,y,3,spec,p.J.ENDPOINT.contexts()[0])
            with self.assertRaisesRegex(ValueError,'First canonical held qid'):
                try:provider.run_request(handle,raw,d)
                finally:provider.release_feature(handle)
            self.assertIsNone(provider.active);self.assertTrue(provider.failed);provider.close()

    def test_deadline_and_descriptor_identity_refuse_before_worker(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            root=Path(tmp);q,t,y,path,spec=fixture(root);fake=FakeExecutor()
            provider=p.FixedProvider(config(),None,evidence_root=root/'e',executor=fake)
            handle=provider.prepare_feature(path,spec,rows=len(q));raw,d=request(q,t,y,-2,spec,p.J.ENDPOINT.contexts()[0])
            with self.assertRaises(ValueError):provider.run_request(handle,raw,{'public_json':d.public_json,'public_id':'0'*64})
            self.assertEqual(fake.calls,[]);provider.close()
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            provider=p.FixedProvider(config(),None,evidence_root=Path(tmp)/'e',executor=FakeExecutor())
            provider.deadline=provider.started
            with self.assertRaisesRegex(ValueError,'Whole-run deadline'):provider.finish()
            provider.close()

if __name__=='__main__':unittest.main(verbosity=2)
