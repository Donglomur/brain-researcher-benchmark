"""Complete3680-fit/3680-inference graph through actual source-owned Runtime."""
from pathlib import Path
import common as c
import protocol as p
import schedule

SOURCE_NAMES = frozenset(('common', 'protocol', 'arrays', 'custody', 'model_io', 'outputs', 'numeric_worker', 'numeric'))


def unique_descriptors(items):
    answer = {}
    for desc in items:
        c.descriptor(desc, True)
        if desc['path'] in answer:
            c.need(c.typed_equal(answer[desc['path']], desc), 'one immutable descriptor per path')
        else:
            answer[desc['path']] = desc
    return list(answer.values())


def source_members(manifest, numeric_source):
    c.need(numeric_source['path'].endswith('/references/r1/numeric.py'), 'only the operative R1 engine; R2 is qualification source')
    c.exact(manifest, ('schema', 'entry', 'bootstrap', 'modules', 'dependency_qualification', 'installed_versions'))
    c.need(manifest['schema'] == 'neural081_reference_source_manifest_v1', 'reference source manifest')
    c.need(type(manifest['modules']) is list and len(manifest['modules']) == len(SOURCE_NAMES), 'complete own-source closure')
    names = []
    for row in manifest['modules']:
        c.exact(row, ('name', 'source')); names.append(row['name']); c.descriptor(row['source'])
        if row['name'] == 'numeric':
            c.need(c.typed_equal(row['source'], numeric_source), 'operative R1 source only')
    c.need(set(names) == SOURCE_NAMES and len(set(names)) == len(names), 'fixed source-owned numerical module roster')
    c.need(manifest['entry']['path'].endswith('/numeric_entry.py') and manifest['bootstrap']['path'].endswith('/worker_bootstrap.py'), 'literal selected entry/bootstrap')
    c.need(manifest['installed_versions'] == {'numpy': '2.2.6', 'scipy': '1.15.3', 'sklearn': '1.6.1'}, 'selected historical library contract')
    sources = [manifest['entry'], manifest['bootstrap'], *[r['source'] for r in manifest['modules']]]
    c.need(len(unique_descriptors(sources)) == len(sources), 'one exact source per module')
    c.descriptor(manifest['dependency_qualification'])
    return sources


def role_map(index, roles, protected):
    expected = [(v, outer, inner) for v in c.VIEWS for outer in c.PEOPLE
                for inner in ['FINAL', *[x for x in c.PEOPLE if x != outer]]]
    c.need(type(roles) is list and len(roles) == 200, 'all200 issued role metadata records')
    result = {}
    for wanted, row in zip(expected, roles):
        c.exact(row, ('view', 'outer', 'inner', 'role', 'allowed'))
        key = (row['view'], row['outer'], row['inner'])
        c.need(key == wanted, 'canonical G0 metadata order: FINAL then nine inner roles')
        allowed = unique_descriptors(row['allowed'])
        c.need(row['role'] in allowed and len(allowed) == len(row['allowed']), 'role body inside unique complete issued closure')
        for desc in allowed:
            path = c.absolute(desc['path'])
            c.need(not any(path == c.absolute(d['path']) or path.is_relative_to(c.absolute(d['path'])) or c.absolute(d['path']).is_relative_to(path) for d in protected), 'global targets never enter reference mounts')
        wanted_windows = {r['window_descriptor']['path']: r['window_descriptor'] for r in index['rows']
                          if r['person'] != row['outer'] and r['person'] != row['inner']}
        actual_windows = [d for d in allowed if d['path'] in {r['window_descriptor']['path'] for r in index['rows']}]
        if row['view'] == 'EEG':
            c.need({d['path']: d for d in actual_windows} == wanted_windows, 'complete role waveform closure')
        else:
            c.need(not actual_windows, 'ZERO never mounts EEG windows')
        result[key] = row
    return result


def output_cap(operation, n, d, q, family, oof_descriptors=()):
    """Full scalar payloads plus bounded ordinary NPY headers and JSON metadata."""
    if operation in ('fit', 'historical'):
        values = 2*d + (n*d + 13*n + 13 if family == 'RBF_KRR' else 12*d + 12)
        return 8*values + 10*256 + 512*d + 131072
    if operation == 'inner_infer':
        return 192*q + 512 + 48*q + 65536
    if operation == 'infer':
        return 96*q + 256 + 512*q + 65536
    c.need(operation == 'select', 'known complete output algebra')
    #369 person metric records,20 settings/21 scans, all180 descriptor links, two complete panels.
    return 4096*369 + len(c.encoded(list(oof_descriptors))) + 1024*q + 131072


def io_reservation(allowed, sources, qualification, output_bytes, request_cap=16*2**20, manifest_cap=2**20):
    # No refunds: source/import bootstrap allowance and every output hash/probe are explicit.
    inputs = sum(d['bytes'] + 1 for d in allowed)
    source = sum(d['bytes'] + 1 for d in sources) + qualification['bytes'] + 1
    return {'read_bytes': 2*inputs + 3*source + 3*request_cap + 3*manifest_cap + 2*output_bytes + 32*2**20,
            'write_bytes': output_bytes + 32*2**20}


def artifact(closure, relative):
    wanted = str(Path(closure['work_root']) / relative)
    matches = [x for x in closure['artifacts'] if x['path'] == wanted]
    c.need(len(matches) == 1, 'one actual closed worker artifact: ' + relative)
    return matches[0]


def read_result(closure, operation, generation, numeric_source, budget):
    desc = artifact(closure, 'RESULT.json')
    result = c.capture_json(desc, budget, [Path(desc['path']).parent])
    c.exact(result, ('schema', 'operation', 'generation', 'numeric_source', 'body'))
    c.need(result['schema'] == 'neural081_reference_result_v1' and result['operation'] == operation and result['generation'] == generation and c.typed_equal(result['numeric_source'], numeric_source), 'actual worker result lineage')
    return desc, result['body']


def run(index, roles, runtime, numeric_source, source_manifest, budget, output_root, protected):
    # The concrete Runtime owns actual engine/observer/source closure, not an injected prediction callback.
    from runtime import Runtime, admit_closure
    c.need(type(runtime) is Runtime, 'actual source-owned direct-engine runtime required')
    p.validate_index(index); generation = index['preparation_generation']
    c.need(protected == [index['protected_support_descriptor'], index['protected_assessment_descriptor']], 'both exact global target descriptors')
    sources = source_members(source_manifest, numeric_source)
    roles_by_key = role_map(index, roles, protected)
    destination = c.new_directory(output_root, budget)
    rows_by_person = {person: [row for row in index['rows'] if row['person'] == person] for person in c.PEOPLE}
    all_window_paths = {row['window_descriptor']['path'] for row in index['rows']}
    counts = {person: len(rows) for person, rows in rows_by_person.items()}
    configurations = {row['id']: row for row in schedule.grid()}
    fitted, oof, selected = {}, {}, {}
    jobs, models, selections, panels = [], [], [], []
    totals = {'fit': 0, 'historical': 0, 'inner_infer': 0, 'infer': 0, 'select': 0}

    for job in schedule.reference_jobs(index):
        budget.check_clock()
        operation, view, outer = job['operation'], job['view'], job['outer']
        inner = job.get('inner', 'FINAL')
        role_record = roles_by_key[(view, outer, inner)]
        n = sum(counts[person] for person in c.PEOPLE if person != outer and person != inner)
        qperson = inner if operation == 'inner_infer' else outer
        q = counts[qperson] if operation in ('inner_infer', 'infer', 'select') else 0
        selection_record = selected.get((view, outer))
        if operation in ('fit', 'historical'):
            config = job.get('configuration')
            family = job.get('family', config['family'] if config else None)
            if inner == 'FINAL' and operation == 'fit':
                c.need(selection_record is not None, 'all180 OOF and selection precede final fit')
                choice = next(x for x in selection_record['body']['selection']['selected_per_family'] if x['family'] == family)
                config = configurations[choice['configuration_id']]
                c.need(config['family'] == family, 'selected configuration belongs to final family')
            payload = {'role': role_record['role'], 'configuration': config,
                       'selection': selection_record['result'] if inner == 'FINAL' else None}
            allowed = list(role_record['allowed'])
            if inner == 'FINAL':
                allowed.append(selection_record['result'])
        elif operation in ('inner_infer', 'infer'):
            family = job.get('family', job.get('configuration', {}).get('family'))
            config_id = job['configuration']['id'] if inner != 'FINAL' else family
            edge = fitted[(view, outer, inner, config_id)]
            query_rows = rows_by_person[qperson]
            query = {'generation': generation, 'view': view, 'person': qperson,
                     'ids': [r['canonical_id'] for r in query_rows],
                     'windows': [r['window_descriptor'] for r in query_rows] if view == 'EEG' else []}
            temperature = 1
            if operation == 'infer' and family != 'HISTORICAL_BP_LDA':
                temperature = next(x['temperature'] for x in selection_record['body']['selection']['selected_temperatures'] if x['family'] == family)
            payload = {'model': edge['model'], 'query': query, 'temperature': temperature,
                       'configuration_id': edge['configuration']['id']}
            allowed = [role_record['role'], *edge['state_artifacts'], *query['windows']]
            if operation == 'infer':
                allowed.append(selection_record['result'])
        else:
            c.need(operation == 'select', 'declared reference schedule operation')
            family = None
            children = oof[(view, outer)]
            expected_pairs = [(conf['id'], person) for conf in schedule.grid() for person in c.PEOPLE if person != outer]
            c.need([(x['configuration_id'], x['person']) for x in children] == expected_pairs, 'complete ordered20-by9 actual inference closures')
            payload = {'role': role_record['role'], 'oof': [x['result'] for x in children],
                       'assessment_ids': [r['canonical_id'] for r in rows_by_person[outer]]}
            allowed = [d for d in role_record['allowed'] if d['path'] not in all_window_paths]
            for child in children:
                allowed.extend((child['result'], child['scores'], child['probabilities_t1']))
        allowed = unique_descriptors(allowed)
        d = 1024 if family == 'TM_LDA' else 320
        memory = schedule.memory(operation, n, d, q, family)
        limits = schedule.numerical_limits(operation, n, d, q, family)
        cap = output_cap(operation, n, d, q, family, payload.get('oof', ()))
        io = io_reservation(allowed, sources, source_manifest['dependency_qualification'], cap)
        seconds = 7200 if operation in ('fit', 'historical') else 300 if operation == 'select' else 900
        original_job_origin = budget.clock()
        deadline = min(budget.end, original_job_origin + seconds)
        work = Path(runtime.allocate(job['id']))
        manifest_desc = c.publish_json(work / 'source-manifest.json', source_manifest, budget)
        request = {'schema': 'neural081_reference_worker_request_v1', 'job': job, 'operation': operation,
                   'generation': generation, 'source': numeric_source, 'payload': payload, 'limits': limits,
                   'output_root': str(work), 'allowed': allowed, 'protected': protected,
                   'source_manifest': manifest_desc, 'clock': {'origin': budget.origin, 'deadline': deadline}, 'worker_io': io}
        request_raw = c.encoded(request)
        c.need(len(request_raw) <= 16*2**20 and manifest_desc['bytes'] <= 2**20, 'bounded exact immutable request/source manifest')
        request_desc = c.publish(work / 'request.json', request_raw, budget)
        mounted = unique_descriptors([*sources, source_manifest['dependency_qualification'], manifest_desc, request_desc, *allowed])
        source_paths = {x['path'] for x in sources}
        mounts = [{'source': desc, 'target': desc['path'], 'opaque_host': desc['path'] not in source_paths and desc not in (manifest_desc, request_desc, source_manifest['dependency_qualification'])} for desc in mounted]
        args = []
        for key, value in (('request', request_desc['path']), ('request-bytes', request_desc['bytes']), ('request-sha256', request_desc['sha256']),
                           ('bootstrap', source_manifest['bootstrap']['path']), ('bootstrap-bytes', source_manifest['bootstrap']['bytes']),
                           ('bootstrap-sha256', source_manifest['bootstrap']['sha256']), ('read-cap', io['read_bytes']), ('write-cap', io['write_bytes']),
                           ('origin', budget.origin), ('deadline', deadline), ('entry-bytes', source_manifest['entry']['bytes'])):
            args.extend(('--' + key, str(value)))
        closure = runtime.run(job['id'], source_manifest['entry']['path'], mounts, args, seconds=seconds,
                              memory_bytes=memory, kind='reference', worker_io=io, workspace=work,
                              original_deadline=deadline)
        admit_closure(closure)
        result_desc, body = read_result(closure, operation, generation, numeric_source, budget)
        actual = {x['path']: x for x in closure['artifacts']}
        def produced(desc):
            c.need(desc['path'] in actual and c.typed_equal(desc, actual[desc['path']]), 'actual closed output descriptor')
            return desc
        if operation in ('fit', 'historical'):
            produced(body['model'])
            c.need(c.typed_equal(body['training_role'], role_record['role']) and body['view'] == view and body['outer'] == outer and body['inner'] == inner and body['family'] == family, 'complete actual fit role edge')
            expected_config = config if operation == 'fit' else {'id': 'HISTORICAL_BP_LDA', 'family': 'HISTORICAL_BP_LDA', 'shrinkage': 'AUTO', 'alpha': None, 'gamma': None}
            c.need(body['configuration'] == expected_config, 'actual selected model configuration')
            state = [x for x in closure['artifacts'] if Path(x['path']).parent == work / 'model']
            edge = {'model': body['model'], 'configuration': body['configuration'], 'state_artifacts': state,
                    'training_role': role_record['role'], 'view': view, 'outer': outer, 'family': family,
                    'selection': payload['selection'], 'closure': closure['receipt'], 'result': result_desc}
            fitted[(view, outer, inner, body['configuration']['id'] if inner != 'FINAL' else family)] = edge
            if inner == 'FINAL':
                models.append(edge)
        elif operation == 'inner_infer':
            c.need(c.typed_equal(body['model'], payload['model']) and body['configuration_id'] == payload['configuration_id'] and body['ids'] == payload['query']['ids'] and body['person'] == inner and body['view'] == view and body['temperature'] == 1, 'actual complete inner inference edge')
            oof.setdefault((view, outer), []).append({'result': result_desc, 'configuration_id': body['configuration_id'],
                'person': inner, 'scores': produced(body['scores']), 'probabilities_t1': produced(body['probabilities_t1']), 'closure': closure['receipt']})
        elif operation == 'select':
            c.need(c.typed_equal(body['role'], role_record['role']) and body['oof'] == payload['oof'] and body['view'] == view and body['outer'] == outer, 'selection exact closed180 producers/support')
            choice = body['selection']
            c.need([x['configuration_id'] for x in choice['setting_scores']] == list(configurations) and
                   [x['family'] for x in choice['selected_per_family']] == list(p.FAMILIES) and
                   [x['family'] for x in choice['selected_temperatures']] == list(p.FAMILIES) and
                   len(choice['temperature_scores']) == 21 and choice['strongest_family'] in p.FAMILIES,
                   'complete computed selection summary')
            selected[(view, outer)] = {'result': result_desc, 'body': body, 'closure': closure['receipt']}
            selections.append({'view': view, 'outer': outer, **selected[(view, outer)]})
            c.need(len(body['analytic_panels']) == 2, 'both full analytic panels')
            for handle, panel in zip(('UNIFORM', 'LAPLACE'), body['analytic_panels']):
                panels.append({'role': 'analytic', 'view': view, 'person': outer, 'handle': handle,
                               'panel': produced(panel), 'predictions': artifact(closure, handle + '_PREDICTIONS.json'), 'closure': closure['receipt']})
        else:
            c.need(body['ids'] == payload['query']['ids'] and body['person'] == outer and body['view'] == view and body['temperature'] == payload['temperature'] and c.typed_equal(body['model'], payload['model']), 'complete calibrated final inference edge')
            panels.append({'role': 'reference', 'view': view, 'person': outer, 'handle': family,
                           'panel': produced(body['panel']), 'predictions': artifact(closure, 'REFERENCE_PREDICTIONS.json'), 'closure': closure['receipt']})
        totals[operation] += 1
        jobs.append({'id': job['id'], 'operation': operation, 'request': request_desc, 'result': result_desc,
                     'closure': closure['receipt'], 'artifact_manifest': closure['artifact_manifest'], 'original_deadline': deadline, 'worker_io': io})
    c.need(totals == {'fit': 3660, 'historical': 20, 'inner_infer': 3600, 'infer': 80, 'select': 20}, 'all3680fits/3680inferences/20selectors')
    c.need(len(models) == 80 and len(selections) == 20 and len(panels) == 120, 'all80 models/20 selections/120 reference-plus-analytic panels')
    result = {'schema': 'neural081_reference_run_v1', 'generation': generation, 'numeric_source': numeric_source,
              'source_manifest': source_manifest, 'jobs': jobs, 'models': models, 'selections': selections, 'panels': panels,
              'counts': totals, 'R2_qualification_study_executed': False}
    result['descriptor'] = c.publish_json(destination / 'REFERENCE_RUN.json', result, budget)
    return result
