"""Full original 960-cell coordinator, with separately owned physical operations."""
from pathlib import Path
from .native import PhaseCustody
from .common import require,parse,capture,encoded,sha,diagnostic_type
from .registry import token,training_key,envelope,VALID
from .seals import Seal
from .banks import TrainingBanks
from .collector import Collection
from .review_service import SemanticService
from .broker import BrokerRegistry

class Campaign:
    def __init__(self,plan,operator_root,source,inputs,programmes,views,host,runner,authority,journal,budget):
        self.plan=plan;self.root=Path(operator_root);self.source=source;self.inputs=inputs
        self.programmes=programmes;self.views=views;self.host=host;self.runner=runner
        self.authority=authority;self.journal=journal;self.budget=budget
        self.collection=Collection(plan['system'],host,runner,views,source,journal,budget)
        self.banks=TrainingBanks(plan,source,inputs,views,host,journal,budget,authority)
        self.semantic=SemanticService(plan['semantic_reviews'].get('service'),operator_root,authority,runner,journal,budget)
        self.broker=BrokerRegistry(plan['native_profile'],operator_root,source,authority,journal,budget)
        self.failures=[];self.original_block=None;self.phase_attempts=[];self.alignment=None
        self.base=journal.root/'participant_phases';self.base.mkdir(mode=0o700)
    def runtime_safe(self):
        self.budget.admit('before dependent campaign dispatch')
        for phase in self.host.originals:
            require(phase.closed and phase.durable and phase.accounting_complete and phase.resource_policy==self.budget.resource_policy and phase.id in self.budget.operations,'all original native custody and selected measured debit known')
        for process in self.runner.originals:
            require(process.reaped and process.group_absent and process.published and process.id in self.budget.operations,'all actual service processes reaped/published/debited')
        self.budget.check('before next original operation')
    def alignment_plan(self):
        spec=self.plan['paired_schedule']
        self.authority.verify(spec['qualification'],'paired_source_image_schedule',
                              {'source':self.source.identity,'input':self.inputs.identity,'pairing':spec['pairing'],'schedule':spec['schedule'],'alignment':spec['alignment'],'pre_exposure':True})
        self.alignment=parse(capture(self.root,spec['alignment'],self.budget,16777216))
        require(self.alignment['schema']=='neural055-original-alignment-schedules-v1','qualified original alignment domain')
        expected={token({'outer_person':p,'seed':s}) for p in self.inputs.rows for s in (55055,55056,55057)}
        require(set(self.alignment['rows'])==expected,'complete30 protected alignment schedules')
        for value in self.alignment['rows'].values():
            require(type(value)is list and len(value)==200 and sorted(value)==list(range(200)) and all(i!=j for i,j in enumerate(value)),'full200 original derangement')
    def permutation(self,c):
        if c['arm']!='ALIGN_SHUFFLE':return None
        require(self.alignment is not None,'protected schedule committed before exposure')
        return self.alignment['rows'][token({'outer_person':c['outer_person'],'seed':c['seed']})]
    def operation_sidecar(self,observed):
        require(any(observed is p for p in self.host.originals),'actual native original')
        d=observed.outputs['operations.json'];p=Path(d['path'])
        raw=capture(p.parent,dict(path=p.name,bytes=d['bytes'],sha256=d['sha256'],mode=oct(p.stat().st_mode&0o777),role='declared_operation_sidecar'),self.budget,8388608)
        value=parse(raw)
        require(value.get('cell')==observed.cell and value.get('phase')==observed.kind,'same actual cell and phase sidecar')
        if observed.cell['mode']!='REFERENCE':
            from .participant_contract import operations
            operations(value,observed.cell,observed.kind)
        # These candidate statements are retained as claims. Independent source
        # and original host/broker evidence are required for semantic admission.
        return {'pin':{'bytes':len(raw),'sha256':sha(raw)},'claims':value,'trusted_by_self_report':False}
    def phase(self,c,phase,programme,model=None,bank=None):
        self.runtime_safe();start=self.budget.clock()
        seconds=self.plan['phase_limits'][('reference_' if c['mode']=='REFERENCE' else '')+('fit' if phase=='FIT' else 'infer')]
        deadline=self.budget.action_deadline(seconds);view=None;context=None;original=None;first=None;identity=None;lease=None
        record={'cell':c,'phase':phase,'origin':start,'deadline':deadline,'original':None,'view':None,'errors':[]}
        self.phase_attempts.append(record)
        custody=PhaseCustody()
        try:
            with self.budget.action(deadline):
                if c['mode']!='REFERENCE':
                    programme,context=self.programmes.enter(c,phase,model if phase=='INFER' else None)
                view,identity=self.views.build(c,phase,deadline,self.permutation(c));record['view']=identity
                runtime=self.source.actor_current();output=self.base/(token(c)+'-'+phase)
                actual_model=None if model is None else model.unchanged()
                if context is not None:lease=self.broker.lease(c,phase,context,view,bank,model,deadline)
                original=self.host.phase(c,phase.lower(),programme,view,actual_model,output,runtime,deadline,start,
                                         role='reference' if c['mode']=='REFERENCE' else 'participant',
                                         bank=None if bank is None else bank['directory'],broker=lease,custody=custody)
                require(original is custody.phase,'same producer-owned original cell phase')
                record['original']=original
                result={'original':original,'view':identity,'sidecar':self.operation_sidecar(original),'context':context,'broker':None if lease is None else lease.document()}
                if phase=='FIT':result['seal']=Seal(c,self.source.identity,identity,original,self.journal,self.budget)
                else:result['prediction']=self.collection.validate_prediction(c,original,self.inputs.rows[c['outer_person']]['case'])
                self.budget.check('after original phase output admission',deadline)
        except BaseException as exc:
            first=exc;record['errors'].append(exc);self.journal.carrier.fail(exc,'cell-phase:'+phase)
            observed=custody.phase
            if observed is not None:record['original']=observed
        finally:
            if view is not None:
                try:self.views.retire(view,deadline)
                except BaseException as exc:
                    record['errors'].append(exc);self.journal.carrier.fail(exc,'cell-view-retirement')
                    if first is None:first=exc
            if context is not None:
                try:self.programmes.retire(c,phase)
                except BaseException as exc:
                    record['errors'].append(exc);self.journal.carrier.fail(exc,'cell-context-retirement')
                    if first is None:first=exc
        if first is not None:raise first
        self.budget.check('after full phase lifetime',deadline)
        return result
    def participant(self,c,pp,bank):
        fit=self.phase(c,'FIT',None,bank=bank)
        pp[0]=self.collection.native_envelope(c,'FIT',fit['original'])
        self.collection.seals[token(c)]=fit['seal']
        infer=self.phase(c,'INFER',None,model=fit['seal'],bank=bank)
        pp[1]=self.collection.native_envelope(c,'INFER',infer['original'])
        subject={'schema':'neural055-complete-operation-semantic-subject-v1','cell':c,
                 'resource_policy':self.budget.resource_policy,
                 'committed_source':self.programmes.subject,'fit_source_context':fit['context'],
                 'fit_original':fit['original'].document(),'infer_original':infer['original'].document(),
                 'sealed_selected_method':fit['seal'].document,'fit_operations':fit['sidecar'],
                 'infer_operations':infer['sidecar'],'mode_permissions':self.plan['mode_permissions'],
                 'fit_trusted_broker':fit['broker'],'infer_trusted_broker':infer['broker'],'same_full_cell_token_ledger':self.broker.ledger.cells.get(token(c)),
                 'tool_bank':None if bank is None else self.banks.document(bank),
                 'actual_host_broker_evidence_required':True,'self_report_is_not_semantic_proof':True}
        evidence=self.semantic.assess(c,subject)
        status='complete_valid' if evidence['status']=='qualified' else 'mode_compliance_unqualified'
        return status,infer['prediction'],fit['seal'],{'semantic':evidence,'operations':subject}
    def reference(self,c,pp,bank):
        if c['evaluated_system']=='R0':
            pp[0]=envelope(c,'FIT','complete',execution='declared_no_fit')
            pp[0]['no_fit_rule']='R0 uniform probabilities and original-order bijection; no EEG value access or training'
            model=None;calibration=None
        else:
            original=bank['original'];reuse=original.cell!=c or bank.get('logical_consumers',0)>0
            pp[0]=self.collection.native_envelope(c,'FIT',original,reuse=reuse)
            bank['logical_consumers']=bank.get('logical_consumers',0)+1
            pp[0]['attributable_costs']=bank['setup'];model=bank['seal'];calibration=bank['calibration']
        programme=self.source.actor_current()/'reference_entry.py'
        infer=self.phase(c,'INFER',programme,model=model)
        pp[1]=self.collection.native_envelope(c,'INFER',infer['original'])
        status='complete_valid_calibration_uninformative' if calibration=='calibration_uninformative_infinite' else 'complete_valid'
        return status,infer['prediction'],None,{'reference_recipe':self.banks.qualification,'actual_current_view':infer['sidecar'],'qualified_training_only_reuse':None if bank is None else self.banks.document(bank)}
    def one_cell(self,c):
        ident=token(c);cause={'type':'unattempted','cell':c}
        pp=[envelope(c,p,'unattempted_after_failure',cause=cause) for p in ('FIT','INFER')]
        bank=None;setup=None;active=False;result=None;first=None;start_ops=set(self.budget.operations)
        try:
            self.runtime_safe()
            needs_bank=(c['mode']=='REFERENCE' and c['evaluated_system']!='R0') or c['tool_setting']=='T1'
            tool=c['tool_setting']=='T1'
            if needs_bank:setup=self.banks.setup_for(c,tool=tool)
            self.budget.begin_cell(c,self.plan['policy']['cell_limits'],setup);active=True
            if needs_bank:bank=self.banks.get(c,tool=tool)
            result=self.reference(c,pp,bank) if c['mode']=='REFERENCE' else self.participant(c,pp,bank)
        except BaseException as exc:
            first=exc;self.failures.append({'cell':c,'error':exc});self.journal.carrier.fail(exc,'cell:'+ident)
            own=[x for x in self.phase_attempts if x['cell']==c]
            for record in own:
                if record['original'] is not None:
                    try:pp[0 if record['phase']=='FIT' else 1]=self.collection.native_envelope(c,record['phase'],record['original'])
                    except BaseException as secondary:self.journal.carrier.fail(secondary,'failed-phase-envelope')
            closed=not self.views.current and self.programmes.active is None and all(x.closed for x in self.host.originals)
            status='safe_failed' if closed else 'blocked_unresolved_containment'
            if bank is None and (c['tool_setting']=='T1' or (c['mode']=='REFERENCE' and c['evaluated_system']!='R0')):status='reference_unqualified'
            result=(status,None,None,{'first_error_type':diagnostic_type(exc)})
        status,prediction,seal,evidence=result
        operations=[i for i in self.budget.operations if i not in start_ops]
        try:
            self.budget.attribute(c,operations,[] if bank is None else bank.get('operation_ids',[]))
            self.collection.store(c,pp,status,case=self.inputs.rows[c['outer_person']]['case']['case_id'],
                                  prediction=prediction,seal=seal,cause=None if first is None else {'type':diagnostic_type(first)},evidence=evidence)
        except BaseException as exc:
            self.journal.carrier.fail(exc,'original-cell-publication');self.failures.append({'cell':c,'error':exc})
            if first is None:first=exc
        finally:
            # Include original semantic review, evidence and terminal publication
            # in the same matched FIT+INFER cell before retiring its allowance.
            if self.budget.active_cell is not None and self.budget.active_cell['cell']==c:
                try:self.budget.finish_cell()
                except BaseException as exc:
                    self.journal.carrier.fail(exc,'cell-final-cost');self.failures.append({'cell':c,'error':exc})
                    if first is None:first=exc
                    self.collection.terminals[ident]['resource_finalization_error']={'type':diagnostic_type(exc),'stage':'original_cell_final_cost'}
                    # Retain the independent prediction/semantic disposition;
                    # exhausted/unknown costs still block the next/scorer launch.
            self.collection.refresh_resource_dispositions(c)
        if first is not None and (self.budget.unknown or not self.collection.terminals[ident]['status'] in ('safe_failed','reference_unqualified','mode_compliance_unqualified')):raise first
        return result
    def run(self):
        self.alignment_plan()
        # All independent setup is training-only and precedes candidate exposure.
        for c in self.banks.expected:
            try:self.runtime_safe();self.banks.fit(c)
            except BaseException as exc:
                self.original_block=exc;self.journal.carrier.fail(exc,'reference-setup-stop');break
        if self.original_block is None:
            for c in self.collection.expected:
                try:
                    self.runtime_safe();self.one_cell(c)
                except BaseException as exc:
                    self.original_block=exc;self.journal.carrier.fail(exc,'campaign-stop');break
        if self.original_block is not None:
            cause={'type':diagnostic_type(self.original_block),'scope':'original_campaign_stop','no_fabricated_process':True}
            for c in self.collection.expected:
                ident=token(c)
                if self.collection.terminals[ident]['status']=='unattempted_after_failure':
                    for p in self.collection.phases[ident]:p['first_error']=cause
                    self.collection.terminals[ident]['first_error']=cause
        self.programmes.unchanged()
        self.runtime_safe();require(self.budget.active_cell is None,'all original cell ledgers closed')
        self.collection.barrier()
        return self.collection

