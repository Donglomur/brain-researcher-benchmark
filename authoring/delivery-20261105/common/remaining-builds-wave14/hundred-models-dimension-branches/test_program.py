"""Invented branch metadata and scores only; all serializations precharged."""
from dataclasses import replace
from pathlib import Path
import json
import math
import unittest

from hundred_models_dimensions import program as p, consumers as c
from hundred_models_dimensions import _catalog_gate as g

HERE=Path(__file__).absolute().parent
ROOT=HERE.parents[4]
P=(ROOT/'authoring/delivery-20261105/hundred-models-paper/public/common/PROTOCOL.json').read_bytes()
I=(ROOT/'authoring/delivery-20261105/hundred-models-paper/source-evidence/MODEL_SOURCE_INVENTORY.json').read_bytes()
PROTOCOL=g.contract(P,I)
DUMMY=g.pin(b'invented nonempirical source test')


def json_size(value):
    """Exact canonical ASCII size; count before dumps, including gate newline."""
    if value is None:return 4
    if type(value) is bool:return 4 if value else 5
    if type(value) is int:return len(str(value))
    if type(value) is float:
        if not math.isfinite(value):raise ValueError('nonfinite before serialization')
        return len(repr(value))
    if type(value) is str:
        return 2+sum(2 if ch in '\\"\b\f\n\r\t' else 6 if ord(ch)<32 or 127<=ord(ch)<=65535
                     else 12 if ord(ch)>65535 else 1 for ch in value)
    if type(value) in (list,tuple):return 2+max(len(value)-1,0)+sum(json_size(x) for x in value)
    if type(value) is dict and all(type(k) is str for k in value):
        return 2+max(len(value)-1,0)+sum(json_size(k)+1+json_size(v) for k,v in value.items())
    raise ValueError('unsupported canonical value')


class Meter:
    def __init__(self,limit=8*1024*1024):self.limit=limit;self.bytes=0;self.calls=0;self.original=g.encoded
    def encoded(self,value):
        size=json_size(value)+1
        if size>self.limit-self.bytes:raise ValueError('prospective canonical serialization cap')
        self.bytes+=size;self.calls+=1
        raw=self.original(value)
        if len(raw)!=size:raise AssertionError('canonical size mismatch; charge retained')
        return raw


def binding(branch):
    required={name for name,_ in c.membership(branch)}
    records=[]
    for model in PROTOCOL['models']:
        if model['id'] not in required:continue
        explicit=model['config'].get('layers')
        records.append({'model_id':model['id'],'configuration':g.pin(g.encoded(model['config'])),
          'profile':g.PROFILE,'framework_identity':'invented-branch-control-only','framework_source_files':[DUMMY],
          'checkpoint':DUMMY,'named_modules':['',*explicit] if explicit else ['','first','last'],
          'emitted_feature_keys':list(explicit) if explicit else ['first','last'],
          'stimulus_order':g.pin(g.encoded(PROTOCOL['stimuli'])),'subjects':PROTOCOL['subjects'],
          'emission_receipt':DUMMY,'graph_receipt':DUMMY,'all102_emission_keysets_identical':True,
          'evidence_origin':'invented_control'})
    raw=g.encoded({'schema':'hundred_models_graph_metadata_v1','protocol':g.PROTOCOL_PIN,
                   'profile':g.PROFILE,'models':records})
    catalog=g.compile_catalog(P,I,raw,g.pin(raw),require_complete=False)
    layers=tuple((name,tuple(catalog['models'][name]['layers'])) for name,_ in c.membership(branch))
    producer={x['model_id']:tuple(x['emitted_feature_keys']) for x in records}
    folders=('models','models_no_dimred','models_pca_rerun') if branch=='figure16' else ('invented_train_folder',)
    ids=PROTOCOL['stimuli'] if branch=='figure16' else ['invented_training_'+str(i).zfill(4) for i in range(1000)]
    n,reps=(102,10) if branch=='figure16' else (1000,3)
    order_pin=g.pin(g.encoded(ids))
    conditions=[]
    for model,names in layers:
        for folder in folders:
            method=dict(p.METHOD_FOLDERS)[folder] if branch=='figure16' else 'pca'
            conditions.append({'model':model,'folder':folder,'stimulus_order':order_pin,
              'layer_order':g.pin(g.encoded(names)),'producer_layer_order':g.pin(g.encoded(producer[model])),
              'n_stimuli':n,'split_emission_receipt':DUMMY,'operation_contract':DUMMY,'score_provenance_receipt':DUMMY,
              'operation_profile':{'pca':'literal_held_script_pca100_fit102','srp':'explicit_admitted_srp_run_metadata',
                                    None:'explicit_admitted_no_reduction_run_metadata'}[method],
              'reduction':{'method':method,'n_samples_estim':102 if method else None,
                'n_components':100 if method=='pca' else None,'max_dim_allowed':None,'standardize_on_dim':None,
                'distance':'pearson','sklearn_kwargs_policy':'constructor-only-n_components;other-keywords-omitted'}})
    run={'schema':'hundred_models_dimension_run_v1','branch':branch,'protocol':g.PROTOCOL_PIN,
       'evidence_origin':'invented_control','split':{'selection':'test' if branch=='figure16' else 'train',
          'ordered_ids':ids,'n_stimuli':n,'repetitions':reps,'order_admission':DUMMY},
       'brain':{'subjects':list(p.SUBJECTS),'rois':list(p.ROIS),'n_stimuli':n,'repetitions':reps,
          'average_external':False,'operation_contract':DUMMY,'shape_manifest':DUMMY,'noise_ceiling_receipt':DUMMY},
       'base_folder':folders[-1],'comparison_folders':list(folders[:-1]),'conditions':conditions}
    run_raw=g.encoded(run)
    bound=p.bind_branch(branch,P,I,raw,g.pin(raw),run_raw,g.pin(run_raw))
    return bound,layers,folders


def frame(roi,layers,folders):
    return c.ROIFrame(roi,tuple(c.ModelCondition(model,folder,tuple(c.LayerScore(name,0.125 if i%2 else -0.25)
        for i,name in enumerate(names))) for model,names in layers for folder in folders),c.NoiseCeiling(0.25,0.5))


class Never:
    def __iter__(self):raise AssertionError('invalid metadata touched numeric stream')


class BranchControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.figure16=binding('figure16');cls.figure17=binding('figure17')

    def test_01_complete17_each_exact_branch_and_partial99_catalog(self):
        for branch,triple,count,n,reps in [('figure16',self.figure16,92,102,10),('figure17',self.figure17,51,1000,3)]:
            bound,layers,folders=triple
            stream=p.run_branch(bound,(frame(roi,layers,folders) for roi in p.ROIS))
            totals=0
            for roi in p.ROIS:
                out=next(stream);self.assertEqual(out.roi,roi);self.assertFalse(out.whole_branch_complete)
                self.assertEqual(len(out.best_layers),count*len(folders));totals+=len(out.depth_rows)
            done=next(stream)
            self.assertTrue(done.whole_branch_complete);self.assertEqual(len(done.models),count)
            self.assertEqual((done.n_stimuli,done.repetitions),(n,reps));self.assertEqual(done.output_rows,totals)
            self.assertFalse(done.catalog_global99_complete);self.assertTrue(done.input_test102_catalog_prerequisite)
            self.assertFalse(done.historical_execution_proven)
            with self.assertRaises(StopIteration):next(stream)

    def test_02_preflight_scope_and_geometry_before_values(self):
        bound,_,_=self.figure17
        for invalid in (replace(bound,run_raw=b'{}'),replace(bound,limits=p.Limits(max_input_rows=1)),
                        replace(bound,limits=p.Limits(depth=replace(p.depth.Limits(),max_rows=1)))):
            with self.assertRaises(ValueError):next(p.run_branch(invalid,Never()))

    def test_03_operation_and_split_metadata_discriminate_source_gaps(self):
        bound,layers,folders=self.figure17
        protocol=g.strict(P)
        producer={row['model_id']:tuple(row['emitted_feature_keys']) for row in g.strict(bound.graph_raw)['models']}
        run=g.strict(bound.run_raw)
        for change in ('train_fit1000','train_test_order','producer_subset','missing_condition'):
            bad=json.loads(bound.run_raw)
            if change=='train_fit1000':bad['conditions'][0]['reduction']['n_samples_estim']=1000
            elif change=='train_test_order':bad['split']['ordered_ids']=PROTOCOL['stimuli']
            elif change=='producer_subset':bad['conditions'][0]['producer_layer_order']=DUMMY
            else:bad['conditions'].pop()
            with self.assertRaises(ValueError):p._run_contract('figure17',protocol,layers,producer,g.encoded(bad))

    def test_04_canonical_precharge_controls(self):
        values=['\x7f','\x1f','\ud800','𝄞',-0.0,1e-12,{'é':[1,True,None]}]
        for value in values:self.assertEqual(json_size(value)+1,len(g.encoded(value)))
        meter=Meter(limit=3)
        with self.assertRaisesRegex(ValueError,'prospective'):meter.encoded('\x7f')
        self.assertEqual(meter.bytes,0)


if __name__=='__main__':unittest.main()
