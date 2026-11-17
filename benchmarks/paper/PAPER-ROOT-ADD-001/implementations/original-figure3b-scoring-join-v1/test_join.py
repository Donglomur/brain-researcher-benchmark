"""Generated selected-endpoint controls; no original arrays/provider/model run."""
import ast
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import join as j
BYTE=65536
WORK=32*1024**2
PINS={'store_sha256':'1'*64,'candidate_sha256':'2'*64,'schedule_sha256':'3'*64,'provider_source_sha256':'4'*64}


def run(original=False,count=2):
    extra={} if original else {'generated_contexts':list(j.ENDPOINT.coordinates()[:count]),'generated_requests':3*count}
    return j.make_run(**PINS,condition='paper_data',working_limit=WORK,**extra)


def fixture(context,count=3):
    qid=np.arange(count,dtype='<f8')
    # One row per label is sufficient for generated pooled-row recovery controls.
    times=np.arange(count,dtype='<i8')
    x=np.arange(count*30,dtype='<f8').reshape(count,30)
    y=(np.arange(count,dtype='<f8')**2+1).reshape(count,1)
    stream=io.BytesIO();np.save(stream,x,allow_pickle=False);rawx=stream.getvalue()
    feature={'sha256':j.sha(rawx),'bytes':len(rawx),'fortran_order':False}
    def bundle(held):
        return b''.join((j.B.HEADER.pack(j.B.MAGIC,1,0,count,count-1,1,float(held)),
                         qid.tobytes(),times.tobytes(),y[qid!=held].tobytes()))
    return qid,times,y,feature,bundle


def frozen(r,context,count=3):
    q,t,y,f,b=fixture(context,count)
    job=j.freeze_job(r,context=context,qid=q,time_indices=t,outputs=1,
                    support_class_sha256='5'*64,target_sha256=j.sha(y.tobytes()),feature=f,
                    bundle_for_held=b,byte_limit=BYTE,working_limit=WORK,max_bundle_bytes=2*1024**2)
    return job,y,b


def raw_prediction(values):
    output=io.BytesIO();np.save(output,np.asfortranarray(values,dtype='>f8'),allow_pickle=False)
    return output.getvalue()


def closure(public,raw):
    return {'schema':'language-private-invocation-closure/v1','request_sha256':public.public_id,
            'candidate_sha256':PINS['candidate_sha256'],'provider_source_sha256':PINS['provider_source_sha256'],
            'natural_exit_zero':True,'owned_processes_absent':True,'private_view_retired':True,
            'transport_sha256':j.sha(raw)}


def pipeline(root,constant=False):
    r=run();plans=[frozen(r,c) for c in j.ENDPOINT.contexts()[:2]]
    writer=j.CompactWriter(root,r,output_limit=131072,working_limit=WORK,byte_limit=BYTE)
    predictions=[]
    try:
        for job,y,bundle in plans:
            writer.begin_job(job);pred=np.empty_like(y)
            for held in range(len(y)):
                public=writer.request(bundle(float(held)))
                value=np.ones((1,1),dtype='<f8') if constant else (y[held:held+1]+float(held))
                raw=raw_prediction(value)
                writer.accept(request_id=public.public_id,raw_prediction=raw,closure=closure(public,raw))
                pred[held]=value
            np.testing.assert_array_equal(writer.finish_job(),pred);predictions.append(pred)
        receipt=writer.finish()
    finally:writer.close()
    reader=j.CompactReader(root,r,receipt,receipt_sha256=j.sha(j.encoded(receipt)),read_limit=65536,working_limit=WORK)
    scores=[]
    try:
        for (job,y,_),pred in zip(plans,predictions):
            actual=reader.score_job(job,y)
            np.testing.assert_array_equal(actual['predictions'],pred)
            np.testing.assert_equal(actual['correlations'],j.ORIGINAL.pooled_pearson(y,pred))
            scores.append(actual['correlations'])
        recovered=reader.finish()
    finally:reader.close()
    return receipt,recovered,scores


class SelectedJoinControls(unittest.TestCase):
    def test_real_selected_scope_has_exact42_coordinates5685_requests_and_parent_unchanged(self):
        r=run(True);binding=j._binding(r)
        self.assertEqual(binding['scope'],'original_figure3b_improvement')
        self.assertEqual((binding['jobs'],binding['requests']),(42,5685))
        self.assertEqual(list(r.contexts),[tuple(c[k] for k in j.P.CONTEXT_KEYS) for c in j.ENDPOINT.coordinates()])
        parent=(HERE.parent/'original-compact-scoring-join-v1/join.py').read_bytes()
        self.assertEqual(j.sha(parent),'1b4878289929fec97f6b89d99f7fcb3edf995142cd3966da8aab47c75faf3d0a')
        old=ast.parse(parent);new=ast.parse((HERE/'join.py').read_bytes())
        for name in ('CompactWriter','CompactReader','_feature','_maps','_packed_bindings'):
            left=next(n for n in old.body if getattr(n,'name',None)==name)
            right=next(n for n in new.body if getattr(n,'name',None)==name)
            self.assertEqual(ast.dump(left,include_attributes=False),ast.dump(right,include_attributes=False))

    def test_nonselected_coordinates_fail_before_bundle_access(self):
        r=run(True)
        for change in ({'field':'unit'},{'layer':4},{'lag_index':16,'lag_bins':-4}):
            context=dict(j.ENDPOINT.contexts()[0],**change)
            with self.assertRaises(ValueError):frozen(r,context)
        wrong=dict(j.ENDPOINT.coordinates()[0],field_index=1)
        with self.assertRaises(ValueError):j.make_run(**PINS,condition='paper_data',working_limit=WORK,
                                                    generated_contexts=[wrong],generated_requests=3)

    def test_generated_packed_pipeline_preserves_rows_and_original_pearson(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            receipt,recovered,scores=pipeline(Path(tmp)/'packed')
            self.assertEqual((receipt['jobs'],receipt['requests']),(2,6))
            self.assertEqual(receipt['scope'],'generated_engineering_control')
            self.assertTrue(recovered['compact_request_identity_join_verified'])
            self.assertFalse(receipt['scientific_qualification']);self.assertEqual(len(scores),2)

    def test_constant_predictions_remain_undefined_in_original_scorer(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            _,_,scores=pipeline(Path(tmp)/'packed',constant=True)
            self.assertTrue(all(np.isnan(s).all() for s in scores))

    def test_wrong_provider_closure_refuses_before_packed_raw_parser(self):
        r=run(count=1);job,_,bundle=frozen(r,j.ENDPOINT.contexts()[0])
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            writer=j.CompactWriter(Path(tmp)/'packed',r,output_limit=131072,working_limit=WORK,byte_limit=BYTE)
            try:
                writer.begin_job(job);public=writer.request(bundle(0.))
                bad=closure(public,b'not-npy');bad['provider_source_sha256']='0'*64
                with mock.patch.object(writer.packed,'accept',side_effect=AssertionError('raw parser reached')):
                    with self.assertRaisesRegex(ValueError,'provider'):writer.accept(request_id=public.public_id,raw_prediction=b'not-npy',closure=bad)
                self.assertTrue(writer.failed)
            finally:writer.close()

    def test_all42_generated_authorities_and5685_requests_form_complete_null_preserving_packet(self):
        r=run(True);panel=j.SelectedPanel(r,working_limit=WORK)
        for i,context in enumerate(j.ENDPOINT.contexts()):
            count=136 if i<15 else 135
            job,_,_=frozen(r,context,count)
            panel.add(job,np.array([np.nan if i==0 else i/100.],dtype='<f8'))
        packet=panel.finish(source_support_sha256='6'*64,prediction_run_sha256='7'*64)
        self.assertEqual(panel.requests,5685);self.assertEqual(len(packet['scores']),42)
        self.assertIsNone(packet['scores'][0]['pearson_r']);self.assertFalse(packet['execution_qualified'])
        reference=json.loads(j.encoded(packet));reference['role']='provided_author_reference'
        comparison=j.ENDPOINT.compare(packet,reference)
        self.assertIsNone(comparison['equal_session_paired_mean_delta'])
        self.assertEqual(comparison['independent_participant_clusters'],8)
        self.assertFalse(comparison['scientific_qualification'])

    def test_complete_coordinates_with_too_few_held_requests_do_not_finish(self):
        r=run(True);panel=j.SelectedPanel(r,working_limit=WORK)
        for context in j.ENDPOINT.contexts():
            job,_,_=frozen(r,context,2);panel.add(job,np.array([.25],dtype='<f8'))
        self.assertEqual(panel.next,42)
        with self.assertRaisesRegex(ValueError,'5685'):panel.finish(source_support_sha256='6'*64,prediction_run_sha256='7'*64)
        self.assertTrue(panel.failed)

    def test_panel_rejects_generated_scope_reordering_and_missing_cells(self):
        with self.assertRaises(ValueError):j.SelectedPanel(run(),working_limit=WORK)
        r=run(True);panel=j.SelectedPanel(r,working_limit=WORK)
        job,_,_=frozen(r,j.ENDPOINT.contexts()[1])
        with self.assertRaisesRegex(ValueError,'reordered'):panel.add(job,np.array([.1],dtype='<f8'))
        self.assertTrue(panel.failed)
        panel=j.SelectedPanel(r,working_limit=WORK)
        with self.assertRaises(ValueError):panel.finish(source_support_sha256='6'*64,prediction_run_sha256='7'*64)


if __name__=='__main__':unittest.main(verbosity=2)
