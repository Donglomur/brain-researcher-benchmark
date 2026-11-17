"""Concrete isolated source execution and closed-byte return path."""
from .common import (need,fields,integer,pin,body_pin,check_pin,decode,relative,
    token,encode,Cleanup)
from .physical.transport import ProviderClient,ObserverClient
from .authority import complete_closure

def validate_output_index(index,descriptor,observation,job_id,limits):
    fields(index,('schema','job_id','outputs'))
    need(index['schema']=='neural004_job_index_v1' and index['job_id']==job_id,'same exact job output')
    need(type(index['outputs']) is dict and len(index['outputs'])<=limits['files'],'complete bounded output inventory')
    inventory=observation['inventory'];need(type(inventory) is list and len(inventory)<=limits['files'],'bounded observer inventory including index')
    by_path={d['path']:d for d in inventory};need(len(by_path)==len(inventory),'unique observed files')
    need(descriptor['path']=='RESULT_INDEX.json' and by_path.get('RESULT_INDEX.json')==descriptor,'exact index belongs to observed inventory')
    need('EXECUTION.json' in index['outputs'] and set(by_path)=={'RESULT_INDEX.json'}|set(index['outputs']),'complete output inventory including execution and no extra files')
    total=0
    for name,d in index['outputs'].items():
        fields(d,('path','bytes','sha256'));need(name==d['path'] and '/' not in relative(name),'literal flat output identity')
        check_pin({k:d[k] for k in ('bytes','sha256')});need(by_path[name]==d,'same observed output body')
        total+=d['bytes'];need(total<=limits['output_bytes'],'whole output bound before reading any payload')
    return total

class JobTransport:
    def __init__(self,provider,observer,ledger,source_pin,limits):
        need(type(provider) is ProviderClient and type(observer) is ObserverClient,'concrete separately admitted transports')
        need(provider.endpoint!=observer.endpoint and provider.admission==observer.admission,'same-source independent endpoint composition')
        check_pin(source_pin);self.provider=provider;self.observer=observer;self.ledger=ledger;self.source_pin=source_pin
        fields(limits,('index_bytes','output_bytes','files','failure_bytes'))
        for x in limits.values():integer(x,1)
        self.limits=limits;self.records=[];self.contexts=set()
    def run(self,context,job_id,files,view,argv,purpose):
        token(context);need(context not in self.contexts,'fresh immutable process realm');self.contexts.add(context)
        self.ledger.reserve({'processes':1},'attempted actual isolated process')
        need(type(files) is dict and len(files)<=self.limits['files'],'source file bound')
        file_pins={name:body_pin(raw) for name,raw in files.items()}
        binding=pin({'context':context,'job_id':job_id,'files':file_pins,'view':view,'argv':argv,'purpose':purpose,
            'source_pin':self.source_pin,'origin_ns':self.ledger.origin,'scientific_ns':self.ledger.scientific})['sha256']
        result=None;primary=None;observation=None;secondary=[]
        try:
            self.ledger.tick();stage=self.provider.stage_exact(context,files,view,binding,self.ledger.origin,self.ledger.scientific)
            self.ledger.tick();result=self.provider.launch_exact(stage,argv,binding,self.ledger.origin,self.ledger.scientific)
        except BaseException as error:primary=error;self.ledger.fail(job_id+'/execution',error)
        try:observation=self.observer.close_job(context,job_id,result,primary,binding,self.ledger.origin,self.ledger.scientific)
        except BaseException as error:
            self.ledger.fail(job_id+'/observer',error)
            if primary is None:primary=error
            else:secondary.append({'type':type(error).__name__,'message':str(error)[:1024]})
        record={'context':context,'job_id':job_id,'binding_digest':binding,'source_pin':self.source_pin,
            'view_pin':pin(view),'origin_ns':self.ledger.origin,'purpose':purpose,'observation':observation,
            'primary':None if primary is None else {'type':type(primary).__name__,'message':str(primary)[:1024]},
            'secondary':secondary,'qualified':False}
        self.records.append(record)
        try:
            if primary is not None:raise primary
            need(type(observation) is dict and observation['job_id']==job_id and observation['binding_digest']==binding and observation['origin_ns']==self.ledger.origin,'observer-owned exact operation join')
            need(type(observation['exit_code']) is int and observation['exit_code']==0 and observation['natural_exit'] is True and
                 observation['stream_eof'] is True and observation['all_descendants_closed'] is True and observation['forced_stop'] is False,'actual natural-zero owned process/EOF/descendant closure')
            need(self.ledger.origin<=observation['finished_ns']<self.ledger.scientific,'finished within original science clock')
            fields(result,('index',));descriptor=result['index'];fields(descriptor,('path','bytes','sha256'))
            check_pin({k:descriptor[k] for k in ('bytes','sha256')});need(descriptor['bytes']<=self.limits['index_bytes'],'index bound')
            raw=self.provider.read_closed_output(context,descriptor['path'],0,descriptor['bytes'])
            need(body_pin(raw)=={k:descriptor[k] for k in ('bytes','sha256')} and self.provider.read_closed_output(context,descriptor['path'],descriptor['bytes'],1)==b'','exact complete index bytes and EOF')
            index=decode(raw,self.limits['index_bytes']);total=validate_output_index(index,descriptor,observation,job_id,self.limits)
            self.ledger.reserve({'retained_bytes':total},'complete closed job bodies');outputs={}
            with self.ledger.live(2*total,'complete closed output bodies'):
                for name,d in index['outputs'].items():
                    raw=self.provider.read_closed_output(context,name,0,d['bytes'])
                    need(body_pin(raw)=={k:d[k] for k in ('bytes','sha256')} and self.provider.read_closed_output(context,name,d['bytes'],1)==b'','exact complete output body and EOF')
                    outputs[name]=raw
            record['index']=index;record['index_pin']=pin(index);record['outputs_closed']=True
            # These bytes are retained even when independent physical qualification
            # is unavailable. They are never silently relabeled qualified.
            return {'outputs':outputs,'record':record}
        except BaseException as error:
            record['primary']={'type':type(error).__name__,'message':str(error)[:1024]};self.ledger.fail(job_id+'/closure',error)
            try:self.observer.record_failure(binding,record,self.records,self.ledger.origin,self.ledger.scientific)
            except BaseException as extra:
                record['secondary'].append({'type':type(extra).__name__,'message':str(extra)[:1024]})
            error.neural004_execution_receipt=record;raise
    def qualify(self,record,envelope,authorities,limits,*,require_success=True):
        verified=authorities.verify(envelope,'observer','operation_closure',{'binding_digest':record['binding_digest'],'observation_pin':pin(record['observation'])})
        cutoffs={'origin_ns':self.ledger.origin,'scientific_ns':self.ledger.scientific,'closeout_ns':self.ledger.closeout,'outer_ns':self.ledger.outer}
        joined=complete_closure(verified,record,limits,cutoffs,require_success=require_success)
        # Keep the immutable observed job record unchanged: its earlier history
        # and artifact pins must not be invalidated by later qualification.
        return joined

def minimized_view(materials,exposure_pin):
    check_pin(exposure_pin)
    for name,d in materials.items():
        need(name.startswith(('/training/','/query/','/sealed/','/common/','/source/author/')),'fixed process view mounts')
        relative(name[1:]);fields(d,('path','bytes','sha256'));check_pin({k:d[k] for k in ('bytes','sha256')})
    # Retains the reviewed backend's transport schema; numerical task schema is separate.
    return {'schema':'ach_minimized_process_view_v1','materials':materials,'exposure_admission':exposure_pin,
        'forbidden_feedback':['native','reference_results','outer_labels','other_contexts']}
