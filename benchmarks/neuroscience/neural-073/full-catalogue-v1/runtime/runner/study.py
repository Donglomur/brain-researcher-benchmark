"""Complete 13-person reference/candidate graph and one locked evaluation boundary.

Scientific qualification requires all original invocations and native/provider
contracts. No paper/provenance repair, small cohort, chosen-best repetition or
unexecuted graph count is accepted as a completed study.
"""
from ..core.custody import CustodyError,digest
from ..core.plan import CONDITIONS,ARMS,REPETITIONS,FAMILIES
from .. import scoring
from .authority import RoleIssuer
from .reference import ReferenceEngine
from .candidate import CandidateRunner,context_inference_records
from .policy import Policy
from .preparation import HostPreparation,ToolPreparation,prepare_outer_tools,prepare_candidate

class FullStudy:
    def __init__(self,*,reference_engine,issuer,policy,host_specs,tool_specs,export_key):
        if type(reference_engine) is not ReferenceEngine or type(issuer) is not RoleIssuer or type(policy) is not Policy:
            raise CustodyError('concrete full reference graph, role issuer and candidate policy required')
        if reference_engine.data.domain!='authentic' or issuer.domain!='authentic':
            raise CustodyError('full authentic study requires independent execution selection')
        self.reference=reference_engine;self.data=reference_engine.data;self.plan=self.data.plan
        self.issuer,self.policy=issuer,policy;self.store=reference_engine.store
        self.contexts=self.plan.contexts();self.host_specs=dict(host_specs);self.tool_specs=dict(tool_specs)
        if set(self.host_specs)!={c.context_id for c in self.contexts} or any(type(v) is not HostPreparation for v in self.host_specs.values()):
            raise CustodyError('all234 exact context host specifications required')
        if set(self.tool_specs)!={(p,c) for p in self.plan.people for c in CONDITIONS} or any(type(v) is not ToolPreparation for v in self.tool_specs.values()):
            raise CustodyError('all39 outer/condition tool specifications required')
        if type(export_key) is not bytes or len(export_key)<32:raise CustodyError('explicit private export key required')
        # One prespecified model/runtime policy, not a different service or
        # hidden tokenizer/source closure for whichever arm/condition is easier.
        provider_fields=('model_revision','source_closure_digest','fixed_model_evidence_digest',
            'stateless_evidence_digest','tokenizer_evidence_digest','usage_evidence_digest',
            'environment_evidence_digest','protocol_evidence_digest','capacity_evidence_digest',
            'capacity_basis','max_frame_bytes','max_capture_bytes')
        from ..process_guard.aggregate_v3 import MonitorRuntime
        for context in self.contexts:
            host=self.host_specs[context.context_id]
            policy.require_adapter(host.provider_admission,context)
            if type(host.monitor_runtime) is not MonitorRuntime:
                raise CustodyError('all234 contexts require exact OOM-protected monitor admission')
            host.monitor_runtime.validate()
        provider_profiles={tuple(getattr(h.provider_admission,k) for k in provider_fields) for h in self.host_specs.values()}
        native_profiles={(h.guard_admission.runtime_manifest_digest,h.guard_admission.environment_evidence_digest,
            h.guard_admission.control_source_digest,h.monitor_runtime.binding_digest) for h in self.host_specs.values()}
        if len(provider_profiles)!=1 or len(native_profiles)!=1:
            raise CustodyError('matched fixed provider and native runtime profiles required across all234 contexts')
        self.export_key=export_key;self.results={};self.started=False;self.feedback_open=False;self.seen_draw_ids=set()
        self.store.assert_private_boundary([h.capsule_parent for h in self.host_specs.values()]+[h.snapshot_parent for h in self.host_specs.values()]+[t.parent for t in self.tool_specs.values()])

    def execute(self):
        if self.started:raise CustodyError('study is single-use; failed original outcomes require a newly selected invocation')
        self.started=True
        self.store.append_event('study_started',{'plan_digest':self.plan.binding_digest,'policy_digest':self.policy.binding_digest,
            'full_contexts':len(self.contexts),'source_question':'declared protocol-label recovery, not direct neural understanding'})
        try:
            for person in self.plan.people:
                self.reference.run_outer(person)
                tools={c:prepare_outer_tools(self.reference,person,c,issuer=self.issuer,tool_spec=self.tool_specs[(person,c)]) for c in CONDITIONS}
                for context in (c for c in self.contexts if c.outer_person==person):
                    prepared=prepare_candidate(self.reference,context,issuer=self.issuer,export_key=self.export_key,
                        host=self.host_specs[context.context_id],reference_tools=tools[context.condition])
                    runner=CandidateRunner(prepared=prepared,issuer=self.issuer,policy=self.policy,store=self.store)
                    result=runner.run()
                    if not runner.closed or context.context_id in self.results:raise CustodyError('unclosed/duplicate original context')
                    _,self.seen_draw_ids=context_inference_records(context,self.policy,
                        result['generation_inference_records'],seen_draw_ids=self.seen_draw_ids)
                    self.results[context.context_id]=result
                self.data.release_bank(person)
            reference_receipt=self.reference.assert_complete()
            closure=self.plan.assert_complete_closure({k:v['closure_digest'] for k,v in self.results.items()})
            self.store.put_json('full_locked_closure',{'plan_digest':self.plan.binding_digest,'closure_digest':closure,
                'reference_receipt':reference_receipt,'contexts':{k:v['closure_digest'] for k,v in self.results.items()}})
            self.feedback_open=True
            return self.evaluate(closure,reference_receipt)
        except BaseException as exc:
            self.store.append_event('study_original_failure',{'type':type(exc).__name__,'message':str(exc),
                'completed_contexts':len(self.results),'reference_original_work':self.reference.work.receipt(),
                'qualified':False,'no_missing_scope_replacement':True})
            raise

    def evaluate(self,closure,reference_receipt):
        if not self.feedback_open:raise CustodyError('feedback requires all234 closed original contexts')
        if closure!=self.plan.assert_complete_closure({k:v['closure_digest'] for k,v in self.results.items()}):
            raise CustodyError('complete closure mismatch')
        records=self.data.score_records(tuple(r.case_id for r in self.plan.records))
        constructions={r.case_id:r.construction for r in self.plan.records}
        bindings={'records_digest':scoring.records_digest(records),'closure_digest':closure,'construction_digest':digest(constructions)}
        authority=self.issuer.capability('score','full_locked_scoring',bindings)
        def panel(values):
            return scoring.score_panel(records,values,authority=authority,closure_digest=closure,construction_by_case=constructions)
        candidate={};reference={};summaries={};comparisons={}
        for condition in CONDITIONS:
            for arm in ARMS:
                panels=[]
                for repetition in REPETITIONS:
                    values={}
                    for c in self.contexts:
                        if (c.condition,c.arm,c.repetition)==(condition,arm,repetition):
                            part=self.results[c.context_id]['submission']['probabilities']
                            if set(values)&set(part):raise CustodyError('overlapping held-person predictions')
                            values.update(part)
                    if set(values)!={r.case_id for r in records}:raise CustodyError('full9532-case panel including failures required')
                    p=panel(values);candidate[(condition,arm,repetition)]=p;panels.append(p)
                summaries[(condition,arm)]=scoring.aggregate_repetitions(panels)
            comparisons[(condition,'I_minus_F')]=scoring.paired_comparison(
                [candidate[(condition,'F',r)] for r in REPETITIONS],
                [candidate[(condition,'I',r)] for r in REPETITIONS])
            views=('C',) if condition=='C_only' else ('N','C','NC')
            for view in views:
                for family in FAMILIES+('training_selected_family',):
                    values={}
                    for person in self.plan.people:
                        actual=family
                        if family=='training_selected_family':actual=self.reference.best_families[(person,condition,view)]['family']
                        values.update(self.reference.results[(person,condition,view,actual)].query_probabilities)
                    rp=panel(values);reference[(condition,view,family)]=rp
                    for arm in ARMS:
                        comparisons[(condition,arm,view,family)]=scoring.compare_reference([candidate[(condition,arm,r)] for r in REPETITIONS],rp)
            for baseline in ('uniform','weighted_prior'):
                values={}
                for person in self.plan.people:
                    vector=[1/25]*25 if baseline=='uniform' else self.reference.priors[(person,condition)]['probabilities']
                    vector=scoring.probability_vector(vector)
                    values.update({rid:vector for rid in self.plan.fold(person).query_ids})
                reference[(condition,baseline)]=panel(values)
        # Prespecified original-vs-control paired contrasts, averaged over exactly
        #3 repetitions within each person. Persons, not records/repetitions, are n.
        for arm in ARMS:
            for control in ('spatial_scrambled','C_only'):
                base=summaries[('original',arm)];other=summaries[(control,arm)]
                acc={p:base['people'][p]['accuracy']-other['people'][p]['accuracy'] for p in self.plan.people}
                bri={p:other['people'][p]['brier_with_failure_penalty']-base['people'][p]['brier_with_failure_penalty'] for p in self.plan.people}
                comparisons[(arm,'original_minus_'+control)]={'accuracy':scoring.person_uncertainty(acc),'brier':scoring.person_uncertainty(bri),
                    'interpretation':'conditional declared-label comparison; C is nuisance-enriched and supports may fingerprint acquisition'}
        flatten=lambda d:{'|'.join(k):v for k,v in d.items()}
        final={'schema':'n073_full_declared_label_study_v1','scope':{'records':9532,'people':13,'protocols':25,'cells':300,'contexts':234},
            'closure_digest':closure,'reference_receipt':reference_receipt,'candidate_panels':flatten(candidate),
            'reference_panels':flatten(reference),'three_repetition_summaries':flatten(summaries),'paired_comparisons':flatten(comparisons),
            'claim_limit':'Declared-catalogue label recovery under documented whole-support controls; no causal/native-neural-understanding/population-validity or SOTA inference.'}
        self.store.put_json('full_study_results',final)
        return final
