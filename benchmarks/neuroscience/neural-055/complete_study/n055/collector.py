"""Complete original hierarchy and target-last barrier; no scorer import."""
from pathlib import Path
from .common import require,parse,capture,encoded,sha
from .registry import campaign,token,envelope,terminal,panels,VALID,FIELDS

class Collection:
    def __init__(self,system,host,runner,views,sources,journal,budget):
        self.expected=campaign(system);self.host=host;self.runner=runner;self.views=views;self.sources=sources;self.journal=journal;self.budget=budget
        self.terminals={};self.phases={};self.predictions={};self.seals={};self.evidence={};self.collections=[]
        self.original_barrier=None;self.barrier_publication=None
        for cell in self.expected:
            cause={'type':'not_dispatched','reason':'precommitted original expected slot'}
            pp=[envelope(cell,p,'unattempted_after_failure',cause=cause) for p in ('FIT','INFER')]
            self.terminals[token(cell)]=terminal(cell,'unattempted_after_failure',pp,cause=cause);self.phases[token(cell)]=pp
            self.refresh_resource_dispositions(cell)
    def refresh_resource_dispositions(self,cell):
        from .resource_policy import states
        ident=token(cell);t=self.terminals[ident];pp=self.phases[ident]
        for p in pp:p['resource_policy']=self.budget.resource_policy
        custody='unresolved'if t['status']=='blocked_unresolved_containment'else'known_closed_or_not_dispatched'
        admission='unavailable'if self.budget.unknown or self.budget.admission_failures else'admitted_remaining_envelope'
        numeric=t.get('numerical_disposition',{}).get('status','unavailable_before_protected_grade')
        if numeric=='unavailable_before_protected_grade':numeric='structurally_valid_unscored'if t['status']in VALID else'unavailable'
        semantic='qualified_current_semantics'if t['status']in VALID else'unavailable'
        accounts=[x for x in self.budget.cell_accounts if x['cell']==cell]
        measured=('qualified_current_measured_envelope'if self.budget.resource_policy is not None and accounts and accounts[-1].get('within_allowance')is True and admission=='admitted_remaining_envelope'and custody=='known_closed_or_not_dispatched'and t['status']in VALID else'unavailable_or_not_completed')
        t['resource_dispositions']=states(self.budget.resource_policy,custody,admission,numeric,semantic,measured)
    def native_envelope(self,cell,phase,observed,reuse=False):
        require(any(observed is x for x in self.host.originals),'actual original native carrier, not deserialized report')
        require(observed.id is not None,'original native operation identity')
        good=observed.closed and observed.errors.first is None and observed.durable
        value=envelope(cell,phase,'complete' if good else ('safe_failed' if observed.closed else 'blocked_unresolved_containment'),
                       execution='qualified_training_bank_reuse' if reuse else 'original_execution',
                       original={'id':observed.id,'costs':self.budget.operations.get(observed.id),'closure':'original_all_resources_closed' if observed.closed else 'unresolved'})
        if observed.errors.first is not None:
            e=observed.errors.document();value['first_error']=e['first_error'];value['secondary_errors']=e['errors'][1:]
        if reuse:value['reuse_relation']={'original_producer_cell':observed.cell,'current_consumer_cell':cell,'original_operation_id':observed.id,'no_new_fit_observed':True}
        else:require(observed.cell==cell and observed.kind==phase.lower(),'same original cell/phase')
        return value
    def store(self,cell,pp,status,case=None,prediction=None,seal=None,cause=None,evidence=None):
        ident=token(cell);require(ident in self.terminals and self.terminals[ident]['cell_key']==cell,'only original exact cell slot')
        require(len(pp)==2 and all(p['cell_key']==cell for p in pp),'complete original phase envelopes')
        value=terminal(cell,status,pp,case=case,cause=cause)
        value['source_input_output_qualification_bindings']=evidence or {}
        if status in VALID:require(prediction is not None and case is not None,'valid cell has full output/case')
        self.terminals[ident]=value;self.phases[ident]=pp
        self.refresh_resource_dispositions(cell)
        if prediction is not None:self.predictions[ident]=prediction
        if seal is not None:self.seals[ident]=seal
        self.evidence[ident]=evidence or {}
        self.budget.check('before original cell disposition publication')
        self.journal.json(ident+'-CELL.json',{'terminal':value,'phase_envelopes':pp,'qualification':self.evidence[ident]})
        self.budget.check('after original cell disposition publication')
    def validate_prediction(self,cell,observed,case):
        require(any(observed is p for p in self.host.originals),'original actual inference object')
        require(observed.cell==cell and observed.kind=='infer' and observed.closed and observed.durable and observed.errors.first is None,'complete actual INFER source/closure')
        d=observed.outputs['prediction.json'];p=Path(d['path'])
        body=capture(p.parent,dict(path=p.name,bytes=d['bytes'],sha256=d['sha256'],mode=oct(p.stat().st_mode&0o777),role='whole_prediction'),self.budget,4194304)
        interface=self.sources.legacy_module('public/interface.py');prediction=interface.decode_json(body)
        interface.validate_prediction(case,prediction,row_sum_abs_tolerance=1e-6)
        self.budget.check('after full original prediction validation',observed.deadline)
        return {'path':str(p),'bytes':len(body),'sha256':sha(body),'value':prediction,'case':case,'original_native_id':observed.id}
    def complete_panels(self):
        result=panels(self.expected,self.terminals)
        self.collections=[]
        for panel in result:
            children=panel['child_cell_keys'];pp=[p for cell in children for p in self.phases[token(cell)]]
            require(len(pp)==20 and len({token(dict(p['cell_key'],phase=p['phase'])) for p in pp})==20,'all20 distinct original panel envelopes')
            self.collections.append({'panel_key':panel['panel_key'],'cells':[self.terminals[token(c)] for c in children],
                                     'phase_envelopes':pp,'summary':panel,'source_identity':self.sources.identity})
        return result
    def barrier(self):
        self.budget.admit('before complete original target barrier')
        require(not self.budget.unknown and self.budget.active_cell is None,'all original costs known and cell allowances closed')
        require(not self.views.current,'all original actor views retired')
        require(len(self.terminals)==960 and len(self.phases)==960,'full960 original disposition registry')
        summaries=self.complete_panels();require(len(summaries)==96,'all96 original panels')
        flat=[p for c in self.expected for p in self.phases[token(c)]]
        require(len(flat)==1920 and len({token(dict(p['cell_key'],phase=p['phase'])) for p in flat})==1920,'all1920 logical phase envelopes')
        for observed in self.host.originals:
            require(observed.closed and observed.durable and observed.accounting_complete,'unknown containment/accounting or missing durable native custody blocks every target')
            require(observed.resource_policy==self.budget.resource_policy and self.budget.resource_policy is not None,'same current measured native policy')
            require(observed.broker is None or observed.broker.closed,'actual trusted broker retired before targets')
        for observed in self.runner.originals:
            require(observed.reaped and observed.group_absent and observed.published,'original controller/service process custody before targets')
        for seal in self.seals.values():seal.unchanged()
        self.sources.current()
        # A blocked slot cannot be relabeled by a merely well-formed panel count.
        require(not any(t['status']=='blocked_unresolved_containment' for t in self.terminals.values()),'global unresolved containment')
        value={'schema':'neural055-complete-original-barrier-v1','source_identity':self.sources.identity,
               'resource_policy':self.budget.resource_policy,'expected_unobserved_native_io_is_not_safety_evidence':True,
               'cell_dispositions':960,'panel_summaries':96,'logical_phase_envelopes':1920,
               'all_native_resources_closed':True,'all_original_processes_reaped':True,
               'all_cell_contexts_retired':True,'terminal_digest':sha(encoded(self.terminals)),
               'phase_digest':sha(encoded(self.phases)),'expected_registry_digest':sha(encoded(self.expected)),
               'original_deadline':self.budget.deadline,'numeric_or_target_access':False}
        self.original_barrier=value
        self.barrier_publication=self.journal.json('CAMPAIGN_BARRIER.json',value)
        self.budget.check('after durable original target barrier')
        return value
    def require_current_barrier(self):
        self.budget.admit('current original scorer remaining-envelope admission')
        require(self.original_barrier is not None and self.barrier_publication is not None,'no target authority before actual original barrier')
        require(self.original_barrier['resource_policy']==self.budget.resource_policy,'no mixed source/scorer resource policy')
        require(self.original_barrier['terminal_digest']==sha(encoded(self.terminals)) and self.original_barrier['phase_digest']==sha(encoded(self.phases)),'same original barrier source/dispositions')
        require(not self.views.current,'no reopened actor context')
        require(all(o.closed and o.durable for o in self.host.originals) and all(o.reaped and o.group_absent and o.published for o in self.runner.originals),'same complete actual lifetime')
        self.budget.check('current original protected admission')
