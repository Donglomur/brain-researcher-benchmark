"""Metadata-only composition of actual complete producer returns.

This module never fits a model, reads a numeric array, supplies a completed
score, or admits its own proposal. The independent outer process observes the
written proposal/input index and the protected FileAuthority installs exact K.
"""
import os
from pathlib import PurePosixPath
from ach_resource_common import bounded_decode
from n079_common import require, fields, identity, checked_pin, descriptor, canonical, close_all
from n079_observer import open_directory
from n079_plan import PERSONS, TRAIN, QUERY, Q, bundles, native_jobs, admit_study_metadata
from n079_role_binding import role_map, bind_identity_slots, validate_identity_slots, binding_contract
from n079_outer_common import configuration_projection

ROLE_ORDER = ('observer', 'issuer', 'supervisor', 'provider', 'features', 'assembler',
              'grams', 'references', 'controller', 'grader')
ONE_SHOTS = frozenset(ROLE_ORDER[4:])


def release_sequence(role):
    """One blocked-roster exchange, releases, and one ack per prior producer."""
    require(role in ROLE_ORDER, 'source-owned complete outer role')
    before = ROLE_ORDER[:ROLE_ORDER.index(role)]
    return 2 + len(before) + sum(r in ONE_SHOTS for r in before)


def object_pin(value):
    return {k: value[k] for k in ('bytes', 'sha256')}


def relative(root, path):
    a, b = PurePosixPath(root), PurePosixPath(path)
    require(a.is_absolute() and b.is_absolute() and str(a) == root and str(b) == path and
            '..' not in a.parts and '..' not in b.parts and a in b.parents,
            'actual object under selected canonical common material root')
    return str(b.relative_to(a))


def validate_observations(observations, source_pin, encoding):
    require(type(observations) is dict and set(observations) <= set(ONE_SHOTS), 'only actual completed producer observations')
    for role, row in observations.items():
        require(row['schema'] == 'n079_outer_actual_role_observation_v1' and row['role'] == role and
                row['source_pin'] == source_pin and row['wait']['natural_zero'] is True and
                row['wait']['code'] == os.CLD_EXITED and row['wait']['status'] == 0 and
                row['wait']['popen_returncode'] == 0 and row['terminal']['status'] == 'complete',
                'actual full source/wait/terminal producer observation')
        require(set(row['streams']) == {role + '/stdout', role + '/stderr'} and
                all(s['eof'] is True and s['durable'] is True and s['bytes'] == s['retained_bytes'] and
                    s['sha256'] == s['retained_sha256'] for s in row['streams'].values()),
                'both whole retained streams, including ordinary empty stderr')
        require(row['index']['descriptor'] == row['terminal']['result']['index'], 'actual return/index descriptor join')
        products = row['products']; require(len({p['path'] for p in products}) == len(products), 'unique complete output inventory')
        require(any({k: p[k] for k in ('path', 'bytes', 'sha256')} == row['index']['descriptor'] for p in products),
                'ordinary output inventory includes the returned index')
        # The observed raw cgroup.events bodies and their original clocks stay
        # in this record. Source-owned outer reader validates populated=0.
        require('population_before' in row and 'population_after' in row, 'actual before/after producer quiescence records')
        identity(row, encoding)


class MetadataBuilder:
    def __init__(self, configuration, io, finalizer_admission, *, outer_bindings):
        fields(configuration, ('schema', 'source_pin', 'study', 'role_templates', 'material_root',
            'proposal_root', 'output_roots', 'producer_payloads', 'candidate_selection', 'native_selection',
            'grader_selection', 'independent_numeric', 'source_admission_pin', 'original_clock_pin', 'report_builder_limits', 'report_result'))
        require(configuration['schema'] == 'n079_complete_metadata_composition_v1', 'complete fixed metadata composition')
        checked_pin(configuration['source_pin']); checked_pin(configuration['source_admission_pin'])
        checked_pin(configuration['original_clock_pin']); descriptor(configuration['independent_numeric'])
        require(set(configuration['role_templates']) == set(ROLE_ORDER), 'all ten immutable role templates')
        require(set(configuration['output_roots']) == set(ONE_SHOTS), 'all six actual owned producer roots')
        candidate = configuration['candidate_selection']
        issuer = configuration['role_templates']['issuer']['role_payload']
        supervisor = configuration['role_templates']['supervisor']['role_payload']
        require(issuer['worker_sources'] == candidate['worker_sources'] and
                issuer['common_materials'] == candidate['common_materials'],
                'controller and independent issuer select the same per-tool source and information sets')
        pins = {tool: {role: {name: row['pin'] for name,row in files.items()} for role,files in roles.items()}
                for tool,roles in candidate['worker_sources'].items()}
        pins['native'] = {name: row['pin'] for name,row in configuration['native_selection']['worker_sources'].items()}
        require(supervisor['worker_sources'] == pins, 'actual backend enforces exactly the admitted candidate/native source pins')
        commands = {**candidate['role_commands'], 'native': configuration['native_selection']['role_command']}
        require(supervisor['role_commands'] == issuer['role_commands'] == commands,
                'actual controller, independent issuer and concrete backend agree on complete role commands')
        fields(outer_bindings, ('budget_transport', 'output_roots'))
        require(set(outer_bindings['output_roots']) == set(ONE_SHOTS), 'all actual outer product roots')
        for role, root in outer_bindings['output_roots'].items():
            fields(root, ('path', 'identity', 'index_result_key', 'maximum_files', 'maximum_bytes'))
            reference = {k: root[k] for k in ('path', 'identity')}
            require(configuration['output_roots'][role] == reference and
                    configuration['role_templates'][role]['output'] == reference and
                    issuer['outer_authority']['output_roots'][role] == reference,
                    'all six immutable product roots share explicit references and preserve outer caps')
        self.finalizer_admission = finalizer_admission
        self.outer_bindings = outer_bindings
        self.cfg, self.io, self.encoding = configuration, io, io.encoding
        self.parts = admit_study_metadata(configuration['study'])
        self.source = configuration['source_pin']; self.study_pin = identity(configuration['study'], self.encoding)
        report_result = configuration['report_result']
        require(report_result['source_pin'] == self.source and report_result['study_pin'] == self.study_pin and
                report_result['controller_root'] == configuration['output_roots']['controller'] and
                report_result['grader_root'] == configuration['output_roots']['grader'] and
                report_result['bundle_ids'] == [row['id'] for row in bundles()],
                'complete originally selected additive report study/source/roots/roster')
        self.coordinate_pin = identity({'channels': configuration['study']['channels'],
            'times': configuration['study']['times'], 'order': 'channel-time'}, self.encoding)
        require(configuration['source_admission_pin'] == configuration['role_templates']['grader']['context']['profile']['source_environment_pin'],
                'source admission component is the exact earlier independent source-environment receipt')
        require(configuration['original_clock_pin'] == identity(configuration['role_templates']['grader']['context']['clock'], self.encoding),
                'same original clock commitment')
        self.serial = 0; self.catalog = {}; self.observations = {}; self.written = []

    def copy(self, value):
        return bounded_decode(canonical(value, self.encoding), self.encoding)

    def write(self, name, value):
        root = self.cfg['proposal_root']; fields(root, ('path', 'identity'))
        raw = canonical(value, self.encoding); fd = None; first = None
        try:
            fd = open_directory(root['path']); st = os.fstat(fd)
            require({'device': st.st_dev, 'inode': st.st_ino} == root['identity'], 'same admitted existing proposal directory')
            item = self.io.write(fd, name, raw, 'scientific')
            path = root['path'] + '/' + item['path']
            # Fresh full ordinary identity after write; outer independently
            # repeats the proposal and grade-index join before release.
            require(self.io.read(path, object_pin(item), 'scientific') == raw, 'complete durable proposal reread')
            result = {'path': 'composition/' + name, **object_pin(item)}
            self.catalog[result['path']] = {'relative_path': relative(self.cfg['material_root'], path),
                'pin': object_pin(item), 'immutable_admission': object_pin(item)}
            self.written.append({'descriptor': result, 'absolute_path': path})
            return result
        except BaseException as error:
            first = error; error.n079_prefix = {'written_metadata': self.written, 'active_name': name}; raise
        finally:
            close_all([] if fd is None else [('metadata proposal directory', lambda: os.close(fd))], first)

    def product(self, role, item):
        descriptor(item); require(role in self.observations, 'observed producer before material relocation')
        rows = [p for p in self.observations[role]['products'] if p['path'] == item['path']]
        require(len(rows) == 1 and object_pin(rows[0]) == object_pin(item), 'actual exact ordinary output body')
        name = role + '/' + item['path']
        root = self.cfg['output_roots'][role]['path']
        entry = {'relative_path': relative(self.cfg['material_root'], root + '/' + item['path']),
                 'pin': object_pin(item), 'immutable_admission': identity(self.observations[role], self.encoding)}
        require(name not in self.catalog or self.catalog[name] == entry, 'same unshadowed observed material alias')
        self.catalog[name] = entry
        return {'path': name, **object_pin(item)}

    def relocate(self, role, value):
        # Only exact Object schemas are paths. Pins and scientific row/source
        # identities remain byte-for-byte values; no arbitrary string rewrite.
        if type(value) is dict:
            if set(value) == {'path', 'bytes', 'sha256'}:
                return self.product(role, value)
            return {k: self.relocate(role, v) for k, v in value.items()}
        if type(value) is list:
            return [self.relocate(role, v) for v in value]
        return value

    def index(self, role, item=None):
        observed = self.observations[role]
        item = observed['index']['descriptor'] if item is None else item
        self.product(role, item)
        raw = self.io.read(self.cfg['output_roots'][role]['path'] + '/' + item['path'], object_pin(item), 'scientific')
        body = bounded_decode(raw, self.encoding)
        if item == observed['index']['descriptor']:
            require(body == observed['index']['body'], 'fresh exact actual outer observed metadata body')
        return body

    def input_index(self, role, payload):
        return self.write(role + '-INPUT.json', {'schema': 'n079_complete_producer_input_v1',
            'source_pin': self.source, 'study_pin': self.study_pin, 'payload': payload})

    def grade_index(self):
        require(set(self.observations) == {'features', 'assembler', 'grams', 'references', 'controller'},
                'complete actually observed pre-grade producer graph')
        prep = self.index('assembler'); refs = self.index('references')['result']; ctl = self.index('controller')
        candidates = self.index('controller', ctl['candidate_index']); native = self.index('controller', ctl['native_index'])
        require(prep['study_pin'] == ctl['study_pin'] == self.study_pin and
                refs['counts']['completed_target_fits'] == 5496 and refs['counts']['spectra'] == 36 and
                refs['counts']['setting_factors'] == 546, 'full actual producer programme before metadata composition')
        graph_pin = identity(self.observations, self.encoding)
        rows = []
        require({r['id'] for r in candidates['consolidated']} == {b['id'] for b in bundles()}, 'all36 actual consolidated bundles')
        for row in candidates['consolidated']:
            fit, report = row['fit_record'], row['report_record']
            require(fit['body']['phase'] == 'training_final' and len(row['queries']) == 102, 'actual fitted and query record scope')
            rows.append({'id': row['id'], 'observed_record_pin': identity(row, self.encoding),
                'seal_pin': fit['evidence'], 'closure_pin': identity(self.observations['controller'], self.encoding),
                'report': {'object': self.product('controller', row['report_object']),
                    'seal_pin': report['source_seal']['evidence'], 'observed_record_pin': report['closure']},
                'queries': [{'video_id': q['video_id'], 'record_pin': identity(q['record'], self.encoding),
                             'closure_pin': q['record']['closure']} for q in row['queries']],
                'predictions': self.relocate('controller', row['predictions'])})
        inners, finals = [], []
        for record in refs['records']:
            person, signal, family = record['key'].split('/'); partition = record['partition']
            require(record['columns'] == Q and record['target_source']['partition'] == partition['id'], 'complete source-bound fit record')
            shared = {'prepared': refs['shared_states'][partition['id']]['prepared'],
                      'factor': refs['shared_states'][partition['id']]['factors'][family + '/' + record['setting']['id']]}
            require(record['shared_state_pin'] == identity(shared, self.encoding), 'actual complete shared factor lineage')
            common = {'person': person, 'signal': signal, 'family': family, 'setting': record['setting'],
                'job_id': record['id'], 'fit_record_pin': identity(record, self.encoding),
                'state_manifest_pin': identity({'shared': shared, 'target_blocks': record['blocks']}, self.encoding),
                'fit_rows_pin': identity(partition['train'], self.encoding)}
            if record['fold'] is None:
                finals.append({**common, 'selection_record_pin': identity(refs['selections'][record['key']], self.encoding),
                    'prediction': self.relocate('references', record['prediction_or_metric'])})
            else:
                inners.append({**common, 'fold': record['fold'],
                    'prediction_commitment': identity(record['blocks'], self.encoding),
                    'metric_observation_pin': identity({'process': self.observations['references'],
                        'object': record['prediction_or_metric']['object']}, self.encoding),
                    'metric_source_pin': self.cfg['role_templates']['references']['numeric_source_pins']['r2'],
                    'validation_rows_pin': identity(partition['other'], self.encoding),
                    'metrics': self.relocate('references', record['prediction_or_metric'])})
        means = []
        for person in PERSONS:
            for signal in ('measured', 'mismatch'):
                key = person + '/' + signal
                means.append({'person': person, 'signal': signal,
                    'training_state_pin': identity(refs['mean_states'][key], self.encoding),
                    'observed_record_pin': identity(self.observations['references'], self.encoding),
                    'fit_rows_pin': identity(list(TRAIN), self.encoding),
                    'prediction': self.relocate('references', refs['baselines'][key + '/mean'])})
        targets = []
        for person in PERSONS:
            moments = [r for r in prep['moment_evidence'] if r['person'] == person and r['partition'] == 'final']
            require(len(moments) == 1, 'one actual complete fit-only final session transformation per person')
            targets.append({'person': person, 'fit': self.relocate('assembler', prep['fit_targets'][person]),
                'query': self.relocate('assembler', prep['query_targets'][person]),
                'transform_pin': identity(moments[0], self.encoding),
                'observed_record_pin': identity(self.observations['assembler'], self.encoding)})
        native_rows = []
        require({r['job'] for r in native['jobs']} == {r['id'] for r in native_jobs()}, 'all22 actual native captures')
        for row in native['jobs']:
            outcomes = {k: v for k, v in native['comparison']['outcomes'].items() if k.startswith(row['job'] + '/')}
            require(outcomes and all(v['capture_complete'] and v['status'] in ('match', 'mismatch', 'undefined_nonfinite')
                    for v in outcomes.values()), 'complete native evidence; genuine undefined is an outcome')
            undefined = any(v['status'] == 'undefined_nonfinite' for v in outcomes.values())
            mismatch = any(v['status'] == 'mismatch' for v in outcomes.values())
            policies = {k: native['comparison_policy_evidence'][k] for k in outcomes}
            native_rows.append({'id': row['job'], 'outcome': 'captured_undefined_nonfinite' if undefined else
                ('captured_mismatch' if mismatch else 'captured_match'), 'source_pin': self.source,
                'observed_record_pin': identity(row, self.encoding), 'closure_pin': row['closure'],
                'output_manifest_pin': row['index'], 'comparison_evidence_pin': identity(outcomes, self.encoding),
                'comparison_policy_pin': identity(policies, self.encoding),
                'undefined_reason': 'Original captured quantity nonfinite under its independently admitted policy; exact per-quantity record retained.' if undefined else None})
        allocation_pin = identity(self.cfg['role_templates']['grader']['context']['allocation'], self.encoding)
        return {'schema': 'n079_protected_grade_index_v1', 'task': 'NEURAL-079', 'study_pin': self.study_pin,
            'source_closure_pin': self.source, 'observation_pin': graph_pin, 'allocation_pin': allocation_pin,
            'coordinate_pin': self.coordinate_pin, 'query_rows_pin': identity(list(QUERY), self.encoding),
            'fit_rows_pin': identity(list(TRAIN), self.encoding),
            'metric_rows_pin': identity(['independent-inner-Pearson'], self.encoding), 'channels': self.cfg['study']['channels'],
            'partitions': [{'fold': p['fold'], 'fit_rows_pin': identity(p['train'], self.encoding),
                            'validation_rows_pin': identity(p['other'], self.encoding)} for p in self.parts[:-1]],
            'candidates': rows, 'reference_inner': inners, 'reference_final': finals, 'means': means,
            'targets': targets, 'native': native_rows,
            'closure': {'controller_pin': identity(self.observations['controller'], self.encoding),
                'reference_pin': identity(self.observations['references'], self.encoding),
                'native_pin': object_pin(ctl['native_index']), 'preparation_pin': identity(self.observations['assembler'], self.encoding),
                'feature_pin': identity(self.observations['features'], self.encoding),
                'reports_pin': identity([r['report'] for r in rows], self.encoding),
                'observer_closeout_pin': graph_pin, 'source_admission_pin': self.cfg['source_admission_pin'],
                'original_clock_pin': self.cfg['original_clock_pin'], 'complete_input_observation_pin': graph_pin}}

    def report_inputs(self, preparation, public):
        from n079_plan import NODES
        coordinate = self.write('report-coordinate-manifest.json', {'channels': self.cfg['study']['channels'],
            'times': self.cfg['study']['times'], 'order': 'channel-time'})
        fit_rows = self.write('report-fit-row-manifest.json', {'video_ids': list(TRAIN)})
        feature = self.write('report-feature-manifest.json', {'outputs': self.cfg['study']['feature_outputs'],
            'source': self.cfg['study']['feature_source'], 'weights': self.cfg['study']['feature_weights'],
            'actual_observation': identity(self.observations['features'], self.encoding)})
        choices = {}
        for bundle in bundles():
            row = public[bundle['id']]; training = row['public_metadata']['training']
            supports = {}
            for person in PERSONS:
                backing = {'schema': 'n079_observed_public_person_support_v1', 'bundle_alias': row['alias'], 'person': person,
                    'trial_arrays': [r for r in training['trial_arrays'] if r['person'] == person],
                    'mean_arrays': [r for r in training['mean_arrays'] if r['person'] == person],
                    'actual_preparation_observation': identity(self.observations['assembler'], self.encoding)}
                supports[person] = [self.write('report-' + row['alias'] + '-' + person + '-support.json', backing)]
            facts = {'schema': 'n079_report_public_input_facts_v1', 'bundle_alias': row['alias'],
                'persons': list(PERSONS), 'training_people': list(PERSONS), 'query_people': list(PERSONS),
                'train_videos': list(TRAIN), 'query_videos': list(QUERY), 'query_shape': [6,127,1800],
                'support': {'people': 6, 'sessions': 48, 'channels': 127, 'time_samples': 1800,
                    'train_videos': 1000, 'query_videos': 102, 'status': 'complete', 'failure_record_ids': []},
                'person_support': supports, 'person_failures': {p: [] for p in PERSONS},
                'feature_manifest': feature, 'feature_output_ids': list(NODES), 'coordinate_manifest': coordinate,
                'fit_row_manifests': [fit_rows], 'held_target_access': 'none', 'source_pin': self.source,
                'observation_pin': identity(self.observations['assembler'], self.encoding)}
            # Support is the actually completed benchmark's full scientific
            # cohort/grid. Neural support exposed to this particular arm is
            # separately visible in its source-owned public training record.
            choices[bundle['id']] = {'alias': row['alias'], 'public_input': self.write('report-' + row['alias'] + '-input.json', facts),
                                    'semantic_records': []}
        return {'schema': 'n079_report_evidence_selection_v1', 'study_pin': self.study_pin, 'source_pin': self.source,
                'work_id': 'controller', 'limits': self.cfg['report_builder_limits'], 'bundles': choices}

    def propose(self, role, observations, blocked_roles, baseline):
        require(role == ROLE_ORDER[self.serial], 'one complete source-owned release order')
        validate_observations(observations, self.source, self.encoding)
        expected = {r for r in ROLE_ORDER[:self.serial] if r in ONE_SHOTS}
        require(set(observations) == expected, 'all and only actual preceding complete producer returns')
        self.observations = observations
        H = role_map(self.finalizer_admission, blocked_roles)
        config = bind_identity_slots(role, self.cfg['role_templates'][role], self.cfg['role_templates'],
                                     self.outer_bindings['budget_transport'], H)
        self.catalog = dict(config['repository']['catalog']) if config['repository'] else {}
        require(config['context']['role'] == role and config['context']['effect_admission']['study_pin'] == self.study_pin,
                'same exact selected immutable role/study template')
        if role == 'observer':
            config['role_payload']['baseline'] = baseline
            config['role_payload']['baseline_admission'] = identity(baseline, self.encoding)
        elif role == 'features':
            payload = self.copy(self.cfg['producer_payloads']['features'])
            originals = {v['id']: v for v in self.cfg['study']['videos']}
            require([v['id'] for v in payload['videos']] == list(range(1, 1103)) and all(
                v['object'] == originals[v['id']]['object'] and v['decoder_pin'] == originals[v['id']]['decoder_pin']
                for v in payload['videos']), 'complete authentic video/decoder identity manifest')
            require(object_pin(payload['selection']['weights']) == self.cfg['study']['feature_weights'] and
                    payload['selection']['source_pin'] == self.cfg['study']['feature_source'], 'same full authenticated visual source/weights')
            config['role_payload'] = {'input_index': self.input_index(role, payload)}
        elif role in ('assembler', 'grams'):
            raw_features = self.product('features', self.index('features')['array']['object'])
            array = {**self.index('features')['array'], 'object': raw_features}
            payload = self.copy(self.cfg['producer_payloads'][role]); payload['study'] = self.cfg['study']; payload['raw_features'] = array
            config['role_payload'] = {'input_index': self.input_index(role, payload)}
        elif role == 'references':
            prep = self.index('assembler'); grams = self.index('grams')
            # Only fitting/inner targets are exposed to this source route.
            reference_prep = {'study_pin': self.study_pin, 'reference_targets': self.relocate('assembler', prep['reference_targets'])}
            reference_grams = {'study_pin': self.study_pin, 'partitions': grams['partitions'], 'grams': self.relocate('grams', grams['grams'])}
            prep_descriptor = self.write('reference-preparation.json', reference_prep)
            gram_descriptor = self.write('reference-grams.json', reference_grams)
            config['role_payload'] = {'input_index': self.input_index(role, {'preparation_index': prep_descriptor, 'gram_index': gram_descriptor})}
        elif role == 'controller':
            require(self.cfg['native_selection']['program_selection']['variant'] == 'literal_cpu',
                    'complete current typed-resource route admits CPU native only; corrected GPU remains separately unqualified')
            prep = self.index('assembler'); public = self.relocate('assembler', prep['public_bundles'])
            candidate = self.copy(self.cfg['candidate_selection']); candidate['public_bundles'] = public
            # Replaced with actual issued export evidence at controller entry;
            # this preliminary pin is only an already observed source record.
            for row in public.values():
                row['public_export_evidence'] = identity(self.observations['assembler'], self.encoding)
            config['role_payload'] = {'candidate': candidate, 'native': self.copy(self.cfg['native_selection']),
                'coordinate_pin': self.coordinate_pin, 'consolidation_block': config['coordinate_block'],
                'consolidation_max_open_files': self.cfg['candidate_selection']['consolidation_max_open_files'],
                'report': self.report_inputs(prep, public)}
            del candidate['consolidation_max_open_files']
        elif role == 'grader':
            index = self.write('GRADE_INPUT.json', self.grade_index())
            selection = self.copy(self.cfg['grader_selection'])
            graph_pin = identity(observations, self.encoding)
            selection.update(index=index, study_pin=self.study_pin, grader_source_pin=self.source, source_closure_pin=self.source,
                observation_pin=graph_pin, allocation_pin=identity(config['context']['allocation'], self.encoding),
                independent_numeric=self.cfg['independent_numeric'], index_observation_pin=identity({
                    'schema': 'n079_fresh_grade_input_observation_v1', 'index': index, 'source_pin': self.source,
                    'input_graph_pin': graph_pin}, self.encoding))
            from n079_budget import allocation
            grade_budget = allocation(config['context']['allocation'])['rows']['target-last-grader']
            require(grade_budget['numeric_block_applications'] >= selection['capacity']['max_numeric_block_applications'] and
                    grade_budget['write_bytes'] >= selection['capacity']['max_output_payload_bytes'] and
                    grade_budget['data_read_bytes'] >= selection['capacity']['max_array_payload_read_bytes'],
                    'actual complete grader resource capacities backed by the charged whole/local allocation')
            config['role_payload'] = {'selection': selection, 'numeric_source': self.cfg['independent_numeric'], 'input_index': index}
        if config['repository'] is not None:
            require(config['repository']['root'] == self.cfg['material_root'], 'same admitted physical material-root interpretation')
            config['repository']['catalog'] = dict(self.catalog)
            # Freeze the candidate catalogue before protocol publications append
            # to self.catalog; the identity-binding object cannot name itself.
        validate_identity_slots(role, config, self.cfg['role_templates'], self.outer_bindings['budget_transport'], H)
        binding = {'schema': 'n079_actual_role_identity_binding_v1',
            'contract_pin': identity(binding_contract(), self.encoding), 'effective_source_pin': self.source,
            'static_role_template_pin': identity(self.cfg['role_templates'][role], self.encoding),
            'original_clock_pin': self.cfg['original_clock_pin'], 'H': H, 'H_pin': identity(H, self.encoding),
            'baseline_pin': identity(baseline, self.encoding),
            'previous_observations_pin': identity(observations, self.encoding),
            'derived_configuration_projection_pin': identity(configuration_projection(config, self.encoding), self.encoding)}
        binding_item = self.write('%02d-%s-IDENTITY-BINDING.json' % (self.serial, role), binding)
        binding_descriptor = {'path': self.cfg['proposal_root']['path'] + '/' + binding_item['path'].split('/')[-1],
                              'pin': object_pin(binding_item)}
        proposal = {'schema': 'n079_role_configuration_proposal_v2', 'role': role, 'source_pin': self.source,
            'identity_binding': binding_descriptor,
            'baseline_pin': identity(baseline, self.encoding), 'observations_pin': identity(observations, self.encoding),
            'blocked_identity_pin': identity(blocked_roles[role]['initial_identity'], self.encoding), 'configuration': config}
        item = self.write('%02d-%s-PROPOSAL.json' % (self.serial, role), proposal)
        self.serial += 1
        return {'path': self.cfg['proposal_root']['path'] + '/' + item['path'].split('/')[-1], 'pin': object_pin(item)}
