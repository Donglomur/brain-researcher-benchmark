"""Complete adaptive receipt admission before the unchanged protected scorer."""
from pathlib import Path
import math
import hashlib


def native_record(c,record,source,selection,budget,interval=None):
    c.need(record['status']=='captured' and record['source']==source,'actual native capture required')
    attempt=c.path(record['attempt']);kind=record['kind']
    cap=715840000 if kind=='fit' else 400000
    raw=c.capture(attempt/'NATIVE.json',262144,record['native'],budget.tick,budget.read)
    value=c.parse(raw)
    c.need(value['schema']=='neural083-sequential-native-phase-v2' and value['status']=='captured'
        and value['kind']==kind and value['ordinal']==record['ordinal'] and value['source']==source
        and value['program']==record['program'] and value['output']==record['output']
        and value['image']==selection['image'] and value['producer_memory_bytes']==selection['memory_bytes']
        and value['producer_seconds']==selection[kind+'_seconds']
        and value['all_native_resources_closed'] is True and value['cli_reaped'] is True
        and value['producer_closed_before_capture'] is True and value['error_type'] is None
        and len(value['closures'])==3 and all(x['closed'] is True for x in value['closures']),
        'complete source/image/condition-bound native closure')
    c.validate_natural_exit(value['natural_exit']);c.validate_cli_commands(value['command_metadata'],cap)
    c.validate_process_ownership(value['process_ownership_metadata'],value['command_metadata'])
    for key in ('phase_started_monotonic','phase_deadline','worker_deadline','elapsed_seconds'):
        number=value[key]
        try:valid=type(number)in (int,float) and math.isfinite(number)
        except OverflowError:valid=False
        c.need(valid,'finite non-boolean original native clock')
    c.need(value['phase_started_monotonic']<value['phase_deadline']<=value['worker_deadline']
        and value['elapsed_seconds']>=0
        and value['phase_started_monotonic']+value['elapsed_seconds']<value['phase_deadline'],
        'original finite timely native interval')
    if interval is not None:
        c.need(interval[0]<=value['phase_started_monotonic'] and value['worker_deadline']==interval[1],
               'native call belongs to original whole worker interval')
    c.capture(attempt.parent/'program.py',1048576,record['program'],budget.tick,budget.read)
    return value


def admit_query_metadata(c,metadata,canonical_case,expected,generation,model,program):
    c.need(type(metadata)is dict and metadata.get('schema')=='neural083_infer_input_v1'
        and metadata.get('generation')==generation and metadata.get('case')==expected['case']
        and metadata.get('setting')==expected['setting'] and metadata.get('arm')==expected['arm'],
        'exact original condition query metadata')
    shape=[100,5] if expected['arm']=='CONTEXT' else [100,251,20]
    c.need(metadata.get('query_shape')==shape and type(metadata.get('query'))is list
        and len(metadata['query'])==100 and metadata['query']==canonical_case['query'],
        'all100 exact canonical ordered query identities, including abstained cases')
    c.need(metadata.get('model')==model and metadata.get('fitted_program')==program,
        'same original sealed training model and source in every query view')
    c.exact_pin(metadata['query_pin'])
    return metadata


def replay_dialogue(ctx,selection,metadata,trial,captured,tool_values,reader,expected_costs,query_deadline):
    """Pure protected dialogue join; caller first admits every actual native call."""
    c=ctx['c'];actor=ctx['actor']
    identity={k:metadata[k] for k in ('generation','case','setting','arm')}
    owner={'condition_id':hashlib.sha256(c.encoded(dict(identity=identity,
        mode=selection['tool_mode'],entrant=selection['entrant']))).hexdigest(),'query_id':trial}
    c.need(captured['owner']==owner,'exact isolated actor owner')
    prefix=hashlib.sha256(c.encoded(owner)).hexdigest()
    def expected_tool(index,action,code):
        c.need(index<len(captured['tool_records']),'every selected tool has a real owned call')
        program=ctx['native_tools'].assembled(ctx['reference_core'],ctx['bodies']['tool_worker.py'],
                                             selection['tool_mode'],action,code)
        c.need(captured['tool_records'][index]['program']==c.pin(program)
            and tool_values[index]['action']==action,'actual source equals selected analysis')
        return tool_values[index]['result']
    if selection['entrant']=='case_adaptive_equal_inputs_tools_compute':
        small=dict(metadata,query=[trial],query_shape=[1]+metadata['query_shape'][1:])
        transcript=actor.initial_messages(ctx['prompt'],selection['tool_mode'],small)
        tool_index=0;decision=None
        c.need(bool(captured['model_records']),'adaptive actor requires actual model reply')
        for turn,receipt in enumerate(captured['model_records']):
            c.need(decision is None,'no model call after explicit final decision')
            config=dict(ctx['provider_config'],owner=owner,request_id=prefix+'-'+str(turn))
            def captured_reader(descriptor,cap):return reader(turn,descriptor,cap)
            validated=ctx['provider'].validate_receipt(receipt,config,owner,captured_reader)
            c.need(receipt['original_deadline']==query_deadline,
                   'provider call retains original query deadline')
            c.need(validated['input_messages']==transcript,'fresh exact query transcript and actual tool history')
            transcript.append(validated['message'])
            reservation=expected_costs.reserve(config['request_id'],owner,
                config['study']['caps']['reported_prompt_tokens'],
                config['study']['generation']['max_output_tokens'],validated['request_binding'])
            actual_entry=expected_costs.settle(reservation,owner,validated['request_binding'],
                validated['usage'],config['study']['declared_rates'])
            c.need(actual_entry==validated['cost_entry'],'actual captured provider usage and owned ledger agree')
            action=validated['action'];decision=actor.outcome(action)
            if decision is None:
                c.need(action['name']in ('python','decoder'),'original selected numerical action')
                code=action['arguments']['code'] if action['name']=='python' else ''
                value=expected_tool(tool_index,action['name'],code);tool_index+=1
                transcript.append(actor.tool_message(action['name'],trial,value))
        c.need(decision==captured['outcome'] and transcript==captured['transcript']
            and tool_index==len(tool_values),'own captured model decision after exact tools, no extra state')
    else:
        c.need(not captured['model_records'] and captured['transcript']==[] and len(tool_values)==1,
               'non-model entrant has no fabricated model calls')
        action='decoder' if selection['entrant']=='decoder_alone' else 'frozen_program'
        value=expected_tool(0,action,'' if action=='decoder' else ctx['frozen_program'])
        c.need(type(value)is dict and set(value)in ({'p_right'},{'abstain'}),'exact numerical entrant result')
        decision=(actor.outcome({'name':'predict','arguments':value}) if 'p_right'in value else
                  actor.outcome({'name':'abstain','arguments':{'reason':value['abstain']}}))
        c.need(decision==captured['outcome'],'captured numerical decision unchanged')
    return decision


def admit_model_costs(c,collector,expected):
    c.need(collector.snapshot()==expected,'whole owned model cost ledger, including every actual request')


def collect(ctx,selection,source,worker_terminal,outer_proof,grade_budget):
    c=ctx['c'];contracts=ctx['contracts'];actor=ctx['actor'];root=c.path(selection['output'])
    configuration=c.pin(c.encoded(selection))
    c.need(outer_proof.get('schema')=='neural083_case_adaptive_outer_admission_v1'
        and outer_proof.get('source')==source and outer_proof.get('configuration')==configuration
        and outer_proof.get('worker_terminal')==c.pin(c.encoded(worker_terminal)),
        'exact independently selected full actor execution proof')
    for flag in ('grading_authorized','natural_exit_zero','process_reaped','process_group_absent',
                 'stdout_eof','stderr_eof','durably_closed_before_original_deadline',
                 'provider_state_and_costs_independently_admitted','method_and_exposure_independently_admitted'):
        c.need(outer_proof.get(flag) is True,'external grading prerequisite: '+flag)
    def read(path,pin,cap=2000000):
        return c.parse(c.capture(path,cap,pin,grade_budget.tick,grade_budget.read))
    complete=read(root/'COMPLETE.json',worker_terminal['complete'],selection['completion_record_cap_bytes'])
    c.need(complete['schema']=='neural083_case_adaptive_complete_v1' and complete['source']==source
        and complete['configuration']==configuration and complete['conditions']==2592
        and complete['conditions_per_panel']==1296 and complete['candidate_queries']==129600
        and complete['independent_reference_queries']==129600
        and complete['submission']==worker_terminal['submission']
        and complete['model_costs']==worker_terminal['model_costs'], 'full selected completion')
    costs=read(root/'MODEL_COSTS.json',worker_terminal['model_costs'],selection['model_cost_record_cap_bytes'])
    interval=(complete['origin'],complete['worker_deadline'])
    for number in interval:
        try:valid=type(number)in (int,float) and math.isfinite(number)
        except OverflowError:valid=False
        c.need(valid,'finite non-boolean actual whole worker interval')
    c.need(interval[0]<interval[1] and interval[1]==interval[0]+selection['limits']['whole_seconds']-30,
           'original source-selected whole worker interval')
    expected_costs=ctx['provider'].TokenCostCollector(selection['model_input_token_budget'],
        selection['model_output_token_budget'],selection['model_request_budget'])
    index=read(selection['canonical']['path'],c.only_pin(selection['canonical']),4000000)
    panel=contracts.canonical(index)
    canonical_cases={row['case']:row for row in panel['cases']}
    submission=read(root/'submission.json',worker_terminal['submission'])
    c.need(submission['schema']=='neural083_case_adaptive_submission_v1'
        and submission['source']==source and submission['configuration']==configuration
        and len(submission['conditions'])==2592,'all full actor conditions')
    bundles={key:dict(schema='neural083_predictions_v1',generation=panel['generation'],outcomes=[])
             for key in contracts.PANELS}
    for expected,row in zip(contracts.schedule(panel),submission['conditions']):
        c.need(row['condition']==expected,'original complete scientific schedule')
        folder=root/'conditions'/('condition%04d'%expected['ordinal'])
        closed=read(folder/'CLOSED.json',row['closed'])
        c.need(closed['schema']=='neural083_case_adaptive_condition_v1'
            and closed['condition']==expected and closed['source']==source
            and closed['configuration']==configuration
            and closed['training_query_model_retired'] is True
            and closed['all_actual_native_calls_closed'] is True,
            'full owned condition before prediction admission')
        c.need(not (folder/'model.bin').exists() and not (folder/'single-query-input').exists(),
            'retired model and single-query view')
        seal=read(folder/'MODEL_SEAL.json',closed['model_seal'])
        retired=read(folder/'TRAIN_RETIRED.json',closed['train_retired'])
        c.need(seal['condition']==expected and seal['model']==closed['model']
            and seal['fit']==closed['fit'] and seal['query_exposed'] is False
            and retired['condition']==expected and retired['query_exposed'] is False
            and retired['model_seal']==closed['model_seal'] and retired['absent'] is True,
            'fitting and retirement precede query exposure')
        c.need(closed['fit']['kind']=='fit' and closed['fit']['ordinal']==expected['ordinal']
            and c.path(closed['fit']['attempt'])==folder/'fit/native','actual condition training call')
        native_record(c,closed['fit'],source,selection,grade_budget,interval)
        expected_fit=(ctx['programme_bodies']['reference_program.py'] if expected['panel']=='reference' else
            ctx['native_tools'].assembled(ctx['reference_core'],ctx['bodies']['tool_worker.py'],
                                         selection['tool_mode'],'construct_training_state'))
        c.need(closed['fit']['program']==c.pin(expected_fit),'fixed original reference or training constructor')
        metadata=read(folder/'QUERY_METADATA.json',closed['query_metadata'])
        admit_query_metadata(c,metadata,canonical_cases[expected['case']],expected,panel['generation'],
                             closed['model'],closed['fit']['program'])
        prediction=read(folder/'predictions.json',closed['output'],100000)
        contracts.prediction(prediction,metadata)
        if expected['panel']=='reference':
            c.need(closed['actors']==[] and closed['reference_infer'] is not None,'separate original reference')
            ref=closed['reference_infer']
            c.need(ref['kind']=='infer' and ref['ordinal']==expected['ordinal']
                and ref['program']==c.pin(expected_fit)
                and c.path(ref['attempt'])==folder/'reference-infer/native','actual fixed independent reference inference')
            native_record(c,ref,source,selection,grade_budget,interval)
            c.need(c.parse(c.capture(ref['output_path'],100000,ref['output'],grade_budget.tick,grade_budget.read))
                   ==prediction,'exact original reference probabilities')
        else:
            c.need(closed['reference_infer'] is None and len(closed['actors'])==100,
                   'every current query investigated independently')
            reconstructed=[];abstained=False
            for i,(trial,record) in enumerate(zip(metadata['query'],closed['actors'])):
                c.need(record['query']==trial,'ordered independent query actor')
                captured=read(folder/('query%03d'%i)/'ACTOR.json',record['actor'],1048576)
                identity={k:metadata[k] for k in ('generation','case','setting','arm')}
                c.need(captured['schema']=='neural083_single_query_actor_v1'
                    and captured['identity']==identity and captured['query']==trial
                    and captured['entrant']==selection['entrant'] and captured['tool_mode']==selection['tool_mode']
                    and captured['other_queries_exposed'] is False and captured['feedback_exposed'] is False,
                    'exact fresh query identity and selected access mode')
                c.need(len(captured['tool_records'])<=selection['max_tool_calls_per_query']
                    and len(captured['model_records'])<=selection['max_model_calls_per_query'],
                    'bounded actual model and tool calls')
                query_clock=ctx['query_budget'].replay(captured['query_budget'],
                    total_native_seconds=selection['infer_seconds'],max_tool_calls=selection['max_tool_calls_per_query'],
                    entrant=selection['entrant'],query_seconds=selection['query_seconds'],whole_deadline=interval[1])
                c.need(captured['query_started']==query_clock['started']
                    and captured['query_deadline']==query_clock['deadline']
                    and interval[0]<=query_clock['started']<query_clock['deadline']<=interval[1]
                    and len(query_clock['grants'])==len(captured['tool_records']),
                    'original query clock and every prospective native grant')
                tool_values=[]
                for tool_index,tool in enumerate(captured['tool_records']):
                    c.need(tool['kind']=='infer' and tool['ordinal']==expected['ordinal']
                        and c.path(tool['attempt'])==folder/('query%03d'%i)/('tool%02d'%tool_index)/'native',
                        'actual sole-query numerical inference call')
                    grant=query_clock['grants'][tool_index]
                    c.need(tool.get('query_grant')==grant,'actual native phase owns exact prospective query grant')
                    native_record(c,tool,source,dict(selection,infer_seconds=grant['producer_seconds']),
                                  grade_budget,(query_clock['started'],query_clock['deadline']))
                    response=read(tool['output_path'],tool['output'],65536)
                    c.need(response['identity']==identity and response['query']==trial,'tool sees same sole query')
                    tool_values.append(response)
                def reader(turn,descriptor,cap):
                    capture_root=folder/('query%03d'%i)/('model%02d'%turn)
                    c.need(Path(descriptor['name']).name==descriptor['name'],'local captured model artifact')
                    return c.capture(capture_root/descriptor['name'],cap,
                        {'bytes':descriptor['bytes'],'sha256':descriptor['sha256']},grade_budget.tick,grade_budget.read)
                replay_dialogue(ctx,selection,metadata,trial,captured,tool_values,reader,expected_costs,query_clock['deadline'])
                result=captured['outcome']
                if result['status']=='abstain':
                    actor.outcome({'name':'abstain','arguments':{'reason':result['reason']}});abstained=True
                else:reconstructed.append(dict(trial=trial,p_right=actor.probability(result['p_right'])))
            c.need((prediction['status']=='abstain')==abstained,'explicit query abstention propagates')
            if not abstained:c.need(prediction['predictions']==reconstructed,'own actor probabilities preserved')
        bundles[expected['panel']]['outcomes'].append(prediction)
    c.need(not (root/'current').exists(),'no surviving full input view')
    admit_model_costs(c,expected_costs,costs)
    return panel,bundles,costs


def grade(ctx,selection,source,worker_terminal,outer_proof,load_targets,budget):
    panel,bundles,costs=collect(ctx,selection,source,worker_terminal,outer_proof,budget)
    c=ctx['c'];binding=c.parse(ctx['programme_bodies']['BINDING.json'])
    original=ctx['comparison'].load_original(c,selection['repository'],binding,budget.read,budget.tick)
    result=ctx['comparison'].grade(panel,bundles['candidate'],bundles['reference'],
        lambda:ctx['comparison'].bounded_targets(load_targets,budget.tick),original,external_admission=True)
    result.update(entrant=selection['entrant'],tool_mode=selection['tool_mode'],
                  model_costs_pin=worker_terminal['model_costs'],
                  model_cost_summary={k:v for k,v in costs.items() if k!='entries'},
                  unchanged_original_endpoint=True,scientific_qualified=False)
    return result
