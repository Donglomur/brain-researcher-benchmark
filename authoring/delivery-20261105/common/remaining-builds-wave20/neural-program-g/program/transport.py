"""Sleep phase binding over the captured concrete offline Docker transport.

A pinned operator admission record is required for every exact phase exposure;
it is not replaced by a candidate boolean. This module is executable transport,
not a callback interface. Merely importing it does not launch a container.
"""
from pathlib import Path
import time
import uuid
from .common import capture, decode, descriptor, encoded, need, pin, publish, relative
from .vendor_transport.provider import Provider
from .vendor_transport.bounds import mount_identity


def file_mount(path, expected, purpose='input'):
    path = Path(path); descriptor(expected)
    return {'path': str(path), 'kind': 'file', 'purpose': purpose, 'files': {path.name: expected}}


def public_view(plan):
    allowed = {'schema', 'view', 'role', 'current_person', 'class_order', 'nights'}
    need(set(plan) == allowed | {'members', 'source_membership', 'presentation', 'operator_identity_fields_must_be_removed_before_publication'}, 'Exact internal view plan')
    return {k: plan[k] for k in sorted(allowed)}


def stage_view(plan, directory, meter):
    """Small public descriptor plus separate readonly physical file mounts."""
    directory = Path(directory); need(directory.is_absolute() and not directory.exists(), 'Fresh private stage')
    directory.mkdir(mode=0o700)
    view = public_view(plan)
    view_pin = publish(directory / 'VIEW.json', encoded(view), meter)
    selected={n['directory'] for n in view['nights']}
    publish(directory/'BINDING.json',encoded({'schema':'neural007_private_view_binding_v1','public_view':view_pin,
            'sources':[r for r in plan['source_membership'] if r['directory'] in selected],'presentation':plan['presentation']}),meter)
    mounts = {'/view/VIEW.json': file_mount(directory / 'VIEW.json', view_pin, 'contract')}
    for row in plan['members']:
        target = '/view/' + relative(row['target'])
        need(target not in mounts, 'Unique per-channel target')
        artifact = row['artifact']; mounts[target] = file_mount(artifact['path'], {k: artifact[k] for k in ('bytes', 'sha256')})
    return mounts, view, view_pin


def source_mounts(root, source_manifest, reference=False):
    """Candidate sandboxes get only the worker closure, never operator source."""
    root = Path(root)
    names = ['__init__.py', 'common.py', 'worker.py', 'entry.py']
    if reference: names += ['science.py', 'references.py']
    return {'/library/program/' + name: file_mount(root / name, source_manifest['files'][name], 'operator_reference' if reference else 'program') for name in names}


def observation(result, required_status='captured'):
    receipt = result['receipt']
    need(receipt['status'] == required_status, 'Concrete producer completion')
    return receipt


class Native:
    def __init__(self, configuration, meter):
        self.config, self.meter = configuration, meter
        self.operands = {}
        self.mechanical_policy = decode(capture(configuration['mechanical_policy_path'], configuration['mechanical_policy_pin'], meter=meter))
        need(self.mechanical_policy['source'] == configuration['source'] and self.mechanical_policy['image'] == configuration['image']
             and self.mechanical_policy['approved_rule'] == 'source_derived_exact_sleep_phase_mounts_v1', 'Independent pre-query mechanical phase-boundary approval')
        need(configuration['schema'] == 'neural007_native_configuration_v1', 'Exact separately admitted native configuration')
        self.provider = Provider(configuration['control_root'], configuration['quarantine_root'],
            configuration['docker_binary'], configuration['docker_socket'], configuration['engine_source'],
            configuration['trusted_exposures'], configuration['source_read_bytes'], configuration['host_write_bytes'])

    def run(self, identity, action, role, job, mounts, clock, limits, exposure_descriptor=None):
        """Request/clock/source are host-owned and re-observed after natural exit."""
        need(action in ('probe', 'policy', 'fit', 'infer', 'reference_fit', 'reference_infer', 'reference_cache'), 'Declared Sleep phase')
        need(role in ('A', 'B', 'reference'), 'Exact candidate/reference realm')
        need(identity not in self.operands,'One private logical phase, no replacement/retry')
        wire=uuid.uuid4().hex
        phase_root = Path(self.config['job_root']) / wire
        need(not phase_root.exists(), 'No implicit phase retry'); phase_root.mkdir(mode=0o700)
        payload = {**job, 'schema': 'neural007_worker_job_v1', 'action': action}
        job_pin = publish(phase_root / 'JOB.json', encoded(payload), self.meter)
        mounts = {**mounts, '/job.json': file_mount(phase_root / 'JOB.json', job_pin, 'contract')}
        command = ['/usr/local/bin/python', '-I', '-B', '/library/program/entry.py', 'worker']
        if exposure_descriptor is None:
            # Exact records are produced by this audited operator rule, never
            # by candidate source or a source-independent assertion. The rule
            # covers mechanical exposure only; final semantic state admission
            # is a distinct externally pinned gate.
            approval = {'schema': 'osl_transport_exposure_v1', 'role': role, 'image': self.config['image'],
                'source': self.config['source'], 'command': command, 'mounts': mount_identity(mounts),
                'approved_image_inventory_sha256': self.mechanical_policy['image_inventory_sha256'],
                'boundary_audit': self.config['mechanical_policy_pin'], 'role_boundary_verified': True}
            exposure_descriptor = publish(phase_root / 'EXPOSURE.json', encoded(approval), self.meter)
            self.config['trusted_exposures'][exposure_descriptor['sha256']] = str(phase_root / 'EXPOSURE.json')
            self.provider.exposures[exposure_descriptor['sha256']] = str(phase_root / 'EXPOSURE.json')
        request = {'schema': 'osl_owned_phase_request_v1', 'phase_id': wire, 'action': 'held_attempt',
                   'role': role, 'image': self.config['image'], 'command': command, 'workdir': '/work',
                   'source': self.config['source'], 'exposure': descriptor(exposure_descriptor),
                   'clock': {'origin': clock['origin'], 'phase_deadline': clock['deadline']},
                   'resources': limits, 'output': {'kind': 'generic', 'manifest': 'OUTPUTS.json'}}
        # The external admission must bind this exact dynamic JOB and source
        # bundle as well as image inventory. No broad path-prefix approval.
        audit_path = self.config['trusted_exposures'].get(exposure_descriptor['sha256'])
        need(audit_path is not None, 'Exact operator exposure record must already exist')
        audit = decode(capture(audit_path, exposure_descriptor, meter=self.meter))
        need(audit['mounts'] == mount_identity(mounts), 'Exact staged exposure, including generated job/code')
        journal = []
        result = self.provider.execute_phase(request, mounts, clock['deadline'], lambda name, value: journal.append({'event': name, 'value': value}))
        # API return carries immutable receipt identity; fresh observer is used
        # before any candidate observes tool text or a later phase is admitted.
        receipt_pin = result['receipt_pin']
        observed = self.provider.observe(wire, pin(encoded(request))['sha256'], receipt_pin, clock['deadline'])
        receipt = observation(observed)
        publish(phase_root / 'JOIN.json', encoded({'request': pin(encoded(request)), 'receipt': receipt_pin,
                'source': request['source'], 'job': job_pin, 'role': role, 'action': action,
                'clock': clock, 'logical_phase':identity,'wire_phase':wire,'observed_at': time.monotonic()}), self.meter)
        view_mount=mounts['/view/VIEW.json']; view_expected=next(iter(view_mount['files'].values()))
        binding_path=Path(view_mount['path']).parent/'BINDING.json'
        binding_pin=pin(capture(binding_path,meter=self.meter))
        self.operands[identity]={'logical_phase':identity,'wire_phase':wire,'binding':{'path':str(binding_path),**binding_pin},'request':{'path':str(Path(self.config['control_root'])/wire/'REQUEST.json'),**pin(encoded(request))},
             'job':{'path':str(phase_root/'JOB.json'),**job_pin},
             'view':{'path':view_mount['path'],**view_expected}}
        return {'receipt': receipt, 'receipt_pin': receipt_pin,'receipt_path':result['receipt_path'], 'logical_phase':identity,'wire_phase':wire,'request': request, 'job': job_pin,
                'view_mounts': mount_identity(mounts), 'operands':self.operands[identity]}
