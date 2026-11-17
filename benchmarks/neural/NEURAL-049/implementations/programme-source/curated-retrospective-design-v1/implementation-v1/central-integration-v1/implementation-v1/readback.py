"""Original captured parent outputs; full public admission before protected grade."""
from pathlib import Path


def natural(record, argv, a, review):
    u.need(type(record) is dict and record.get('argv') == argv and record.get('cwd') == a['roots']['source'],'original nested command/cwd')
    for key in ('successful_observation','spawn_attempted','spawn_returned','natural_exit','process_reaped','process_group_absent',
                'streams_closed','selector_closed','stdout_eof','stderr_eof','wait_attempted','mutating_signals_disabled','no_mutating_signals'):
        u.need(record.get(key) is True,'natural closed caller '+key)
    for key in ('timed_out','cleanup_attempted','parent_timer_elapsed','output_overflow','cleanup_ownership_unknown','failed_unknown_child_state',
                'spawn_ownership_unknown','requires_separate_child_inspection','term_attempted','term_sent','kill_attempted','kill_sent',
                'forced_termination_supported','forced_termination_available'):
        u.need(record.get(key) is False,'no uncertain caller '+key)
    u.need(type(record.get('exit_code')) is int and record['exit_code'] == 0
           and type(record.get('mutating_signal_count')) is int and record['mutating_signal_count'] == 0,'ordinary zero/no mutating signals')
    for key in ('error_type','timer_disable_error','timer_restore_error'): u.need(record.get(key) is None,'no caller/timer failure')
    u.need(record.get('cleanup_mode') == 'observation_and_bounded_wait_only','conservative caller policy')
    u.need(record['normal_end'] == a['clock']['readback_end'] and record['cleanup_end'] == review['central_observation_deadline']
           and a['clock']['origin'] <= u.finite(record['observed_start']) <= u.finite(record['normal_closed_at'])
           <= u.finite(record['final_closed_at']) < a['clock']['readback_end'],'unchanged complete original nested clock')


def json_at(host, desc, cap, required):
    u.need(type(desc) is dict and set(desc) == {'path','pin'} and u.path(desc['path']) == u.path(required),'fixed artifact path before capture')
    return u.parse(host.read(required,cap,u.only_pin(desc['pin']),readonly=True))


def captured_parent(env, authority):
    return {**env['captured_parent'],'manifest_path':str(env['parent_manifest_path']),
            'authority_descriptor':authority,'authority_pin':authority['pin']}


def observation(host, desc, a, env, review, validation_budget):
    root = Path(a['roots']['observation']); res = a['resources']; captured = captured_parent(env,review['authority'])
    obs = json_at(host,desc,res['producer_bytes'],root/'OBSERVATION.json')
    u.need(obs.get('schema') == 'neural049_observation_v1' and obs.get('status') == 'complete' and obs.get('source') == env['parent_pin']
           and obs.get('authority') == review['authority']['pin'] and obs.get('original_origin') == a['clock']['origin']
           and obs.get('own_outer_exit_not_self_certified') is True,'same actual parent observation')
    u.need(a['clock']['origin'] <= u.finite(obs['observed_end']) < a['clock']['readback_end'],'original observation deadline')
    parent = env['parent']; parent['outer'].natural(obs['caller'],parent['outer'].command(a,captured),a)
    u.need(json_at(host,obs['caller_artifact'],65536,root/'CALLER.json') == obs['caller'],'original worker caller record')
    for name in ('stdout','stderr'):
        raw = host.read(root/(name+'.bin'),65536,obs['streams'][name],readonly=True)
        if name == 'stderr': u.need(raw == b'','empty original successful worker stderr')
        else:
            returned = u.parse(raw)
            u.need(type(returned) is dict and returned.get('status') == 'collected'
                   and returned.get('producer') == obs['producer'],'actual complete collection producer')
    inventory = obs['resource_inventory']; u.need(set(inventory) == {'public','private'},'both native retirement realms')
    for realm,row in inventory.items():
        u.need(row['empty'] is True and row['study'] == a['native_'+realm]['study']
               and a['clock']['origin'] <= u.finite(row['observed']) < a['clock']['readback_end'],'original empty native inventory')
        u.only_pin(row['raw'])
    # This executes the actual complete public numerical/artifact admission.
    # It may load public arrays and compare R1/R2; it never scores labels.
    admitted = parent['admission'].admit(a,captured,obs['producer'],validation_budget)
    u.need(admitted['public_output_admission_complete'] is True and admitted['protected_target_bodies_read'] is False,
           'complete original public admission, zero protected labels')
    counts = {k:admitted['closure'][k] for k in ('phase_count','native_count','provider_count')}
    u.need(obs['closure_counts'] == counts and obs['schedule'] == admitted['producer']['disposition'],'actual full schedule/event closure')
    expected = parent['schedule'].census(admitted['table'],a['modules'],a['cache'])
    u.need(admitted['producer']['census'] == expected and expected['people'] == 12 and expected['days'] == 55,
           'all original people/day/event and selected complete-module support')
    support = {p:sum(len(day['ids']) for day in admitted['table'][p]) for p in parent['contracts'].PEOPLE}
    return {'observation':desc,'producer':obs['producer'],'journal':admitted['producer']['journal'],
            'closure_counts':counts,'census':expected,'support_by_person':support,
            'selected_modules':a['modules'],'cache':a['cache'],'full_support':{'people':12,'days':55,'events':expected['events']},
            'public_output_admission_complete':True,'central_reexecuted_complete_original_public_admission':True,
            'public_array_validation_numeric_costs':admitted['limits'].record(),
            'protected_target_bodies_read_by_central':False,'private_grading_performed':False}


def expected_contrasts(families, selected):
    core = [('F_NC','F_C'),('I_NC','I_C')]+[('I_'+v,'F_'+v) for v in ('C','N','NC')]
    core += [('ref_'+f+'_NC','ref_'+f+'_C') for f in families]
    core += [('ref_strong_NC','ref_strong_C'),('F_NC','ref_strong_NC'),('I_NC','ref_strong_NC')]
    result = {'core':core}
    if 'T1' in selected: result['T1'] = [('F_NC_T1','F_NC'),('I_NC_T1','I_NC'),('F_NC_T1','ref_strong_NC'),('I_NC_T1','ref_strong_NC')]
    if 'D' in selected:
        result['D'] = [('F_NC','F_NC_D'),('I_NC','I_NC_D')]+[('ref_'+f+'_NC','ref_'+f+'_NC_D') for f in (*families,'strong')]
    return result


def score_shape(value, a, env, prior):
    """Validate complete returned reporting grammar; do not recompute a score."""
    c = env['parent']['contracts']; endpoints = c.ENDPOINTS; people = set(c.PEOPLE)
    views = ['C','N','NC']+(['NC_D'] if 'D' in a['modules'] else [])
    models = {x['id'] for x in c.cells(a['modules'])}|{'ref_'+f+'_'+v for f in (*c.FAMILIES,'strong') for v in views}|{'train_mean'}
    u.need(set(value) == {'scores','contrasts','angle_intervals','secondary_endpoint_intervals','reference_anchor',
                          'qualified_neural_contribution','causal_or_continuous_forecast_claim','policy_realizations','actual_census'},'complete score fields')
    u.need(set(value['scores']) == set(endpoints) and set(value['contrasts']) == set(endpoints),'all three endpoints')
    pairs = expected_contrasts(c.FAMILIES,a['modules'])
    for endpoint in endpoints:
        u.need(set(value['scores'][endpoint]) == models,'all actor/family/strong/mean score models')
        for row in value['scores'][endpoint].values():
            u.need(set(row) == {'status','value','people','weighting'} and set(row['people']) == people
                   and row['weighting'] == 'equal_people_of_event_pooled_within_person_OOF_R2','complete person macro grammar')
            defined = True
            for person,z in row['people'].items():
                u.need(set(z) == {'status','n','sse','sst','r2'} and type(z['n']) is int
                       and z['n'] == prior['support_by_person'][person],'all event-weighted original person rows')
                u.need(u.finite(z['sse']) >= 0 and u.finite(z['sst']) >= 0,'finite nonnegative error/support')
                if z['status'] == 'defined': u.need(z['n'] > 0 and z['sst'] > 0 and u.finite(z['r2']) <= 1.,'defined person score')
                else:
                    u.need(z['r2'] is None and ((z['status'] == 'undefined_empty_person' and z['n'] == 0 and z['sse'] == z['sst'] == 0)
                           or (z['status'] == 'undefined_constant_person' and z['n'] > 0 and z['sst'] == 0)), 'explicit undefined support')
                    defined = False
            u.need(row['status'] == ('defined' if defined else 'undefined_complete_endpoint'),'no surviving-person macro')
            if defined: u.finite(row['value'])
            else: u.need(row['value'] is None,'undefined full endpoint remains null')
        effects = value['contrasts'][endpoint]; u.need(set(effects) == set(pairs),'all selected contrast families')
        for name,rows in effects.items():
            u.need([(x['left'],x['right']) for x in rows] == pairs[name],'exact complete declared contrast order')
            for z in rows:
                u.need(set(z) == {'left','right','status','value','person_differences'},'contrast fields')
                defined = all(value['scores'][endpoint][z[k]]['value'] is not None for k in ('left','right'))
                u.need((z['status'] == 'defined') is defined,'contrast status follows complete endpoints')
                if z['status'] == 'defined':
                    u.finite(z['value']); u.need(type(z['person_differences']) is list and len(z['person_differences']) == 12,'all paired people')
                    for x in z['person_differences']: u.finite(x)
                else: u.need(z['status'] == 'undefined_full_support' and z['value'] is None and z['person_differences'] is None,'status-first undefined contrast')
    u.need(set(value['angle_intervals']) == set(pairs),'separate selected angle interval families')
    for family,row in value['angle_intervals'].items():
        defined = all(z['status'] == 'defined' for z in value['contrasts']['angle'][family])
        u.need((row['status'] == 'approximate_simultaneous_band') is defined,'interval status follows full contrast family')
        if row['status'] == 'undefined_complete_family':
            u.need(set(row) == {'status','bands'} and row['bands'] is None,'undefined interval family')
        else:
            u.need(row['status'] == 'approximate_simultaneous_band' and row['replicates'] == 10000
                   and row['order_index_zero_based'] == 9499 and row['resampling_unit'] == 'whole_person'
                   and row['same_counter_draws_across_families'] is True and row['not_joint_across_families'] is True
                   and row['not_author_policy_variance'] is True and row['not_population_random_sample_guarantee'] is True
                   and u.finite(row['radius']) >= 0 and len(row['bands']) == len(pairs[family]),'full exact interval method and limits')
            for band in row['bands']:
                u.need(type(band) is list and len(band) == 2 and u.finite(band[0]) <= u.finite(band[1]),'finite ordered band')
    u.need(value['secondary_endpoint_intervals'] is None and value['reference_anchor'] == 'R1 after independent R2 agreement'
           and value['qualified_neural_contribution'] is None and value['causal_or_continuous_forecast_claim'] is False
           and type(value['policy_realizations']) is int and value['policy_realizations'] == 1
           and value['actual_census'] == prior['census'],'complete scope, no unsupported inference')


def result(bundle, argv, a, review, env, config, host, validation_budget):
    natural(bundle['record'],argv,a,review); u.need(bundle['stderr'] == b'','successful original nested stderr empty')
    returned = u.parse(bundle['stdout'])
    if review['operation'] == 'collect':
        u.need(type(returned) is dict and set(returned) == {'status','observation','source'}
               and returned['status'] == 'observed' and returned['source'] == env['parent_pin'],'actual parent observe return')
        return observation(host,returned['observation'],a,env,review,validation_budget)
    u.need(type(returned) is dict and set(returned) == {'status','score','source'} and returned['status'] == 'scored'
           and returned['source'] == env['parent_pin'],'actual parent grade return')
    # Parent publication is bounded by its whole write Budget, not by the
    # separate producer-JSON cap. Exact extent is prepaid before this capture.
    q = review['grading_document']; score = json_at(host,returned['score'],a['resources']['host_write_bytes'],q['output'])
    u.need(set(score) == {'schema','status','source','authority','late_authority','observation','original_origin','results',
                         'costs_before_publication','numeric_costs','own_outer_exit_not_self_certified'}
           and score.get('schema') == 'neural049_protected_score_v1' and score.get('status') == 'complete'
           and score.get('source') == env['parent_pin'] and score.get('authority') == review['authority']['pin']
           and score.get('late_authority') == review['grading_selection'] and score.get('observation') == q['observation']
           and score.get('original_origin') == a['clock']['origin'] and score.get('own_outer_exit_not_self_certified') is True,
           'exact actual protected report source/authority/observation')
    costs = score['costs_before_publication']
    u.need(costs['origin'] == a['clock']['origin'] and costs['deadline'] == a['clock']['readback_end']
           and a['clock']['origin'] <= u.finite(costs['observed']) < a['clock']['readback_end'],'original protected scoring clock')
    for key,limit in (('read_reserved_bytes','host_read_bytes'),('write_reserved_bytes','host_write_bytes')):
        u.need(u.integer(costs[key]) <= a['resources'][limit],'original protected-score logical resource bound')
    numeric = score['numeric_costs']; expected = {k:a['profiles']['audit']['numeric_'+k] for k in
              ('allocation_bytes','elements','serialized_bytes','files','work')}
    u.need(numeric['limits'] == expected and set(numeric['reserved']) == set(expected)
           and numeric['arbitrary_method_internal_allocations_not_measured'] is True,'original actual numerical audit limits')
    for key,limit in expected.items(): u.need(u.integer(numeric['reserved'][key]) <= limit,'actual reported numerical reservation')
    prior = env['prior_collection']['joined']; score_shape(score['results'],a,env,prior)
    validation_budget.tick()
    return {'protected_report':returned['score'],'observation':score['observation'],'full_support':prior['full_support'],
            'census':prior['census'],'support_by_person':prior['support_by_person'],'selected_modules':a['modules'],'cache':a['cache'],
            'private_grading_performed':True,'protected_target_bodies_read_by_central':False,
            'metrics_computed_by':'unchanged authenticated parent grade.execute','scientific_qualification_inferred':False}
