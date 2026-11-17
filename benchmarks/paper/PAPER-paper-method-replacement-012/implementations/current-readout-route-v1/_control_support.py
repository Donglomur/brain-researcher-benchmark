"""Generated-only source oracle helpers; never load author pickles or neural arrays."""
from contextlib import contextmanager, redirect_stdout, ExitStack
from copy import deepcopy
import ast
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from typing import Literal
import unittest
from unittest.mock import patch
import warnings

COMPONENT = Path(__file__).resolve().parent
IMPLEMENTATIONS = COMPONENT.parent
OFFICIAL = COMPONENT / 'reference'
SOURCE_SHA = 'd7de1027643595308fd10daf8608d8d0ab466011ff80304f359ee7e44b5d4449'
UTILS_SHA = 'f813bc57f8de0c492f05a23e172f21a40e28e5b0663afe057a658d7f8dc79938'
READER_FIXTURE_SHA = 'b3ac2859ae109e056fd716dc0ba8b4fcfbdc8f9fced0afb909a7e7cd47f4679c'
GENERATED_LOGICAL_BYTES = 0
MAX_GENERATED_BYTES = 256 * 1024


def pinned(path, expected):
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != expected:
        raise AssertionError('control source pin changed: '+str(path))
    return body


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


route = module(COMPONENT/'route.py', '_nuclr_generated_current_route')


def full_generated_documents(reader):
    """Reuse only the pinned factory; no prior control method or array helper runs."""
    path = IMPLEMENTATIONS/'native-metadata-reader-v2/test_native_metadata_reader.py'
    tree = ast.parse(pinned(path, READER_FIXTURE_SHA))
    chosen = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t,ast.Name) and t.id=='HOLDS' for t in node.targets):
            chosen.append(node)
        if isinstance(node,ast.FunctionDef) and node.name in ('completion_for','original_generated_projection_helper'):
            chosen.append(node)
        if isinstance(node,ast.ClassDef) and node.name=='SavedMetadataControls':
            factory = deepcopy(node)
            factory.body = [part for part in factory.body if isinstance(part,ast.FunctionDef) and part.name=='setUpClass']
            chosen.append(factory)
    namespace = {'__file__':str(path),'reader':reader,'ast':ast,'Path':Path,'hashlib':hashlib,
                 'SimpleNamespace':SimpleNamespace,'deepcopy':deepcopy,'unittest':unittest,
                 'HELPER_SHA256':'428ac5555647eac596d801d7a80df8fdb6bdbc5b27b8bdc88f88f7848cd3c598'}
    exec(compile(ast.Module(body=chosen,type_ignores=[]),str(path),'exec'),namespace)
    factory = namespace['SavedMetadataControls']
    factory.setUpClass()
    return factory.manifest, factory.joined, factory.completion


class SynchronousRay:
    """Records the literal author jobs, but never starts Ray or child workers."""
    def __init__(self):
        self.jobs=[]; self.gets=[]; self.init_kwargs=None; self.stopped=False
    def remote(self, fn):
        def execute(*args):
            result=fn(*args); self.jobs.append(result); return result
        return SimpleNamespace(remote=execute)
    def init(self,**kwargs):
        self.init_kwargs=kwargs
    def get(self,result):
        self.gets.append(result); return result
    def shutdown(self):
        self.stopped=True


def source_namespace(ros, scaler, estimator):
    import numpy as np
    from sklearn.metrics import balanced_accuracy_score, f1_score, classification_report
    source_tree=ast.parse(pinned(OFFICIAL/'multi_split_eval.py',SOURCE_SHA))
    utils_tree=ast.parse(pinned(OFFICIAL/'utils.py',UTILS_SHA))
    fn=[n for n in source_tree.body if isinstance(n,ast.FunctionDef) and n.name=='eval_multisplit_with_cv']
    mask=[n for n in utils_tree.body if isinstance(n,ast.FunctionDef) and n.name=='presence_mask']
    assert len(fn)==len(mask)==1
    ray=SynchronousRay()
    namespace={'np':np,'ray':ray,'RandomOverSampler':ros,'StandardScaler':scaler,'LogisticRegression':estimator,
        'Literal':Literal,'tqdm':lambda values,**kwargs:values,'balanced_accuracy_score':balanced_accuracy_score,
        'f1_score':f1_score,'classification_report':classification_report}
    exec(compile(ast.Module(body=mask+fn,type_ignores=[]),'<pinned-author-AST>','exec'),namespace)
    main=next(n for n in source_tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
    normalizers=[n for n in main.body if isinstance(n,ast.If) and isinstance(n.test,ast.BoolOp)]
    assert len(normalizers)==1
    namespace['_normalizer']=ast.Module(body=normalizers,type_ignores=[])
    return namespace,ray


def run_source(packet,ros,scaler,estimator):
    import numpy as np
    namespace,ray=source_namespace(ros,scaler,estimator)
    original_dictionary=deepcopy(packet['splits'][0])
    namespace['splits']=original_dictionary
    exec(compile(namespace['_normalizer'],'<literal-author-dictionary-normalization>','exec'),namespace)
    assert namespace['splits']==[original_dictionary]
    ids=packet['checkpoints'][0]['ids']
    labels=np.asarray([packet['label_map'][uid] for uid in ids])
    operands=[np.asarray(row['embeddings'],dtype=np.float32) for row in packet['checkpoints']]
    with redirect_stdout(io.StringIO()),warnings.catch_warnings():
        from sklearn.exceptions import UndefinedMetricWarning
        warnings.simplefilter('ignore',UndefinedMetricWarning)
        namespace['eval_multisplit_with_cv'](operands,np.asarray(ids),labels,namespace['splits'],class_balance_type='resample')
    selected=[r for r in ray.jobs if 'index' in r]
    assert len(selected)==1 and ray.stopped
    chosen=selected[0]
    return {'selected_index':chosen['index'],'true':chosen['true'].tolist(),'pred':chosen['pred'].tolist(),
        'f1':namespace['f1_score'](chosen['true'],chosen['pred'],average='macro'),
        'bacc':namespace['balanced_accuracy_score'](chosen['true'],chosen['pred']),
        'ray_jobs':len(ray.jobs),'ray_init_called_without_workers':ray.init_kwargs,
        'input_float32':all(x.dtype==np.float32 for x in operands)}


def tiny_packet(evaluator, epochs=(2,10,100), alternate_order=False):
    """Small invented nondevelopment-session neuron rows, never source embeddings."""
    sid='sb025_20191007'
    numbers=[10,2,8,1,9,0,11,3,12,4,13,5,16,6,15,7,14,17,18,19]
    ids=[f'{sid}_u{number}' for number in numbers]
    labels=['EC','EC','EC','EC','IN','IN']+['EC']*8+['IN']*2+['EC','IN','EC','IN']
    label_map=dict(zip(ids,labels))
    metadata=[{'id':uid,'session_id':sid,'subject_id':'sb025','source_neuron_index':number}
              for uid,number in zip(ids,numbers)]
    train=ids[:6]; val=ids[6:16]; test=ids[16:]
    if alternate_order:
        ids=ids[7:]+ids[:7]
    features=[[(-4 if label_map[uid]=='EC' else 4)+i*0.013456789, float(i%3)+0.123456789]
              for i,uid in enumerate(ids)]
    return {'schema_version':1,'task_id':evaluator.TASK_ID,'source_commit':evaluator.SOURCE_COMMIT,
        'input_role':'generated_engineering_control','label_level':'ei','panel':'transductive','context_variant':'population_context',
        'class_balance':'resample','label_vocabulary':['EC','IN'],'source_label_mapping':{'EC':'EC','IN':'IN'},
        'label_map':label_map,'metadata':metadata,'source_session_manifest':[sid],'representation_training_sessions':[sid],
        'splits':[{'id':'generated-only','train':train,'val':val,'test':test}],
        'checkpoints':[{'id':f'epoch_{epoch}','epoch':epoch,'ids':list(ids),'embeddings':deepcopy(features)} for epoch in epochs],
        'provenance':{'split_sha256':'a'*64,'metadata_sha256':'b'*64,'data_receipt_sha256':'c'*64,
            'split_member':'ei_transductive.pkl','split_release':'other_explicit','split_release_detail':'Generated-only source-differential control'}}


class PipelineTrace:
    """Real scaling, explicitly fake ROS indices/classifier, or real hosted libraries."""
    def __init__(self, *, real_ros=None, real_classifier=None, macro_reverse=False):
        import numpy as np
        from sklearn.preprocessing import StandardScaler
        self.events=[]; self.samples=[]; self.scalers=[]; self.estimators=[]
        self.real_ros=real_ros; self.real_classifier=real_classifier; self.macro_reverse=macro_reverse
        owner=self
        class Sampler:
            def __init__(self,**kwargs):
                self.kwargs=kwargs; owner.events.append('ros_init')
                assert kwargs=={'random_state':42}
            def fit_resample(self,indices,labels):
                owner.events.append('ros')
                if real_ros is None:
                    # Deliberately NOT an implementation of RandomOverSampler.
                    picked=np.concatenate((np.arange(len(labels)),np.asarray([1,0,1])))
                    result=indices[picked],labels[picked]
                else:
                    result=real_ros(**self.kwargs).fit_resample(indices,labels)
                    picked=result[0].reshape(-1)
                owner.samples.append({'indices_in':indices.copy(),'labels_in':labels.copy(),'picked':picked.copy()})
                return result
        class Scaler(StandardScaler):
            def __init__(self):
                super().__init__(); owner.events.append('scaler_init')
            def fit(self,X,y=None,**kwargs):
                owner.events.append('scaler_fit')
                result=super().fit(X,y,**kwargs)
                owner.scalers.append({'X':X.copy(),'mean':self.mean_.copy(),'scale':self.scale_.copy()})
                return result
        class Classifier:
            def __init__(self,**kwargs):
                owner.events.append('classifier_init')
                self.kwargs=kwargs
                self.index=len(owner.estimators)
                self.record={'kwargs':kwargs}; owner.estimators.append(self.record)
                self.model=real_classifier(**kwargs) if real_classifier else None
            def fit(self,X,y):
                owner.events.append('classifier_fit')
                self.record.update({'X':X.copy(),'y':y.copy()})
                if self.model:
                    self.model.fit(X,y)
                return self
            def predict(self,X):
                owner.events.append('predict')
                self.record['prediction_X']=X.copy()
                if self.model:
                    return self.model.predict(X)
                if owner.macro_reverse and len(X)==10:
                    # Literal prediction vectors: bacc prefers A, macro-F1 prefers B.
                    count=sum(len(e.get('prediction_X',[]))==10 for e in owner.estimators[:-1])
                    return np.asarray(['EC']*2+['IN']*8 if count==0 else ['EC']*10)
                return np.resize(np.asarray(['EC','IN']),len(X))
        self.Sampler=Sampler; self.Scaler=Scaler; self.Classifier=Classifier

    @contextmanager
    def installed(self):
        import sklearn.preprocessing
        import sklearn.linear_model
        if self.real_ros is not None:
            import imblearn.over_sampling
            with ExitStack() as stack:
                stack.enter_context(patch.object(imblearn.over_sampling,'RandomOverSampler',self.Sampler))
                stack.enter_context(patch.object(sklearn.preprocessing,'StandardScaler',self.Scaler))
                stack.enter_context(patch.object(sklearn.linear_model,'LogisticRegression',self.Classifier))
                yield
            return
        top=ModuleType('imblearn'); sub=ModuleType('imblearn.over_sampling')
        top.__version__='REAL_ROS_TRACED' if self.real_ros else 'TRACE_DOUBLE_NOT_REAL_ROS'
        sub.RandomOverSampler=self.Sampler
        top.over_sampling=sub
        with patch.dict(sys.modules,{'imblearn':top,'imblearn.over_sampling':sub}),\
             patch.object(sklearn.preprocessing,'StandardScaler',self.Scaler),\
             patch.object(sklearn.linear_model,'LogisticRegression',self.Classifier):
            yield


def assert_trace_pair(case, source_trace, adapter_trace, source_index, adapter_index):
    import numpy as np
    for field in ('indices_in','labels_in','picked'):
        np.testing.assert_array_equal(source_trace.samples[source_index][field],adapter_trace.samples[adapter_index][field])
    for field in ('X','mean','scale'):
        np.testing.assert_array_equal(source_trace.scalers[source_index][field],adapter_trace.scalers[adapter_index][field])
    for field in ('X','y','prediction_X'):
        np.testing.assert_array_equal(source_trace.estimators[source_index][field],adapter_trace.estimators[adapter_index][field])
    for trace,index in ((source_trace,source_index),(adapter_trace,adapter_index)):
        kwargs=trace.estimators[index]['kwargs']
        case.assertEqual({k:kwargs[k] for k in ('solver','C','tol','max_iter','class_weight')},
                         {'solver':'newton-cg','C':1.0,'tol':1e-4,'max_iter':1000,'class_weight':None})
        case.assertEqual(trace.scalers[index]['X'].dtype,np.float32)
