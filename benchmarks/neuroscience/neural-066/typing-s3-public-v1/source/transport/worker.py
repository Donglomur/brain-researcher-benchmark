"""Exact N065 science-job bindings over concrete owned offline Docker phases."""
import failures
import copy, time, uuid
from pathlib import Path
from .io import capture, publish, encoded, parse, pin, need, failure
from .vendor.provider import Provider
from .vendor.bounds import mount_identity, fsync_dir
from .vendor.bounds import relative
ACTIONS = {'native_project', 'membership', 'case_plan', 'candidate_view', 'candidate_policy', 'candidate_fit', 'candidate_infer', 'r2_inner', 'r2_final', 'r2_infer', 'r0fit', 'r0infer', 'r1count', 'r1infer'}

def file_mount(path, expected, purpose='input'):
    path = Path(path)
    return {'path': str(path), 'kind': 'file', 'purpose': purpose, 'files': {path.name: expected}}

def typed_mount_plan(action, role, job, mounts, source_identity):
    """Closed scientific roles mapped to the unchanged generic vendor ABI.

    `program` means the exact public runner or current sealed submission;
    `input` means only this request's staged inputs, own fresh model, or
    operator-only original assets. These meanings are enforced by targets,
    action/role, file pins and the source-owned producer/consumer joins.
    """
    need(action in ACTIONS and job.get('action') == action and job.get('role') == role, 'Exact typed request action and role')
    candidate = action in ('candidate_policy', 'candidate_fit', 'candidate_infer')
    reference = action in ('r2_inner', 'r2_final', 'r2_infer', 'r0fit', 'r0infer', 'r1count', 'r1infer')
    need((candidate and role in ('A', 'B')) or (reference and role == 'reference') or (not candidate and not reference and role == 'operator'), 'Closed scientific action-to-role relation')
    need('/program' in mounts and mounts['/program']['kind'] == 'directory', 'Single exact role source directory')
    source = {'/program': mounts['/program']}
    need(mount_identity(source) == source_identity, 'Exact closed role source inventory')
    need(mounts['/program']['purpose'] == ('program' if candidate else 'operator_reference'), 'Source-owned runner role uses exact supported vendor purpose')
    expected_targets = {'/program'}
    if action == 'native_project':
        need(type(job.get('native_originals')) is dict and job['native_originals'], 'Exact original asset pin roster')
        need(set(job['inputs']) == {'record', 'records', 'assets', 'loader', 'membership_policy'}, 'Closed native metadata/loader inputs')
        bound = {}
        for d in job['inputs'].values():
            need(type(d) is dict and set(d) == {'path', 'bytes', 'sha256'}, 'Exact native metadata input descriptor')
            name = relative(d['path'])
            target = '/input/' + name
            need(target not in bound and not name.startswith('originals/'), 'Disjoint native metadata and original roots')
            bound[target] = {k: d[k] for k in ('bytes', 'sha256')}
        for name, d in job['native_originals'].items():
            name = relative(name)
            target = '/input/originals/' + name
            need(target not in bound, 'Unique exact native original target')
            bound[target] = d
        for target, d in bound.items():
            need(target in mounts, 'Every exact native metadata and original binding present')
            m = mounts[target]
            need(m['kind'] == 'file' and m['purpose'] == 'input' and m['files'] == {Path(m['path']).name: d}, 'Exact immutable native file purpose and pin')
            expected_targets.add(target)
    else:
        need('/input' in mounts and mounts['/input']['kind'] == 'directory' and mounts['/input']['purpose'] == 'input', 'Exact per-phase staged input directory')
        expected_targets.add('/input')
    if candidate:
        need('/submitted' in mounts, 'Current candidate submission required')
        m = mounts['/submitted']
        need(m['kind'] == 'directory' and m['purpose'] == 'program' and m['files'] == job['submitted']['files'], 'Exact current candidate source binding, never a blanket purpose grant')
        expected_targets.add('/submitted')
        if action == 'candidate_infer':
            need('/model' in mounts and 'model_context' in job, 'Own fresh-final model and context required')
            m = mounts['/model']
            need(m['kind'] == 'directory' and m['purpose'] == 'input' and m['files'] == job['model_files'] and m['files'].get('MODEL.json') == job['model_pin'], 'Exact final-model envelope and own-state files')
            need(job['scope']['query_access'] is True and job['scope']['training_access'] is False and job['scope']['provider_after_seal'] is False, 'Fresh model is inference-only current-query input')
            expected_targets.add('/model')
    need(set(mounts) == expected_targets, 'No extra source/data/model/contract mounts beyond the closed action plan')
    targets = sorted(mounts)
    need(not any(b.startswith(a + '/') for i, a in enumerate(targets) for b in targets[i+1:]), 'Disjoint complete source-owned mount plan')
    return {'schema': 'neural066_typed_mount_plan_v1', 'action': action, 'role': role, 'targets': targets, 'vendor_purposes': {k: v['purpose'] for k,v in mounts.items()}, 'source': source_identity}

class Native:

    def __init__(self, configuration, budget):
        self.c = copy.deepcopy(configuration)
        self.budget = budget
        self.attempts = {}
        self.failed = False
        need(self.c['schema'] == 'neural066_worker_transport_configuration_v1', 'Qualified complete N066 transport configuration')
        self.policy = parse(budget.read_file(self.c['mechanical_policy_path'], self.c['mechanical_policy_pin'], 2097152))
        need(self.policy['source'] == self.c['source'] and self.policy['image'] == self.c['image'] and (self.policy['approved_rule'] == 'neural066_exact_role_phase_mounts_v1'), 'Independent source/image role boundary')
        need(set(self.c['source_mounts']) == {'A', 'B', 'reference', 'operator'}, 'All role-specific closed source inventories')
        need(self.c['source_mounts']['A'] == self.c['source_mounts']['B'], 'Frozen/adaptive have the same candidate runner source, not author-code arms')
        need(self.policy['source_mounts'] == self.c['source_mounts'] and self.policy['python'] == self.c['python'], 'Mechanical policy binds exact per-role source inventory and interpreter')
        self.provider = Provider(self.c['control_root'], self.c['quarantine_root'], self.c['docker_binary'], self.c['docker_socket'], self.c['engine_source'], self.c['trusted_exposures'], self.c['source_read_bytes'], self.c['host_write_bytes'])

    def run(self, logical_id, action, role, job, mounts, clock, limits, exposure_descriptor=None):
        try:
            return self._run(logical_id, action, role, job, mounts, clock, limits, exposure_descriptor)
        except BaseException as exc:
            failures.hold(exc, 'caught')
            self.failed = True
            value = {'logical_id': logical_id, 'status': 'failed', 'error': failure(exc), 'custody': 'unknown', 'raw_result': None, 'automatic_retry': False}
            self.attempts.setdefault(logical_id, value)
            return value

    def _run(self, logical_id, action, role, job, mounts, clock, limits, exposure_descriptor=None):
        need(not self.failed and logical_id not in self.attempts, 'No subsequent dispatch after failure/unknown or phase retry')
        need(action in ACTIONS and role in ('A', 'B', 'reference', 'operator'), 'Declared N065 phase/role')
        job = copy.deepcopy(job)
        mounts = copy.deepcopy(mounts)
        clock = copy.deepcopy(clock)
        limits = copy.deepcopy(limits)
        need(job.get('action') == action and job.get('role') == role, 'Exact immutable scientific request action/role')
        need(clock['origin'] <= self.budget.tick() < clock['deadline'], 'Original host phase deadline')
        plan = typed_mount_plan(action, role, job, mounts, self.c['source_mounts'][role])
        wire = uuid.uuid4().hex
        root = Path(self.c['job_root']) / wire
        record = {'logical_id': logical_id, 'wire_phase': wire, 'action': action, 'role': role, 'case': job.get('case'), 'mode': job.get('mode'), 'condition': job.get('condition'), 'status': 'attempted', 'raw_result': None, 'typed_mount_plan': plan}
        self.attempts[logical_id] = record
        raw_result = None
        try:
            need(root.is_absolute() and (not root.exists()), 'Fresh owned scientific phase namespace')
            root.mkdir(mode=448)
            fsync_dir(root.parent)
            raw = encoded(job)
            jp = publish(root / 'REQUEST.json', raw, self.budget)
            mounts['/job/REQUEST.json'] = file_mount(root / 'REQUEST.json', jp, 'contract')
            argv = [self.c['python'], '-I', '-B', '/program/worker.py', '--request', '/job/REQUEST.json', '--wire', '/request.json', '--input', '/input', '--output', '/output']
            if exposure_descriptor is None:
                audit = {'schema': 'osl_transport_exposure_v1', 'role': role, 'image': self.c['image'], 'source': self.c['source'], 'command': argv, 'mounts': mount_identity(mounts), 'approved_image_inventory_sha256': self.policy['image_inventory_sha256'], 'boundary_audit': self.c['mechanical_policy_pin'], 'role_boundary_verified': True}
                exposure_descriptor = self.budget.save(root / 'EXPOSURE.json', encoded(audit))
                self.provider.exposures[exposure_descriptor['sha256']] = str(root / 'EXPOSURE.json')
            request = {'schema': 'osl_owned_phase_request_v1', 'phase_id': wire, 'action': 'held_attempt' if role != 'operator' else 'prepare_originals', 'role': role, 'image': self.c['image'], 'command': argv, 'workdir': '/work', 'source': self.c['source'], 'exposure': exposure_descriptor, 'clock': {'origin': clock['origin'], 'phase_deadline': clock['deadline']}, 'resources': limits, 'output': {'kind': 'generic', 'manifest': 'OUTPUTS.json'}}
            record.update(scientific_request=jp, wire_request=pin(encoded(request)), mounts=mount_identity(mounts), clock=clock)
            self.budget.event({'event': 'N065-PHASE-INTENT', **record})
            need(self.budget.tick() < clock['deadline'], 'Original phase cutoff immediately before transport')
            raw_result = self.provider.execute_phase(request, mounts, clock['deadline'], lambda name, value: self.budget.event({'event': 'N065-TRANSPORT', 'logical_id': logical_id, 'name': name, 'value': value}))
            record['raw_result'] = raw_result
            observed = self.provider.observe(wire, pin(encoded(request))['sha256'], raw_result['receipt_pin'], clock['deadline'])
            r = observed['receipt']
            need(r['status'] == 'captured' and r['all_native_resources_closed'] is True and (r['cli_reaped'] is True) and (r['error'] is None) and (not r['deadline_exceeded']), 'Complete independent capture/custody admission')
            now = self.budget.tick()
            t = r['timing']
            need(clock['origin'] <= t['started'] <= t['finished'] <= raw_result['finished_after_receipt'] <= now < clock['deadline'], 'No future/rollback/late closure evidence')
            record.update(status='captured', receipt_path=raw_result['receipt_path'], receipt_pin=raw_result['receipt_pin'], capture_root=r['quarantine_root'], output_files=r['output_inventory']['files'])
            self.budget.save(root / 'JOIN.json', encoded(record))
            need(self.budget.tick() < clock['deadline'], 'Final phase journal/receipt inside original cutoff')
            return copy.deepcopy(record)
        except BaseException as exc:
            failures.hold(exc, 'caught')
            self.failed = True
            record.update(status='failed', error=failure(exc), raw_result=raw_result, custody='unknown', automatic_retry=False)
            try:
                self.budget.save(root / 'FAILED.json', encoded(record))
                self.budget.event({'event': 'N065-PHASE-FAILED', **record})
            except BaseException as secondary:
                failures.hold(secondary, 'caught')
                failures.note(exc, 'Failure metadata publication uncertain: ' + failures.kind(secondary))
            return copy.deepcopy(record)

    def recover(self, phase_id, request_pin, ownership_pin, original_deadline, limits, controller_closed_proof):
        self.failed = True
        return self.provider.recover(phase_id, request_pin, ownership_pin, original_deadline, lambda name, value: self.budget.event({'event': 'N065-RECOVERY', 'name': name, 'value': value}), limits, controller_closed_proof)
