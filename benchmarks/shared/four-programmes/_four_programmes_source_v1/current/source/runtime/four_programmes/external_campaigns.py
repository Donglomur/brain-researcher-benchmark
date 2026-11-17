"""Full original N056 and N098 programme argv and observed-output admission."""
from pathlib import Path
import hashlib,json
from .common import need,closed,pin,encode,relative,integer

CONDITIONS=("A_F","A_I","B_F","B_I")

def n056_argv(binding,profile,authority,*,repo,catalog,programme_output,evidence_output):
    need(binding["programme"]=="NEURAL-056","N056 whole programme")
    req=binding["request"];rb=binding["root"]["programme_bindings"]
    expected=rb["profile"]
    need(req["participant"]["profile"]==req["campaign_inputs"]["profile"]==expected==rb["provider_profile"],
         "same original participant/provider profile")
    need(authority["profile"]=={k:expected[k] for k in ("bytes","sha256")} or authority["profile"]==expected,
         "original N056 profile body identity")
    need(authority["inputs"]==req["campaign_inputs"]["input_manifest"]==rb["inputs"],"same original neural input manifest")
    need(authority["build_only"] is False,"future explicit original scientific selection")
    need(profile["scope"]=={"people":10,"arms":3,"roles":4,"query_shape":[200,17,100]},"entire original N056 scope")
    budget=binding["resources"]["programme_budget"]
    need(budget["kind"]=="n056_original_profile_budget_v2" and budget["profile"]==expected,"same full programme budget")
    for key in ("whole_limits","case_limits","whole_wall_ns","case_wall_ns","terminal_ns","case_terminal_ns","whole_disk_reservation_bytes"):
        need(budget[key]==profile[key],"same original N056 budget "+key)
    need(budget["outer_wall_ns"]==profile["outer"]["wall_ns"] and
         budget["outer_cleanup_ns"]==profile["outer"]["cleanup_ns"],"same original outer nested interval")
    root=Path(repo);outer=root/catalog["APIs"]["n056_outer"]["path"]
    def path(d):return str(Path(d["path"]) if Path(d["path"]).is_absolute() else root/d["path"])
    authority_pin=rb["legacy_authority"]
    return [profile["outer"]["python"]["path"],"-B",str(outer),"--authority",path(authority_pin),
            "--authority-bytes",str(authority_pin["bytes"]),"--authority-sha256",authority_pin["sha256"],
            "--profile",path(expected),"--destination",str(programme_output),"--capture",str(evidence_output)]

def _n056_scope(outputs,expected_source_id):
    """Whole original metadata relations; no neural array/model/target access.

    These are the literal original protocol/collect relations. The original
    scientific collector and grader already ran in the observed process; this
    cannot replace them or infer a score from counts.
    """
    people=tuple('sub-'+str(i).zfill(2) for i in range(1,11))
    arms=('representation','low_level','response_permuted')
    roles=('reference_fixed','reference_tuned','F','I')
    protocol=outputs['PROTOCOL_OPERATOR_ONLY.json'];report=outputs['REPORT.json']
    collected=outputs['COLLECTOR.json'];grade=outputs['GRADE.json']
    need(protocol['schema']=='neural056_complete_protocol_v1' and
         protocol['roles']==list(roles) and protocol['arms']==list(arms),
         'same complete original role and arm order')
    need([c['person'] for c in protocol['cases']]==list(people) and
         len({c['case_id'] for c in protocol['cases']})==10,'all ten original distinct cases')
    for c in protocol['cases']:
        person=c['person']
        need(c['training_people']==[p for p in people if p!=person] and
             [i['held'] for i in c['inner']]==[p for p in people if p!=person] and
             all(i['training_people']==[p for p in people if p not in (person,i['held'])] for i in c['inner']) and
             set(c['arms'])==set(arms),'all original outer and inner participant partitions')
    for key,value in (('inner_image_count',3300),('fit_image_count',13240),('refit_image_count',16540),
                      ('outer_image_count',200),('coordinate_count',1700),('outputs_per_role',30),
                      ('total_final_blocks',120),('final_fit_predict_jobs',120)):
        need(type(protocol[key]) is int and protocol[key]==value,'full original '+key)
    k=integer(protocol['candidate_trials'],1);need(k<=8,'whole selected finite candidate roster')
    need(protocol['reference_alphas']==[.0001,.01,1.,100.,10000.] and
         protocol['reference_inner_jobs']==1350 and protocol['candidate_inner_jobs']==540*k and
         protocol['investigator_contexts']==270*k+30 and
         protocol['external_fit_predict_processes']==2940+1080*k,
         'all original independent/candidate inner and final opportunities')
    identity=hashlib.sha256(json.dumps(protocol,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    need(report['schema']=='neural056_programme_report_v1' and report['source_id']==expected_source_id and
         report['protocol_id']==collected['protocol_id']==grade['protocol_id']==identity,
         'exact full original source and protocol joins')
    need(type(collected['expected_blocks']) is int and collected['expected_blocks']==120 and
         type(collected['records']) is list and len(collected['records'])==120,
         'entire original final collection')
    expected={(r,p,a) for r in roles for p in people for a in arms}
    need({(r['role'],r['person'],r['arm']) for r in collected['records']}==expected,
         'no duplicate or substituted final role/person/arm')
    methods={}
    for row in collected['records']:
        need(row['protocol_id']==identity,'every final block belongs to original full protocol')
        key=(row['role'],row['person'])
        if key in methods:need(methods[key]==row['method_id'],'same selected method across all three arms')
        methods[key]=row['method_id'];train=row['train'];query=row['query']
        need(train['complete'] is True and query['complete'] is True and
             train['completed_ns']<=query['started_ns'] and query['model']==train['outputs'] and
             train['source']==query['source'] and len(train['inputs'])==len(query['inputs'])==1 and
             train['inputs'][0]['root']!=query['inputs'][0]['root'],
             'original fit-before-query and exact frozen model/source lineage')
    need(grade['schema']=='neural056_complete_grade_v1' and type(grade['all_final_blocks']) is int and
         grade['all_final_blocks']==120 and set(grade['roles'])==set(roles) and
         set(grade['split_half_reliability'])==set(people),'whole original protected grading output')
    for role in roles:
        scores=grade['roles'][role]['participant_coordinate_results']
        need(set(scores)==set(arms) and all(set(scores[a])==set(people) for a in arms),
             'every original protected participant/arm score retained')
    need(set(report['selection'])=={c['case_id'] for c in protocol['cases']} and
         all(set(x)=={'reference','F','I'} for x in report['selection'].values()),
         'all original full paired selections retained')
    return identity

def n056_outputs(observed,*,store,completion_pin,join_pin,expected_source_id,stream_cap,metadata_cap):
    # Exact type and actual source-owned original OS closure are required. A
    # participant dictionary with success-shaped flags is not an admission.
    from .observer import OriginalProcessObservation
    need(type(observed) is OriginalProcessObservation and observed.success,"actual original outer closure")
    integer(metadata_cap,1)
    completion=store.document(completion_pin,metadata_cap);join=store.document(join_pin,metadata_cap)
    need(set(completion['stream_eof'])==set(completion['stream_persistence'])==
         set(completion['stream_counts'])==set(completion['streams'])==
         set(completion['known_stream_prefix_pins'])=={'stdout','stderr'},'both full original inner streams')
    need(completion["exit_code"]==0 and type(completion["exit_code"]) is int and
         completion["forced"] is False and completion["failure"] is None and completion["cleanup_error"] is None and
         completion["cleanup_empty"] is True and all(v is True for v in completion["stream_eof"].values()) and
         all(v=="complete" for v in completion["stream_persistence"].values()) and
         completion["leaf_resource_verdict"]["complete"] is True,"actual original inner controller closure")
    for name in ('stdout','stderr'):
        d=completion['streams'][name];raw=store.read(d,stream_cap)
        need(type(completion['stream_counts'][name]) is int and completion['stream_counts'][name]==len(raw) and
             pin(raw)==completion['known_stream_prefix_pins'][name], 'same complete original inner '+name)
    need(join["original"]==completion_pin and join["source_id"]==expected_source_id and
         join["source_join_verified"] is True and join["original_outer_completion_observed"] is False and
         join["completion_requires_external_original_exit_zero"] is True,"original non-self-attesting terminal join")
    expected={"REPORT.json","COLLECTOR.json","GRADE.json","WHOLE_COST.json","OPERATION_INDEX.json","PROTOCOL_OPERATOR_ONLY.json"}
    need(set(join["complete_original_artifacts"])==expected,"full original output domain")
    outputs={name:store.document(d,metadata_cap) for name,d in join["complete_original_artifacts"].items()}
    need(outputs["REPORT.json"]["complete_outputs"] is True and outputs["REPORT.json"]["original_final_blocks"]==120,
         "all120 original final blocks")
    protocol_id=_n056_scope(outputs,expected_source_id)
    operations=outputs["OPERATION_INDEX.json"]
    need(type(operations['actual_original_operations']) is int and type(operations['budget_process_starts']) is int and
         len(operations["operations"])==operations["actual_original_operations"]==operations["budget_process_starts"] and
         len({row['path'] for row in operations['operations']})==len(operations['operations']) and
         len(operations['operations'])>=outputs['PROTOCOL_OPERATOR_ONLY.json']['external_fit_predict_processes'],
         "all original fit/query/investigation lifetimes")
    for row in operations["operations"]:
        terminal=store.document(row,metadata_cap)
        need(terminal["complete"] is True,"no failed original operation hidden")
    return {"schema":"four_n056_full_original_admission_v1","outer":observed.receipt,
            "original_completion":completion_pin,"original_join":join_pin,
            "original_artifacts":join["complete_original_artifacts"],"original_final_blocks":120,
            "original_protocol_id":protocol_id,"original_report":outputs['REPORT.json'],
            "full_original_products_retained_at_exact_descriptors":True,"scientific_qualification":False}

def n098_argv(binding,selection,*,repo,catalog,analysis_python):
    need(binding["programme"]=="NEURAL-098","N098 whole campaign")
    req=binding["request"];rb=binding["root"]["programme_bindings"]
    need(selection["operation"]=="campaign" and selection["conditions"]==list(CONDITIONS),"complete four original conditions")
    need(rb["legacy_selection"]==req["campaign_inputs"]["legacy_selection"] and
         selection["operands"]["prompt"]==req["participant"]["prompt"]==rb["prompt"],"same exact original selection and prompt")
    budget=binding["resources"]["programme_budget"]
    need(budget["kind"]=="neural098_original_budget_v2" and budget["whole"]==selection["budget"] and
         budget["condition"]==selection["operands"]["condition_limits"],"entire unchanged original nested budgets")
    source=catalog["programmes"]["NEURAL-098"]["source_manifest"]
    need(selection["whole_source_sha256"]==source["sha256"],"exact10-file original manifest")
    entry=Path(repo)/catalog["APIs"]["n098_entry"]["path"];d=rb["legacy_selection"]
    return [str(analysis_python),"-I","-B",str(entry),"--repo",str(repo),"--source-bytes",str(source["bytes"]),
            "--source-sha256",source["sha256"],"run","--selection",d["path"],"--selection-bytes",str(d["bytes"]),
            "--selection-sha256",d["sha256"]]

def n098_outputs(observed,*,store,complete_pin,selection_pin,source_sha):
    from .observer import OriginalProcessObservation
    need(type(observed) is OriginalProcessObservation and observed.success,"actual original N098 external closure")
    complete=store.document(complete_pin,16777216)
    need(complete["schema"]=="neural098-complete-run-v1" and complete["task_id"]=="NEURAL-098" and
         complete["selection"]==selection_pin and complete["source_sha256"]==source_sha and
         complete["complete_source_programme_operation"] is True and
         complete["independent_outer_natural_exit_required"] is True and complete["failures"]==[],"original full campaign completion")
    stages=complete["completed_stages"]
    need(type(stages) is list and len(stages)<=8192 and len({r["name"] for r in stages})==len(stages),"complete unique original stage ledger")
    captured={r["name"]:store.document(r["record"],16777216) for r in stages}
    need({"P00_SELECTION","P02_ENVIRONMENT_SELECTION","P07_EPISODE_POLICY","P13_REPORT","P14_ROOT_PUBLICATION_AUDIT_INPUT"}<=set(captured),
         "all source-owned full-campaign stage boundaries")
    report=captured["P13_REPORT"]
    need(report["conditions"]==list(CONDITIONS) and set(report["outcomes"])==set(CONDITIONS) and
         report["participants"]==33 and report["support_cells"]==2376 and report["fits_per_complete_pipeline"]==330 and
         report["accuracy_cells"]==1386 and report["contrasts"]==792,"complete original N098 support")
    pub=captured["P14_ROOT_PUBLICATION_AUDIT_INPUT"]
    need(len(pub["ordinary_source_dependencies"])==49 and pub["approved_for_publication"] is False and
         pub["private_history_push_allowed"] is False,"all49 parent identities, no publication grant")
    return {"schema":"four_n098_full_original_admission_v1","outer":observed.receipt,"complete":complete_pin,
            "original_ledger":stages,"original_report":report,"all49_parent_descriptors":pub["ordinary_source_dependencies"],
            "held_parent_bodies_not_opened_by_adapter":True,"scientific_qualification":False}
