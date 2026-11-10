"""Complete NEURAL066 controller. Entry is root-authorized future operation only.

No provider, model, numeric reader or worker starts at import. Every external
attempt has one original cutoff and concrete independently observed closure.
"""
import failures
import argparse
import copy
import os
from pathlib import Path
import sys
import time
if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import CONDITIONS, MODES, R2_ARMS, cases, expected_counts, encoded, identity, need, roster, no_science_promotion
from safe_io import capture, child, pin, strict, durable_new
from budget import Budget
from workspace import Workspace, descriptor
from operation import admit
from transport.worker import Native, file_mount
from assembly import relative, public_view, candidate_bindings, model_bindings, output_metadata
import preparation
import operator_policy

def failure(exc):
    return {'type': failures.kind(exc), 'message': failures.describe(exc), 'notes': list(failures.evidence(exc, '__notes__', [])), 'read_capture': failures.evidence(exc, 'capture_observation', None), 'unadmitted_provider_failure': failures.evidence(exc, 'neural066_provider_failure', None), 'known_provider_close': failures.evidence(exc, 'neural066_provider_close', None), 'secondary_failure_evidence': failures.evidence(exc, 'neural066_secondary_failures', [])}

class Controller:

    def __init__(self, op, authority, root, budget, operation_pin, authority_pin, source_manifest_pin, child_limits_pin):
        self.op = copy.deepcopy(op)
        self.authority = copy.deepcopy(authority)
        self.root = Path(root)
        self.budget = budget
        self.ws = Workspace(root, budget, op['metadata'])
        self.operation_pin = operation_pin
        self.authority_pin = authority_pin
        self.source_manifest_pin = source_manifest_pin
        self.child_limits_pin = child_limits_pin
        self.rows = [{'job': j, 'status': 'not_started'} for j in roster()]
        self.active = None
        self.stopped = False
        self.unknown = False
        self.worker_closed_flags = {}
        self.model_closed_flags = {}
        self.model_started = False
        self.native = None
        self.projections = []
        self.projected = []
        self.case_captures = {}
        self.candidate_views = {}
        self.methods = {}
        self.models = {}
        self.inner = {}
        self.model_contexts = {}
        self.declarations = {}
        self.barrier = None
        self.predictions = {}
        self.expected = {}
        self.score_pins = {}
        self.reference_evidence = {}
        self.source_mounts = {}
        self.persistent = []
        self.current_mounts = []

    def role(self, job):
        return 'A' if job.get('mode') == MODES[0] else 'B'

    def phase_clock(self):
        return {'origin': self.budget.origin, 'deadline': min(self.budget.attempt['deadline'], self.budget.subattempt['deadline'] if self.budget.subattempt is not None else self.budget.end)}

    def profile(self, action):
        return self.op['phase_limits'][action]

    def document(self, path, d):
        return self.ws.read(path, d)

    def original(self, d):
        return descriptor(child(self.op['native_inputs']['root'], d['path']), d)

    def job_limits(self, action):
        p = self.profile(action)
        return {**p, 'json_bytes': self.op['metadata']['json_bytes'], 'output_bytes': p['output_bytes'], 'max_output_files': p['max_output_files']}

    def reserve_model(self, job, cfg):
        self.model_closed_flags[job['phase_id']] = False
        self.budget.reserve_producer('model-' + job['phase_id'], cfg['read_bytes'], cfg['write_bytes'], cfg['write_bytes'])

    def model_closed(self, job, value):
        need(value['all_native_resources_closed'] is True and value['finished'] <= self.budget.tick(), 'Independent current provider retirement')
        self.model_closed_flags[job['phase_id']] = True
        self.budget.event({'kind': 'model_closed', 'phase_id': job['phase_id'], 'closure': value})

    def record_model_failure(self, job, value):
        self.model_closed_flags[job['phase_id']] = value.get('custody') == 'closed'
        self.budget.event({'kind': 'model_failure', 'phase_id': job['phase_id'], 'returned_unadmitted_evidence': value})

    def run_worker(self, job, action, role, request, bindings, extra=None, profile=None, logical_id=None):
        if role == 'operator':
            need('membership_policy' not in request['inputs'] and 'MEMBERSHIP_POLICY.json' not in bindings, 'No substituted operator policy binding')
            bindings = {**bindings, 'MEMBERSHIP_POLICY.json': self.policy_binding}
            request = {**request, 'inputs': {**request['inputs'], 'membership_policy': relative(self.policy_binding, 'MEMBERSHIP_POLICY.json')},
                       'membership_policy_pin': {k:self.policy_binding[k] for k in ('bytes','sha256')}}
        p = profile or self.profile(job['action'])
        ident = logical_id or job['phase_id']
        mounts = {}
        owned = []
        self.budget.tick()
        need(len(encoded(request)) <= min(2097152, self.op['candidate']['request_bytes'] if role in ('A', 'B') else 2097152), 'Complete scientific job fits actual worker request reader')
        try:
            inp = self.ws.stage('mounts/' + ident + '/input', bindings, 'input')
            owned.append(inp)
            if action == 'native_project':
                # Metadata and original assets share /input without an
                # enclosing directory binding that would shadow descendants.
                inputs = {'/input/' + name: file_mount(child(inp['path'], name), d, 'input') for name, d in inp['files'].items()}
            else:
                inputs = {'/input': inp}
            extras = extra or {}
            need(not (set(self.source_mounts[role]) & set(inputs) or set(self.source_mounts[role]) & set(extras) or set(inputs) & set(extras)), 'No overwritten source/input/extra mount target')
            mounts = {**self.source_mounts[role], **inputs, **extras}
            self.current_mounts = owned
            resources = self.op['mechanical_limits'][action]
            need(resources['max_output_bytes'] >= request['limits']['output_bytes'] and resources['memory_bytes'] <= p['memory_bytes'], 'Exact complete output and enforced phase memory envelope')
            need(sum((resources[k] for k in ('setup_seconds', 'producer_seconds', 'capture_seconds', 'cleanup_seconds'))) <= self.phase_clock()['deadline'] - self.budget.tick(), 'Entire physical phase fits remaining original logical allowance')
            self.budget.reserve_producer(ident, p['producer_read_bytes'], p['producer_write_bytes'], p['producer_retained_bytes'])
            self.worker_closed_flags[ident] = False
            record = self.native.run(ident, action, role, request, mounts, self.phase_clock(), resources)
            self.ws.json('attempts/' + ident + '.json', record)
            need(record['status'] == 'captured', 'External failed or unadmitted custody; stop every later dispatch')
            self.worker_closed_flags[ident] = True
            self.budget.tick()
            for mount in owned:
                self.ws.retire(mount, True)
            self.current_mounts = []
            return record
        except BaseException:
            self.stopped = True
            if ident in self.worker_closed_flags and (not self.worker_closed_flags[ident]):
                self.unknown = True
            raise

    def candidate_request(self, job, action, submitted, recipe, realm):
        p = self.profile('candidate_fit' if action == 'candidate_fit' else 'candidate_infer' if action == 'candidate_infer' else 'candidate_author')
        limits = {**self.job_limits(job['action']), **self.op['candidate'], 'model_json_bytes': self.op['metadata']['json_bytes']}
        return {'schema': 'neural066_scientific_job_v1', 'action': action, 'role': self.role(job), 'case': self.candidate_views[job['slot'], job['mode'], job['condition']]['view']['case'], 'mode': job['mode'], 'condition': job['condition'], 'submitted': submitted, 'recipe': recipe, 'guest_duration_seconds': min(p['wall_seconds'], self.phase_clock()['deadline'] - self.budget.tick()), 'limits': limits, 'scope': {'other_cases': False, 'private_labels': False, 'query_access': realm != 'train', 'training_access': realm != 'query', 'fit_training_only': realm == 'train', 'preliminary_fitted_state': False, 'provider_after_seal': False}}

    def run_nested(self, job, number, request, bindings, source_bindings):
        ident = identity([job['phase_id'], 'shared-preliminary', number])
        p = self.op['tool_limits']
        self.budget.begin_subattempt(p['read_bytes'], p['write_bytes'], min(self.budget.attempt['deadline'], self.budget.tick() + p['wall_seconds']))
        try:
            source = self.ws.stage('mounts/' + ident + '/submitted', source_bindings, 'program')
            request['limits'] = {**request['limits'], **p, 'json_bytes': self.op['metadata']['json_bytes']}
            request['guest_duration_seconds'] = min(p['wall_seconds'], self.phase_clock()['deadline'] - self.budget.tick())
            record = self.run_worker(job, 'candidate_policy', self.role(job), request, bindings, {'/submitted': source}, p, ident)
            self.ws.retire(source, True)
            self.budget.end_subattempt()
            return record
        except BaseException:
            self.stopped = True
            self.budget.subattempt = None
            raise

    def source_admission(self, job):
        reservation = admit(self.op, self.authority, self.op['authority_root'],meter=self.budget)
        for role, files in self.op['sources_by_role'].items():
            bindings = {p: descriptor(child(self.op['source_root'], p), d) for p, d in files.items()}
            mount = self.ws.stage('sources/' + role, bindings, 'program' if role in ('A', 'B') else 'operator_reference')
            self.source_mounts[role] = {'/program': mount}
            self.persistent.append(mount)
        need(self.op['sources_by_role']['A'] == self.op['sources_by_role']['B'], 'Identical common tools/source across candidate modes')
        self.native = Native(self.op['native_transport'], self.budget)
        native = self.op['native_inputs']
        self.policy_binding = self.original(native['membership_policy'])
        self.membership_policy = operator_policy.validate(self.document(self.policy_binding['source_path'], self.policy_binding))
        need({k:self.policy_binding[k] for k in ('bytes','sha256')} == self.authority['reviewed_membership_policy'], 'Exact root-selected operator policy')
        co = self.original(native['cohort'])
        lo = self.original(native['logs'])
        cohort = self.document(co['source_path'], co)
        self.logs = self.document(lo['source_path'], lo)
        self.membership = preparation.validate_membership(cohort, self.logs, native['small_asset_pins'], self.membership_policy)
        self.case_by_slot = {c['slot']: c for c in self.membership['cases']}
        self.logs_binding = lo
        self.membership_binding = self.ws.json('private/MEMBERSHIP.json', self.membership)
        self.seed_binding = self.ws.json('private/OPAQUE_SEED_PROVENANCE.json', {'method': 'fresh operator random32 bytes, no query/label tuning', 'not_a_scientific_randomization': True})
        seed = os.urandom(32)
        need(len(seed) == 32, 'Complete operator namespace seed')
        sp = self.root / 'private' / 'OPAQUE_SEED.bin'
        sd = self.budget.save(sp, seed)
        self.seed_binding = descriptor(sp, sd)
        rawbindings = {name: descriptor(child(native['raw_root'], name), d) for name, d in self.membership['assets'].items()}
        self.originals = self.ws.stage('originals', rawbindings, 'input')
        self.persistent.append(self.originals)
        self.loader_binding = self.original(native['loader'])
        need({k: self.loader_binding[k] for k in ('bytes', 'sha256')} == self.membership_policy['asset_pins']['loader'], 'Original exact author trigger source')
        self.public_contract = self.document(self.op['public_contract']['path'], self.op['public_contract'])
        self.investigation_policy = self.document(self.op['investigation_policy']['path'], self.op['investigation_policy'])
        need(self.investigation_policy['schema'] == 'neural066_precommitted_investigation_policy_v1' and self.investigation_policy['hidden_target_conclusions'] == 'deferred' and (type(self.investigation_policy['estimand']) is str) and (type(self.investigation_policy['limitations']) is list), 'Precommitted declaration policy before any participant episode')
        self.language_policy = self.document(self.op['language_policy']['path'], self.op['language_policy'])
        need(self.language_policy == {'schema': 'neural066_fixed_language_policy_v1', 'laplace': 1, 'neural_weight': 0.5, 'language_only_weight': 1.0, 'emission_floor': 1e-12, 'tie': 'lowest_class_index', 'target_fit': False}, 'Exact prospective fixed language recipe')
        self.contrast_rows = self.document(self.op['contrasts']['path'], self.op['contrasts'])['records']
        self.gate_spec = self.document(self.op['gates']['path'], self.op['gates'])
        need(len(self.contrast_rows) == 164 and len(self.gate_spec['gates']) == 24, 'Complete adopted contrasts/gates')
        records = {preparation.key(r): r for r in self.logs['records'] if preparation.eligible(r, self.membership_policy)}
        targets = {c['slot']: {k: [v[3] for v in records[k]['keys']] for k in c['query_keys']} for c in self.membership['cases']}
        self.target_vault = self.ws.json('private/TARGET_VAULT.json', {'schema': 'neural066_preparer_target_vault_v1', 'targets': targets, 'access_scope': 'trusted_preparer_only_until_prescore_barrier', 'logs_pin': {k: lo[k] for k in ('bytes', 'sha256')}})
        del targets, records
        self.budget.event({'kind': 'protected_preparer_target_observation', 'source_logs': lo, 'vault': self.target_vault, 'scorer_target_reads': 0, 'does_not_claim_whole_operation_target_reads_zero': True})
        self.provider_mounts = copy.deepcopy(self.op['provider_mounts'])
        self.provider_profile = copy.deepcopy(self.op['provider_profile'])
        self.provider_models = copy.deepcopy(self.op['provider_models'])
        self.provider_admission = self.document(self.op['provider_admission']['path'], self.op['provider_admission'])
        self.reference_environment = copy.deepcopy(self.op['reference_environment'])
        env = self.reference_environment
        env['metadata'] = {p: self.budget.read_file(d['source_path'], {k: d[k] for k in ('bytes', 'sha256')}, self.op['metadata']['json_bytes']) for p, d in env['bindings'].items()}
        return {'reservation': reservation, 'membership': self.membership_binding, 'all_native_bodies_authenticated': True}

    def native_project(self, job):
        index = job['timeline_slot']
        record = self.membership['timelines'][index]
        records = [r for r in self.logs['records'] if (r['modality'], r['alias'], r['session'], r['task']) == (record['modality'], record['recording_alias'], record['session'], record['task'])]
        docs = {'record': record, 'records': records, 'assets': {p: self.membership['assets'][p] for p in record['raw_assets']}}
        bindings = {k + '.json': self.ws.json('native-input/' + str(index) + '/' + k + '.json', v) for k, v in docs.items()}
        bindings['loader.py'] = self.loader_binding
        inputs = {k: relative(bindings[k + '.json'], k + '.json') for k in docs}
        inputs['loader'] = relative(self.loader_binding, 'loader.py')
        extra = {'/input/originals/' + p: file_mount(child(self.originals['path'], p), self.membership['assets'][p], 'input') for p in record['raw_assets']}
        request = self.operator_request(job, inputs)
        request['native_originals'] = {p: self.membership['assets'][p] for p in record['raw_assets']}
        captured = self.run_worker(job, job['action'], 'operator', request, bindings, extra)
        self.projections.append(captured)
        self.projected.append(self.ws.result(captured))
        return {'capture': self.capture_pin(captured)}

    def operator_request(self, job, inputs):
        return {'schema': 'neural066_scientific_job_v1', 'action': job['action'], 'role': 'operator', 'inputs': inputs, 'mode': job.get('mode'), 'condition': job.get('condition'), 'limits': self.job_limits(job['action']), 'guest_duration_seconds': self.phase_clock()['deadline'] - self.budget.tick(), 'contracts': getattr(self, 'contracts', None)}

    def capture_pin(self, record):
        return {'logical_id': record['logical_id'], 'receipt_path': record['receipt_path'], 'receipt_pin': record['receipt_pin']}

    def membership_phase(self, job):
        bindings = {'membership.json': self.membership_binding, 'logs.json': self.logs_binding}
        ds = []
        for i, c in enumerate(self.projections):
            name = 'projection-' + str(i) + '.json'
            bindings[name] = self.ws.from_capture(c, 'RESULT.json')
            ds.append(relative(bindings[name], name))
        inputs = {'membership': relative(bindings['membership.json'], 'membership.json'), 'logs': relative(bindings['logs.json'], 'logs.json'), 'projections': ds}
        cap = self.run_worker(job, 'membership', 'operator', self.operator_request(job, inputs), bindings)
        self.joined = self.ws.result(cap)
        self.joined_binding = self.ws.from_capture(cap, 'RESULT.json')
        from shape import admit_actual_shapes
        self.shape = admit_actual_shapes(self.op, self.membership, self.logs, self.projected, self.joined, self.membership_policy)
        d = self.ws.json('private/PROJECTION_ANCESTRY.json', {'projections': [self.capture_pin(c) for c in self.projections], 'joined': self.joined_binding})
        self.contracts = {'source_contract_pin': self.source_manifest_pin, 'language_policy_pin': {k: self.op['language_policy'][k] for k in ('bytes', 'sha256')}, 'projection_pin': {k: d[k] for k in ('bytes', 'sha256')}}
        return {'capture': self.capture_pin(cap), 'shape': self.shape}

    def view_phase(self, job):
        case = self.case_by_slot[job['slot']]
        name = 'view-input/' + job['phase_id']
        bindings = {'case.json': self.ws.json(name + '/case.json', case), 'logs.json': self.logs_binding, 'joined.json': self.joined_binding, 'opaque.seed': self.seed_binding}
        ds = []
        roots = []
        for i, c in enumerate(self.projections):
            prefix = 'projection-' + str(i)
            roots.append(prefix)
            for relative_name in ('RESULT.json', 'TIMING.npy', 'EOG.npy', 'NEURAL_PRE.npy', 'NEURAL.npy', 'NEURAL_POST.npy'):
                bindings[prefix + '/' + relative_name] = self.ws.from_capture(c, relative_name)
            ds.append(relative(bindings[prefix + '/RESULT.json'], prefix + '/RESULT.json'))
        inputs = {'case': relative(bindings['case.json'], 'case.json'), 'logs': relative(bindings['logs.json'], 'logs.json'), 'joined': relative(bindings['joined.json'], 'joined.json'), 'projections': ds, 'projection_roots': roots, 'opaque_seed_path': 'opaque.seed'}
        cap = self.run_worker(job, job['action'], 'operator', self.operator_request(job, inputs), bindings)
        if job['action'] == 'case_plan':
            self.case_captures[job['slot']] = cap
        else:
            self.candidate_views[job['slot'], job['mode'], job['condition']] = public_view(self.ws, cap)
        return {'capture': self.capture_pin(cap)}

    def candidate_phase(self, job):
        key = (job['slot'], job['mode'], job['condition'])
        public = self.candidate_views[key]
        if job['action'] == 'candidate_author':
            from investigation import author
            self.methods[key] = author(self, job, public)
            return {'source_seal': self.methods[key]['source_seal'], 'recipe_seal': self.methods[key]['recipe_seal']}
        method = self.methods[key]
        realm = 'train' if job['action'] == 'candidate_fit' else 'query'
        data, _ = candidate_bindings(self.ws, public, realm, 'candidate-input/' + job['phase_id'])
        submitted = self.ws.stage('mounts/' + job['phase_id'] + '/submitted', method['bindings'], 'program')
        extras = {'/submitted': submitted}
        owned = [submitted]
        request = self.candidate_request(job, job['action'], method['submitted'], method['recipe'], realm)
        if realm == 'train':
            context = {**public['private']['context'], 'mode': job['mode'], 'support_commitment': public['view']['support_commitment'], 'source_seal': {k: method['source_seal'][k] for k in ('bytes', 'sha256')}, 'recipe_seal': {k: method['recipe_seal'][k] for k in ('bytes', 'sha256')}, 'original_fit_phase_id': job['phase_id']}
            self.model_contexts[key] = context
        context = self.model_contexts[key]
        request['model_context'] = context
        data['FIT_CONTEXT.json'] = self.ws.json('candidate-input/' + job['phase_id'] + '/FIT_CONTEXT.json', context)
        if realm == 'query':
            model_capture = self.models['candidate', *key]
            bindings, model = model_bindings(self.ws, model_capture, context, self.op['candidate']['model_bytes'])
            mount = self.ws.stage('mounts/' + job['phase_id'] + '/model', bindings, 'input')
            extras['/model'] = mount
            owned.append(mount)
            request['model_pin'] = {k: bindings['MODEL.json'][k] for k in ('bytes', 'sha256')}
            request['model_files'] = {name: {k: d[k] for k in ('bytes', 'sha256')} for name, d in bindings.items()}
        cap = self.run_worker(job, job['action'], self.role(job), request, data, extras)
        for mount in owned:
            self.ws.retire(mount, True)
        if realm == 'train':
            model_bindings(self.ws, cap, context, self.op['candidate']['model_bytes'])
            self.models['candidate', *key] = cap
        else:
            self.prediction(job, cap, public, 'candidate')
        return {'capture': self.capture_pin(cap)}

    def reference_phase(self, job):
        from reference.assembly import build_request
        base = self.case_captures[job['slot']]
        condition = 'NEURAL' if job['action'].startswith('r1') else job['condition']
        prefix = condition + '/'
        infer = job['action'].endswith('infer')
        names = [prefix + 'VIEW.json', prefix + ('INFER_VIEW.json' if infer else 'FIT_VIEW.json')]
        if job['action'] in ('r2_inner', 'r2_final'):
            names.append(prefix + 'REFERENCE_PLAN.json')
        case_capture = output_metadata(self.ws, base, names)
        public = public_view(self.ws, base, condition)
        action = job['action']
        group = 'r2' if action.startswith('r2') else 'r0' if action.startswith('r0') else 'r1'
        key = (group, job['slot'], job['condition'])
        kwargs = {}
        if action == 'r2_inner':
            kwargs.update(grid_index=job['grid'], cell=[job['cell'] // 3, job['cell'] % 3])
        if infer:
            kwargs['model_capture'] = output_metadata(self.ws, self.models[key], ['RESULT.json', 'MODEL.json'])
        if action == 'r2_final':
            kwargs['inner_captures'] = [output_metadata(self.ws, c, ['RESULT.json']) for c in self.inner[key]]
        p = self.profile(action)
        limits = {k: p[k] for k in ('read_bytes', 'write_bytes', 'array_bytes')}
        limits['json_bytes'] = self.op['metadata']['json_bytes']
        reference_request, bindings = build_request(action, public['private']['context'], case_capture, self.reference_environment, limits, self.op['reference_device'], **kwargs)
        request = {'schema': 'neural066_scientific_job_v1', 'action': action, 'role': 'reference', 'case': public['view']['case'], 'condition': condition, 'reference_request': reference_request, 'limits': self.job_limits(action), 'guest_duration_seconds': self.phase_clock()['deadline'] - self.budget.tick()}
        cap = self.run_worker(job, action, 'reference', request, bindings)
        scientific = self.ws.result(cap)
        diagnostic = scientific.get('read_custody')
        # Persist a private exact-body reference before testing scientific
        # completeness. The original RESULT remains in the immutable capture;
        # the ledger binds its whole bytes and its diagnostic subdocument.
        evidence = {'schema': 'neural066_reference_capture_evidence_v1', 'phase_id': job['phase_id'], 'action': action, 'context': public['private']['context'], 'capture': self.capture_pin(cap), 'result': self.ws.from_capture(cap, 'RESULT.json'), 'read_custody_pin': pin(encoded(diagnostic)), 'scientific_status': scientific.get('status'), 'diagnostic_evidence_is_scientific_acceptance': False, 'raw_input_exported': False}
        self.reference_evidence[job['phase_id']] = self.ws.json('reference-evidence/' + job['phase_id'] + '.json', evidence)
        need(type(diagnostic) is dict and set(diagnostic) == {'schema', 'observations', 'logical_read_reservation', 'acknowledged_prefix_bytes', 'unknown_pending_upper', 'raw_input_exported', 'physical_IO_or_RSS_certified'} and diagnostic['schema'] == 'neural066_reference_read_custody_v1' and diagnostic['raw_input_exported'] is False and diagnostic['physical_IO_or_RSS_certified'] is False, 'Exact private reference read custody envelope')
        observations = diagnostic['observations']
        need(type(observations) is list and all(type(value) is dict for value in observations), 'Ordered source-owned capture observations')
        for value in observations:
            if not value:
                continue  # An array descriptor can fail before capture starts.
            need(value.get('schema') == 'neural066_read_extent_observation_v1' and value.get('status') in ('not_started', 'reserved', 'failed', 'failed_close', 'complete'), 'Original safe_io observation semantics')
            need(all(type(value.get(k)) is int and value[k] >= 0 for k in ('reserved_upper', 'requested_upper', 'acknowledged_bytes', 'unknown_pending_upper')), 'Known prefix and unknown reservation are separate nonnegative extents')
            need(value['acknowledged_bytes'] + value['unknown_pending_upper'] <= value['requested_upper'] <= value['reserved_upper'] and type(value.get('descriptor_closed')) is bool and type(value.get('named_stable')) is bool, 'Capture prefix/reservation/close identities')
            prefix = value.get('acknowledged_prefix_pin')
            need(type(prefix) is dict and set(prefix) == {'bytes', 'sha256'} and type(prefix['bytes']) is int and prefix['bytes'] == value['acknowledged_bytes'] and type(prefix['sha256']) is str and len(prefix['sha256']) == 64 and all(c in '0123456789abcdef' for c in prefix['sha256']), 'Exact acknowledged-prefix pin without its raw body')
        need(all(type(diagnostic[k]) is int and diagnostic[k] >= 0 for k in ('logical_read_reservation', 'acknowledged_prefix_bytes', 'unknown_pending_upper')), 'Typed private diagnostic totals')
        need(diagnostic['logical_read_reservation'] == scientific['costs']['read_bytes'] == sum(value.get('reserved_upper', 0) for value in observations) and diagnostic['acknowledged_prefix_bytes'] == sum(value.get('acknowledged_bytes', 0) for value in observations) and diagnostic['unknown_pending_upper'] == sum(value.get('unknown_pending_upper', 0) for value in observations), 'Exact retained full read reservation and observed/unknown totals')
        need(scientific.get('schema') == 'neural066_reference_result_v1' and scientific.get('status') == 'complete' and (scientific.get('action') == action) and (scientific.get('context') == public['private']['context']), 'Captured reference evidence is not scientific completion; incomplete/incorrect result stops all later dispatch')
        need(all(value.get('status') == 'complete' and value['descriptor_closed'] is True and value['named_stable'] is True for value in observations) and diagnostic['unknown_pending_upper'] == 0 and 'error' not in scientific, 'Failed/unknown read evidence cannot be scientific success')
        if action == 'r2_inner':
            self.inner.setdefault(key, []).append(cap)
        elif infer:
            self.prediction(job, cap, public, group)
        else:
            self.models[key] = cap
        return {'capture': self.capture_pin(cap), 'reference_evidence': self.reference_evidence[job['phase_id']]}

    def prediction(self, job, cap, public, role):
        context = identity([role, job['slot'], job.get('mode', 'reference'), job['condition']])
        need(context not in self.predictions, 'One complete output per original model/context')
        self.predictions[context] = {'capture': cap, 'public': public}
        self.expected[context] = {'slot': job['slot'], 'person_slot': job['person_slot'], 'modality': job['modality'], 'role': role, 'fold': job['fold'], 'mode': job.get('mode', 'reference'), 'condition': job['condition'], 'private_queries': public['private']['private_queries']}

    def declaration_phase(self, job):
        from declaration import build
        mode = job['mode']
        selected = {c: e for c, e in self.predictions.items() if self.expected[c]['role'] == 'candidate' and self.expected[c]['mode'] == mode}
        need(len(selected) == 468 and len(self.model_closed_flags) == 936 and all(self.model_closed_flags.values()), 'All same-mode predictions sealed and every provider retired')
        d = build(self.ws, selected, self.investigation_policy, mode, self.op['investigation_policy'], self.methods)
        self.declarations[mode] = d
        return d

    def prescore(self, job):
        from protected_score import admit_predictions
        completed = {r['job']['phase_id'] for r in self.rows if r['status'] == 'complete'}
        need(set(job['parents']) <= completed and all((r['status'] == 'complete' for r in self.rows if r['job']['phase_id'] < job['phase_id'])), 'Every original fit/preparation/declaration complete before targets')
        required = {}
        for c in cases():
            for mode in MODES:
                for arm in CONDITIONS:
                    required[identity(['candidate', c['slot'], mode, arm])] = ('candidate', c['slot'], mode, arm)
            for role, arms in (('r0', CONDITIONS), ('r2', R2_ARMS), ('r1', ('LANGUAGE_ONLY',))):
                for arm in arms:
                    required[identity([role, c['slot'], 'reference', arm])] = (role, c['slot'], 'reference', arm)
        need(set(self.predictions) == set(self.expected) == set(required) and len(required) == 1794, 'Exact complete original1794 context set')
        need(set(self.declarations) == set(MODES) and len(self.methods) == 936 and (len(self.models) == 1794) and (len(self.inner) == 312) and all((len(v) == 18 for v in self.inner.values())), 'All936 fresh candidates/468R0/78R1/312R2 final states and5616 inner fits')
        need(len(self.model_closed_flags) == 936 and all(self.worker_closed_flags.values()) and all(self.model_closed_flags.values()) and (not self.unknown), 'All original model/worker custodians independently closed; unknown cannot mean zero')
        shared={};arm_views={}
        for context,entry in self.predictions.items():
            meta=self.expected[context];view=entry['public']['view']
            need((meta['role'],meta['slot'],meta['mode'],meta['condition'])==required[context],'Exact current producer/context mapping')
            case_shared={k:view[k]for k in ('case','generation','support_commitment','queries','source_contract_pin','projection_pin','language_policy_pin')}
            prior=shared.setdefault(meta['slot'],case_shared);need(prior==case_shared,'All matched arms/modes/references share full original support and query order')
            arm_key=(meta['slot'],view['condition']);same={k:view[k]for k in ('feature_spec','arrays','geometry','layout')}
            prior=arm_views.setdefault(arm_key,same);need(prior==same,'Identical input bytes/schema for same-arm F/I/independent references')
        for context, entry in self.predictions.items():
            d = self.ws.from_capture(entry['capture'], 'PREDICTIONS.json')
            body = self.ws.read(d['source_path'], d)
            admit_predictions(body, entry['public']['view'])
            self.budget.tick()
        remaining = [self.profile(a) for a in ('score_primary', 'score_independent', 'report', 'terminal_observation')]
        need(self.budget.reads + sum((p['read_bytes'] for p in remaining)) <= self.budget.limits['read_bytes'] and self.budget.writes + sum((p['write_bytes'] for p in remaining)) <= self.budget.limits['write_bytes'] and (self.budget.tick() + sum((p['wall_seconds'] for p in remaining)) <= self.budget.work_end), 'All scorer/report/retirement work fits remaining original allocation')
        result = {'schema': 'neural066_prescore_barrier_v1', 'prediction_contexts': 1794, 'reference_fits': 6474, 'candidate_final_seals': 936, 'declarations': self.declarations, 'complete_original_parents': job['parents'], 'target_vault': self.target_vault, 'scorer_target_reads_before_barrier': 0, 'trusted_preparer_target_reads_previously_recorded': True, 'costs': self.budget.snapshot()}
        self.barrier = self.ws.json('protected/PRESCORE_BARRIER.json', result)
        return self.barrier

    def language_states(self):
        result = {}
        for c in cases():
            cap = self.models['r1', c['slot'], 'LANGUAGE_ONLY']
            fit = self.ws.result(cap)
            d = self.ws.from_capture(cap, 'LANGUAGE_STATE.json')
            v = self.ws.read(d['source_path'], d)
            need(v['schema'] == 'neural066_training_language_state_v1' and v['context'] == fit['context'] and (v['fit_provenance'] == fit['fit_provenance']) and (v['model'] == fit['model']) and ({k: d[k] for k in ('bytes', 'sha256')} == {k: fit['language_state'][k] for k in ('bytes', 'sha256')}), 'Exact own original count FIT, state, support and successful result')
            result[c['slot']] = v['counts']
        return result

    def grade_phase(self, job):
        need(self.barrier is not None and len(self.predictions) == 1794 and all(self.worker_closed_flags.values()) and all(self.model_closed_flags.values()) and (not self.unknown), 'Sealed complete barrier before every private scorer read')
        vault = self.ws.read(self.target_vault['source_path'], self.target_vault)
        gold = vault['targets']
        languages = self.language_states()
        self.budget.event({'kind': 'protected_scorer_target_observation', 'phase': job['phase_id'], 'barrier': self.barrier, 'vault': self.target_vault})
        if job['action'] == 'score_primary':
            from protected_score import admit_predictions, grade_stream

            def items():
                for context, entry in self.predictions.items():
                    d = self.ws.from_capture(entry['capture'], 'PREDICTIONS.json')
                    body = self.ws.read(d['source_path'], d)
                    yield (context, admit_predictions(body, entry['public']['view']))
                    self.budget.tick()
            self.primary = grade_stream(items(), self.expected, gold, languages, self.contrast_rows)
            self.score_pins['primary'] = self.ws.json('protected/PRIMARY.json', self.primary)
        else:
            from independent_score import verify_stream
            value = verify_stream(self.predictions, self.expected, gold, self.primary, self.ws, languages, self.contrast_rows)
            self.score_pins['independent'] = self.ws.json('protected/INDEPENDENT.json', value)
        return dict(self.score_pins)

    def handle(self, job):
        a = job['action']
        if a == 'source_admission':
            return self.source_admission(job)
        if a == 'native_project':
            return self.native_project(job)
        if a == 'membership':
            return self.membership_phase(job)
        if a in ('case_plan', 'candidate_view'):
            return self.view_phase(job)
        if a.startswith('candidate_'):
            return self.candidate_phase(job)
        if a.startswith(('r0', 'r1', 'r2')):
            return self.reference_phase(job)
        if a == 'investigation_declaration':
            return self.declaration_phase(job)
        if a == 'prescore_barrier':
            return self.prescore(job)
        if a.startswith('score_'):
            return self.grade_phase(job)
        if a == 'report':
            return self.ws.json('REPORT.json', {'schema': 'neural066_private_report_v1', 'scores': self.score_pins, 'scope': self.op['scope'], 'declarations': self.declarations, 'prescore_barrier': self.barrier, 'gate_ledger': {'original_obligations': self.gate_spec, 'source_implementation_does_not_self_qualify_gates': True}, 'full_contrasts': 164, 'all_source_qualification_remains_separate': True, 'observed_key_endpoint': True, 'event_assisted_batch_transductive': True, 'case_local_policy_construction': True, 'provider_language_pretraining_admitted': True, 'crossmodal_unique_recruits': None, 'descriptive_only': True, **no_science_promotion()})
        if a == 'terminal_observation':
            need(all(self.worker_closed_flags.values()) and all(self.model_closed_flags.values()) and (not self.unknown), 'All consumers closed before terminal owned retirement')
            for mount in self.persistent:
                self.ws.retire(mount, True)
            need(all((v['credit_released'] for v in self.ws.views)), 'Every exact owned stage durably retired')
            return {'controller_internal_only': True, 'outer_observer_still_required': True}
        raise ValueError('Unknown complete roster action')

    def run(self):
        self.ws.json('PLANNED_PHASES.json', {'schema': 'neural066_planned_phases_v1', 'jobs': [r['job'] for r in self.rows]})
        for row in self.rows:
            if self.stopped:
                continue
            job = row['job']
            self.active = job
            profile = self.profile(job['action'])
            now = self.budget.last
            extra = self.op['candidate']['max_preliminary_tools'] if job['action'] == 'candidate_author' else 0
            read = profile['read_bytes'] + extra * self.op['tool_limits']['read_bytes']
            write = profile['write_bytes'] + extra * self.op['tool_limits']['write_bytes']
            end = min(self.budget.work_end, now + profile['wall_seconds'] + extra * self.op['tool_limits']['wall_seconds'])
            try:
                need(all((any((r['job']['phase_id'] == pid and r['status'] == 'complete' for r in self.rows)) for pid in job['parents'])), 'Actual complete original predecessor phases')
                self.budget.tick()
                self.budget.begin_attempt(read, write, end)
                self.budget.event({'kind': 'logical_start', 'job': job})
                self.budget.tick()
                value = self.handle(job)
                self.budget.tick()
                self.budget.event({'kind': 'logical_complete', 'phase_id': job['phase_id'], 'value': value})
                self.budget.tick()
                self.budget.end_attempt()
                row.update(status='complete', result=value)
            except BaseException as exc:
                failures.hold(exc, 'caught')
                self.stopped = True
                row.update(status='failed', error=failure(exc))
                if job['phase_id'] in self.reference_evidence:
                    row['reference_evidence'] = self.reference_evidence[job['phase_id']]
                self.unknown = self.unknown or any((not v for v in self.worker_closed_flags.values())) or any((not v for v in self.model_closed_flags.values()))
                self.budget.attempt = None
                self.budget.subattempt = None
                self.budget.work_end = self.budget.end - self.op['host_finish_seconds']
                try:
                    self.budget.event({'kind': 'logical_failed', 'job': job, 'error': failure(exc), 'unknown_external_activity': self.unknown})
                except BaseException as e:
                    failures.hold(e, 'caught')
                    row['failure_journal_error'] = failure(e)
        self.budget.attempt = None
        self.budget.subattempt = None
        self.budget.work_end = self.budget.end - self.op['host_finish_seconds'] if self.stopped else self.original_work_deadline
        ledger = self.ws.json('PHASE_LEDGER.json', {'schema': 'neural066_controller_phase_ledger_v1', 'rows': self.rows})
        counts = {k: sum((r['status'] == k for r in self.rows)) for k in ('complete', 'failed', 'not_started')}
        custody = {'all_worker_phases_closed': bool(self.worker_closed_flags) and all(self.worker_closed_flags.values()), 'all_model_sessions_closed': len(self.model_closed_flags) == 936 and all(self.model_closed_flags.values()), 'all_owned_views_retired': bool(self.ws.views) and all((v['credit_released'] for v in self.ws.views)), 'unknown_external_activity': self.unknown}
        value = {'schema': 'neural066_controller_return_v1', 'operation_pin': self.operation_pin, 'authority_pin': self.authority_pin, 'source_manifest_pin': self.source_manifest_pin, 'child_limits_pin': self.child_limits_pin, 'origin': self.budget.origin, 'deadline': self.budget.end, 'work_deadline': self.original_work_deadline, 'status': 'complete' if counts['complete'] == 11306 and all((custody[k] for k in custody if k != 'unknown_external_activity')) and (not self.unknown) else 'incomplete', 'custody': custody, 'roster': {'expected': 11306, **counts, 'ledger_pin': {'path': 'PHASE_LEDGER.json', 'bytes': ledger['bytes'], 'sha256': ledger['sha256']}}, 'costs': self.budget.snapshot(), 'score_pins': self.score_pins, 'runtime_qualified': False, 'scientific_qualified': False}
        publish_return(self.ws, value)
        return value

def publish_return(ws, value):
    """Fixed-point self-publication cost, original final cutoff, no false receipt."""
    b = ws.budget
    base_w = b.writes
    base_r = b.retained
    base_f = b.file_writes
    value = copy.deepcopy(value)
    last = None
    for _ in range(16):
        body = encoded(value)
        n = len(body)
        if n == last:
            break
        last = n
        value['costs'].update(logical_write_charge=base_w + n, retained_charge=base_r + n, successfully_published_host_file_write_bytes=base_f + n)
    else:
        raise ValueError('Finite fixed-point complete return framing')
    need(n <= ws.metadata['json_bytes'], 'Full terminal return extent')
    b.write(n)
    try:
        durable_new(ws.root / 'CONTROLLER_RETURN.json', body)
        b.file_writes += n
        b.tick()
    except BaseException as primary:
        failures.hold(primary, 'caught')
        try:
            b.attempt = None
            b.subattempt = None
            b.work_end = b.end
            b.save(ws.root / 'RETURN_INVALIDATED.json', encoded({'schema': 'neural066_return_invalidated_v1', 'error': failure(primary), 'complete': False}))
        except BaseException as secondary:
            failures.hold(secondary, 'caught')
            failures.note(primary, 'Invalidation publication failed: ' + failures.kind(secondary))
        raise
    return value

def main(argv=None, *, bootstrap_proof=None):
    need(type(bootstrap_proof) is dict and set(bootstrap_proof) == {'schema', 'source_root', 'operation_pin', 'authority_pin', 'source_manifest_pin', 'child_limits_pin', 'origin', 'deadline', 'work_deadline', 'read_charge', 'postcheck_write_reserve'} and (bootstrap_proof['schema'] == 'neural066_captured_controller_bootstrap_v1'), 'Exact captured-source bootstrap required before reading any operation operand')
    p = argparse.ArgumentParser()
    p.add_argument('--operation', required=True)
    p.add_argument('--authority', required=True)
    p.add_argument('--root', required=True)
    p.add_argument('--origin', type=float, required=True)
    p.add_argument('--deadline', type=float, required=True)
    p.add_argument('--work-deadline', type=float, required=True)
    p.add_argument('--child-limits', required=True)
    args = p.parse_args(argv)
    limits_raw = capture(args.child_limits, 2097152)
    limits = strict(limits_raw)
    opraw = capture(args.operation, 16777216)
    op = strict(opraw)
    authorityraw = capture(args.authority, 16777216)
    authority = strict(authorityraw)
    need(limits == op['controller_limits'] and args.deadline == args.origin + limits['wall_seconds'], 'Exact enclosing original clock/partition')
    proof = bootstrap_proof
    need(proof['source_root'] == op['source_root'] and proof['operation_pin'] == pin(opraw) and (proof['authority_pin'] == pin(authorityraw)) and (proof['child_limits_pin'] == pin(limits_raw)) and (proof['source_manifest_pin'] == {k: op['source_manifest'][k] for k in ('bytes', 'sha256')}) and all((type(proof[k]) is type(v) and proof[k] == v for k, v in (('origin', args.origin), ('deadline', args.deadline), ('work_deadline', args.work_deadline)))), 'Bootstrap exact raw source/operation/authority and original clock join')
    need(type(proof['read_charge']) is int and proof['read_charge'] > 0 and (proof['postcheck_write_reserve'] == 8192), 'Complete source reauthentication and postcheck invalidation reservation')
    root = Path(args.root)
    root.mkdir(mode=448, parents=True, exist_ok=True)
    journal = root / 'controller-journal'
    journal.mkdir(mode=448)
    b = Budget(limits, args.origin, journal)
    b.work_end = args.work_deadline
    b.max_event_bytes = op['metadata']['event_bytes']
    b.max_events = op['metadata']['max_events']
    b.reserve_producer('captured-child-bootstrap', proof['read_charge'], proof['postcheck_write_reserve'], proof['postcheck_write_reserve'])
    b.read(len(limits_raw) + len(opraw) + len(authorityraw))
    need(b.tick() < args.work_deadline, 'Original cutoff before source admission')
    source = op['source_manifest']
    source_body = b.read_file(source['path'], {k: source[k] for k in ('bytes', 'sha256')}, op['metadata']['json_bytes'])
    c = Controller(op, authority, root, b, pin(opraw), pin(authorityraw), pin(source_body), pin(limits_raw))
    c.original_work_deadline = args.work_deadline
    result = c.run()
    return 0 if result['status'] == 'complete' else 2
if __name__ == '__main__':
    raise SystemExit(main())
