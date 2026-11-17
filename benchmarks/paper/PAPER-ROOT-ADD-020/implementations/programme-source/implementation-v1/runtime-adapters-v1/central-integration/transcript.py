"""Source-owned actual phase journal and independent metadata-only replay.

Replay never calls the controller, scientific kernels, a model, or a grader.
The only production entry binds the unchanged complete source programme.
"""
import os

ZERO='0'*64
RESOURCE=('read_bytes','write_bytes','retained_bytes','live_bytes')

class Journal:
    def __init__(self,path,reader,limit):
        self.path=u.components(path);self.reader=reader;self.limit=limit;self.size=0;self.sequence=0;self.head=ZERO
        reader.tick();self.fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400);self.closed=False
    def append(self,record):
        self.reader.tick();core={'sequence':self.sequence,'previous':self.head,**record}
        digest=u.sha(u.canonical(core));raw=u.canonical({**core,'record_digest':digest})+b'\n'
        u.need(self.size+len(raw)<=self.limit and self.reader.write_bytes+len(raw)<=self.reader.write_limit,'complete phase trace write limit')
        self.reader.write_bytes+=len(raw);self.size+=len(raw)
        view=memoryview(raw)
        while view:
            n=os.write(self.fd,view);u.need(n>0,'short trace write');view=view[n:]
        self.sequence+=1;self.head=digest;self.reader.tick()
    def close(self):
        if not self.closed:
            try:os.fsync(self.fd)
            finally:os.close(self.fd);self.closed=True
        self.reader.tick()

class BoundTrace:
    """Transparent observer of the actual source-owned BoundDispatcher."""
    def __init__(self,bound,journal):
        self.bound=bound;self.runtime=bound.runtime;self.monitor=bound.monitor;self.journal=journal;self.pending=None
    def __call__(self,phase,parents,origin,deadline,binding):
        u.need(self.pending is None,'previous actual phase was not observed')
        self.pending={'phase':phase,'parents_digest':u.scientific_digest(parents),'binding':binding,'producer_error':None}
        try:return self.bound(phase,parents,origin,deadline,binding)
        except BaseException as error:self.pending['producer_error']=type(error).__name__;raise
    def observe(self,phase,result,origin,deadline,binding):
        u.need(self.pending is not None and self.pending['phase']==phase and self.pending['binding']==binding,'exact actual open phase')
        row=self.pending;observation=None;failure=None
        try:
            observation=self.bound.observe(phase,result,origin,deadline,binding);return observation
        except BaseException as error:failure=type(error).__name__;raise
        finally:
            self.pending=None
            self.journal.append({**row,'result':result,'observation':observation,'observer_error':failure})

def read_records(raw):
    u.need(type(raw)is bytes and raw.endswith(b'\n'),'complete terminated phase journal')
    head=ZERO;out=[]
    for seq,line in enumerate(raw.splitlines()):
        row=u.parse(line);u.need(type(row)is dict and set(row)=={'sequence','previous','phase','parents_digest','binding',
                         'producer_error','result','observation','observer_error','record_digest'},'exact phase record')
        digest=row['record_digest'];core={k:v for k,v in row.items()if k!='record_digest'}
        u.need(row['sequence']==seq and row['previous']==head and digest==u.sha(u.canonical(core)),'phase chain/order changed')
        head=digest;out.append(row)
    return out,head

def _replay(rows,plan,document,result):
    """Pure metadata checker, tested on small invented plans only in authoring."""
    phases=plan['phases'];u.need(len(rows)==len(phases)==result['phase_count'],'exact full phase cardinality')
    outputs={};seals={};totals={k:0 for k in RESOURCE};last=document['origin_ns'];contexts=set()
    origin=document['origin_ns'];deadline=document['deadline_ns'];profile=document['profile']
    for phase,row in zip(phases,rows):
        u.need(row['phase']==phase and phase['id']not in outputs and set(phase['dependencies'])<=set(outputs),'source graph/causal order differs')
        parents={k:outputs[k]for k in phase['dependencies']}
        binding=u.scientific_digest({'phase':phase,'parents':parents,'origin_ns':origin,'programme_digest':plan['programme_digest'],
                                  'implementation_digest':plan['implementation_digest']})
        u.need(row['binding']==binding and row['parents_digest']==u.scientific_digest(parents)
               and row['producer_error']is None and row['observer_error']is None,'actual phase binding or failure differs')
        producer=row['result'];obs=row['observation']
        u.need(type(producer)is dict and set(producer)=={'phase_id','binding_digest','artifact','receipt'}
               and producer['phase_id']==phase['id'] and producer['binding_digest']==binding
               and producer['receipt']=={'scientific_dispatcher':'paper020_v2','implementation_digest':plan['implementation_digest']},'actual scientific dispatcher/source identity required')
        u.need(type(obs)is dict and obs.get('phase_id')==phase['id'] and obs.get('binding_digest')==binding
               and obs.get('origin_ns')==origin and obs.get('implementation_digest')==plan['implementation_digest']
               and obs.get('natural_complete')is True and type(obs.get('exit_code'))is int and obs['exit_code']==0
               and obs.get('all_descendants_closed')is True and obs.get('host_alive')is True
               and obs.get('external_host_natural_exit_required')is True
               and obs.get('observation_scope')=='live_host_phase_children','actual complete live-host phase observation required')
        u.only_pin({'bytes':0,'sha256':obs['host_observation_digest']})
        finish=obs['finished_ns'];u.need(type(finish)is int and last<=finish<deadline,'original ordered phase clock');last=finish
        for key in RESOURCE:
            v=obs[key];u.need(type(v)is int and v>=0,'typed actual resource observation')
            totals[key]=max(totals[key],v)if key=='live_bytes'else totals[key]+v
            u.need(totals[key]<=profile[key],'complete resource limit exceeded')
        a=producer['artifact'];kind=phase['kind']
        if kind=='source_and_exposure_admission':
            u.need(a.get('admission_digest')==document['admission_digest'] and a.get('implementation_digest')==plan['implementation_digest']
                   and a.get('native_schema_digest')==document['native_schemas_digest'],'exact source admission/schema commitment')
        if kind=='whole_programme_commitment':
            actor,track=phase['actor'],phase['track']
            policy=({'kind':'reviewed_reference_portfolio','source':plan['implementation_digest'],'track':track}
                    if actor=='reference'else document['candidate_policies'][actor][track])
            u.need(a.get('policy_digest')==u.sha(u.canonical(policy))
                   and a.get('source_view_digest')==u.sha(u.canonical(document['views'][actor+'/'+track])),
                   'exact actual source view and policy commitment')
        if kind in ('fit','predict','reproduction'):
            u.need(all(obs.get(k)is True for k in ('view_isolation_verified','source_seal_unchanged','protected_grading_targets_absent')),'scientific isolation/source/target proof required')
            u.need(a.get('implementation_digest')==plan['implementation_digest'],'scientific artifact source differs')
        if kind in ('fresh_native_context','fresh_training_context'):
            u.need(type(a.get('context'))is str and a['context']not in contexts,'context reused across conditions/tracks');contexts.add(a['context'])
        if kind=='fit':
            for key in ('model_digest','fit_receipt_digest','input_digest'):u.only_pin({'bytes':0,'sha256':a.get(key)})
            u.need(obs.get('fit_receipt_digest')==a.get('fit_receipt_digest') and obs.get('model_digest_after_fit')==a.get('model_digest'),'actual closed fit/model join')
        if kind=='seal_complete_fit':
            u.need(set(a.get('fit_models',{}))==set(phase['configurations'])==set(a.get('fit_receipts',{})),'all configurations before queries')
            for key,parent in parents.items():
                case=key.rsplit('/',1)[-1]
                u.need(a['fit_models'][case]==parent['model_digest'] and a['fit_receipts'][case]==parent['fit_receipt_digest'],'actual full fit seal differs')
            seals[phase['id']]=u.scientific_digest(a)
        if kind=='query_features_after_seal':
            u.need(len(phase['dependencies'])==1 and a.get('seal_digest')==seals.get(phase['dependencies'][0]),'query release before complete actual fit seal')
        if kind=='predict':
            u.only_pin({'bytes':0,'sha256':a.get('query_digest')})
            deps=[x for x in phase['dependencies']if x in seals];u.need(len(deps)==1,'one complete fit seal per prediction')
            seal=outputs[deps[0]];case=phase['configuration']
            u.need(a.get('model_digest')==seal['fit_models'][case] and a.get('fit_receipt_digest')==seal['fit_receipts'][case]
                   and obs.get('model_digest_after_inference')==a['model_digest'],'inference changed actual sealed fit')
        if kind=='independent_full_process_and_resource_closure':
            u.need(len(parents)==1 and 'validate-all'in parents,'whole validated outputs required')
            for key in ('native_bundle_digest','prediction_bundle_digest','expected_bundle_digest','native_schema_digest'):
                u.only_pin({'bytes':0,'sha256':a.get(key)});u.need(a[key]==parents['validate-all'].get(key),'full output seal changed before outer closure')
        if kind=='load_targets_last_and_grade':
            u.need(phase is phases[-1] and 'outer-close'in outputs and all(outputs['outer-close'].get(k)is True for k in
                   ('all_outputs_validated','resources_passed','natural_complete','all_descendants_closed')),'protected targets must follow complete outer closure')
        outputs[phase['id']]=a
    u.need(phases[-1]['kind']=='load_targets_last_and_grade' and result['result']==outputs[phases[-1]['id']]
           and result['resources']==totals and type(result['finished_ns'])is int and last<=result['finished_ns']<deadline,
           'actual final grade/resource/strict-clock join required')
    return outputs

def validate(entry,contract,document,provisional,raw):
    # Fixed production source loader supplies entry; no callable executor/grade argument.
    entry._validate_complete_provisional(provisional,document)
    plan=entry.basis('programme').build_plan(contract);plan['implementation_digest']=entry.EXPECTED
    u.need(len(plan['phases'])==23786 and plan['programme_digest']==document['programme_digest'],'unchanged entire programme required')
    rows,head=read_records(raw);outputs=_replay(rows,plan,document,provisional['result'])
    counts={}
    for phase in plan['phases']:counts[phase['kind']]=counts.get(phase['kind'],0)+1
    u.need(counts.get('reproduction')==336 and counts.get('fit')==10584 and counts.get('predict')==10584
           and counts.get('fresh_training_context')==756 and counts.get('seal_complete_fit')==756
           and counts.get('query_features_after_seal')==756,'all original native/prediction/regime/null contexts required')
    return {'phase_count':len(rows),'head':head,'counts':counts,'outputs':outputs,'rows':rows}
