"""Complete protected programme. Every operation uses source-owned callers."""
import os,secrets,time,shutil,sys,json
from pathlib import Path
from .core import need,digest,read_json,capture,save,descriptor,Budget,ScopedBudget,qualified
from .protocol import compile_programme,ALPHAS,ROLES,choose
from .runtime import Dispatcher,tree
from .actors import Provider,admit_program,author_frozen
from .packets import Panel
from .preparation import prepare
from .experiment import trial,finals
from .evaluation import collect,grade
from .legacy_reconcile import reconcile
from .terminal import TerminalCustody,finalize_attempt

def dispatcher_with_budget(dispatcher,budget):
    instance=object.__new__(Dispatcher);instance.profile=dispatcher.profile
    instance.parent=dispatcher.parent;instance.budget=budget;instance.operations=dispatcher.operations;return instance

def run(authority_path,authority_pin,profile_path,destination,outer_run_deadline_ns):
    source=Path(__file__).resolve().parents[1];origin=source;started=time.monotonic_ns()
    manifest=read_json(source/'RUNTIME_MANIFEST.json')
    for row in manifest['files']:capture(source/row['path'],row['bytes'],row)
    source_id=digest(manifest);authority=read_json(authority_path,4*1024**2,authority_pin)
    profile=read_json(profile_path,4*1024**2,authority['profile'])
    from .profile import validate
    capacity=validate(profile)
    qualified(authority,source_id,descriptor(profile_path,4*1024**2),profile['qualification_root'])
    from .environment import check
    check()
    need(profile['scope']=={'people':10,'arms':3,'roles':4,'query_shape':[200,17,100]},'full mandatory scope')
    configs=profile['trial_configs'];need(type(configs)is list and 1<=len(configs)<=8 and all(type(x)is dict for x in configs),'pre-view finite common configuration roster')
    need(profile['investigator_policy']['max_rounds']>=2,'inspection then sealed-program opportunity')
    need(profile['provider']['argv']==[profile['runtime']['python'],'/source/provider_worker.py'],'source-owned concrete local provider')
    out=Path(destination).absolute();need(not out.is_relative_to(source),'outputs cannot mutate source or enter future actor source mounts')
    out.mkdir(mode=0o700)
    need(shutil.disk_usage(out).free>=profile['whole_disk_reservation_bytes'],'full selected storage reservation')
    evidence_end=min(started+profile['whole_wall_ns'],outer_run_deadline_ns)
    budget=Budget(profile['whole_limits'],started,evidence_end-profile['terminal_ns'])
    budget.evidence_deadline=evidence_end
    slots={'PROGRAMME_FAILURE.json':profile['programme_terminal_bytes'],'WHOLE_COST.json':profile['programme_terminal_bytes']}
    slots.update({f'CASE_COST_{i:02d}_{r}.json':profile['case_terminal_bytes'] for i in range(10) for r in ('F','I')})
    custody=TerminalCustody(out,slots,budget,evidence_end)
    report=None;final_records=[];originals={};failure=None
    try:
        from .core import write_new,canonical
        source=out/'runtime_source';source.mkdir()
        for row in manifest['files']:
            target=source/row['path'];target.parent.mkdir(parents=True,exist_ok=True)
            write_new(target,capture(origin/row['path'],row['bytes'],row,budget),budget)
        write_new(source/'RUNTIME_MANIFEST.json',canonical(manifest)+b'\n',budget)
        dispatcher=Dispatcher(profile['runtime'],budget)
        inputs=read_json(authority['inputs']['path'],16*1024**2,authority['inputs'],budget)
        panel_path,preparation=prepare(inputs,str(source),out/'preparation',dispatcher)
        originals['preparation']=preparation
        panel=Panel(panel_path,budget);nonce=secrets.token_bytes(32)
        protocol=compile_programme(panel.roster,digest(panel.design),len(configs),nonce)
        save(out/'PROTOCOL_OPERATOR_ONLY.json',protocol,budget)
        save(out/'ALIAS_NONCE_OPERATOR_ONLY.json',{'hex':nonce.hex()},budget)
        need(profile['investigator_contexts']==protocol['investigator_contexts'],'all fresh I contexts in capacity')
        need(profile['fit_predict_processes']==protocol['external_fit_predict_processes'],'all reference/candidate fits and queries in capacity')
        r=profile['investigator_policy']['max_rounds'];tokens=profile['investigator_policy']['tokens_per_round']
        total_i_calls=protocol['investigator_contexts']*r
        # Equal whole-role token ceilings; F commits before all neural views.
        need(profile['F_authoring_tokens']=={k:tokens[k]*total_i_calls for k in ('input','output')},
             'matched total available F/I model tokens')
        documentation=capture(source/'TASK.md',1024**2,budget=budget).decode()
        provider=Provider(profile['provider'],dispatcher,str(source),budget)
        need(type(profile['F_authoring_rounds'])is int and 1<=profile['F_authoring_rounds']<=total_i_calls,'finite F authoring within matched role ceiling')
        answer,generation=author_frozen(provider,documentation,configs,profile['F_authoring_rounds'],out/'F_authoring',tokens)
        need(answer.get('configs')==configs,'all F trial identities frozen before views')
        frozen=admit_program(answer,out/'F_program',len(configs),budget,'F');originals['F_generation']=generation
        trusted={'directory':str(source),'tree':tree(source,16*1024**2,2048,budget),
                 'metadata':{'source_id':source_id}}
        all_selections={}
        for case_index,case in enumerate(protocol['cases']):
            caseout=out/case['case_id'];caseout.mkdir()
            fixed=finals(panel,case,trusted,{'alpha':1.0},caseout/'reference_fixed',dispatcher,'reference_fixed',protocol,True)
            final_records+=fixed
            dev=[]
            for i,alpha in enumerate(ALPHAS):
                dev.append(trial(panel,case,trusted,{'alpha':alpha},caseout/('reference_trial_'+str(i)),dispatcher,True))
            winner=choose(dev);selected={'alpha':ALPHAS[winner]}
            final_records+=finals(panel,case,trusted,selected,caseout/'reference_tuned',dispatcher,'reference_tuned',protocol,True)
            all_selections[case['case_id']]={'reference':{'winner':winner,'scores':[x['score'] for x in dev]}}
            # Identical per-outer application compute limits for F and I. Their
            # model-token availability is matched at the whole-role level above.
            for role in ('F','I'):
                scope=ScopedBudget(budget,profile['case_limits'],profile['case_wall_ns'],terminal_ns=profile['case_terminal_ns'])
                # Whole custody already reserved this slot; reserve its case share once.
                scope.inner.reserve(written=profile['case_terminal_bytes'])
                case_panel=panel.with_budget(scope)
                scope.reserve(cpu_ns=profile['case_controller_cpu_ns']);controller_start=time.process_time_ns()
                local_trials=[]
                try:
                    local=dispatcher_with_budget(dispatcher,scope)
                    local_provider=Provider(profile['provider'],local,str(source),scope) if role=='I' else None
                    investigator={'provider':local_provider,'policy':profile['investigator_policy']} if role=='I' else None
                    roleout=caseout/role;roleout.mkdir()
                    for j,config in enumerate(configs):
                        local_trials.append(trial(case_panel,case,frozen if role=='F' else None,config,
                            roleout/('trial_'+str(j)),local,False,investigator))
                    selected_index=choose(local_trials)
                    # The selector receives only scores and frozen trial identity.
                    # No I-generated source/model/history is reused in final refit.
                    selection={'winner':selected_index,'scores':[x['score'] for x in local_trials],
                               'trial_config_ids':[digest(x) for x in configs],
                               'transfer':'index and scalar scores only; fresh I final context'}
                    save(roleout/'SELECTION.json',selection,scope)
                    final_records+=finals(case_panel,case,frozen if role=='F' else None,configs[selected_index],
                           roleout/'final',local,role,protocol,False,investigator)
                    all_selections[case['case_id']][role]=selection
                finally:
                    active=sys.exception();case_errors=[]
                    try:
                        elapsed=time.process_time_ns()-controller_start;scope.observe(cpu_ns=elapsed)
                        need(elapsed<=profile['case_controller_cpu_ns'],'case controller CPU exceeded independent cap')
                    except Exception as exc:case_errors.append('controller:'+type(exc).__name__+': '+str(exc))
                    try:
                        custody.emit(f'CASE_COST_{case_index:02d}_{role}.json',{
                           'case_id':case['case_id'],'role':role,'cost':scope.compact(),
                           'original_failure':None if active is None else type(active).__name__+': '+str(active),
                           'accounting_failures':case_errors,
                           'terminal_cost_rule':'snapshot before this reserved file write; add its observed bytes'},
                           extra_ledger=scope.inner,deadline_ns=scope.evidence_deadline)
                    except Exception as exc:case_errors.append('case_evidence:'+type(exc).__name__+': '+str(exc))
                    if case_errors:
                        print(json.dumps({'case_cost_errors':case_errors,'known_case_cost':scope.compact()}),file=sys.stderr)
                        if active is None:raise ValueError('; '.join(case_errors))
        # Commit complete full-panel lineage and strictly admit every block
        # before opening any outer held response, including for legacy checking.
        save(out/'COLLECTOR.json',{'protocol_id':digest(protocol),'expected_blocks':120,'records':final_records},budget)
        admitted=collect(final_records,protocol,budget)
        result=grade(panel,final_records,protocol,budget)
        legacy=reconcile(panel,admitted,result,out/'legacy_endpoint_check',budget)
        save(out/'GRADE.json',result,budget)
        save(out/'OPERATION_INDEX.json',{'operations':dispatcher.operations,
             'actual_original_operations':len(dispatcher.operations),'budget_process_starts':budget.actual['process_starts']},budget)
        need(len(dispatcher.operations)==budget.actual['process_starts'],'every started successful operation has an original terminal')
        report={'schema':'neural056_programme_report_v1','complete_outputs':True,
           'selected_capacity':capacity,
           'protocol_id':digest(protocol),'source_id':source_id,'original_final_blocks':120,
           'selection':all_selections,'original_endpoint':legacy,
           'F_matching':'pre-view program/config','I_matching':'pre-view policy/config; fresh independent sessions',
           'I_generated_source_identity_is_context_specific':True,'I_is_identical_fitted_estimator_ablation':False,
           'data_exposure':'public-development; transductive released MVNN; no fresh population inference',
           'native_no_tools_neural_comprehension_measured':False,'scientifically_qualified':False}
        save(out/'REPORT.json',report,budget)
    except Exception as exc:
        failure={'error':type(exc).__name__+': '+str(exc),'complete_outputs':False,
                 'completed_final_blocks':len(final_records),'originals_retained':True,'automatic_retry':False}
        raise
    finally:
        active=sys.exception()
        closure=finalize_attempt(custody,budget,failure,len(final_records))
        custody.close()
        if closure['errors']:
            # Original outer stderr provides independently bounded fallback.
            print(json.dumps({'terminal_custody_failure':closure},sort_keys=True),file=sys.stderr)
            if active is None:raise ValueError('terminal cost/failure evidence incomplete')
    return report
