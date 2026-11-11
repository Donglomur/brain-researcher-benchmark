"""Whole-programme source controller: admission, execution, collection and target-last grading.

All authentic operations require a future exact independent root selection.
This module supplies real process and file operations, but contains no selected
scientific authority and performs no work on import.
"""
from pathlib import Path
import io
from .custody import read_pin,parse,write_new,write_json,new_directory,need,pin,encode
from .guard import RequiredUnscorable,integer
from .scope import Scope
from .authorization import Selection
from .census import validate,require_executable
from .process import sandbox_argv,execute,admit_original_process
from .preparation import read_npz
from .kernels import dispatch,flatten
from .scoring import grade_bundle,report
from .views import materialize

def selected_plan(root,authority_pin,budget,operation):
    selection=Selection(root,authority_pin,budget);body=selection.admit(operation)
    scope=Scope(root,body['contract_bindings'],budget)
    need(scope.digest==body['scope_digest'],'authority exact full scope')
    census=parse(read_pin(root,body['census_pin'],body['census_cap_bytes'],budget))
    validate(scope,census)
    need(pin(encode(census))==body['census_content_identity'],'immutable exact census')
    return selection,scope,census

def run_numeric_job(root,job,output,budget):
    """Concrete numeric producer inside a separately bounded qualified worker."""
    need(job['kind']=='numeric','fixed numeric job')
    loaded={};reservations=[];arguments=dict(job['parameters'])
    try:
        for binding in job['input_bundles']:
            data,reserved=read_npz(root,binding['pin'],binding['schema'],budget,binding['cap_bytes'])
            reservations.append(reserved)
            for argument,name in binding['arguments'].items():
                need(argument not in arguments and name in data,'one admitted scientific input for every argument')
                arguments[argument]=data[name]
        result=dispatch(job['kernel'],arguments,reservation=job['logical_array_bytes'],budget=budget)
        skeleton,arrays=flatten(result);buf=io.BytesIO()
        import numpy as np
        np.savez(buf,**arrays);raw=buf.getvalue()
        need(len(raw)<=job['limits']['output_bytes'],'complete numerical result within selected bound')
        data_pin=write_new(Path(output)/'result.npz',raw,budget)
        record={'schema':'critical_init_numeric_job_v1','job_id':job['id'],'kernel':job['kernel'],
                'variant':job['variant'],'support_identity':job['support_identity'],
                'skeleton':skeleton,'array_file':data_pin,'budget':budget.record()}
        receipt=write_json(Path(output)/'result.json',record,budget)
        return {'report':receipt,'arrays':data_pin}
    finally:
        for reserved in reservations:budget.release_array(reserved)

def execute_selected(root,authority_pin,parent,budget,*,operation):
    """Parent invocation itself must be under the independently qualified outer envelope."""
    selection,scope,census=selected_plan(root,authority_pin,budget,operation)
    need(operation in ('prepare','independent_reference','native_reference','candidate'),'selected execution stage')
    require_executable(census)
    body=selection.body
    # Exact outer host lifetime/storage/cgroup attestation is a distinct prerequisite
    # from the child cgroup receipts produced here.
    outer=parse(read_pin(root,body['outer_envelope_pin'],2_000_000,budget))
    need(outer['authority']==authority_pin and outer['scope_digest']==scope.digest,'original outer admission exact join')
    need(outer['memory_enforced']is True and outer['whole_CPU_enforced']is True and outer['aggregate_storage_enforced']is True,'whole controller and descendants bounded')
    run=new_directory(parent,body['run_nonce'],budget)
    outcomes=[];failed=set();selected=[j for j in census['jobs']if j['operation']==operation]
    need(selected,'nonempty complete selected stage')
    try:
        for j in selected:
            if set(j['dependencies'])&failed:
                outcomes.append({'job_id':j['id'],'status':'required_unscorable','reason':'original dependency failed'});failed.add(j['id']);continue
            evidence=new_directory(run,j['id'],budget)
            # The independently frozen runtime includes the fixed worker entry.
            # Native entries and their full import closure are pinned in the census.
            profile=body['runtime_profile'];command=j['command']
            need(command==body['selected_commands'][j['id']],'exact immutable command selection')
            for source in j['command_source_pins']:read_pin(root,source,body['evidence_cap_bytes'],budget)
            argv=sandbox_argv(profile,view=body['views'][j['id']],work=evidence,command=command,
                              model_socket=body.get('model_socket')if operation=='candidate'else None)
            try:
                rec=execute(argv,cwd=evidence,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'},
                            group_parent=body['cgroup_parent'],group_name=body['run_nonce']+'-'+j['id'],
                            limits=j['limits'],budget=budget,evidence=evidence)
                outcomes.append({'job_id':j['id'],'status':'process_finished_pending_independent_outer_completion','original_process':rec})
            except BaseException as error:
                failed.add(j['id']);outcomes.append({'job_id':j['id'],'status':'failed','type':type(error).__name__,
                    'original_process':getattr(error,'record',None),'known_prefix':getattr(error,'known_output_prefix',None),
                    'cleanup_uncertain':getattr(error,'cleanup_uncertain',False),'costs':budget.record()})
                if isinstance(error,(KeyboardInterrupt,SystemExit,TimeoutError)):raise
        result={'scope_digest':scope.digest,'census':body['census_pin'],'operation':operation,'outcomes':outcomes,
                'whole_scope_job_count':len(census['jobs']),'selected_stage_job_count':len(selected),'costs':budget.record(),
                'scientifically_qualified':False,'outer_original_natural_exit_still_required':True}
        write_json(run/'STAGE_RECEIPT.json',result,budget)
        return result
    except BaseException as error:
        error.complete_attempt_prefix={'outcomes':outcomes,'costs':budget.record(),'run_root':str(run),'authority':authority_pin}
        raise

def collect(root,authority_pin,budget,condition):
    selection,scope,census=selected_plan(root,authority_pin,budget,'collect')
    need(condition in ('paper_data','paper_data_author_code'),'separate condition collection')
    evidence=selection.body['collections'][condition];required=[j['id']for j in census['jobs']if j['operation']=='candidate']
    need(set(evidence)==set(required),'full candidate job collection, no success-only subset')
    results={};failures=[]
    for jobid in required:
        row=evidence[jobid]
        try:
            outer=parse(read_pin(root,row['external_outer_pin'],2_000_000,budget))
            admission=admit_original_process(root=root,process_pin=row['original_process'],candidate_pin=row['candidate_report'],
                    outer=outer,stream_cap=selection.body['stream_cap_bytes'],budget=budget)
            payload=parse(read_pin(root,row['candidate_report'],selection.body['candidate_report_cap_bytes'],budget))
            need(payload['job_id']==jobid and payload['condition']==condition and payload['scope_digest']==scope.digest,'candidate exact whole-scope job identity')
            results[jobid]={'status':'collected','report':row['candidate_report'],'payload':payload,'admission':admission}
        except BaseException as error:
            failures.append({'job_id':jobid,'type':type(error).__name__,'admission':getattr(error,'original_process_admission',None),'costs':budget.record()})
            results[jobid]={'status':'failed','failure_index':len(failures)-1}
            if isinstance(error,(KeyboardInterrupt,SystemExit,TimeoutError)):raise
    return {'condition':condition,'scope_digest':scope.digest,'results':results,'failures':failures,
            'protected_targets_opened':False,'costs':budget.record()}

def protected_grade(root,authority_pin,budget,collections):
    selection,scope,census=selected_plan(root,authority_pin,budget,'grade')
    need(set(collections)=={'paper_data','paper_data_author_code'},'both paired collections')
    # Authenticate immutable collected candidate reports/arrays and original
    # outer closure BEFORE opening any protected target or reference byte.
    prepared={}
    for arm in ('paper_data','paper_data_author_code'):
        c=collections[arm];need(c['scope_digest']==scope.digest and c['protected_targets_opened']is False,'target-last original collection')
        expected=selection.body['sealed_collection_pins'][arm]
        need(pin(encode(c))=={'bytes':expected['bytes'],'sha256':expected['sha256']},'exact original collected report')
        if c['failures']:raise RequiredUnscorable('G14','Whole paired candidate collection contains original failures',c['failures'])
        prepared[arm]={}
        for jobid,row in c['results'].items():
            p=row['payload'];objects={}
            for b in p['bundles']:
                data,res=read_npz(root,b['pin'],b['schema'],budget,b['cap_bytes'])
                # Reservation deliberately retained through target loading and scoring.
                need(not set(objects)&set(data),'unique candidate output names');objects.update(data)
            objects.update(p['identities'])
            need('scientific_identity' in objects,'population/estimator/variant identity is mandatory')
            prepared[arm][jobid]=objects
    graded={}
    for jobid,bank in selection.body['protected_reference_banks'].items():
        need(all(jobid in prepared[a]for a in prepared),'no orphan protected target')
        need(all(prepared[a][jobid]['scientific_identity']==bank['scientific_identity']for a in prepared),'paired candidate populations and estimator variant match this specific bank')
        refs={}
        for name in ('independent','native'):
            b=bank[name];arrays,res=read_npz(root,b['pin'],b['schema'],budget,b['cap_bytes'])
            refs[name]=dict(arrays,**b['identities'])
            need(refs[name]['scientific_identity']==bank['scientific_identity'],'independent/native comparison uses the same scientific variant, never crosses paper/code disagreements')
        graded[jobid]={arm:grade_bundle(prepared[arm][jobid],refs['independent'],refs['native'],bank['metrics'])for arm in prepared}
    expected_jobs=set(next(iter(prepared.values())))
    need(set(graded)==expected_jobs,'complete protected bank coverage')
    return {'scope_digest':scope.digest,'jobs':graded,'costs':budget.record(),'composite_score':None,
            'full_scientific_qualification':False}

