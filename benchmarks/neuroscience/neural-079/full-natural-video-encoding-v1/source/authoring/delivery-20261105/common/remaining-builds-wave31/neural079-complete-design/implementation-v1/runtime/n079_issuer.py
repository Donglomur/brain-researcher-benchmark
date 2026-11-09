"""Protected source/input custody joins; this service never computes a score.

External deployment admission remains a trust boundary. Dynamic source, views
and output promotions are bound to actual source-owned producer observations;
an incoming hash or candidate success flag alone is insufficient.
"""
import os
from ach_resource_common import bounded_decode, close_all
from n079_common import require, fields, identity, checked_pin, pin
from n079_observer import open_directory, observed_file


class IssuerService:
    def __init__(self, context, selected, observer):
        context.require_effect('custody_read', 'custody-issuer')
        fields(selected, ('static_requests', 'producer_roles', 'role_commands', 'worker_sources',
                          'study_pin', 'compiled_pin', 'protected_target_rule', 'deployment_selection_pin',
                          'common_materials', 'source_generation_context', 'study', 'outer_authority'))
        require(selected['study_pin'] == context.effect_admission['study_pin'], 'same complete independently admitted study')
        require(context.admission['receipts']['custody_receipt']['n079_issuer_selection_pin'] ==
                identity(selected, context.encoding_limits), 'protected issuer rules bound by external deployment custody')
        require(identity(selected['study'], context.encoding_limits) == selected['study_pin'], 'exact complete admitted study body')
        require(set(selected['static_requests']) == {'feature_environment', 'concrete_namespace_backend', 'provider_deployment_and_spend'},
                'static deployment declarations cannot shadow dynamic custody operations')
        from n079_outer_custody import OuterReleaseReader
        self.outer = OuterReleaseReader(context, selected['outer_authority'])
        self.outer_graphs = {}; self.native_views = {}; self.observation_evidence = {}; self.grading = None
        for name in ('compiled_pin', 'deployment_selection_pin'):
            checked_pin(selected[name])
        self.context, self.selected, self.observer = context, selected, observer
        self.jobs = {}; self.observations = {}; self.views = {}; self.programs = {}; self.promotions = {}
        self.all_policies_sealed = False; self.target_released = False
        self.public_bundles = {}; self.composed = {}; self.numeric_view_declarations = {}
        self.candidate_information_closed = False; self.export_evidence = None; self.target_objects = []; self.report_snapshots = {}; self.report_publications = {}
        require(selected['protected_target_rule'] == {'persons': 6, 'query_videos': 102, 'channels': 127, 'times': 1800,
            'normalization': 'fit-only', 'source': 'actual complete preparation output'}, 'full protected target rule, not unknown future bytes')

    def caller(self, actual, role):
        expected = self.context.admission['selection']['peers'][role]
        require(all(actual[k] == expected[k] for k in ('pid', 'uid', 'gid')), 'actual source-selected custody caller')

    def evidence(self, kind, payload):
        record = {'kind': kind, 'payload': payload, 'source_pin': self.context.source_pin,
                  'study_pin': self.selected['study_pin'], 'observed_ns': self.context.tick()}
        result = identity(record, self.context.encoding_limits)
        self.context.journal.append('issued_custody_evidence', {'record': record, 'evidence': result})
        return result

    def read_index(self, observation, index_name):
        matches = [x['object'] for x in observation['files'] if x['object']['path'] == index_name]
        require(len(matches) == 1 and matches[0]['bytes'] <= self.context.encoding_limits['bytes'], 'one bounded observed producer index')
        item = matches[0]; parent = None; fd = None; error = None
        try:
            parent = open_directory(observation['request']['output'])
            observed_file(self.context, parent, item, 'custody-issuer')
            require('/' not in index_name, 'fixed index leaf')
            self.context.ledger.charge('custody-issuer', {'source_read_bytes': item['bytes'] + 1}, 'independent index decode read')
            fd = os.open(index_name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
            raw = bytearray()
            while len(raw) <= item['bytes']:
                self.context.tick(); block = os.read(fd, min(65536, item['bytes'] - len(raw) + 1))
                if not block:
                    break
                raw.extend(block)
            require(pin(bytes(raw)) == {k: item[k] for k in ('bytes', 'sha256')}, 'fresh full index decode identity')
            return bounded_decode(bytes(raw), self.context.encoding_limits)
        except BaseException as exc:
            error = exc; raise
        finally:
            close_all(([] if fd is None else [('issuer index file', lambda: os.close(fd))]) +
                      ([] if parent is None else [('issuer index directory', lambda: os.close(parent))]), error)

    def register_product(self, payload, actual):
        self.caller(actual, 'controller')
        fields(payload, ('job', 'view_id', 'view_key', 'scope', 'expected_scope_pin'))
        require(payload['job'] in self.observations and payload['view_id'] not in self.views, 'fresh view from observed producer')
        job = self.jobs[payload['job']]
        require(job['role'] in ('assembler', 'features', 'training'), 'source-owned allowed public export producer')
        index = self.read_index(self.observations[payload['job']], 'RESULT_INDEX.json')
        require(index['schema'] == 'n079_product_index_v1' and payload['view_key'] in index['views'], 'actual typed public-view index')
        view = index['views'][payload['view_key']]
        require(view['scope'] == payload['scope'] and identity(view['scope'], self.context.encoding_limits) == payload['expected_scope_pin'],
                'exact allowed training/current-query scope, not an inferred alias')
        inventory = {x['object']['path']: x['object'] for x in self.observations[payload['job']]['files']}
        for item in view['outputs'].values():
            require(item['path'] in inventory and item == inventory[item['path']], 'every view backing actually observed')
            require(item not in self.target_objects, 'protected target backing excluded from public views')
        evidence = self.evidence('registered_view', {'job': payload['job'], 'view': view, 'id': payload['view_id']})
        self.views[payload['view_id']] = {'body': view, 'evidence': evidence, 'job': payload['job']}
        return evidence

    def native_admission(self, kind, payload, actual):
        self.caller(actual, 'controller')
        require(self.candidate_information_closed and 'controller' in self.outer_graphs and not self.target_released,
                'native private evidence only after all candidate information closes')
        selected = self.outer_graphs['controller']['configuration']['role_payload']['native']
        if kind == 'native_quantity_policy':
            fields(payload, ('key', 'selection'))
            require(payload['key'] in selected['comparisons'] and payload['selection'] == selected['comparisons'][payload['key']],
                    'exact independently admitted native source/input/units/support/reference/tolerance/nonfinite policy')
            return self.evidence(kind, payload)
        fields(payload, ('job', 'view', 'dependencies', 'program_evidence', 'base_view_evidence', 'binding'))
        import native_adapter
        program = native_adapter.compile_program(selected['program_selection'])
        jobs = {j['id']: j for j in program['jobs']}; name = payload['job']['id']
        require(name in jobs and payload['job'] == jobs[name] and name not in self.native_views,
                'one exact complete native job from original22 schedule')
        job = jobs[name]
        require(payload['program_evidence'] == selected['program_evidence'] and
                payload['base_view_evidence'] == selected['base_view_evidence'] and
                set(payload['dependencies']) == set(job['dependencies']), 'same independent programme and all original dependency edges')
        view = {**selected['views'][name], 'original_inputs': dict(selected['views'][name]['original_inputs']),
                'original_native_target_names': dict(selected['views'][name]['original_native_target_names'])}
        for dependency in job['dependencies']:
            require(dependency in self.observations, 'actual prior complete native dependency before current view')
            observed = self.observations[dependency]
            capture = self.read_index(observed, 'CAPTURE_INDEX.json')
            index_object = next(r['object'] for r in observed['files'] if r['object']['path'] == 'CAPTURE_INDEX.json')
            promotions = {}
            for member in capture['native_files']:
                choices = [p for p in self.promotions.values() if p['body']['job'] == dependency and
                           p['body']['output']['path'] == member['path']]
                require(len(choices) == 1, 'every original native dependency file actually promoted once')
                row = choices[0]['body']; promotions[member['path']] = {'path': row['material_name'],
                    **{k: row['output'][k] for k in ('bytes', 'sha256')}}
            record = native_adapter.make_dependency_record(capture, {k: index_object[k] for k in ('bytes', 'sha256')},
                                                           self.observation_evidence[dependency], promotions)
            require(record == payload['dependencies'][dependency], 'complete actual capture/output/observer dependency lineage')
            for file_id in job['dependency_files'][dependency]:
                member = record['native_files'][file_id]; alias = dependency + '-' + file_id
                require(alias not in view['original_inputs'], 'dependency cannot shadow original full support')
                view['original_inputs'][alias] = member['descriptor']
                view['original_native_target_names'][alias] = member['native_relative_path']
        require(payload['view'] == view and payload['binding'] == {'task': 'NEURAL-079', 'job': name,
            'program_pin': native_adapter.pin(native_adapter.canonical(program)), 'source_pin': self.context.source_pin,
            'view_pin': identity(view, self.context.encoding_limits)}, 'same complete actual native source/process view')
        evidence = self.evidence(kind, payload)
        self.native_views[name] = {'view': view, 'binding': payload['binding'], 'program_evidence': payload['program_evidence'], 'evidence': evidence}
        return evidence

    def controller_metadata(self, item):
        from n079_common import descriptor
        descriptor(item); require('/' not in item['path'], 'one exact source-owned controller metadata leaf')
        root = self.selected['outer_authority']['output_roots']['controller']; fd = None; first = None
        try:
            fd = open_directory(root['path']); st = os.fstat(fd)
            require({'device': st.st_dev, 'inode': st.st_ino} == root['identity'], 'actual independently selected controller output root')
            observation = observed_file(self.context, fd, item, 'custody-issuer')
            raw = self.outer.io.read(root['path'] + '/' + item['path'], {k: item[k] for k in ('bytes', 'sha256')})
            value = bounded_decode(raw, self.context.encoding_limits)
            self.context.journal.append('independent_live_controller_metadata', observation)
            return value
        except BaseException as error:
            first = error; raise
        finally:
            close_all([] if fd is None else [('controller metadata root', lambda: os.close(fd))], first)

    def report_admission(self, kind, payload, actual):
        import n079_report_evidence as reports
        from n079_composition import relative
        from n079_plan import bundles, QUERY
        bundle_map = {b['id']: b for b in bundles()}
        if kind == 'admit_report_material':
            self.caller(actual, 'supervisor')
            fields(payload, ('bundle_id', 'object', 'material_name', 'relative_path'))
            row = self.report_publications[payload['bundle_id']]
            root = self.selected['outer_authority']['output_roots']['controller']['path']
            require(payload['object'] == row['public'] and payload['material_name'] == row['material']['path'] and
                    payload['relative_path'] == relative(self.selected['outer_authority']['material_root'], root + '/' + row['public']['path']),
                    'only exact independently derived public report metadata is mountable')
            return self.evidence(kind, payload)
        self.caller(actual, 'controller')
        require(not self.candidate_information_closed and not self.target_released, 'own pre-report information phase remains open')
        key = payload['bundle_id']; require(key in bundle_map and payload['bundle_alias'] == self.public_bundles[key]['alias'], 'same own opaque bundle')
        if kind == 'report_evidence_input_admission':
            fields(payload, ('snapshot', 'source_pin', 'study_pin', 'bundle_id', 'bundle_alias', 'pre_report_cutoff'))
            require(key not in self.report_snapshots and payload['pre_report_cutoff'] is True and
                    payload['source_pin'] == self.context.source_pin and payload['study_pin'] == self.selected['study_pin'],
                    'one exact original pre-report source/study snapshot')
            source_choice = self.outer_graphs['controller']['configuration']['role_payload']['report']
            cap = source_choice['limits']; snapshot = self.controller_metadata(payload['snapshot'])
            reports._validate_snapshot(snapshot)
            require(snapshot['bundle_id'] == key and snapshot['bundle_alias'] == payload['bundle_alias'] and
                    snapshot['semantic_records'] == [], 'no fabricated semantic instrumentation')
            choice = source_choice['bundles'][key]
            repository = self.outer_graphs['controller']['configuration']['repository']
            original = repository['catalog'][choice['public_input']['path']]
            require(original['pin'] == {k: choice['public_input'][k] for k in ('bytes', 'sha256')}, 'original admitted public facts descriptor')
            public_input = bounded_decode(self.outer.io.read(repository['root'] + '/' + original['relative_path'], original['pin']), self.context.encoding_limits)
            require(self.controller_metadata(snapshot['public_input']) == public_input, 'exact source-owned public facts copy')
            for named in ('program', 'fitted'):
                seal = snapshot[named]; admitted = self.programs[seal['body']['id']]
                require(seal['body'] == admitted['body'] and seal['evidence'] == admitted['evidence'], 'exact already-issued source/state seal')
            require(snapshot['program']['body']['id'] == bundle_map[key]['policy_id'] and snapshot['fitted']['body']['id'] == key,
                    'same immutable policy and complete fitted own bundle')
            training_output = self.read_index(self.observations[key + '-training'], 'RESULT_INDEX.json')
            expected_state_files = training_output['payload']['state_files']
            require(len(expected_state_files) == len(set(expected_state_files)) and
                    set(snapshot['fitted']['states']) == set(expected_state_files),
                    'all declared actual fitted-state files, with none omitted from report evidence')
            require(snapshot['fitted']['body']['state_pins'] ==
                    [{k: item[k] for k in ('bytes', 'sha256')} for _, item in sorted(snapshot['fitted']['states'].items())],
                    'actual whole fitted bundle matches its original output-state seal')
            for filename, item in snapshot['fitted']['states'].items():
                promotion = self.promotions[item['path']]['body']
                require(promotion['job'] == key + '-training' and promotion['output']['path'] == filename and
                        {k: promotion['output'][k] for k in ('bytes', 'sha256')} == {k: item[k] for k in ('bytes', 'sha256')},
                        'actual full fitted-state backing')
            require([q['video_id'] for q in snapshot['queries']] == list(QUERY), 'all102 observed query records before report')
            for query in snapshot['queries']:
                name = key + '-query-%d' % query['video_id']; actual_job = self.jobs[name]
                require(query['job'] == name and query['closure'] == self.observation_evidence[name] and
                        query['view_evidence'] == actual_job['view_evidence'], 'actual current-query source/view/closure')
                sealed = self.programs[query['source_seal']['body']['id']]
                require(query['source_seal']['body'] == sealed['body'] and query['source_seal']['evidence'] == sealed['evidence'],
                        'actual source-sealed complete query method')
                promoted = self.promotions[query['prediction']['path']]['body']
                require(promoted['job'] == name and {k: promoted['output'][k] for k in ('bytes', 'sha256')} ==
                        {k: query['prediction'][k] for k in ('bytes', 'sha256')}, 'actual observed six-person query prediction')
            expected_jobs = {k for k in self.jobs if k.startswith(key + '-')}
            require({r['context'] for r in snapshot['jobs']} == expected_jobs and expected_jobs <= set(self.observations) and
                    not any(self.jobs[k]['work_id'] == 'report/' + key for k in expected_jobs), 'all own actual work before any report execution')
            for row in snapshot['jobs']:
                name = row['context']; observed = self.observations[name]
                output = self.read_index(observed, 'RESULT_INDEX.json')
                require(row == {'context': name, 'phase': 'closed', 'request_pin': self.jobs[name]['request_pin'],
                    'output_pin': reports.ident(output, cap), 'inventory_pin': reports.ident(observed['request']['inventory'], cap),
                    'closure': self.observation_evidence[name]}, 'independent exact observed process projection')
            for item in snapshot['cost_records']:
                value = self.controller_metadata(item)
                reports.validate_cost_prefix(value, key, bundle_map[key]['policy_id'], self.selected['study_pin'], cap)
                retained = self.observer.request('retained_bundle_budget_prefix', {'evidence': value['evidence']})
                require(value == retained, 'actual central observer cost prefix, never caller counters')
            evidence = self.evidence(kind, payload)
            self.report_snapshots[key] = {'snapshot': snapshot, 'descriptor': payload['snapshot'], 'public_input': public_input,
                                          'cap': cap, 'evidence': evidence}
            return evidence
        fields(payload, ('bundle_id', 'bundle_alias', 'public', 'private', 'snapshot', 'admission'))
        admitted = self.report_snapshots[key]
        require(key not in self.report_publications and payload['snapshot'] == admitted['descriptor'] and
                payload['admission'] == admitted['evidence'], 'one exact admitted pre-report projection')
        derived = reports.derive(admitted['snapshot'], admitted['public_input'], [], admitted['cap'])
        require(self.controller_metadata(payload['public']) == derived['public'], 'independently derived sanitized public report evidence')
        private = self.controller_metadata(payload['private'])
        require(private == {'schema': 'n079_report_private_evidence_v1', 'snapshot': payload['snapshot'], 'admission': payload['admission'],
            'public': payload['public'], 'bundle_id': key, 'bundle_alias': payload['bundle_alias'], 'source_pin': self.context.source_pin,
            'study_pin': self.selected['study_pin'], 'derived': derived}, 'complete private derivation stays private')
        evidence = self.evidence(kind, payload)
        material = {'path': 'report-metadata-' + payload['bundle_alias'], **{k: payload['public'][k] for k in ('bytes', 'sha256')}}
        self.report_publications[key] = {**payload, 'evidence': evidence, 'material': material}
        return evidence

    def grading_admission(self, payload, actual):
        self.caller(actual, 'grader')
        fields(payload, ('index', 'index_observation_pin', 'study_pin', 'source_closure_pin', 'observation_pin',
                         'allocation_pin', 'numeric_source', 'dependency_admission_pin'))
        require(self.grading is None and self.candidate_information_closed, 'one complete target-last index admission')
        graph = self.outer.release('grader', actual)
        installed = graph['configuration']; selection = installed['role_payload']['selection']
        require(payload['index'] == installed['role_payload']['input_index'] and payload['numeric_source'] == installed['role_payload']['numeric_source'] and
                all(payload[k] == selection[k] for k in ('index_observation_pin', 'study_pin', 'source_closure_pin',
                    'observation_pin', 'allocation_pin', 'dependency_admission_pin')), 'exact independently installed grader selection')
        require(payload['source_closure_pin'] == self.context.source_pin and payload['study_pin'] == self.selected['study_pin'] and
                payload['allocation_pin'] == self.context.effect_admission['allocation_pin'], 'same whole source/study/allocation')
        from n079_composition import MetadataBuilder, object_pin, relative
        from n079_plan import admit_study_metadata, bundles, native_jobs, QUERY
        # Re-run ONLY the fixed metadata derivation from independently retained
        # outer observations. No numerical array is opened or graded here.
        builder = MetadataBuilder.__new__(MetadataBuilder)
        builder.io = self.outer.io; builder.encoding = self.context.encoding_limits
        builder.source = self.context.source_pin; builder.study_pin = self.selected['study_pin']
        builder.parts = admit_study_metadata(self.selected['study']); builder.catalog = {}; builder.observations = graph['observations']
        builder.coordinate_pin = identity({'channels': self.selected['study']['channels'],
            'times': self.selected['study']['times'], 'order': 'channel-time'}, builder.encoding)
        builder.cfg = {'study': self.selected['study'], 'output_roots': self.selected['outer_authority']['output_roots'],
            'material_root': self.selected['outer_authority']['material_root'],
            'source_admission_pin': self.context.profile['source_environment_pin'],
            'original_clock_pin': identity({k: getattr(self.context.clock, k) for k in ('origin', 'scientific', 'closeout', 'outer')}, builder.encoding),
            'role_templates': {'references': {'numeric_source_pins': installed['numeric_source_pins']},
                               'grader': {'context': {'allocation': self.context.allocation}}}}
        # The central ledger implementation exposes its exact original
        # allocation through EffectContext, not a candidate-reported total.
        builder.cfg['role_templates']['grader']['context']['allocation'] = self.context.allocation
        expected = builder.grade_index()
        repository = installed['repository']; item = payload['index']; entry = repository['catalog'][item['path']]
        require(entry['pin'] == object_pin(item), 'same selected ordinary grade input body')
        path = repository['root'] + '/' + entry['relative_path']
        require(relative(repository['root'], path) == entry['relative_path'], 'safe complete grade input path')
        body = bounded_decode(self.outer.io.read(path, object_pin(item)), self.context.encoding_limits)
        require(body == expected, 'independent exact complete grade-index derivation from actual original records')
        require(payload['index_observation_pin'] == identity({'schema': 'n079_fresh_grade_input_observation_v1',
                'index': item, 'source_pin': self.context.source_pin, 'input_graph_pin': identity(graph['observations'], builder.encoding)}, builder.encoding),
                'actual independently retained post-write index observation lineage')
        require(all(repository['catalog'].get(k) == v for k, v in builder.catalog.items()), 'every derived numerical/report target has its actual observed backing')
        expected_jobs = {b['id'] + '-query-%d' % q for b in bundles() for q in QUERY}
        expected_jobs |= {b['id'] + '-training' for b in bundles()} | {b['id'] + '-report' for b in bundles()}
        expected_jobs |= {j['id'] for j in native_jobs()}
        require(expected_jobs <= set(self.observations) and set(self.jobs) == set(self.observations),
                'all actual candidates/reports/22 native jobs and every additional attempt observed')
        evidence = self.evidence('grading_index_admission', {'payload': payload, 'outer_release': graph['release'],
            'actual_input_pin': object_pin(item), 'all_process_observations': sorted(self.observations)})
        self.grading = {'body': body, 'descriptor': item, 'evidence': evidence}; self.outer_graphs['grader'] = graph
        return evidence

    def handle(self, kind, payload, actual):
        if kind in self.selected['static_requests']:
            declaration = self.selected['static_requests'][kind]
            self.caller(actual, declaration['role'])
            require(identity(payload, self.context.encoding_limits) == declaration['payload_pin'],
                    'exact independently admitted deployment/environment/source request')
            return self.evidence(kind, payload)
        if kind == 'register_outer_inputs':
            self.caller(actual, 'controller'); fields(payload, ('role',))
            require(payload['role'] == 'controller' and not self.outer_graphs, 'one actual pre-candidate outer graph')
            graph = self.outer.release('controller', actual)
            require(set(graph['observations']) == {'features', 'assembler', 'grams', 'references'}, 'all actual full prerequisites')
            self.outer_graphs['controller'] = graph
            preparation = graph['observations']['assembler']['index']['body']
            self.target_objects = [dict(row['object'], path='assembler/' + row['object']['path'])
                                   for row in preparation['query_targets'].values()]
            require(len(self.target_objects) == 6, 'all actual protected full query targets')
            self.public_bundles = graph['configuration']['role_payload']['candidate']['public_bundles']
            from n079_plan import bundles
            require(set(self.public_bundles) == {b['id'] for b in bundles()}, 'all36 full public preparation exports')
            self.export_evidence = self.evidence(kind, graph)
            return self.export_evidence
        if kind == 'admit_outer_public_materials':
            self.caller(actual, 'supervisor'); fields(payload, ('catalog', 'export_evidence'))
            require(payload['export_evidence'] == self.export_evidence and self.export_evidence is not None, 'actual registered public graph')
            paths = set()
            for row in self.public_bundles.values():
                paths.update(d['path'] for d in row['training'].values())
                paths.update(d['path'] for query in row['queries'].values() for d in query.values())
            actual_catalog = self.outer_graphs['controller']['configuration']['repository']['catalog']
            require(payload['catalog'] == {k: actual_catalog[k] for k in sorted(paths)}, 'all and only actual permitted public backing mappings')
            return self.evidence(kind, payload)
        if kind in ('report_evidence_input_admission', 'publish_own_report_metadata', 'admit_report_material'):
            return self.report_admission(kind, payload, actual)
        if kind in ('native_complete_view', 'native_quantity_policy'):
            return self.native_admission(kind, payload, actual)
        if kind == 'grading_index_admission':
            return self.grading_admission(payload, actual)
        if kind == 'register_product':
            return self.register_product(payload, actual)
        if kind == 'register_preparation_exports':
            self.caller(actual, 'finalizer')
            require(not self.public_bundles and payload['job'] == 'prepare-full' and payload['job'] in self.observations,
                    'one actual complete source-owned preparation return')
            index = self.read_index(self.observations[payload['job']], 'RESULT_INDEX.json')
            from n079_plan import bundles
            require(index['schema'] == 'n079_preparation_index_v1' and index['study_pin'] == self.selected['study_pin'] and
                    set(index['public_bundles']) == {b['id'] for b in bundles()}, 'complete actual public preparation programme')
            self.public_bundles = index['public_bundles']
            return self.evidence(kind, {'job': payload['job'], 'exports': index['public_exports']})
        if kind == 'compose_public_view':
            self.caller(actual, 'controller')
            fields(payload, ('bundle', 'alias', 'phase', 'query', 'materials', 'public_export_evidence',
                              'training_seal', 'previous_current_context'))
            require(payload['bundle'] in self.public_bundles and not self.target_released and not self.candidate_information_closed,
                    'admitted actual preparation bundle before information boundary closes')
            public = self.public_bundles[payload['bundle']]
            require(payload['public_export_evidence'] == self.export_evidence, 'actual registered full preparation export evidence')
            require(payload['alias'] == public['alias'], 'same opaque public bundle identity')
            phase, query = payload['phase'], payload['query']
            require(phase in ('training', 'query', 'report') and ((phase == 'query') == (query is not None)), 'exact current-context phase')
            allowed = {'/training/' + n: d for n, d in public['training'].items()}
            if query is not None:
                require(str(query) in public['queries'], 'one complete current-query view')
                allowed.update({'/query/' + n: d for n, d in public['queries'][str(query)].items()})
            from n079_plan import bundles
            tool = next(b['tool'] for b in bundles() if b['id'] == payload['bundle'])
            allowed.update({'/common/' + n: d for n, d in self.selected['common_materials'][tool].items()})
            if phase == 'report':
                require(payload['bundle'] in self.report_publications, 'actual independent own pre-report evidence')
                allowed['/report/evidence.json'] = self.report_publications[payload['bundle']]['material']
            for name, item in payload['materials'].items():
                if name in allowed:
                    require({k: item[k] for k in ('bytes', 'sha256')} == {k: allowed[name][k] for k in ('bytes', 'sha256')},
                            'same source-derived allowed public backing')
                else:
                    require(name.startswith('/sealed/'), 'no additional public data namespace')
                    promotions = [v['body'] for v in self.promotions.values() if v['body']['material_name'] == item['path'] and
                                  {k: v['body']['output'][k] for k in ('bytes', 'sha256')} == {k: item[k] for k in ('bytes', 'sha256')}]
                    require(len(promotions) == 1, 'actual observed state/prediction promotion')
                    job = self.jobs[promotions[0]['job']]; work = job['work_id']
                    permitted = work == 'training/' + payload['bundle']
                    permitted |= query is not None and work == 'query/%s/%d' % (payload['bundle'], query)
                    permitted |= phase == 'report' and (work.startswith('query/' + payload['bundle'] + '/') or work == 'report/' + payload['bundle'])
                    require(permitted, 'no cross-bundle or previous-query feedback in current query')
                require(item not in self.target_objects, 'no protected target object in public view')
            require(set(allowed) <= set(payload['materials']), 'all allowed full training/current stimulus support present')
            evidence = self.evidence(kind, payload)
            view = {'schema': 'ach_minimized_process_view_v1', 'materials': payload['materials'], 'exposure_admission': evidence,
                    'forbidden_feedback': ['native', 'reference_results', 'outer_labels', 'other_contexts']}
            self.composed[evidence['sha256']] = {'body': payload, 'view': view, 'evidence': evidence}
            return evidence
        if kind == 'seal_program':
            self.caller(actual, 'controller')
            fields(payload, ('id', 'policy_id', 'phase', 'method_pin', 'state_pins', 'lineage', 'global_policy_pin'))
            require(payload['id'] not in self.programs and not self.target_released, 'fresh immutable fitted source/state before targets')
            checked_pin(payload['method_pin']); checked_pin(payload['global_policy_pin'])
            for value in payload['state_pins']:
                checked_pin(value)
            require(payload['phase'] in ('global_policy', 'training_final', 'query_final', 'report'), 'named generated source lifecycle')
            if payload['phase'] == 'global_policy':
                require(not self.all_policies_sealed and not any(j['role'] in ('training', 'query', 'inspect', 'report', 'fit-helper')
                        for j in self.jobs.values()), 'all global programs before candidate numeric process exposure')
            else:
                require(self.all_policies_sealed and payload['policy_id'] in self.programs, 'same sealed global policy')
                require(payload['global_policy_pin'] == self.programs[payload['policy_id']]['body']['method_pin'], 'immutable policy source')
            evidence = self.evidence(kind, payload)
            self.programs[payload['id']] = {'body': payload, 'evidence': evidence}
            return evidence
        if kind == 'seal_all_policies':
            self.caller(actual, 'controller')
            from n079_plan import policies
            expected = {x['id'] for x in policies()}
            require(not self.all_policies_sealed and set(payload) == expected and set(self.programs) == expected and
                    all(payload[k] == self.programs[k]['evidence'] for k in expected), 'all12 exact policies before exposure')
            self.all_policies_sealed = True; return self.evidence(kind, payload)
        if kind == 'all_policy_sources_sealed':
            self.caller(actual, 'provider')
            from n079_plan import policies
            require(self.all_policies_sealed and set(payload) == {p['id'] for p in policies()} and
                    all(payload[k]['program_pin'] == self.programs[k]['body']['method_pin'] for k in payload),
                    'actual provider binds all same sealed global sources')
            return self.evidence(kind, payload)
        if kind == 'actual_numeric_view_exposure':
            self.caller(actual, 'provider')
            evidence = payload['observed_stage']; require(evidence['sha256'] in self.composed, 'source-admitted intended view')
            view = self.composed[evidence['sha256']]
            require(view['body']['bundle'] == payload['bundle'] and identity(view['view'], self.context.encoding_limits) == payload['view_pin'],
                    'declared view authorization; actual stage chronology is recorded separately')
            self.numeric_view_declarations[payload['bundle']] = evidence
            return self.evidence('declared_numeric_view_authorization', payload)
        if kind == 'provider_current_public_context':
            self.caller(actual, 'provider')
            require(not self.candidate_information_closed, 'provider never receives later private reference/native/grade feedback')
            work = payload['work_id']
            if work.startswith('policy/'):
                require(not self.all_policies_sealed and payload['context_evidence'] == self.selected['source_generation_context'],
                        'source-only initial policy context')
            else:
                evidence = payload['context_evidence']; require(evidence['sha256'] in self.composed, 'actual admitted provider context')
                view = self.composed[evidence['sha256']]['body']
                expected = 'query/%s/%d' % (view['bundle'], view['query']) if view['query'] is not None else view['phase'] + '/' + view['bundle']
                require(work == expected, 'provider has only exact current phase/bundle/query information')
            return self.evidence(kind, payload)
        if kind == 'close_candidate_information_phase':
            self.caller(actual, 'controller')
            from n079_plan import bundles, QUERY
            expected = {b['id'] + '-query-%d' % q for b in bundles() for q in QUERY}
            expected |= {b['id'] + '-training' for b in bundles()} | {b['id'] + '-report' for b in bundles()}
            actual_jobs = {k for k, j in self.jobs.items() if j['role'] in ('training', 'query', 'report', 'inspect', 'fit-helper')}
            require(not self.candidate_information_closed and expected <= set(self.observations) and
                    payload['complete_jobs'] == sorted(actual_jobs) and actual_jobs <= set(self.observations),
                    'all exact candidate work observed before information cutoff')
            self.candidate_information_closed = True
            return self.evidence(kind, payload)
        if kind == 'actual_complete_process_view':
            self.caller(actual, 'supervisor')
            require(payload['context'] not in self.jobs and payload['role'] in self.selected['producer_roles'], 'fresh admitted process role')
            require(payload['argv'] == self.selected['role_commands'][payload['role']], 'same actual source-owned command')
            if payload['role'] in ('training', 'query', 'report', 'inspect', 'fit-helper'):
                require(self.all_policies_sealed and not self.target_released and not self.candidate_information_closed,
                        'all policies sealed and candidate information phase open')
                joined = [v for v in self.composed.values() if v['evidence'] == payload['view_evidence']]
                require(len(joined) == 1 and joined[0]['view'] == payload['view'], 'exact protected public-view body')
                current = joined[0]['body']
                expected_work = 'query/%s/%d' % (current['bundle'], current['query']) if current['query'] is not None else current['phase'] + '/' + current['bundle']
                require(payload['work_id'] == expected_work and payload['binding']['bundle'] == current['bundle'] and
                        payload['binding']['query'] == current['query'], 'actual budget and process share the exact current information context')
                programs = [v for v in self.programs.values() if v['evidence'] == payload['program_evidence']]
                require(len(programs) == 1, 'one actual sealed policy/fitted method identity')
                from n079_plan import bundles
                bundle = next(b for b in bundles() if b['id'] == current['bundle'])
                expected_sources = self.selected['worker_sources'][bundle['tool']][payload['role']]
                require({k:v for k,v in payload['sources'].items() if k not in ('/program/method.py','/request/request.json')} == expected_sources,
                        'actual complete per-tool sandbox source closure; same availability for F and I')
                import base64
                encoded_request = payload['sources']['/request/request.json']
                raw_request = base64.b64decode(encoded_request['body_base64'], validate=True)
                require(pin(raw_request) == encoded_request['pin'] == payload['request_pin'], 'actual whole generated request body')
                request = bounded_decode(raw_request, self.context.encoding_limits)
                require(request['helper_configuration'] == self.selected['common_materials'][bundle['tool']].get('helper-configuration.json') and
                        request['bundle_alias'] == current['alias'] and request['query_video_id'] == current['query'] and
                        request['public_metadata'] == self.public_bundles[current['bundle']]['public_metadata'],
                        'same source-owned current input and helper configuration in actual request')
                require(programs[0]['body']['policy_id'] == bundle['policy_id'], 'same immutable global policy and mode/tool/seed')
                if current['phase'] in ('query', 'report'):
                    require(current['training_seal'] == self.programs[current['bundle']]['evidence'], 'same final fitted state before all outer queries/reports')
                method = payload['sources']['/program/method.py']
                require(method['pin'] == programs[0]['body']['method_pin'], 'actual source bytes match immutable generated method')
                actual_states = [{k: item[k] for k in ('bytes', 'sha256')}
                    for name, item in sorted(payload['view']['materials'].items()) if name.startswith('/sealed/')]
                require(programs[0]['body']['state_pins'] == actual_states,
                        'complete currently mounted learned/query/report state belongs to the actual method seal')
            elif payload['role'] == 'native':
                admitted = self.native_views.get(payload['context'])
                require(admitted is not None and payload['view'] == admitted['view'] and
                        payload['view_evidence'] == admitted['evidence'] and payload['binding'] == admitted['binding'] and
                        payload['program_evidence'] == admitted['program_evidence'], 'actual complete native dependency/view programme')
            else:
                declaration = self.selected['producer_roles'][payload['role']]
                require(payload['program_evidence'] == declaration['program_evidence'] and
                        payload['view_evidence'] == declaration['view_evidence'], 'trusted preparation/native/reference complete view authority')
            self.jobs[payload['context']] = payload
            return self.evidence(kind, payload)
        if kind == 'independent_producer_observation':
            self.caller(actual, 'supervisor')
            require(payload['job'] in self.jobs and payload['job'] not in self.observations, 'actual admitted job before observation')
            require(payload['binding'] == self.jobs[payload['job']]['binding'], 'same source/view job binding')
            observation = self.observer.request('job_observation', payload)
            require(observation['request'] == payload, 'independent observed exact job')
            self.observations[payload['job']] = observation
            evidence = self.evidence(kind, observation); self.observation_evidence[payload['job']] = evidence
            return evidence
        if kind == 'immutable_observed_output_promotion':
            self.caller(actual, 'supervisor')
            require(payload['job'] in self.observations and payload['material_name'] not in self.promotions, 'once-only observed material promotion')
            observed = self.observations[payload['job']]
            require(payload['output'] in [x['object'] for x in observed['files']], 'exact observed output body')
            # Immutability after this join additionally depends on the admitted
            # host/custody writer exclusion; observation alone cannot create it.
            evidence = self.evidence(kind, payload); self.promotions[payload['material_name']] = {'body': payload, 'evidence': evidence}
            return evidence
        if kind == 'target_last_release':
            self.caller(actual, 'grader')
            fields(payload, ('index', 'index_admission', 'closure', 'selection_pin', 'prediction_objects_pin',
                             'report_objects_pin', 'reference_fit_records', 'candidate_bundles', 'native_jobs', 'reports'))
            require(not self.target_released and self.grading is not None and self.candidate_information_closed,
                    'actual full index admission and closed candidate/native programme before targets')
            index = self.grading['body']
            require(payload['index'] == self.grading['descriptor'] and payload['index_admission'] == self.grading['evidence'] and
                    payload['closure'] == index['closure'] and payload['reference_fit_records'] == 5496 and
                    payload['candidate_bundles'] == 36 and payload['native_jobs'] == 22 and payload['reports'] == 36,
                    'exact complete protected grading input/barrier')
            checked_pin(payload['selection_pin'])
            predictions = {}
            for row in index['candidates']:
                for person in row['predictions']:
                    predictions[row['id'], person['person']] = person['matrix']
            for row in index['reference_final']:
                predictions['reference/' + row['signal'] + '/' + row['family'], row['person']] = row['prediction']
            for row in index['means']:
                predictions['mean/' + row['signal'], row['person']] = row['prediction']
            require(payload['prediction_objects_pin'] == identity([d['object'] for _, d in sorted(predictions.items())], self.context.encoding_limits) and
                    payload['report_objects_pin'] == identity([r['report'] for r in sorted(index['candidates'], key=lambda r: r['id'])], self.context.encoding_limits),
                    'every actual prediction/report included before protected targets')
            self.target_released = True; return self.evidence(kind, payload)
        raise ValueError('unselected protected issuer request')
