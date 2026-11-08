"""Complete scientific program composition over actual reviewed return paths.

The trusted controller owns all raw targets/reference work. Only minimized
physical training/query realms reach generated code or the investigator. Final
grader label materialization follows complete artifact admission. Deployment,
external physical instrumentation and authentic source semantics remain gates.
"""
import secrets
from ach_util import need,pin,pin_bytes,encode,read_exact,integer,exact_fields
from ach_plan import compile_programme,context_schedule
from ach_policy import validate_global,committed_policy_body
from ach_views import obligations,training_view,materialize_private_rows,runtime_query_row,minimal_row
from ach_reference import ReferenceBudget,ReferenceRunner
from ach_data import MatReader,extract_private
from ach_native import run_native,project_collection,bind_native_policy_sources
from ach_investigator import ProviderSession,Investigator

class SourceStore:
    def __init__(self,catalog,ledger):self.catalog,self.ledger=catalog,ledger
    def read_original(self,descriptor):
        need(descriptor['path'] in self.catalog,'only independently selected original author source')
        selected=self.catalog[descriptor['path']]
        need(selected['descriptor']==descriptor,'same exact original source member')
        return read_exact(selected['local_path'],{k:descriptor[k] for k in ('bytes','sha256')},descriptor['bytes'],self.ledger)

def aliases_for(rows):
    """One fresh distinct public alias per private entity; private audit only."""
    result={'rows':{k:'row_'+secrets.token_hex(16) for k in sorted(rows)},
        'animals':{k:'animal_'+secrets.token_hex(16) for k in sorted({r['animal'] for r in rows.values()})},
        'sessions':{k:'session_'+secrets.token_hex(16) for k in sorted({r['animal']+'|'+r['session'] for r in rows.values()})}}
    all_values=[]
    for namespace,mapping in result.items():
        need(len(mapping)==len(set(mapping.values())),'one-to-one '+namespace+' alias mapping')
        all_values.extend(mapping.values())
    need(len(all_values)==len(set(all_values)),'disjoint opaque alias namespaces')
    return result

def pregrade(libraries,plan,study,panels,fitted,sources,artifacts):
    """Run actual full V2 admission before constructing grader label payload.

    grade repeats these gates on the same objects; the duplicate work is charged.
    Native nonagreement is retained as a separate outcome and never suppresses
    otherwise complete improvement. No numeric grading callback is accepted.
    """
    core=plan['core'];expected=libraries.get('core','study').compile_plan(study,sorted(plan['null_mappings']))
    need(core==expected,'complete exact original study and null work')
    admission=libraries.get('core','grading').validate_complete_predictions(core,panels,fitted,sources)
    native=libraries.get('core','native_compare').compare(artifacts['native_policy'],artifacts['native_roots'],artifacts['native_panels'])
    completion=libraries.get('core','completion')
    fits=completion.validate_reference_fit_records(core,study,artifacts['reference_fit_records'],
        artifacts['reference_selections'],artifacts['reference_final_states'],fitted)
    diagnostics=completion.validate_diagnostics(core,artifacts['diagnostics'])
    prerequisites=completion.validate_programme_prerequisites(core,native,artifacts['ed_dispositions'],
        artifacts['null_reports'],fits,diagnostics,artifacts['candidate_method_admission'])
    return {'admission':admission,'prerequisites':prerequisites}

class Controller:
    def __init__(self,libraries,helpers,authority,provider,observer,jobs,ledger,journal,source_pin,authorization_header):
        self.libs,self.helpers,self.authority=libraries,helpers,authority
        self.provider,self.observer,self.jobs=provider,observer,jobs
        self.ledger,self.journal,self.source_pin=ledger,journal,source_pin
        self.authorization=authorization_header
    def _query_closure(self,result,receipt,entitlement):
        raw={'result_pin':pin(result),'journal_receipt':receipt,'entitlement_pin':pin(entitlement)}
        evidence,evidence_pin=self.authority.evidence('query_journal',pin(entitlement)['sha256'],raw)
        exact_fields(evidence,('raw_pin','journal_bytes_fsynced','source_execution_observation_pin',
                              'no_candidate_or_reference_feedback_exposed','finished_ns'),'actual operator query closure')
        need(evidence['raw_pin']==pin(raw) and evidence['journal_bytes_fsynced'] is True and
             evidence['no_candidate_or_reference_feedback_exposed'] is True and
             self.ledger.origin<=integer(evidence['finished_ns'])<self.ledger.scientific,
             'independently observed exact query computation and durable output')
        from ach_util import require_pin
        require_pin(evidence['source_execution_observation_pin']);self.ledger.tick()
        return evidence_pin
    def run(self,inputs):
        self.authority.validate_inputs(inputs);self.ledger.tick()
        s=inputs['study'];policies=inputs['policies'];profile=inputs['profile']
        need(profile['native']['duration_ns']==self.ledger.scientific-self.ledger.origin,'same strict original native/full-program deadline')
        validate_global(inputs['native_bundle']['programs'],policies,self.source_pin,inputs['authoring_commitment'])
        joins={'feature_manifest_pin':pin(inputs['feature_manifest']),'field_mapping_pin':pin(inputs['field_mapping']),
            'native_policy_pin':pin(inputs['native_policy']),'ED_dispositions_pin':pin(inputs['ed_dispositions']),
            'authoring_commitment_pin':pin(inputs['authoring_commitment']),
            'original_members_pin':pin(self.libs.native_contract()['original_input_members']),
            'source_environment_pin':self.authority.selection['source_environment_pin'],
            'complete_resource_profile_pin':self.authority.selection['runtime_profile_pin']}
        need(all(inputs['study_admission'][k]==v for k,v in joins.items()),'same admitted complete source/field/policy/profile operands')
        provider_deployments={}
        for actor,descriptor in inputs['provider_deployments'].items():
            provider_deployments[actor]=self.helpers.get('transport').deployment(descriptor['path'],descriptor['pin'],self.ledger,'provider')
        need(set(provider_deployments)==set(policies),'both independently bound provider policies')
        main_deployment=self.provider.admission
        for actor,d in provider_deployments.items():
            need({k:v for k,v in d.items() if k!='investigator'}=={k:v for k,v in main_deployment.items() if k!='investigator'},
                 'same exact source/runtime/authority/peer/spend deployment across A/B')
            need(d['investigator']['policy_pin']==pin(policies[actor]),'arm-specific immutable policy admission')
        a,b=(provider_deployments[k]['investigator'] for k in ('A_clarified','B_author_code'))
        need({k:v for k,v in a.items() if k!='policy_pin'}=={k:v for k,v in b.items() if k!='policy_pin'},
             'matched actual provider endpoint/model/cost ceiling and spend enforcement')
        bind_native_policy_sources(self.libs,inputs['native_bundle'],inputs['native_policy'])
        programme=compile_programme(self.libs,s,inputs['null_policies'],policies,inputs['study_admission'])
        # Independently selected complete decoded/materialized extents are reserved
        # before arrays. They are logical ceilings, not measured physical RSS.
        private_live=self.ledger.acquire_live(integer(profile['private_live_bytes'],1),'whole private admitted dataset/rows/artifacts')
        reader=None;native_live=None;primary=None
        try:
            self.journal.append('complete_programme_plan',programme)
            native=run_native(self.libs,inputs['native_qualification'],inputs['native_bundle'],inputs['native_admission'],
                SourceStore(inputs['source_catalog'],self.ledger),self.provider,self.observer,self.authority,profile['native'],self.ledger)
            self.ledger.observe({'native_observed_'+('live_peak_bytes' if k=='live_bytes' else k):v
                for k,v in native['resources'].items()},'complete native independently observed resource report')
            commitment={'programs_pin':pin(inputs['native_bundle']['programs']),'policies_pin':pin(policies),
                'before_numeric_exposure':native['commitment']['before_numeric_exposure'],
                'independent_four_policy_history':native['commitment']['all_four_independently_authored'],
                'authoring_views_verified':native['commitment']['authoring_views_verified'],
                'no_native_or_cross_context_feedback':True,'observation_pin':pin(native['commitment'])}
            # The feedback exclusion is the source-owned flow below plus the
            # independently selected physical authoring/isolation evidence.
            validate_global(inputs['native_bundle']['programs'],policies,self.source_pin,commitment)
            projected=project_collection(self.libs,inputs['native_bundle'],native,self.provider,inputs['native_projection'],inputs['native_policy'],
                self.ledger,profile['projection']);native_live=projected['retained_live_token']
            self.journal.append('native_outcome',{'comparison':projected['comparison'],'collection':native})
            reader=MatReader(inputs['assets'],inputs['field_mapping'],self.ledger,inputs['data_access_admission'])
            private=extract_private(s,inputs['field_mapping'],reader)
            rows={};kinds=None
            for cohort in ('full','paired'):
                rows[cohort],current=materialize_private_rows(self.libs,s,private,inputs['feature_manifest'],cohort)
                need(kinds is None or kinds==current,'same complete feature schema across cohorts');kinds=current
            common=inputs['candidate_materials']['common'];author=inputs['candidate_materials']['author_code']
            need(not set(common)&set(author),'distinct common/author source mounts')
            need(all(x.startswith('/common/') for x in common) and all(x.startswith('/source/author/') for x in author),
                 'source-owned common and authenticated author-code access roots')
            admitted_materials=inputs['native_admission']['read_only_materials']
            need(sorted(encode(v) for v in common.values())==sorted(encode(v) for v in admitted_materials['common']) and
                 sorted(encode(v) for v in author.values())==sorted(encode(v) for v in admitted_materials['B_author']),
                 'same complete paper/conventions and all authenticated original author-code members')
            sources={'operator':self.source_pin,**{arm:pin_bytes(committed_policy_body(policies[arm])) for arm in policies}}
            panels={};fitted={};fits={};reference_records={};reference_selections={};reference_states={};diagnostics={};methods={};null_graphs={};realm_closures={}
            reference=ReferenceRunner(self.libs,s,kinds,profile['reference'],ReferenceBudget(self.ledger,self.journal),self.journal)
            realizations=['observed']+sorted(programme['null_mappings'])
            for realization in realizations:
                realized={};generation={}
                for cohort,original in rows.items():
                    if realization=='observed':realized[cohort]=original;continue
                    admitted=programme['null_mappings'][realization]
                    subset={k:v for k,v in admitted['mapping'].items() if k in original}
                    need(set(subset)==set(original) and set(subset.values())==set(original),'complete cohort-preserving original null map')
                    shifted=self.libs.get('core','nulls').shift_private_rows(original,{**admitted,'mapping':subset})
                    realized[cohort]=shifted['rows'];generation[cohort]=shifted['lineage_pin']
                for context in context_schedule(programme,s):
                    if context['realization']!=realization:continue
                    actor,cohort,animal=context['actor'],context['cohort'],context['animal']
                    materials=dict(common)
                    if actor=='B_author_code':materials.update(author)
                    local_fits={};query_receipts={variant:{} for variant in context['variant_panels']}
                    for variant,key in context['variant_panels'].items():
                        spec=programme['core']['panels'][key]
                        training={qid:r for qid,r in realized[cohort].items() if r['animal'] in spec['training_animals']}
                        if actor=='operator':
                            fit=reference.fit(spec,training)
                            model=self.libs.get('core','reference_workflow').reference_model_record(s,key,spec,fit,sources[actor])
                            for record in fit['fit_records']:
                                need(record['phase'] not in reference_records,'unique complete actual reference phase')
                                reference_records[record['phase']]=record
                            reference_selections[key]={'loss_cells':fit['loss_cells'],'selection':fit['selection']}
                            reference_states[key]=fit['fitted_state'];diagnostics[key]={}
                        else:
                            aliases=aliases_for(training);public=training_view(self.libs,s,training,spec,aliases)
                            self.journal.append('private_training_view_join',{'panel_key':key,'spec_pin':pin(spec),
                                'private_row_ids':sorted(training),'aliases':aliases,'training_view_pin':pin(public),
                                'history_schedule_pin':s['admission_evidence']['logical_history']})
                            session=ProviderSession(self.helpers,inputs['provider_wire'][actor],profile['provider_wire'],
                                inputs['provider_deployments'][actor]['path'],inputs['provider_deployments'][actor]['pin'],
                                self.ledger,self.authorization,self.journal)
                            fit=Investigator(self.jobs,session,self.journal,self.ledger).fit(policies[actor],spec,public,materials)
                            model={'model_id':spec['bundle_fit_id'],'panel_key':key,'source_pin':sources[actor],
                                'training_animals':spec['training_animals'],'state_pin':pin(fit['seal']),
                                'selection_pin':pin(fit['selection']),'feature_schema_pin':s['feature_schema_pin']}
                            methods[key]=fit['method_admission']
                        local_fits[variant]=fit;fits[key]=fit;fitted[spec['bundle_fit_id']]=model
                        self.journal.append('final_model_record',model)
                    # All four whole bundles are sealed before this outer realm
                    # opens its first actual query. No context reuses an investigator.
                    barrier=self.libs.get('core','history').HistoryBarrier(obligations(self.libs,s,cohort,animal),s['sessions'][animal])
                    query_metadata={q['id']:q for q in self.libs.get('core','study').cohort_queries(s,cohort,animal)}
                    while True:
                        batch=barrier.next_batch()
                        if batch is None:break
                        closed={}
                        for obligation in batch['obligation_ids']:
                            qid,variant=obligation.rsplit('|',1);key=context['variant_panels'][variant];query=query_metadata[qid]
                            row=runtime_query_row(s,query,private,inputs['feature_manifest'],batch['released_target_keys'],realized[cohort][qid]['epochs'])
                            entitlement={'panel_key':key,'query_id':qid,'view_pin':pin(row),'active_obligation':obligation,
                                'batch_pin':pin(batch),'view_admission_pin':inputs['study_admission']['authoring_commitment_pin']}
                            if actor=='operator':
                                result,receipt=reference.query(local_fits[variant],row,entitlement)
                                closure=self._query_closure(result,receipt,entitlement)
                                diagnostics[key][qid]=result['diagnostics']
                            else:
                                public=minimal_row(row,variant,'query_'+secrets.token_hex(16),training=False)
                                candidate=local_fits[variant]
                                need(pin_bytes(candidate['fit']['source'])==candidate['seal']['seal']['revision_pin'],
                                     'same generated final source after outer seal')
                                need(pin({k:pin_bytes(v) for k,v in candidate['fit']['files'].items()})==
                                     candidate['fit']['state_pin']==candidate['seal']['seal']['model_pin'], 'same sealed whole fitted state')
                                need(pin(candidate['fit']['result']['heads'])==candidate['seal']['seal']['head_manifest_pin'],
                                     'same whole four-head interface after final seal')
                                self.journal.append('private_outer_query_view_join',{'panel_key':key,'query_id':qid,
                                    'public_id':public['id'],'private_view_pin':pin(row),'public_view_pin':pin(public),
                                    'entitlement_pin':pin(entitlement),'sealed_model_record_pin':pin(fitted[programme['core']['panels'][key]['bundle_fit_id']])})
                                prediction,outcome=self.jobs.candidate_predict(candidate['fit'],public,materials)
                                result={'query_id':qid,'prediction':prediction,'model_record_pin':pin(fitted[programme['core']['panels'][key]['bundle_fit_id']]),
                                    'public_query_pin':pin(public),'entitlement_pin':pin(entitlement)}
                                receipt=self.journal.append('candidate_outer_query',result);closure=outcome['closure_pin']
                            query_receipts[variant][qid]=result
                            closed[obligation]={'obligation_id':obligation,'prediction_pin':pin(result),'closure_pin':closure}
                        barrier.close_batch(closed)
                    barrier_receipt=barrier.finish()
                    realm_closures['|'.join((realization,actor,cohort,animal))]=self.journal.append(
                        'outer_query_realm_closed',{'context':context,'barrier':barrier_receipt})
                    for variant,key in context['variant_panels'].items():
                        spec=programme['core']['panels'][key];model=fitted[spec['bundle_fit_id']]
                        if actor=='operator':
                            panels[key]=self.libs.get('core','reference_workflow').reference_prediction_panel(s,spec,model,
                                local_fits[variant]['fitted_state'],query_receipts[variant])
                        else:
                            need(set(query_receipts[variant])==set(spec['query_ids']),'complete actual candidate outer predictions')
                            panels[key]={'panel_key':key,'model_id':spec['bundle_fit_id'],'model_record_pin':pin(model),
                                'source_pin':sources[actor],'predictions':{q:r['prediction'] for q,r in query_receipts[variant].items()}}
                        self.journal.append('prediction_panel',panels[key])
                if realization!='observed':
                    selected={k:spec for k,spec in programme['core']['panels'].items() if spec['realization']==realization}
                    graph={'panels':{k:pin(panels[k]) for k in selected},
                        'models':{spec['bundle_fit_id']:pin(fitted[spec['bundle_fit_id']]) for spec in selected.values()},
                        'reference_fits':{k:pin(fits[k]['fit_records']) for k,spec in selected.items() if spec['actor']=='operator'},
                        'reference_selections':{k:pin(reference_selections[k]) for k,spec in selected.items() if spec['actor']=='operator'},
                        'candidate_methods':{k:pin(methods[k]) for k,spec in selected.items() if spec['actor']!='operator'},
                        'query_realm_closures':{k:v for k,v in realm_closures.items() if k.split('|')[0]==realization},
                        'generation':generation,'policy_pin':programme['null_mappings'][realization]['policy_pin']}
                    self.journal.append('complete_null_fit_query_graph',graph)
                    null_graphs[realization]={'policy_pin':programme['null_mappings'][realization]['policy_pin'],
                        'generation_pin':pin(generation),'complete_fit_query_graph_pin':pin(graph)}
            artifacts={'native_policy':inputs['native_policy'],'native_roots':[r['id'] for r in self.libs.native_contract()['roots']],
                'native_panels':projected['panels'],'reference_fit_records':reference_records,
                'reference_selections':reference_selections,'reference_final_states':reference_states,
                'diagnostics':diagnostics,'ed_dispositions':inputs['ed_dispositions'],'null_reports':null_graphs,
                'candidate_method_admission':methods}
            self.ledger.tick();self.ledger.reserve({'complete_artifact_admissions':2},'pregrade and actual protected grade')
            complete=pregrade(self.libs,programme,s,panels,fitted,sources,artifacts)
            self.journal.append('all_artifacts_admitted_before_grader_labels',complete)
            # Raw private target extraction is needed for disjoint training folds
            # and released histories. This is the first GRADER label payload;
            # candidate and reference query processes never receive their targets.
            labels={q['id']:private['targets'][q['target_key']]['seconds'] for q in s['queries']}
            self.ledger.reserve({'protected_label_values':len(labels)},'target-last protected grader payload')
            result=self.libs.get('core','grading').grade(programme['core'],s,panels,fitted,sources,labels,programme_artifacts=artifacts)
            self.ledger.tick();receipt=self.journal.append('scientific_controller_result_provisional',result)
            raw={'result_receipt':receipt,'ledger':self.ledger.report(),'journal_roster_pin':pin(self.journal.records),
                'source_pin':self.source_pin,'original_counts':programme['counts']}
            evidence,evidence_pin=self.authority.evidence('final_controller_seal',pin(raw)['sha256'],raw)
            need(evidence.get('raw_pin')==pin(raw) and evidence.get('all_scientific_graph_work_closed') is True,
                 'independent scientific graph checkpoint; cleanup, serialization and final exit remain external obligations')
            return {'result':result,'result_receipt':receipt,'independent_controller_seal_pin':evidence_pin,
                'source_work_complete':True,'external_final_natural_zero_required':True,
                'full_deployable_benchmark_qualified':False,'scientific_qualified':False}
        except BaseException as error:
            primary=error
            if hasattr(error,'ach_failure_descriptor'):
                diagnostic=error.ach_failure_descriptor
                try:
                    self.ledger.observe({'native_observed_'+('live_peak_bytes' if k=='live_bytes' else k):v
                        for k,v in diagnostic['measured_resources'].items()},'failed native measured prefix')
                    self.journal.append('native_failure_descriptor',diagnostic,cutoff='closeout')
                except BaseException as secondary:setattr(error,'native_failure_closeout_error',type(secondary).__name__)
            self.ledger.fail('complete programme',error)
            try:self.journal.failure('complete programme',error)
            except BaseException as secondary:setattr(error,'programme_failure_journal_error',type(secondary).__name__)
            raise
        finally:
            cleanup=[]
            for operation in ((reader.close if reader is not None else lambda:None),
                              (lambda:self.ledger.release_live(native_live)) if native_live is not None else lambda:None,
                              lambda:self.ledger.release_live(private_live)):
                try:operation()
                except BaseException as error:cleanup.append(error);self.ledger.fail('controller cleanup',error)
            if cleanup:
                if primary is not None:setattr(primary,'controller_cleanup_errors',[type(e).__name__ for e in cleanup])
                else:raise cleanup[0]
