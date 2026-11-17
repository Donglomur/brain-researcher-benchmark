"""Fixed earlier prediction-tree capture and all-job seal, not native isolation.

The registry receives only actual local Capture occurrences. Pins select earlier
members of that store; they never construct a Capture or a source admission.
"""
from dataclasses import dataclass
from .domain import Refusal,Pin,closed,canonical,strict_json,CONDITIONS
from .support import Preparation
from . import schemas
from .interchange import validate_npy_envelope
_TOKEN=object()

@dataclass(frozen=True)
class PredictionTree:
    owner: object
    job: object
    capture: object
    raw_document: bytes
    records: tuple
    token: object
    def require(self):
        if self.token is not _TOKEN or self.owner.trees.get(self.job.job_id) is not self:
            raise Refusal('original prediction tree occurrence')
        self.owner.check_tree(self)
        return self

class PredictionRegistry:
    def __init__(self,campaign,preparation):
        if type(preparation) is not Preparation or preparation.plan is not campaign.plan or preparation.store is not campaign.store:
            raise Refusal('campaign original preparation')
        preparation.require_ready()
        self.campaign=campaign;self.preparation=preparation;self.store=campaign.store
        self.trees={};self.attempts=set();self.sealed=False
    def _read_earlier(self,pin,parent):
        cap=self.store.earlier_capture(pin,parent)
        return cap,self.store.read(cap.pin)
    def admit(self,job,capture):
        if self.sealed or job.job_id in self.attempts:raise Refusal('prediction tree consumed/sealed')
        self.attempts.add(job.job_id)
        prepared=self.preparation.require_job(job)
        self.store.require_capture(capture)
        doc=schemas.job_output(self.store.json(capture.pin))
        closed(doc,('schema','job','condition','cases','outputs','configuration','split','source'),'job output')
        if doc['schema']!='trial_session_job_output_v2' or doc['job']!=job.job_id or doc['condition']!=job.condition:
            raise Refusal('job output identity')
        if doc['cases']!=list(job.case_ids) or len(doc['outputs'])!=len(prepared):raise Refusal('complete job case roster')
        if (Pin.parse(doc['configuration']),Pin.parse(doc['split']),Pin.parse(doc['source']))!=(job.configuration,job.split,job.original_source):
            raise Refusal('job caller lineage')
        records=[]
        for row,case_handle in zip(doc['outputs'],prepared):
            closed(row,('case','prediction'),'job prediction row')
            if row['case']!=case_handle.case_id:raise Refusal('job case order')
            pcap,praw=self._read_earlier(Pin.parse(row['prediction']),capture)
            p=schemas.prediction(strict_json(praw))
            closed(p,('schema','job','condition','case_id','trial_ids','output_columns','prediction',
                      'model','training','selection','source','cost','prepared','unit_selection','split','split_binding'),'prediction')
            if (p['schema'],p['job'],p['condition'],p['case_id'])!=('trial_session_prediction_v2',job.job_id,job.condition,case_handle.case_id):
                raise Refusal('prediction job/condition/case')
            case_handle.require_original();d=case_handle.document();query_rows,ids=case_handle.query_support()
            if not query_rows:raise Refusal('empty query support')
            if tuple(canonical(x) for x in p['trial_ids'])!=ids:raise Refusal('prediction ordered original query IDs')
            columns=list(range(d['y']['shape'][1]))
            if p['output_columns']!=columns:raise Refusal('prediction output coordinates')
            expected={'prepared':case_handle.capture.pin,'unit_selection':case_handle.regional.capture.pin,
                      'split':self.preparation.split.pin,'split_binding':self.preparation.binding.pin,'source':job.original_source}
            if any(Pin.parse(p[k])!=v for k,v in expected.items()):raise Refusal('prediction preparation/source lineage')
            # Every selected ancestor was captured before the prediction document.
            lineage=[]
            for name in ('prepared','unit_selection','split','split_binding','model','training','selection','cost'):
                c,raw=self._read_earlier(Pin.parse(p[name]),pcap);lineage.append((c,raw))
            training=schemas.training(strict_json(next(raw for c,raw in lineage if c.pin==Pin.parse(p['training']))))
            closed(training,('schema','job','condition','cases','interchange','regions','split','split_binding','configuration','source'),'training lineage')
            expected_training={'schema':'trial_session_training_lineage_v2','job':job.job_id,'condition':job.condition,
                    'cases':list(job.case_ids),'interchange':[x.capture.pin.document() for x in prepared],
                    'regions':[x.regional.capture.pin.document() for x in prepared],
                    'split':job.split.document(),'split_binding':self.preparation.binding.pin.document(),
                    'configuration':job.configuration.document(),'source':job.original_source.document()}
            schemas.exact(training,expected_training,'exact selected training lineage')
            leaf=p['prediction'];closed(leaf,('pin','dtype','shape','axis_ids'),'prediction leaf')
            if leaf['shape']!=[len(query_rows),len(columns)] or leaf['axis_ids']!=['original_trial','output']:
                raise Refusal('prediction leaf coordinates')
            lcap,lraw=self._read_earlier(Pin.parse(leaf['pin']),pcap)
            validate_npy_envelope(lraw,leaf['dtype'],tuple(leaf['shape']),self.store.budget.limits.memory_bytes)
            # Fixed model-state tree also resolves all primitive parameter/normalizer leaves earlier.
            mcap,mraw=next((c,raw) for c,raw in lineage if c.pin==Pin.parse(p['model']))
            model=schemas.model_state(strict_json(mraw));closed(model,('schema','parameters','normalization'),'model state')
            if model['schema']!='trial_session_model_state_v1' or not model['parameters']:raise Refusal('model state schema/parameters')
            for group in ('parameters','normalization'):
                for field in model[group]:
                    closed(field,('name','leaf') if group=='parameters' else ('case_index','name','leaf'),'model field')
                    if group=='normalization' and field['case_index']>=len(prepared):raise Refusal('normalizer case coordinate')
                    item=field['leaf'];closed(item,('pin','dtype','shape','axis_ids'),'model leaf')
                    acap,araw=self._read_earlier(Pin.parse(item['pin']),mcap)
                    validate_npy_envelope(araw,item['dtype'],tuple(item['shape']),self.store.budget.limits.memory_bytes)
                    lineage.append((acap,araw))
            records.append((case_handle,pcap,praw,lcap,lraw,tuple(lineage)))
        tree=PredictionTree(self,job,capture,self.store.read(capture.pin),tuple(records),_TOKEN)
        self.trees[job.job_id]=tree
        return tree
    def check_tree(self,tree):
        self.preparation.require_job(tree.job);self.store.require_capture(tree.capture)
        if self.store.read(tree.capture.pin)!=tree.raw_document:raise Refusal('sealed job output changed')
        # Recheck original complete captured bytes before any scoring-target access.
        for case,pcap,praw,lcap,lraw,lineage in tree.records:
            case.require_original()
            for cap,raw in ((pcap,praw),(lcap,lraw))+lineage:
                self.store.require_capture(cap)
                if cap.ordinal>=tree.capture.ordinal or self.store.read(cap.pin)!=raw:
                    raise Refusal('sealed earlier tree changed')

class ResultBarrier:
    def __init__(self,campaign,registry):
        self.campaign=campaign;self.registry=registry;self.store=campaign.store
        self.expected=tuple(j.job_id for j in campaign.plan.jobs if j.role in ('candidate','reference'))
        self.sealed=False;self.attempted=False;self.snapshot=None;self.seal_capture=None
        self.score_attempted=False
    def seal(self):
        if self.attempted:raise Refusal('barrier already attempted')
        self.attempted=True
        try:
            if not self.expected or set(self.registry.trees)!=set(self.expected):raise Refusal('all candidate/reference jobs must be captured')
            for case in self.campaign.plan.cases:
                if case.availability!='available':continue
                jobs=[j for j in self.campaign.plan.jobs if case.case_id in j.case_ids]
                if {j.condition for j in jobs if j.role=='candidate'}!=set(CONDITIONS):
                    raise Refusal('each available case requires both candidate conditions')
                if not any(j.role=='reference' for j in jobs):raise Refusal('each case requires independent reference')
            if any(self.campaign.states[k]!='complete' for k in self.expected):raise Refusal('incomplete job census')
            self.snapshot=tuple(self.registry.trees[k].require() for k in self.expected)
            self.seal_capture=self.store.put_json('campaign/prediction-seal.json',
                {'schema':'trial_session_prediction_seal_v2','jobs':list(self.expected),
                 'outputs':[t.capture.pin.document() for t in self.snapshot],
                 'split':self.registry.preparation.split.pin.document(),
                 'split_binding':self.registry.preparation.binding.pin.document()})
            self.registry.sealed=True;self.sealed=True
        except BaseException as exc:self.store.budget.fail('prediction-seal',exc);raise
    def require(self):
        if self.campaign.barrier is not self or not self.sealed or not self.registry.sealed:
            raise Refusal('original sealed campaign barrier')
        self.store.require_capture(self.seal_capture)
        if tuple(self.registry.trees.get(k) for k in self.expected)!=self.snapshot:raise Refusal('sealed tree roster changed')
        for tree in self.snapshot:
            tree.require()
            if tree.capture.ordinal>=self.seal_capture.ordinal:raise Refusal('post-seal prediction capture')
        return self.snapshot

def require_result_barrier(barrier):
    if type(barrier) is not ResultBarrier:raise Refusal('actual original result barrier')
    return barrier.require()
