"""Concrete qualified-host staging/capture composition.

Admission, measurements, credential custody and semantic review are independently
selected trusted dependencies. They are not replaced by booleans from a candidate.
No constructor is selected or invoked by the default unqualified CLI.
"""
import ast
import io
import json
import os
from pathlib import Path
import uuid
from .protocol import require, canonical, pin_bytes, check_pin
from .phase_budget import PhaseBudget
from .container_engine import ContainerEngine


def prediction_body(value, length):
    import numpy as np
    require(type(value)is np.ndarray and value.dtype==np.dtype('<f8')
            and value.shape==(length,) and np.isfinite(value).all(),'complete finite current prediction')
    stream=io.BytesIO();np.lib.format.write_array(stream,value,version=(1,0),allow_pickle=False)
    return stream.getvalue()


def prediction_array(body,length):
    import numpy as np
    require(type(body)is bytes and body[:8]==b'\x93NUMPY\x01\x00','ordinary NPY1 prediction')
    header_length=int.from_bytes(body[8:10],'little')
    require(0<header_length<=4096 and len(body)==10+header_length+8*length,'exact prediction extent')
    header=ast.literal_eval(body[10:10+header_length].decode('latin1').strip())
    require(header=={'descr':'<f8','fortran_order':False,'shape':(length,)},'exact prediction header')
    result=np.load(io.BytesIO(body),allow_pickle=False,max_header_size=4096)
    require(np.isfinite(result).all(),'finite complete prediction');return result


class QualifiedHost:
    def __init__(self, *, guard, root, artifacts, serializers, monitor_factory,
                 journal, custody, container_selection, profile, docs,
                 source_tools, credential_capability, protected_target_loader,
                 protected_group_loader, replicate, clock):
        # Guard is called before root path access or any model/data operation.
        guard();self.guard=guard
        self.root=Path(root);require(self.root.is_absolute(),'absolute owned execution root')
        self.artifacts=artifacts;self.serializers=serializers;self.monitor_factory=monitor_factory
        self.journal=journal;self.custody=custody;self.container_selection=container_selection
        self.profile=profile;self.docs=docs;self.source_tools=source_tools
        self.credential_capability=credential_capability
        self.protected_target_loader=protected_target_loader;self.protected_group_loader=protected_group_loader
        self.clock=clock;self.replicate=replicate;self.tool_feedback_byte_cap=profile['tool_feedback_byte_cap']
        self.prediction_claims={};self.current=None;self.training_mounts={};self.prior_tools={};self.sealed_models={}
        # Independently verifies owned ordinary root and filesystem/namespace policy.
        require(custody.admit_host_root(str(self.root)) is True,'host root custody required')

    def fresh_context(self,request,request_pin,public):
        self.guard()
        require(self.current is None or self.current.closed,'previous context must close before reset')
        context=uuid.uuid4().hex
        require('person' not in public and 'source_order' not in public,'canonical identities remain operator-only')
        self.current=Context(self,request,request_pin,public,context)
        return self.current

    def confirm_trained_state_unchanged(self,request,report):
        self.guard()
        return self.custody.confirm_trained_state_unchanged(request,report)

    def fail_current_context(self,reason,request_pin):
        if self.current is None or self.current.request_pin!=request_pin:
            return {'status':'no_context_created_for_failed_request'}
        if self.current.closed:return {'status':'already_closed_context','context':self.current.opaque_id}
        return self.current.fail(reason)


class Context:
    def __init__(self,host,request,request_pin,public,opaque_id):
        self.host=host;self.request=request;self.request_pin=request_pin
        self.public_description=dict(public);self.opaque_id=opaque_id;self.closed=False
        self.path=host.root/opaque_id;self.path.mkdir(mode=0o700)
        self.input=self.path/'input';self.work=self.path/'work';self.output=self.path/'output'
        self.code=self.path/'code'
        for p in (self.input,self.work,self.output,self.code):p.mkdir(mode=0o700)
        self.ordinal=0;self.mounts=[];self.engine=None;self.sealed_training=None
        self.monitor=host.monitor_factory(request,request_pin,opaque_id)
        self.budget=PhaseBudget(request,monitor=self.monitor,journal=self.journal,clock=host.clock)
        self.cutoff=min(self.budget.cutoff,request['original_deadline']-host.container_selection['cleanup_seconds'])
        require(self.budget.started<self.cutoff,'full phase incl cleanup must fit original clock')
        self.max_steps=host.profile['max_investigation_steps']
        self.public_description['tool_feedback_byte_cap']=host.tool_feedback_byte_cap

    def journal(self,row):
        self.host.journal({'context':self.opaque_id,'request_pin':self.request_pin,**row})

    def _write(self,directory,name,body):
        self.host.guard();require(type(body)is bytes,'bounded staged bytes')
        require(type(name)is str and name and '/'not in name and name not in ('.','..'),'plain staging filename')
        self.budget.charge_io(write_bytes=len(body))
        path=directory/name
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o444)
        try:
            at=0
            while at<len(body):
                self.budget.tick();n=os.write(fd,body[at:]);require(n>0,'complete staged write');at+=n
        finally:os.close(fd)
        return str(path)

    def _source(self,body,*,role,context):
        require(context==self.opaque_id and len(body)<=65536,'current bounded source')
        self.ordinal+=1;path=self._write(self.code,f'program-{self.ordinal}.py',body)
        return {'path':path,'pin':pin_bytes(body)}

    def _artifact_limit(self,handle):
        require(type(handle)is dict and set(handle)=={'role','pin','custody_id'}
                and handle['role'] in self.host.artifacts.role_caps,'configured artifact role')
        check_pin(handle['pin'])
        total=self.host.profile['artifact_bytes']
        require(type(total)is int and total>0,'positive host artifact ceiling')
        cap=min(total,self.host.artifacts.role_caps[handle['role']])
        require(handle['pin']['bytes']<=cap,'complete artifact exceeds host or role ceiling')
        return cap

    def _artifact_mount(self,handle,target,role):
        cap=self._artifact_limit(handle)
        path=self.host.artifacts.qualified_path(handle,cap)
        self.mounts.append({'source':path,'target':target,'role':role})

    def _engine(self):
        self.engine=ContainerEngine(qualification_guard=self.host.guard,
            selection=self.host.container_selection,context=self.opaque_id,mounts=self.mounts,
            work_directory=str(self.work),output_directory=str(self.output),code_stager=self._source,
            artifact_store=self.host.artifacts,budget=self.budget,journal=self.journal,
            independent_custody=self.host.custody,original_deadline=self.request['original_deadline'])

    def _documents(self):
        for i,h in enumerate(self.host.docs):self._artifact_mount(h,f'/docs/document-{i}.txt','documents')
        for name,h in self.host.source_tools.items():
            require(type(name)is str and '/'not in name and name.endswith('.py'),'pinned flat tool source')
            self._artifact_mount(h,'/tools/'+name,'reference_tools')

    def stage_documents_only(self):
        self._documents();self._engine()

    def _training(self,training,arm):
        expected=tuple(dict.fromkeys(training['run_ids'].tolist()))
        metadata,body=self.host.serializers.serialize_training(training,arm,expected,self.host.serializers.budget)
        path=self._write(self.input,'training.npz',body)
        meta=self._write(self.input,'training.json',canonical(metadata))
        self.mounts.extend([{'source':path,'target':'/input/training.npz','role':'training'},
                            {'source':meta,'target':'/input/training.json','role':'training'}])
        self.public_description['training']=metadata
        key=(self.request['person'],self.request['mode'],arm)
        require(key not in self.host.training_mounts,'one sealed training view per person/mode/arm')
        self.host.training_mounts[key]=(metadata,path,meta)

    def _reuse_training(self,arm):
        key=(self.request['person'],self.request['mode'],arm)
        require(key in self.host.training_mounts,'training view must seal before current query')
        metadata,path,meta=self.host.training_mounts[key]
        self.mounts.extend([{'source':path,'target':'/input/training.npz','role':'training'},
                            {'source':meta,'target':'/input/training.json','role':'training'}])
        self.public_description['training']=metadata
        # Only these exact immutable files are reused. Training workspaces,
        # transcripts and prior-query workspaces are never mounted. The external
        # custody observer authenticates each actual mount/inode on every launch.

    def _tools(self,artifacts):
        for family,handle in artifacts.get('reference_tools',{}).items():
            require(family in ('R0','R1','R2'),'independent frozen reference family')
            if family=='R0':
                # The reference engine's private admission schema includes
                # constant channel metadata. The no-neural candidate receives
                # only the trained scalar prior; no sensor schema is exported.
                key=handle['custody_id']
                if key not in self.host.prior_tools:
                    metadata,arrays=self.host.artifacts.load_reference_state(handle,self._artifact_limit(handle))
                    require(metadata['family']=='R0' and set(arrays)=={'target_mean'},'scalar prior reference')
                    self.host.prior_tools[key]=self.host.artifacts.put_bytes(
                        canonical({'family':'R0','target_mean':float(arrays['target_mean'])}),
                        'model',{'kind':'training_only_scalar_prior'})
                self._artifact_mount(self.host.prior_tools[key],'/tools/R0.json','reference_tools')
            else:self._artifact_mount(handle,'/tools/'+family+'.zip','reference_tools')

    def stage_training_only(self,training,artifacts):
        self._documents();self._training(training,self.request['arm']);self._tools(artifacts)
        self._artifact_mount(artifacts['program'],'/program/sealed_recipe.py','reference_tools')
        self._artifact_mount(artifacts['method_recipe'],'/program/method_recipe.json','reference_tools')
        self.public_description['sealed_predata_recipe']={'program':'/program/sealed_recipe.py',
            'method':'/program/method_recipe.json','read_only':True}
        self._engine()

    def stage_current_case(self,query,artifacts,*,readonly_trained_state):
        require(readonly_trained_state is True,'frozen learned state')
        self._documents();arm='no_neural' if query['arm']=='no_neural' else 'neural'
        self._reuse_training(arm);self._tools(artifacts)
        metadata,body=self.host.serializers.serialize_query(query,self.host.serializers.budget)
        meta=self._write(self.input,'query.json',canonical(metadata))
        self.mounts.append({'source':meta,'target':'/input/query.json','role':'query'})
        if body is not None:
            path=self._write(self.input,'query.npz',body)
            self.mounts.append({'source':path,'target':'/input/query.npz','role':'query'})
        state=artifacts['frozen_state']
        self._artifact_mount(state,'/state/state.npz','frozen_state')
        require(state['custody_id'] in self.host.sealed_models,'state-bound predictor provenance required')
        model=self.host.sealed_models[state['custody_id']]
        require(model['state']==state and self.host.custody.program_for_state(state)==model['program'],
                'exact independently bound state/program join')
        self._artifact_mount(model['program'],'/tools/trained_predictor.py','reference_tools')
        self._artifact_mount(model['method_recipe'],'/tools/trained_method.json','reference_tools')
        self.public_description['trained_predictor']={'program':'/tools/trained_predictor.py',
            'method':'/tools/trained_method.json','state':'/state/state.npz','read_only':True}
        self.public_description['current_query']=metadata
        self._engine()

    def capture_authoring(self,sealed,*,source_cap):
        require(set(sealed)=={'program','method_recipe'},'complete sealed authoring')
        body=self.host.artifacts.read_exact(sealed['program'],source_cap)
        require(0<len(body)<=source_cap,'bounded complete program');return sealed

    def _output(self,name,cap):
        self.host.guard()
        # Independent store ingests only this context's ordinary output, with
        # stable no-follow identity/size and exact full-byte accounting.
        return self.host.custody.read_owned_output(str(self.output/name),cap,self.opaque_id,self.budget)

    def execute_training_and_seal(self,sealed,artifacts):
        chosen=artifacts if sealed is None else sealed
        self.engine.execute_sealed_program(chosen['program'],action='train',phase='training',cutoff=self.cutoff)
        body=self._output('state.npz',self.host.profile['model_state_bytes'])
        from .numeric_state import validate_state
        shape_report=validate_state(body,expanded_cap=self.host.profile['expanded_model_state_bytes'],
                                    progress=self.reference_progress)
        state=self.host.artifacts.put_bytes(body,'frozen_state',{'context':self.opaque_id,
                         'program':chosen['program'],'method_recipe':chosen['method_recipe'],
                         'numeric_format':shape_report})
        # Predictor source for adaptive training may differ from global recipe;
        # bind it in metadata and retain it explicitly in the host's state map.
        require(self.host.custody.bind_state_program(state,chosen['program'],chosen['method_recipe']) is True,
                'independent state/program/method sealing refused')
        require(state['custody_id'] not in self.host.sealed_models,'immutable state provenance')
        self.host.sealed_models[state['custody_id']]={'state':state,'program':chosen['program'],
                                                    'method_recipe':chosen['method_recipe']}
        report=self.host.artifacts.put_bytes(canonical({'program':chosen['program'],
                    'method_recipe':chosen['method_recipe'],'state':state,'training_only':True}),
                    'training_report',{'context':self.opaque_id})
        return {'frozen_state':state,'training_report':report}

    def execute_current_prediction(self,sealed,query,artifacts):
        chosen=(self.host.custody.program_for_state(artifacts['frozen_state']) if sealed is None else sealed['program'])
        self.engine.execute_sealed_program(chosen,action='predict',phase='case',cutoff=self.cutoff)
        body=self._output('prediction.npy',8*query['length']+4106)
        prediction=prediction_array(body,query['length'])
        return self.capture_prediction(prediction,query,method='fixed_program' if sealed is None else 'case_synthesis')

    def capture_reference_state(self,metadata,arrays,report):
        handle=self.host.artifacts.put_reference_state(metadata,arrays,role='frozen_state')
        trace=self.host.artifacts.put_bytes(canonical(report),'training_report',{'context':self.opaque_id})
        return {'frozen_state':handle,'training_report':trace}

    def capture_prediction(self,prediction,query,*,method):
        body=prediction_body(prediction,query['length'])
        metadata={'query_id':query['id'],'length':query['length'],'request_pin':self.request_pin,
                  'context':self.opaque_id,'method':method,'arm':self.request['arm']}
        handle=self.host.artifacts.put_bytes(body,'prediction',metadata)
        self.host.prediction_claims[handle['custody_id']]=metadata
        trace=self.host.artifacts.put_bytes(canonical(metadata),'method_trace',{'context':self.opaque_id})
        return {'prediction':handle,'method_trace':trace}

    def read_prediction(self,handle,qid,n):
        claim=self.host.prediction_claims[handle['custody_id']]
        require(claim['query_id']==qid and claim['length']==n,'exact emitted query provenance')
        return prediction_array(self.host.artifacts.read_exact(handle,8*n+4106),n)

    def capture_submission(self,body,person):
        return self.host.artifacts.put_bytes(body,'submission',{'person':person,'request_pin':self.request_pin})

    def read_submission(self,handle):
        return self.host.artifacts.read_exact(handle,1048576)

    def capture_protected_report(self,report):
        # Protected report store/roles are never candidate mount capabilities.
        return {'protected_report':self.host.artifacts.put_bytes(canonical(report),'protected_report',
                        {'operator_only':True,'request_pin':self.request_pin}),
                'uncertainty_report':self.host.artifacts.put_bytes(canonical(report['uncertainty']),
                        'uncertainty_report',{'operator_only':True,'request_pin':self.request_pin})}

    def reference_progress(self,event):
        return self.budget.reference_progress(event)

    def finish_observed(self,artifacts):
        observed=self.budget.finish();self.closed=True
        return {'schema':'neural001_phase_report_v1','request_pin':self.request_pin,'status':'ok',
                'usage':observed['usage'],'peaks':observed['peaks'],'artifacts':artifacts,
                'context_id':self.opaque_id,'admission':observed['admission'],
                'observation':observed['observation']}

    def fail(self,reason):
        self.closed=True
        observed=self.monitor.fail(reason,self.budget.used,self.budget.pending,self.budget.unknown)
        self.journal({'kind':'context_failed','reason':reason,'observation':observed,
                      'unknown_consumption_not_zero':True,'cleanup_requires_independent_custody':True})
        return observed
