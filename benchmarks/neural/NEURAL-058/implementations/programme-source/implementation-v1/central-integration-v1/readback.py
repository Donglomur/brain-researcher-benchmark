"""Join actual original terminals/public metadata; never compute replacement scores."""
from pathlib import Path


def natural(record, argv, cwd, origin, normal_end, cleanup_end):
    u.need(type(record) is dict and record.get('argv') == argv and record.get('cwd') == cwd,
           'actual original command and cwd')
    for field in ('successful_observation','spawn_attempted','spawn_returned','natural_exit',
                  'process_reaped','process_group_absent','streams_closed','selector_closed',
                  'stdout_eof','stderr_eof','wait_attempted','mutating_signals_disabled','no_mutating_signals'):
        u.need(record.get(field) is True, 'required natural caller fact: '+field)
    for field in ('timed_out','cleanup_attempted','parent_timer_elapsed','output_overflow',
                  'cleanup_ownership_unknown','failed_unknown_child_state','spawn_ownership_unknown',
                  'requires_separate_child_inspection','term_attempted','term_sent','kill_attempted',
                  'kill_sent','forced_termination_supported','forced_termination_available'):
        u.need(record.get(field) is False, 'no uncertain/mutating closure: '+field)
    u.need(type(record.get('exit_code')) is int and record['exit_code'] == 0
           and type(record.get('mutating_signal_count')) is int and record['mutating_signal_count'] == 0
           and record.get('cleanup_mode') == 'observation_and_bounded_wait_only', 'ordinary natural zero')
    for key in ('error_type','timer_disable_error','timer_restore_error'):
        u.need(record.get(key) is None, 'no caller/timer error')
    u.need(record['normal_end'] == normal_end and record['cleanup_end'] == cleanup_end
           and origin <= u.finite(record['observed_start']) <= u.finite(record['normal_closed_at'])
           <= u.finite(record['final_closed_at']) < normal_end, 'original unchanged caller interval')


def json_at(host, path, expected, cap):
    return u.parse(host.read(path, cap, u.only_pin(expected), readonly=True))


def complete(host, production, production_pin, env, observation):
    root = Path(production['roots']['output']); limits = production['limits']
    raw = host.read(root/'COMPLETE.json', limits['complete_metadata_bytes'], observation['complete'], readonly=True)
    doc = u.parse(raw); core = env['parent']['core']; schedule = env['parent']['schedule']
    u.need(doc.get('schema') == 'neural058_production_complete_v1' and doc.get('task') == 'NEURAL-058'
           and doc.get('source') == env['parent_pin'] and doc.get('selection') == production_pin
           and doc.get('protected_targets_read') is False and doc.get('scientifically_qualified') is False,
           'same complete original source-bound producer')
    roster = doc['roster']; choices = doc['reference_selection']['choices']
    u.need(len(roster['source']) == 423 and len(roster['source_animals']) == 126
           and len(roster['evaluation']) == 29 and len(roster['eval_animals']) == 13,
           'complete original session/animal support')
    expected = schedule.required_counts(roster, choices)
    u.need(doc['counts'] == expected, 'all fixed and source-selected reference counts')
    panels = list(schedule.panels())
    u.need(doc['completed_panels'] == [p['id'] for p in panels], 'all ordered24 complete panels')
    authors = {x['id'] for p in panels for x in schedule.author_contexts(roster,p)}
    outputs = {p['id']+'/'+x['session'] for p in panels for x in schedule.candidate_sessions(roster,p)}
    u.need(set(doc['methods']) == set(doc['candidate_fits']) == set(doc['author_transcripts']) == authors
           and set(doc['candidate_outputs']) == outputs, 'all168 methods/fits/transcripts and696 outputs')
    cv = {x['role']+'/'+x['config']['id']+'/'+str(x['fold']) for x in schedule.reference_selection(roster)}
    models = {x['role']+'/'+x['config']['id'] for x in schedule.final_models(choices)}
    predictions = {x['role']+'/'+x['model'].split('/')[-1]+'/'+x['session']
                   for x in schedule.final_reference_sessions(roster,choices)}
    u.need(set(doc['reference_cv']) == cv and set(doc['reference_models']) == models
           and set(doc['reference_predictions']) == predictions, 'full independent trained-reference graph')
    graph = observation['graph']
    u.need(graph.get('schema') == 'neural058_public_graph_admission_v1' and graph.get('task') == 'NEURAL-058'
           and graph.get('complete') == core.pin(core.encoded(doc)) and graph.get('counts') == expected
           and graph.get('selection') == production_pin and graph.get('source') == env['parent_pin']
           and graph.get('all_public_producers_admitted') is True and graph.get('protected_targets_read') is False,
           'original independent full public admission joins exact body')
    host.read(root/'JOURNAL.jsonl', limits['journal_bytes'], observation['journal'], readonly=True, retain=False)
    return doc


def observation(host, selected, production, env):
    root = Path(production['roots']['observation']); request = selected['request_document']
    desc = selected['observation_descriptor']
    u.need(desc['path'] == str(root/'OBSERVATION.json'), 'fixed original observation location')
    obs = json_at(host, desc['path'], desc['pin'], request['observation_metadata_bytes'])
    u.need(obs.get('schema') == 'neural058_external_observation_v1' and obs.get('task') == 'NEURAL-058'
           and obs.get('source') == env['parent_pin'] and obs.get('production') == selected['production']
           and obs.get('protected_targets_read') is False
           and obs.get('provisional_until_root_observes_this_observer_natural_zero_and_EOF') is True,
           'exact original public-only external observation')
    natural(obs['caller'], request['literal_collect_argv'], request['cwd'], request['origin'],
            request['normal_end'], request['cleanup_end'])
    for name in ('stdout','stderr'):
        raw = host.read(root/(name+'.bin'), 65536, obs['stream_pins'][name], readonly=True)
        if name == 'stderr': u.need(raw == b'', 'original successful collect stderr')
        else:
            terminal = entry_terminal(raw, 'collect', env['parent_pin'])
            u.need(terminal['result']['complete'] == obs['complete']
                   and terminal['result']['output'] == production['roots']['output']
                   and terminal['result']['selection'] == selected['production_binding'],
                   'actual original collect terminal joins complete product')
    doc = complete(host, production, selected['production_binding'], env, obs)
    rows = obs['independent_container_absence']
    u.need(type(rows) is list and len(rows) == len(doc['products'])
           and {x['operation'] for x in rows} == set(doc['products']), 'all actual native resources independently inspected')
    for row in rows:
        u.need(row['container'] == doc['products'][row['operation']]['native']['container']
               and type(row['absence_status']) is int and row['absence_status'] == 404
               and request['origin'] <= u.finite(row['observed']) < request['deadline'],
               'exact container absence and original readback clock')
        u.only_pin(row['response'])
    return {'observation':desc, 'complete':obs['complete'], 'journal':obs['journal'],
            'counts':doc['counts'], 'actual_original_full_public_admission_observed':True,
            'central_reexecuted_full_graph_or_science':False, 'private_grading_performed':False}


def entry_terminal(raw, mode, source):
    lines = raw.splitlines(); u.need(len(lines) == 1, 'one actual original entry terminal')
    value = u.parse(lines[0])
    u.need(value.get('schema') == 'neural058_entry_terminal_v1' and value.get('status') == 'complete'
           and value.get('mode') == mode and value.get('source') == source, 'exact successful original entry')
    return value


def stream_sizes(record, stdout, stderr):
    for name, body in (('stdout',stdout),('stderr',stderr)):
        for field in (name+'_bytes','observed_'+name+'_bytes'):
            u.need(type(record.get(field)) is int and record[field] == len(body), 'original stream extent and no discarded overflow')
    for field in ('combined_stream_bytes','retained_stream_bytes'):
        u.need(type(record.get(field)) is int and record[field] == len(stdout)+len(stderr), 'complete original combined streams')


def result(bundle, argv, selected, production, env, host):
    request = selected['request_document']; r = selected['review']
    natural(bundle['record'], argv, r['cwd'], r['origin'], r['parent_deadline'], r['observation_deadline'])
    stream_sizes(bundle['record'],bundle['stdout'],bundle['stderr'])
    u.need(bundle['stderr'] == b'', 'parent successful stderr empty')
    mode = 'observe' if r['operation'] == 'collect' else 'grade'
    terminal = entry_terminal(bundle['stdout'], mode, env['parent_pin']); returned = terminal['result']
    costs = terminal['budget_before_terminal']
    u.need(costs['origin'] == r['origin'] and costs['deadline'] == r['parent_deadline']
           and r['origin'] <= u.finite(costs['observed']) < r['parent_deadline'], 'same original terminal clock')
    for observed,cap in (('read_reserved_bytes','read_bytes'),('write_reserved_bytes','write_bytes')):
        u.need(type(costs[observed]) is int and 0 <= costs[observed] <= r['parent_limits'][cap],
               'actual original whole-operation budget within exact selected entry cap')
    if mode == 'observe':
        u.need(returned['root'] == production['roots']['observation'] and returned['provisional'] is True,
               'original provisional observation, not fabricated closure')
        selected = {**selected,'observation_descriptor':{'path':str(Path(returned['root'])/'OBSERVATION.json'),
                                                        'pin':u.only_pin(returned['observation'])}}
        return observation(host, selected, production, env)
    u.need(returned['root'] == request['output_root']
           and returned['root_observed_natural_grade_closure_still_required'] is True,
           'exact original protected grade return')
    desc = {'path':str(Path(request['output_root'])/'SCORES.json'),'pin':u.only_pin(returned['scores'])}
    report = json_at(host, desc['path'], desc['pin'], request['metadata_bytes'])
    core = env['parent']['core']; binding = core.pin(core.encoded({k:v for k,v in request.items() if k != 'qualification'}))
    u.need(report.get('schema') == 'neural058_protected_scores_v1' and report.get('task') == 'NEURAL-058'
           and report.get('source') == env['parent_pin'] and report.get('production') == selected['production_binding']
           and report.get('observation') == request['observation']['pin'] and report.get('grade_authority') == binding,
           'actual original protected score source/selection/observation lineage')
    panels = {p['id'] for p in env['parent']['schedule'].panels()}
    references = {role+'/'+family for role in ('C','J') for family in ('ridge','forest','set','strongest')}
    u.need(set(report['candidate']) == panels and set(report['references']) == references, 'all24 panels/eight reference projections')
    animals = set(selected['complete_document']['roster']['eval_animals'])
    for row in list(report['candidate'].values())+list(report['references'].values()):
        u.need(set(row['animals']) == animals, 'all13 protected animal endpoints, including undefined')
    u.need(len(report['contrasts']) == 24 and len(report['native_session_speed_convention_diagnostic']) == 24
           and len(report['native_reference_session_speed_convention_diagnostic']) == 8
           and len(report['native_clipped_session_seed_aggregation_diagnostic']) == 8, 'all distinct original endpoints/diagnostics')
    return {'protected_report':desc, 'observation':request['observation'], 'production':selected['production'],
            'counts':selected['complete_document']['counts'], 'private_grading_performed':True,
            'metrics_computed_by':'unchanged authenticated parent grading.run', 'scientific_qualification_inferred':False}
