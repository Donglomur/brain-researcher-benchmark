#!/usr/bin/env python3
"""Source-frozen complete historical forecasting programme and private grader."""
import argparse
import os
from pathlib import Path
import signal
import sys
import time
import uuid

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import (MAX_OUTPUT, PUBLIC, assets, authenticate, capture, decode,
                    encoded, file_mount, need, ordinary, pin, prepare_grader_prediction, publish)
from transport.provider import Provider
from transport.bounds import mount_identity
import grade

LIMITS = {'setup_seconds': 10, 'producer_seconds': 20, 'capture_seconds': 10, 'cleanup_seconds': 10,
          'memory_bytes': 3 * 1024**3, 'cpu_nanos': 1750000000, 'pids': 64, 'scratch_bytes': 64 * 1024**2,
          'max_files': 3, 'max_directories': 1, 'max_file_bytes': MAX_OUTPUT, 'max_output_bytes': 40 * 1024**2,
          'manifest_bytes': 16384, 'max_cli_calls': 128, 'max_cli_bytes': 4 * 1024**2,
          'inventory_bytes': 65536, 'source_read_bytes': 512 * 1024**2, 'host_write_bytes': 48 * 1024**2}


def configuration(path):
    config = decode(capture(path, 32768))
    need(config['schema'] == 'neural018_submitted_program_configuration_v1', 'Exact operator configuration')
    need(config['image'] == grade.IMAGE, 'Original numerical image, no pull or substitution')
    for name in ('assets_root', 'docker_binary', 'docker_socket', 'docker_config', 'control_root', 'quarantine_root'):
        need(type(config[name]) is str and Path(config[name]).is_absolute(), 'Absolute operator path ' + name)
        ordinary(config[name])
    source_pin = authenticate(config['source'])
    policy = decode(capture(config['mechanical_policy_path'], 32768, config['mechanical_policy_pin']))
    need(policy == {'schema': 'neural018_mechanical_boundary_v1', 'source': source_pin, 'image': config['image'],
                    'image_inventory_sha256': policy.get('image_inventory_sha256'),
                    'approved_rule': 'three_original_public_inputs_then_isolated_original_grader_v1'},
         'Independent source/image/input boundary review required')
    allocation = decode(capture(config['allocation_path'], 32768, config['allocation_pin']))
    need(allocation['schema'] == 'neural018_new_runtime_allocation_v1' and allocation['source'] == source_pin
         and allocation['historical_charges_seconds'] == [60, 120, 180, 90, 250, 90, 120]
         and allocation['historical_total_seconds'] == 910 and allocation['historical_amended_ceiling_seconds'] == 1000,
         'Historical 790 + 120 / 1000 accounting is never erased')
    need(type(allocation['new_whole_seconds']) is int and allocation['new_whole_seconds'] == 140
         and type(allocation['new_cumulative_ceiling_seconds']) is int
         and allocation['new_cumulative_ceiling_seconds'] >= 910 + 140
         and allocation['operator_approved'] is True,
         'Fresh explicit cumulative runtime grant for this 140-second attempt')
    need(allocation['source_read_bytes'] == LIMITS['source_read_bytes'] + 1048576
         and allocation['transport_write_bytes'] == LIMITS['host_write_bytes']
         and allocation['additional_operator_output_bytes'] >= 2 * 1024**2,
         'Explicit transport and additional operator artifact allocation')
    return config, policy, allocation, source_pin


def commit(program, output, source_pin, allocation):
    output = ordinary(output)
    need(not output.exists() and output.parent.is_dir(), 'Fresh existing-parent operator attempt')
    body = capture(program, 200000)
    output.mkdir(mode=0o700)
    identity = publish(output / 'program.py', body, 0o444)
    publication = {'schema': 'neural018_program_commit_v1', 'source': source_pin, 'program': identity,
                   'before_public_input_release': True, 'allocation': allocation,
                   'complete_query_shape': [574, 40, 182], 'historical_panel_only': True}
    publish(output / 'COMMIT.json', encoded(publication))
    return identity


def public_mounts(root):
    """Only declarations are read here; concrete provider authenticates file bodies."""
    values = assets()['public']
    need(set(values) == set(PUBLIC), 'Exactly three original public operands')
    return {PUBLIC[key]: file_mount(Path(root) / row['path'], {k: row[k] for k in ('bytes', 'sha256')}, 'input')
            for key, row in values.items()}


class Native:
    def __init__(self, config, policy, output, source_pin, origin, deadline):
        self.config, self.policy, self.output, self.source = config, policy, output, source_pin
        self.origin, self.deadline = origin, deadline

    def produce(self, program_pin):
        phase = uuid.uuid4().hex
        command = ['/usr/local/bin/python', '-I', '-B', '/library/worker.py']
        mounts = public_mounts(self.config['assets_root'])
        mounts.update({'/program/program.py': file_mount(self.output / 'program.py', program_pin, 'program'),
                       '/library/worker.py': file_mount(HERE / 'worker.py', pin(capture(HERE / 'worker.py', 32768)), 'program')})
        need(len(mounts) == 5, 'Only three original public operands, programme and transport worker')
        exposure = {'schema': 'osl_transport_exposure_v1', 'role': 'A', 'image': self.config['image'],
                    'source': self.source, 'command': command, 'mounts': mount_identity(mounts),
                    'approved_image_inventory_sha256': self.policy['image_inventory_sha256'],
                    'boundary_audit': self.config['mechanical_policy_pin'], 'role_boundary_verified': True}
        exposure_path = self.output / 'EXPOSURE.json'
        exposure_pin = publish(exposure_path, encoded(exposure))
        provider = Provider(self.config['control_root'], self.config['quarantine_root'], self.config['docker_binary'],
                            self.config['docker_socket'], pin(capture(HERE / 'transport/SOURCE_MANIFEST.json', 32768)),
                            {exposure_pin['sha256']: str(exposure_path)}, LIMITS['source_read_bytes'] + 1048576,
                            LIMITS['host_write_bytes'])
        request = {'schema': 'osl_owned_phase_request_v1', 'phase_id': phase, 'action': 'held_attempt', 'role': 'A',
                   'image': self.config['image'], 'command': command, 'workdir': '/work', 'source': self.source,
                   'exposure': exposure_pin, 'clock': {'origin': self.origin, 'phase_deadline': self.deadline - 80},
                   'resources': LIMITS.copy(), 'output': {'kind': 'generic', 'manifest': 'OUTPUTS.json'}}
        publish(self.output / 'CANDIDATE_REQUEST.json', encoded(request))
        result = provider.execute_phase(request, mounts, self.deadline, lambda *_: None)
        observed = provider.observe(phase, pin(encoded(request))['sha256'], result['receipt_pin'], self.deadline)
        receipt = observed['receipt']
        need(receipt['status'] == 'captured' and receipt['producer_closed_before_capture'] is True
             and receipt['all_native_resources_closed'] is True and receipt['cli_reaped'] is True
             and receipt['error'] is None and receipt['natural_exit']['ExitCode'] == 0
             and receipt['natural_exit']['OOMKilled'] is False, 'Observed successful stopped producer capture')
        need(receipt['source'] == self.source and receipt['image'] == self.config['image']
             and receipt['role'] == 'A' and receipt['exposure'] == exposure_pin
             and receipt['input_before'] == receipt['input_after'], 'Exact complete source/input/exposure receipt')
        directory = ordinary(receipt['quarantine_root'])
        need(directory == ordinary(Path(self.config['quarantine_root']) / phase), 'Exact captured directory')
        inventory = receipt['output_inventory']
        need(inventory['complete'] is True and set(inventory['files']) == {'predictions.npz', 'RESULT.json', 'OUTPUTS.json'},
             'Complete opaque output inventory')
        need(decode(capture(directory / 'RESULT.json', 16384, inventory['files']['RESULT.json'])) ==
             {'schema': 'neural018_program_exit_v1', 'candidate_exit_code': 0}, 'Successful programme result')
        submission = directory / 'predictions.npz'
        capture(submission, MAX_OUTPUT, inventory['files']['predictions.npz'])
        return submission, {'phase': phase, 'receipt': result['receipt_pin'], 'receipt_path': result['receipt_path'],
                            'submission': inventory['files']['predictions.npz'], 'source': self.source,
                            'program': program_pin, 'producer_removed_before_capture': True,
                            'all_native_resources_closed': True}


def complete(config, output, source_pin, program_pin, backend, grader, deadline):
    authenticate(source_pin)
    capture(output / 'program.py', 200000, program_pin)
    submission, evidence = backend.produce(program_pin)
    need(evidence['source'] == source_pin and evidence['program'] == program_pin
         and evidence['producer_removed_before_capture'] is True and evidence['all_native_resources_closed'] is True,
         'Stopped same-program candidate required before private grader')
    authenticate(source_pin)
    capture(output / 'program.py', 200000, program_pin)
    prepare_grader_prediction(submission, evidence['submission'])
    publish(output / 'PREDICTION_COMMIT.json', encoded(evidence))
    need(time.monotonic() + 60 <= deadline, 'Entire original grader allowance remains')
    result = grader('score', submission, output / 'SCORE.json', config, deadline, source_pin)
    capture(submission, MAX_OUTPUT, evidence['submission'])
    need(result['status'] in ('scored', 'rejected_no_score'), 'Original grader disposition')
    if result['status'] == 'scored':
        need(set(result['signed_differences']) == set(assets()['reference_panel']), 'Retain all five signed comparisons')
    else:
        need(result['target_loader_invocations'] == 0, 'Invalid output rejected before private numerical targets')
    publish(output / 'COMPLETE.json', encoded({'schema': 'neural018_program_completion_v1', 'status': result['status'],
            'source': source_pin, 'program': program_pin, 'prediction_commit': pin(capture(output / 'PREDICTION_COMMIT.json', 32768)),
            'runtime_qualification_inherited': False, 'scientific_qualification': False, 'automatic_retry_authorized': False}))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('configuration', 'program', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args(argv)
    origin = time.monotonic()
    config, policy, allocation, source_pin = configuration(args.configuration)
    deadline = origin + allocation['new_whole_seconds']
    need(signal.getitimer(signal.ITIMER_REAL) == (0., 0.), 'No conflicting process timer')
    def hard(*unused):
        os._exit(124)
    def interrupted(*unused):
        signal.signal(signal.SIGALRM, hard)
        signal.setitimer(signal.ITIMER_REAL, max(.001, deadline - time.monotonic()))
        raise TimeoutError('Original work cutoff; preserve owned resource journal')
    signal.signal(signal.SIGALRM, interrupted)
    signal.setitimer(signal.ITIMER_REAL, max(.001, deadline - 10 - time.monotonic()))
    output, committed = ordinary(args.output), False
    try:
        identity = commit(args.program, output, source_pin, allocation)
        committed = True
        backend = Native(config, policy, output, source_pin, origin, deadline)
        result = complete(config, output, source_pin, identity, backend, grade.execute, deadline - 10)
        return 0 if result['status'] == 'scored' else 2
    except BaseException as exc:
        if committed:
            publish(output / 'FAILURE.json', encoded({'schema': 'neural018_program_failure_v1', 'error_type': type(exc).__name__,
                    'source': source_pin, 'no_automatic_retry': True, 'cleanup': 'Consult exact provider and grader ownership receipts; absence is not inferred.',
                    'historical_charge_seconds': 910, 'new_allocation_seconds': 140}))
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == '__main__':
    raise SystemExit(main())
