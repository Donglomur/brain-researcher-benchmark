"""Full F/I source generation, adaptive training and fresh current-query runs.

Only actual provider responses and actual supervised outputs advance state.
Inner exploration is adaptive training; no unbiased inner-investigator claim.
"""
import base64
from n079_common import fields, require, integer, identity, pin, canonical
from n079_plan import policies, bundles, QUERY, PERSONS, Q


def tools(tool_arm):
    require(tool_arm in ('basic', 'fit-helper'), 'selected tool arm')
    definitions = {
        'commit_program': ('Commit an immutable pre-data Python run(request) policy and initial method.',
                           {'source': {'type': 'string'}, 'policy': {'type': 'string'}}),
        'run_python': ('Execute a Python run(request) analysis in a fresh permitted-data sandbox.',
                       {'source': {'type': 'string'}}),
        'finish': ('Seal the current complete method for the declared phase.', {'source': {'type': 'string'}}),
    }
    if tool_arm == 'fit-helper':
        definitions['fit_helper'] = ('Execute the source-pinned reference fit/transform/predict helper on authorized rows only.',
                                     {'request': {'type': 'object'}})
    return [{'type': 'function', 'function': {'name': name, 'description': description,
            'parameters': {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}}}
            for name, (description, properties) in definitions.items()]


class Controller:
    def __init__(self, context, supervisor, provider, selected, report_builder):
        context.require_effect('candidate_job', 'controller')
        fields(selected, ('protocol_text', 'worker_sources', 'role_commands', 'initial_context_evidence',
                          'source_byte_limit', 'analysis_step_limit', 'public_bundles', 'common_materials',
                          'deployment_selection_pin'))
        from n079_protocol import PROTOCOL
        require(selected['protocol_text'] == PROTOCOL, 'exact fixed common candidate protocol before any provider or numeric exposure')
        from n079_report_evidence import ReportEvidenceBuilder
        require(type(report_builder) is ReportEvidenceBuilder and report_builder.context is context, 'actual fixed source-owned report evidence builder')
        self.report_builder = report_builder; self.report_evidence = {}; self.report_materials = {}; self.report_public = {}
        self.context, self.supervisor, self.provider, self.selected = context, supervisor, provider, selected
        self.programs = {}; self.fitted = {}; self.queries = {}; self.reports = {}; self.jobs = []
        self.source_limit = integer(selected['source_byte_limit'], 1)
        self.step_limit = integer(selected['analysis_step_limit'], 1)
        require(set(selected['public_bundles']) == {b['id'] for b in bundles()}, 'all36 full public bundles')
        require(set(selected['common_materials']) == set(selected['worker_sources']) == {'basic','fit-helper'},
                'explicit matched F/I per-tool source and material availability')
        basic, helper = selected['common_materials']['basic'], selected['common_materials']['fit-helper']
        require('helper-configuration.json' not in basic and set(helper) == set(basic) | {'helper-configuration.json'} and
                all(helper[k] == v for k,v in basic.items()), 'same common data with only the declared packaged helper configuration added')
        for tool in ('basic','fit-helper'):
            expected = {'training','query','report','inspect'} | ({'fit-helper'} if tool == 'fit-helper' else set())
            require(set(selected['worker_sources'][tool]) == expected, 'all actual sandbox roles for the declared tool arm')
            for sources in selected['worker_sources'][tool].values():
                require(('/source/n079_candidate_helper.py' in sources) == (tool == 'fit-helper') and
                        ('/source/n079_numeric_r1.py' in sources) == (tool == 'fit-helper'), 'same callable packaged helper for F and I only in its arm')
        self.serial = 0

    def source(self, value, work):
        require(type(value) is str and len(value) <= self.source_limit, 'bounded generated source characters before encoding')
        raw = value.encode('utf-8'); require(len(raw) <= self.source_limit, 'bounded generated source bytes')
        self.context.ledger.charge(work, {'code_revisions': 1, 'source_read_bytes': len(raw)}, 'actual generated source revision')
        # Syntax parsing does not execute generated code in the protected host.
        import ast
        ast.parse(raw)
        return {'body_base64': base64.b64encode(raw).decode('ascii'), 'pin': pin(raw)}

    def seal(self, name, policy, phase, source, states, lineage):
        body = {'id': name, 'policy_id': policy, 'phase': phase, 'method_pin': source['pin'],
                'state_pins': [pin_ for _, pin_ in sorted(states.items())], 'lineage': lineage,
                'global_policy_pin': source['pin'] if phase == 'global_policy' else self.programs[policy]['source']['pin']}
        evidence = self.context.authority.exchange('seal_program', body)
        return {'source': source, 'states': states, 'body': body, 'evidence': evidence}

    def input_state_pins(self, view):
        return {name: {key: item[key] for key in ('bytes', 'sha256')}
                for name, item in sorted(view['materials'].items()) if name.startswith('/sealed/')}

    def preseal(self):
        require(not self.programs and not self.jobs, 'source generation before any candidate numeric work')
        for policy in policies():
            work = 'policy/' + policy['id']
            messages = [{'role': 'system', 'content': self.selected['protocol_text']},
                        {'role': 'user', 'content': 'Before any numeric exposure, commit the complete %s policy for %s tools. '
                         'Return exactly one commit_program action; include run(request) for training, query and report. '
                         'F cannot revise source or call a provider after data exposure. I follows the sealed policy while generating fitted code.' %
                         (policy['mode'], policy['tool'])}]
            result = self.provider.call(work, messages, tools(policy['tool']), self.selected['initial_context_evidence'])
            require(len(result['actions']) == 1 and result['actions'][0]['name'] == 'commit_program', 'one complete actual policy commitment')
            arguments = result['actions'][0]['arguments']; fields(arguments, ('source', 'policy'))
            source = self.source(arguments['source'], work)
            sealed = self.seal(policy['id'], policy['id'], 'global_policy', source, {},
                               {'provider_request': result['request_pin'], 'provider_response': result['response_pin'],
                                'policy_text': arguments['policy'], 'numeric_exposure': None})
            sealed['policy_text'] = arguments['policy']; self.programs[policy['id']] = sealed
        self.context.authority.exchange('seal_all_policies', {k: v['evidence'] for k, v in self.programs.items()})
        self.provider.seal_policies({p['id']: {'policy_source_pin': self.selected['public_bundles'][p['id'] + '-measured']['policy_source_pin'],
                                             'program_pin': self.programs[p['id']]['source']['pin']} for p in policies()})

    def view(self, bundle, phase, query, states, previous=None):
        public = self.selected['public_bundles'][bundle['id']]
        fields(public, ('alias', 'training', 'queries', 'public_metadata', 'policy_source_pin', 'public_export_evidence'))
        require(set(public['queries']) == {str(q) for q in QUERY}, 'all102 independently backed current stimuli')
        materials = {'/training/' + name: item for name, item in public['training'].items()}
        if query is not None:
            materials.update({'/query/' + name: item for name, item in public['queries'][str(query)].items()})
        materials.update({'/sealed/' + name: item for name, item in states.items()})
        materials.update({'/common/' + name: item for name, item in self.selected['common_materials'][bundle['tool']].items()})
        if phase == 'report':
            materials['/report/evidence.json'] = self.report_materials[bundle['id']]
            for q, record in self.queries[bundle['id']].items():
                materials['/sealed/query-%d.f64' % q] = record['prediction']
        body = {'bundle': bundle['id'], 'alias': public['alias'], 'phase': phase, 'query': query,
                'materials': materials, 'public_export_evidence': public['public_export_evidence'],
                'training_seal': None if bundle['id'] not in self.fitted else self.fitted[bundle['id']]['evidence'],
                'previous_current_context': previous}
        evidence = self.context.authority.exchange('compose_public_view', body)
        return {'schema': 'ach_minimized_process_view_v1', 'materials': materials,
                'exposure_admission': evidence, 'forbidden_feedback': ['native', 'reference_results', 'outer_labels', 'other_contexts']}, evidence

    def execute(self, bundle, phase, source, program_evidence, view, view_evidence, *, query=None, exploratory=False, helper=None, context_phase=None):
        work = ('query/%s/%d' % (bundle['id'], query)) if query is not None else phase + '/' + bundle['id']
        if phase == 'inspect':
            require(context_phase in ('training', 'query', 'report') and ((context_phase == 'query') == (query is not None)), 'exact current investigation phase')
            work = context_phase + '/' + bundle['id'] if query is None else 'query/%s/%d' % (bundle['id'], query)
        self.serial += 1
        context_id = '%s-%s' % (bundle['id'], 'query-%d' % query if phase == 'query' else phase)
        if exploratory:
            context_id += '-analysis-%d' % self.serial
        public = self.selected['public_bundles'][bundle['id']]
        request = {'schema': 'n079_generated_request_v1', 'phase': phase, 'bundle_alias': public['alias'],
                   'query_video_id': query, 'persons': list(PERSONS), 'shape': [6, 127, 1800],
                   'public_metadata': public['public_metadata'], 'helper': helper,
                   'report_evidence_path': '/report/evidence.json' if (phase == 'report' or context_phase == 'report') else None,
                   'helper_configuration': self.selected['common_materials'][bundle['tool']].get('helper-configuration.json')}
        raw = canonical(request, self.context.encoding_limits)
        role = 'fit-helper' if helper is not None else phase
        source_files = dict(self.selected['worker_sources'][bundle['tool']][role])
        source_files.update({'/request/request.json': {'body_base64': base64.b64encode(raw).decode('ascii'), 'pin': pin(raw)},
                             '/program/method.py': source})
        binding = {'task': 'NEURAL-079', 'bundle': bundle['id'], 'phase': phase, 'query': query,
                   'view_pin': identity(view, self.context.encoding_limits), 'method_pin': source['pin'],
                   'program_evidence': program_evidence, 'source_pin': self.context.source_pin}
        job = {'schema': 'n079_actual_job_v1', 'context': context_id, 'work_id': work, 'role': role,
               'sources': source_files, 'view': view, 'binding': binding, 'argv': self.selected['role_commands'][role],
               'request_pin': pin(raw), 'view_evidence': view_evidence, 'program_evidence': program_evidence}
        self.context.ledger.charge(work, {'code_executions': 1}, 'actual fresh generated-code/helper process')
        if helper is not None:
            self.context.ledger.charge(work, {'fit_calls': 1, 'numeric_block_applications': 1}, 'actual packaged full requested fit block; arbitrary Python internals remain unclassified')
        result = self.supervisor.run(job); self.jobs.append(result)
        require(result['phase'] == 'closed' and result['request_pin'] == pin(raw), 'actual independently observed complete generated job')
        index = result['output']
        require(index['schema'] == 'n079_generated_result_v1' and index['phase'] == phase and index['request_pin'] == pin(raw),
                'exact actual source/request/output join')
        return result

    def promote_states(self, result):
        payload = result['output']['payload']; fields(payload, ('state_files', 'analysis'))
        require(type(payload['state_files']) is list and len(set(payload['state_files'])) == len(payload['state_files']), 'explicit unique fitted-state outputs')
        inventory = {x['path']: x for x in result['inventory']}; states = {}
        for name in payload['state_files']:
            require(type(name) is str and '/' not in name and name in inventory and name != 'RESULT_INDEX.json', 'observed ordinary fitted state leaf')
            states[name] = self.supervisor.promote(result['context'], name, result['context'] + '-' + name)
        return states

    def investigate(self, bundle, phase, source, sealed, view, evidence, *, query=None):
        work = 'query/%s/%d' % (bundle['id'], query) if query is not None else phase + '/' + bundle['id']
        messages = [{'role': 'system', 'content': self.selected['protocol_text'] + '\nSealed global policy:\n' +
                     self.programs[bundle['policy_id']]['policy_text']},
                    {'role': 'user', 'content': canonical({'phase': phase, 'query_video_id': query,
                        'bundle_alias': self.selected['public_bundles'][bundle['id']]['alias'],
                        'public_metadata': self.selected['public_bundles'][bundle['id']]['public_metadata'],
                        'initial_method_utf8': base64.b64decode(source['body_base64']).decode('utf-8'),
                        'own_report_evidence': self.report_public.get(bundle['id']) if phase == 'report' else None}, self.context.encoding_limits).decode('utf-8')}]
        latest_states = {}; lineage = []
        for step in range(self.step_limit):
            result = self.provider.call(work, messages, tools(bundle['tool']), evidence)
            require(len(result['actions']) == 1, 'one bounded analysis action per response')
            action = result['actions'][0]; lineage.append({'request': result['request_pin'], 'response': result['response_pin']})
            require(action['name'] in ('run_python', 'fit_helper', 'finish'), 'only current-context source actions')
            if action['name'] == 'finish':
                fields(action['arguments'], ('source',))
                source = self.source(action['arguments']['source'], work)
                return source, latest_states, lineage
            helper = None
            if action['name'] == 'fit_helper':
                require(bundle['tool'] == 'fit-helper', 'packaged helper exists only in its selected arm')
                fields(action['arguments'], ('request',)); helper = action['arguments']['request']
            else:
                fields(action['arguments'], ('source',)); source = self.source(action['arguments']['source'], work)
            transient = self.seal(bundle['id'] + '-analysis-%d-%d' % (self.serial, step), bundle['policy_id'],
                                  'query_final' if query is not None else ('report' if phase == 'report' else 'training_final'),
                                  source, self.input_state_pins(view), lineage)
            observed = self.execute(bundle, 'inspect', source, transient['evidence'], view, evidence,
                                    query=query, exploratory=True, helper=helper, context_phase=phase)
            latest_states = self.promote_states(observed)
            view, evidence = self.view(bundle, phase, query, {**sealed['states'], **latest_states}, observed['context'])
            # Actual source-produced analysis only; no protected scores, other
            # bundle state or previous held-query transcript is appended.
            messages.append({'role': 'assistant', 'content': result['analysis'], 'tool_calls': [
                {'id': action['id'], 'type': 'function', 'function': {'name': action['name'],
                 'arguments': canonical(action['arguments'], self.context.encoding_limits).decode('utf-8')}}]})
            messages.append({'role': 'tool', 'tool_call_id': action['id'],
                             'content': canonical(observed['output']['payload'], self.context.encoding_limits).decode('utf-8')})
        raise ValueError('complete phase investigation did not finish within selected ceiling')

    def prepare_report(self, bundle):
        from n079_products import write_index, read_index
        from n079_composition import relative
        prefix = self.context.report_observer.request('bundle_budget_prefix', {'bundle_id': bundle['id']})
        cost = write_index(self.context, self.report_builder.output_fd, prefix, 'controller',
                           'pre-report-cost-%d.json' % len(self.report_evidence))
        self.report_builder.repository.register(cost)
        evidence = self.report_builder.prepare(self, bundle, [cost]); self.report_evidence[bundle['id']] = evidence
        material_name = 'report-metadata-' + self.selected['public_bundles'][bundle['id']]['alias']
        body = {'bundle_id': bundle['id'], 'object': evidence['public'], 'material_name': material_name,
                'relative_path': relative(self.context.report_material_root,
                    self.context.report_output_path + '/' + evidence['public']['path'])}
        registered = self.supervisor.request('register_report_material', body)
        require(registered['descriptor'] == {'path': material_name, **{k: evidence['public'][k] for k in ('bytes', 'sha256')}},
                'actual independently issued sanitized report material')
        self.report_materials[bundle['id']] = registered['descriptor']
        self.report_public[bundle['id']] = read_index(self.context, self.report_builder.repository, evidence['public'], 'controller')

    def run_candidates(self):
        require(set(self.programs) == {p['id'] for p in policies()}, 'all12 sealed global sources')
        for bundle in bundles():
            policy = self.programs[bundle['policy_id']]; source = policy['source']
            view, evidence = self.view(bundle, 'training', None, {})
            self.provider.numeric_exposure(bundle['id'], identity(view, self.context.encoding_limits), evidence)
            state = {}; lineage = []
            if bundle['mode'] == 'I':
                source, state, lineage = self.investigate(bundle, 'training', source, policy, view, evidence)
                view, evidence = self.view(bundle, 'training', None, state)
            prefit = self.seal(bundle['id'] + '-training-source', bundle['policy_id'], 'training_final',
                               source, self.input_state_pins(view), lineage)
            observed = self.execute(bundle, 'training', source, prefit['evidence'], view, evidence)
            states = self.promote_states(observed)
            fitted = self.seal(bundle['id'], bundle['policy_id'], 'training_final', source,
                               {k: {x: v[x] for x in ('bytes', 'sha256')} for k, v in states.items()},
                               {'training_job': observed['context'], 'closure': observed['closure'], 'analysis': lineage})
            fitted['states'] = states; self.fitted[bundle['id']] = fitted; self.queries[bundle['id']] = {}
            for query in QUERY:
                view, evidence = self.view(bundle, 'query', query, states)
                qsource = source; qstates = {}; qlineage = []
                if bundle['mode'] == 'I':
                    qsource, qstates, qlineage = self.investigate(bundle, 'query', source, fitted, view, evidence, query=query)
                    view, evidence = self.view(bundle, 'query', query, {**states, **qstates})
                qseal = self.seal(bundle['id'] + '-q%d' % query, bundle['policy_id'], 'query_final',
                                  qsource, self.input_state_pins(view), qlineage)
                observed = self.execute(bundle, 'query', qsource, qseal['evidence'], view, evidence, query=query)
                payload = observed['output']['payload']; fields(payload, ('prediction', 'shape', 'dtype'))
                require(payload['shape'] == [6, 127, 1800] and payload['dtype'] == '<f8' and
                        payload['prediction']['bytes'] == 6 * Q * 8 and payload['prediction'] in observed['inventory'], 'full observed current-query prediction')
                promoted = self.supervisor.promote(observed['context'], payload['prediction']['path'], observed['context'] + '-prediction')
                self.queries[bundle['id']][query] = {'prediction': promoted, 'closure': observed['closure'],
                                                  'source_seal': qseal, 'view_evidence': evidence, 'job': observed['context']}
            self.prepare_report(bundle)
            view, evidence = self.view(bundle, 'report', None, states)
            rsource = source
            if bundle['mode'] == 'I':
                rsource, rstates, _ = self.investigate(bundle, 'report', source, fitted, view, evidence)
                view, evidence = self.view(bundle, 'report', None, {**states, **rstates})
            rseal = self.seal(bundle['id'] + '-report-source', bundle['policy_id'], 'report', rsource, self.input_state_pins(view),
                              {'prediction_jobs': [self.queries[bundle['id']][q]['job'] for q in QUERY]})
            observed = self.execute(bundle, 'report', rsource, rseal['evidence'], view, evidence)
            self.reports[bundle['id']] = {'report': observed['output']['payload'], 'job': observed['context'],
                                          'closure': observed['closure'], 'source_seal': rseal}
        return {'schema': 'n079_complete_candidate_programme_v1', 'programs': self.programs, 'fitted': self.fitted,
                'queries': self.queries, 'reports': self.reports, 'all_actual_jobs': self.jobs, 'report_evidence': self.report_evidence,
                'counts': {'bundles': 36, 'queries': 3672, 'reports': 36, 'person_video_predictions': 22032}}
