"""Concrete actual NativeHost consumers. Only operator.coordinator constructs it."""
import os,subprocess,signal,resource
from pathlib import Path
from .storage import Store,encode,decode,digest,seal_readonly_tree
from .packet import Packet,prediction_plane
from .linux import stop_process
from .admission import full_plan
from .frozen import Frozen,plain
from . import custody
from gain.host import NativeHost,TrainingCapture,QueryCapture
from prospective.phase_order import EVENTS

class Training(TrainingCapture):
    def __init__(self,packet,sid):
        self._metadata=packet.metadata[sid];self._fit=None;self._validation=None;self.closed=False
        try:self._fit=packet.counts(sid,'FIT');self._validation=packet.counts(sid,'VALIDATION')
        except BaseException:self.close();raise
    @property
    def metadata(self):return self._metadata
    @property
    def fit_counts(self):return self._fit
    @property
    def validation_counts(self):return self._validation
    def close(self):self.closed=True;self._fit=None;self._validation=None

class Query(QueryCapture):
    def __init__(self,counts):self._counts=counts;self.closed=False
    @property
    def counts(self):return self._counts
    def close(self):self.closed=True;self._counts=None

class Host(NativeHost):
    def __init__(self,profile,work,group,runtime,ledger,supervisor_pid,selection,errors):
        self.errors=errors;self.closed=False;self.group_fd=None;self.stores=[]
        self.profile=profile;self.work=Path(work);self.group=group;self.runtime=runtime;self.ledger=ledger;self.closed=False
        self.events=[];self.frozen=None;self.stage=0;self.issued=False;self.targets_opened=[]
        self.membership='/'+str((group.path/'coordinator').relative_to('/sys/fs/cgroup'))
        self.group_fd=None;self.stores=[]
        self.group_fd=os.open(group.path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            custody.issue(self,self.group_fd,supervisor_pid,selection,errors)
            self.plans,self.resource_plan=full_plan(profile)
            self.packet_store=self.store(profile['packet_root']);self.packet=Packet(self.packet_store,profile['packet'],ledger)
            actual_axes=digest(encode({sid:{'unit_ids':m['unit_ids'],'rows':[r['id']for r in m['rows']],'mouse_id':m['mouse_id']}for sid,m in self.packet.metadata.items()}))
            if profile['binding_pins']['unit_axes']!=actual_axes:raise ValueError('actual original full axis commitment')
            if profile['binding_pins']['protocol']!=profile['source_files']['source/PROTOCOL.json']['sha256']or profile['binding_pins']['feature_basis']!=profile['source_files']['gain/features.py']['sha256']:raise ValueError('actual protocol and feature source join')
            if profile['binding_pins']['method_family']!='d4fe1f15c638b3a939fc3ded63edaab7df638d32138c73a3b76670e036906e1c':raise ValueError('unchanged root-selected five-model recipe')
            self.result_store=self.store(self.work/'results',True)
            self.code_store=self.store(self.work/'candidate-code',True)
            source=self.store(profile['candidate_root'])
            for name,p in profile['candidate_files'].items():self.code_store.put(name,source.read(name,p,p['bytes']))
            seal_readonly_tree(self.code_store.path)
            # A positive exact file list builds the candidate code tree; no
            # parent credential, interpreter environment or sibling mount.
        except BaseException:
            # coordinator retains this exact object before __init__; retirement
            # belongs to that outer owner even on a failed acquisition return.
            raise
    def store(self,path,writable=False):
        if writable:Path(path).mkdir(mode=0o700)
        s=Store.__new__(Store);self.stores.append(s)
        Store.__init__(s,str(path),self.ledger,writable,self.errors);return s
    def need(self,stage):
        custody.require(self,'actual host consumer')
        if self.stage!=stage:raise RuntimeError('actual phase order, no replay')
    def event(self,name):
        expected=EVENTS[len(self.events)]
        if expected[0]!=name:raise RuntimeError('phase event order')
        last=self.events[-1]['receipt']if self.events else None
        n=len(self.events);b=self.profile['binding_pins'];receipt=digest(encode({'sequence':n,'phase':name,'bindings':b,'previous':last,'publication':getattr(self.frozen,'manifest_pin',None)}))
        freeze=receipt if n==6 else self.events[6]['receipt']if n>6 else None
        self.events.append({'sequence':n,'phase':name,'query_visibility':expected[1],'bindings':b,'receipt':receipt,'previous_receipt':last,'prediction_receipt':freeze})
    def describe_complete_panel(self):self.need(0);return self.packet.metadata
    def admit_full_resources(self,plans):
        self.need(0)
        if plans!=self.plans:raise ValueError('source-selected full plan must equal actual original metadata')
        self.result_store.put('RESOURCE_ADMISSION.json',encode(self.resource_plan));self.stage=1
    def capture_original_index(self):self.need(1);return self.packet.index
    def freeze_design_and_issue_prediction_view(self,descriptor_projection):
        self.need(1)
        from prospective.phase_projection import project_prediction_index
        if descriptor_projection!=project_prediction_index(self.packet.index,list(self.packet.metadata)):raise ValueError('actual view join')
        self.result_store.put('DESIGN.json',encode({'index':descriptor_projection,'dimensions':self.profile['packet']['dimensions'],'source':self.profile['source_files'],'candidate':self.profile['candidate_files']}));self.event('design_freeze')
        self.view=self.store(self.work/'prediction-view',True);self.packet.view(self.view,False)
        seal_readonly_tree(self.view.path)
        self.event('prediction_view_issued');self.stage=2
    def open_training(self,sid):
        if self.stage not in (2,3,4):raise RuntimeError('training phase')
        custody.require(self,'original training capture');return Training(self.packet,sid)
    def retain_reference_dispositions(self,sid,reference,calls):
        if self.stage not in (2,3,4,5):raise RuntimeError('reference phase')
        self.result_store.put('reference-stage-'+str(self.stage)+'/'+sid+'.json',encode(plain({'record':reference.__dict__,'counts':calls.counts,'failures':calls.failures})))
    def _barrier(self,references,stage,events):
        self.need(stage)
        if set(references)!=set(self.packet.metadata):raise ValueError('whole32 barrier')
        body={sid:plain(r.__dict__)for sid,r in references.items()}
        self.result_store.put('barrier-'+str(stage)+'.json',encode(body))
        for e in events:self.event(e)
        self.stage+=1
    def freeze_fit_grid(self,references):self._barrier(references,2,['fit_grid_frozen'])
    def record_validation_and_freeze_selection(self,references):self._barrier(references,3,['validation_scored','method_selection_frozen'])
    def freeze_refit_models(self,references):self._barrier(references,4,['refit_frozen'])
    def capture_complete_candidate_predictions(self,metadata):
        self.need(5)
        if metadata!=self.packet.metadata:raise ValueError('full candidate metadata join')
        out=self.work/'prediction-output';record=self.runtime.run('prediction',self.view.path,self.code_store.path,out,self.profile['candidate_argv'])
        if not record['stopped']:raise RuntimeError('candidate stop not observed')
        raw=self.store(out);b=raw.capture_untrusted('PREDICTIONS.json',self.profile['runtime_output_bytes']);self.ledger.take('metadata_bytes',len(b));j=decode(b)
        if set(j)!={'schema','sessions'}or j['schema']!='neural092_candidate_prediction_v1'or type(j['sessions'])is not dict or set(j['sessions'])!=set(metadata):raise ValueError('complete32 candidate output')
        captured={}
        for sid,entry in j['sessions'].items():
            if set(entry)!={'unit_ids','query_ids','means_path'}or entry['means_path']!=sid+'.f64':raise ValueError('closed output axes/path')
            i=self.packet.infos[sid];nr=len(i['rows']['QUERY']);u=len(i['unit_ids']);self.ledger.take('decoded_bytes',8*nr*u)
            x=prediction_plane(raw.capture_untrusted(entry['means_path'],8*nr*u),nr,u)
            captured[sid]={'session_id':sid,'unit_ids':entry['unit_ids'],'query_ids':entry['query_ids'],'means':x}
        return captured
    def freeze_and_readback_all_predictions(self,references,candidates):
        self.need(5);s=self.store(self.work/'frozen-predictions',True)
        f=Frozen(s,self.packet.metadata,self.packet.infos,references,candidates)
        self.frozen=f;self.event('all_predictions_frozen');self.stage=6;return f
    def open_private_query(self,frozen,sid):
        self.need(6)
        if frozen is not self.frozen or not frozen.ready or frozen.closed or sid in self.targets_opened:raise RuntimeError('original full immutable capture before targets')
        self.targets_opened.append(sid);return Query(self.packet.counts(sid,'QUERY'))
    def publish_private_scores(self,frozen,result,attempt):
        self.need(6)
        if frozen is not self.frozen or set(self.targets_opened)!=set(self.packet.metadata):raise RuntimeError('full panel scoring required')
        self.result_store.put('PRIVATE_SCORES.json',encode(result));self.event('private_query_scored');self.stage=7
    def legacy(self,name,args):
        p=self.profile;errors=self.errors;start=len(errors.events);stream=child=None;code=None
        dest=self.work/(name+'.stdout')
        def body():
            nonlocal stream,child,code
            self.ledger.take('files',1);self.ledger.take('write_bytes',p['runtime_output_bytes'])
            argv=[p['python']['path'],'-I',str(Path(p['source_root'])/'source/run.py'),*args]
            stream=dest.open('xb')
            def cap():resource.setrlimit(resource.RLIMIT_FSIZE,(p['runtime_output_bytes'],p['runtime_output_bytes']))
            child=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,env={'PATH':'/usr/bin:/bin','LANG':'C','PYTHONDONTWRITEBYTECODE':'1'},close_fds=True,start_new_session=True,preexec_fn=cap)
            try:code=errors.call('legacy_original_wait',lambda:child.wait(timeout=p['wall_seconds']))
            except BaseException:stop_process(child,errors,'legacy_process_stop',p['control_seconds'])
            if code is not None and code!=0:raise RuntimeError('original observed route failed: '+name)
        try:errors.call('legacy_'+name,body)
        except BaseException:pass
        finally:
            if stream is not None:errors.cleanup('legacy_log_close',stream.close)
        errors.finish(start);return dest
    def release_observed_query_and_execute_original_investigation(self,frozen):
        self.need(7)
        if frozen is not self.frozen or not frozen.ready:raise RuntimeError('original frozen predictions')
        view=self.store(self.work/'observed-view',True);self.packet.view(view,True);seal_readonly_tree(view.path);self.event('observed_query_released')
        out=self.work/'observed-output';record=self.runtime.run('observed',view.path,self.code_store.path,out,self.profile['observed_argv'])
        if not record['stopped']:raise RuntimeError('observed candidate stop')
        raw=self.store(out);b=raw.capture_untrusted('submission.json',1000000);pin=self.result_store.put('observed-submission.json',b)
        ref=self.work/'observed-reference.json'
        # Invoke original source/run.py dispatch, not a synthetic summary.
        self.legacy('legacy-reference',['reference','--public-index',str(Path(view.path)/'public/INDEX.json'),'--packet-root',view.path,'--output',str(ref)])
        p=self.profile['packet'];original_index=str(Path(self.profile['packet_root'])/p['index']['path']);roster=str(Path(self.profile['packet_root'])/p['roster']['path'])
        scored=self.legacy('legacy-score',['score','--roster',roster,'--index',original_index,'--index-sha256',p['index']['pin']['sha256'],'--packet-root',view.path,'--submission',str(Path(self.result_store.path)/'observed-submission.json')])
        local=self.store(self.work);refbody=local.capture_untrusted(ref.name,self.profile['runtime_output_bytes']);scorebody=local.capture_untrusted(scored.name,self.profile['runtime_output_bytes'])
        reference_pin=self.result_store.put('ORIGINAL_OBSERVED_REFERENCE.json',refbody);score=decode(scorebody)
        if score.get('admitted')is not True or score.get('task_id')!='NEURAL-092':raise ValueError('original observed scorer refused')
        self.result_store.put('ORIGINAL_OBSERVED_SCORE.json',scorebody);self.event('investigation_closed');self.stage=8
        return {'candidate_submission':pin,'original_reference':reference_pin,'score':score,'post_prediction_only':True}
    def export_phase_claim(self):
        self.need(8);return {'schema':'neural092_phase_claim_v1','task_id':'NEURAL-092','bindings':self.profile['binding_pins'],'events':self.events}
    def retain_terminal_attempt(self,attempt):
        self.result_store.put('ATTEMPT.json',encode(plain({'events':attempt.events,'counts':attempt.calls.counts,'failures':attempt.calls.failures,'stage':self.stage,'runtime':self.runtime.records,'io':self.ledger.used,'completion_before_outer_cleanup':False,'host_errors':self.errors.events})))
    def close(self):
        if self.closed:return
        self.closed=True;errors=self.errors;start=len(errors.events)
        for s in reversed(self.stores):errors.cleanup('host_store_retirement',s.close)
        errors.cleanup('host_custody_revoke',lambda:custody.revoke(self))
        fd=self.group_fd;self.group_fd=None
        if fd is not None:errors.cleanup('host_group_fd_close',lambda:os.close(fd))
        errors.finish(start)
