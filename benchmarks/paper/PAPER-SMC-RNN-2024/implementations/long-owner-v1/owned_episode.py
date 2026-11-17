"""SMC successor composition with a preactivation clock and parent event custody.

The unchanged v1 public execute still refuses unsupported ownership. This narrow
composition reuses its methods, materials, requests, worker and paired grader.
It does not monkeypatch v1 or execute a candidate in the operator process.
"""
from pathlib import Path
import time
from common import CONDITIONS, body, encoded, need, pin, publish


def execute(invocation, invocation_pin, source, journal, L):
    protocol_path = Path(invocation['protocol_path'])
    expected = invocation['protocol_pin']['sha256']
    output = Path(invocation['output'])
    protocol, runtime = L.admit_protocol(protocol_path, expected)
    qualification = L.qualify(runtime, protocol['source'])
    pair, manifests = L.public_context(protocol['pair_path'], protocol['task_path'])
    # Original arrays are opened only here, after an actual active-owner ACK.
    L.benchmark().inspect_pair(protocol['pair_path'], L.PAIR_SHA, protocol['task_path'], L.TASK_SHA,
                               max_bytes=L.PAIR_CAP)
    root = L.path(output)
    need(not root.exists() and root.parent.is_dir()
         and not root.is_relative_to(Path(protocol['pair_path']).parent)
         and not root.is_relative_to(protocol_path.parent), 'Fresh disjoint execution root')
    root.mkdir(mode=0o700)
    for name in ('control', 'quarantine', 'jobs', 'freezes'):
        (root / name).mkdir(mode=0o700)
    origin = invocation['clock']['origin']
    deadline = invocation['clock']['deadline']
    controller_deadline = invocation['clock']['controller_deadline']
    need(origin <= time.monotonic() < controller_deadline < deadline,
         'Original preactivation clock with retained recovery reserve')
    exposure_paths, prepared = {}, {}
    for index, condition in enumerate(CONDITIONS):
        folder = root / 'jobs' / condition
        folder.mkdir(mode=0o700)
        job = L.job_for(protocol, condition)
        job_pin = L.publish(folder / 'EXECUTION.json', L.encoded(job), 0o444)
        mounts = L.mounts_for(protocol_path, protocol, condition, folder / 'EXECUTION.json', job_pin, manifests)
        exposure = {'schema': 'osl_transport_exposure_v1', 'role': 'A' if index == 0 else 'B',
            'image': runtime['image'], 'source': protocol['source'], 'command': L.COMMAND,
            'mounts': L.mount_identity(mounts), 'approved_image_inventory_sha256': qualification['image_inventory_sha256'],
            'boundary_audit': {k: runtime['qualification'][k] for k in ('bytes', 'sha256')},
            'role_boundary_verified': True}
        exposure_pin = L.publish(folder / 'EXPOSURE.json', L.encoded(exposure))
        exposure_paths[exposure_pin['sha256']] = str(folder / 'EXPOSURE.json')
        request = {'schema': 'osl_owned_phase_request_v1', 'phase_id': condition, 'action': 'held_attempt',
            'role': exposure['role'], 'image': runtime['image'], 'command': L.COMMAND, 'workdir': '/work',
            'source': protocol['source'], 'exposure': exposure_pin,
            'clock': {'origin': origin, 'phase_deadline': controller_deadline},
            'resources': L.resources(protocol['outcome'], runtime),
            'output': {'kind': 'generic', 'manifest': 'OUTPUTS.json'}}
        request_pin = L.publish(folder / 'REQUEST.json', L.request_bytes(request))
        prepared[condition] = request, mounts, request_pin
    # Both complete programme/declaration/request sets precede native release.
    for condition in CONDITIONS:
        request, _, request_file = prepared[condition]
        journal('PREPARED', {'request': request, 'request_file': request_file})
    cls = L.provider_class()
    provider = cls(root / 'control', root / 'quarantine', runtime['docker_binary'], runtime['docker_socket'],
                   pin(body(L.TRANSPORT / 'SOURCE_MANIFEST.json')), exposure_paths,
                   runtime['source_read_bytes'], runtime['host_write_bytes'])
    closed = {}
    try:
        for condition in CONDITIONS:
            request, mounts, _ = prepared[condition]
            L.admit_protocol(protocol_path, expected)
            result = provider.execute_phase(request, mounts, deadline, journal)
            receipt = L.observe_closed(provider, request, result, deadline)
            predictions = L.captured_predictions(receipt, condition, protocol['outcome'], protocol['programs'][condition])
            for filename in predictions.values():
                filename.chmod(0o400)
            frozen_path = root / 'freezes' / (condition + '.json')
            L.benchmark().freeze(protocol['pair_path'], L.PAIR_SHA, protocol['task_path'], L.TASK_SHA,
                condition, protocol['outcome'], predictions, protocol_path.parent / condition / 'declaration.json',
                frozen_path, max_bytes=L.PAIR_CAP)
            closed[condition] = {'request': pin(L.request_bytes(request)), 'receipt': result['receipt_pin'],
                'receipt_path': result['receipt_path'], 'freeze': pin(body(frozen_path)), 'freeze_path': str(frozen_path)}
        need(time.monotonic() < controller_deadline, 'Closed pair inside original controller interval')
        report = {'schema': 'smc_restricted_closed_pair_v1', 'route': L.ROUTE,
            'protocol_path': str(L.path(protocol_path)), 'protocol_sha256': expected,
            'source': protocol['source'], 'outcome': protocol['outcome'], 'conditions': closed,
            'all_programmes_frozen_before_execution': True, 'both_conditions_closed_before_private_grade': True,
            'private_target_accessed': False, 'runtime_qualification': runtime['qualification'],
            'AI_attribution_verified': False, 'generic_primary_profile_equivalence': False,
            'scientific_success': None, 'owner_successor_route': 'smc_long_owner_v1',
            'owner_invocation_pin': invocation_pin, 'owner_source': source,
            'owner_closure_still_required': True}
        report_pin = L.publish(root / 'PAIR_CLOSED.json', L.encoded(report))
        journal('CONTROLLER-DONE', report_pin)
        return report
    except BaseException as exc:
        L.publish(root / 'FAILED.json', L.encoded({'status': 'terminal_preserved_failure',
            'type': type(exc).__name__, 'conditions_closed': sorted(closed),
            'private_target_accessed': False, 'automatic_retry': False,
            'owner_invocation_pin': invocation_pin, 'owner_closure_still_required': True}))
        raise
