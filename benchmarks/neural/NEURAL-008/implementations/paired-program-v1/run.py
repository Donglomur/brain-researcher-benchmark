#!/usr/bin/env python3
"""Original finite paired programme, with a concrete offline Docker boundary."""
import argparse
from pathlib import Path
import sys
import time
import uuid

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import ARMS, REPO, decode, encoded, file_mount, need, ordinary, pin, publish, read, scorer, source
from prepare import admit

ENGINE = REPO / 'benchmarks/neural/NEURAL-007/implementations/whole-night-programme/program'
sys.path.insert(0, str(ENGINE))
from vendor_transport.provider import Provider
from vendor_transport.bounds import mount_identity

LIMITS = {'setup_seconds': 20, 'producer_seconds': 20, 'capture_seconds': 10, 'cleanup_seconds': 10,
          'memory_bytes': 3 * 1024**3, 'cpu_nanos': 1750000000, 'pids': 64, 'scratch_bytes': 64 * 1024**2,
          'max_files': 3, 'max_directories': 1, 'max_file_bytes': 1048576, 'max_output_bytes': 2 * 1024**2,
          'manifest_bytes': 16384, 'max_cli_calls': 128, 'max_cli_bytes': 4 * 1024**2,
          'inventory_bytes': 65536, 'source_read_bytes': 48 * 1024**2, 'host_write_bytes': 8 * 1024**2}


def commit(program, method, claims, output):
    """No arm input is opened until one source/method/claim commitment exists."""
    output = ordinary(output)
    need(not output.exists() and output.parent.is_dir(), 'Fresh existing-parent operator output')
    program_body, method_body, claim_body = read(program, 200000), read(method, 32768), read(claims, 16384)
    description = decode(method_body)
    need(set(description) == {'schema_version', 'method_id', 'method_description', 'training_policy', 'limitations'}
         and type(description['schema_version']) is int and description['schema_version'] == 1,
         'Original method declaration')
    for key in ('method_id', 'method_description', 'training_policy', 'limitations'):
        need(type(description[key]) is str and 0 < len(description[key]) <= 4096, 'Bounded nonempty method statement')
    assessment = scorer()
    assessment.paired_core.check_claims(decode(claim_body), assessment.SPEC)
    output.mkdir(mode=0o700)
    pins = {name: publish(output / name, body) for name, body in
            (('program.py', program_body), ('method.json', method_body), ('claims.json', claim_body))}
    (output / 'program.py').chmod(0o444)
    publication = {'schema': 'neural008_same_program_commit_v1', 'files': pins,
                   'arms': list(ARMS), 'people_per_arm': 2, 'epochs_per_arm': 5450,
                   'created_monotonic': time.monotonic(), 'inputs_released': False}
    publish(output / 'COMMIT.json', encoded(publication))
    return publication


class Native:
    """Task binding over unchanged accepted007 transport; no host fallback."""
    def __init__(self, config, output, clock, source_pin):
        need(config['schema'] == 'neural008_native_configuration_v1', 'Exact native configuration')
        self.config, self.output, self.clock, self.source = config, output, clock, source_pin
        self.policy = decode(read(config['mechanical_policy_path'], 32768, config['mechanical_policy_pin']))
        need(self.policy == {'schema': 'neural008_mechanical_boundary_v1',
                             'approved_rule': 'exact_original_paired_views_and_frozen_program_v1',
                             'source': source_pin, 'image': config['image'],
                             'image_inventory_sha256': self.policy.get('image_inventory_sha256')},
             'Independent pinned source/image/exposure review required')
        self.provider = None

    def run(self, arm, view, program_pin):
        phase = uuid.uuid4().hex
        role = 'A' if arm == ARMS[0] else 'B'
        command = ['/usr/local/bin/python', '-I', '-B', '/library/worker.py']
        mounts = {**view,
                  '/program/program.py': file_mount(self.output / 'program.py', program_pin, 'program'),
                  '/library/worker.py': file_mount(HERE / 'worker.py', pin(read(HERE / 'worker.py', 32768)), 'program')}
        need(len(mounts) == 17, 'Exactly fifteen public files plus frozen programme and worker')
        approval = {'schema': 'osl_transport_exposure_v1', 'role': role, 'image': self.config['image'],
                    'source': self.source, 'command': command, 'mounts': mount_identity(mounts),
                    'approved_image_inventory_sha256': self.policy['image_inventory_sha256'],
                    'boundary_audit': self.config['mechanical_policy_pin'], 'role_boundary_verified': True}
        exposure_path = self.output / (arm + '.exposure.json')
        exposure = publish(exposure_path, encoded(approval))
        if self.provider is None:
            self.provider = Provider(self.config['control_root'], self.config['quarantine_root'],
                self.config['docker_binary'], self.config['docker_socket'],
                pin(read(ENGINE / 'vendor_transport/SOURCE_MANIFEST.json', 32768)),
                {exposure['sha256']: str(exposure_path)}, 96 * 1024**2, 16 * 1024**2)
        else:
            self.provider.exposures[exposure['sha256']] = str(exposure_path)
        request = {'schema': 'osl_owned_phase_request_v1', 'phase_id': phase, 'action': 'held_attempt', 'role': role,
                   'image': self.config['image'], 'command': command, 'workdir': '/work', 'source': self.source,
                   'exposure': exposure, 'clock': {'origin': self.clock[0], 'phase_deadline': self.clock[1]},
                   'resources': LIMITS.copy(), 'output': {'kind': 'generic', 'manifest': 'OUTPUTS.json'}}
        # The provider persists its own bounded journal; avoid a second unbounded copy.
        result = self.provider.execute_phase(request, mounts, self.clock[1], lambda *_: None)
        observed = self.provider.observe(phase, pin(encoded(request))['sha256'], result['receipt_pin'], self.clock[1])
        receipt = observed['receipt']
        need(receipt['status'] == 'captured' and receipt['producer_closed_before_capture'] is True
             and receipt['all_native_resources_closed'] is True and receipt['cli_reaped'] is True
             and receipt['error'] is None and receipt['natural_exit']['ExitCode'] == 0
             and receipt['natural_exit']['OOMKilled'] is False, 'Observed removed producer and successful complete capture')
        need(receipt['source'] == self.source and receipt['role'] == role and receipt['image'] == self.config['image']
             and receipt['exposure'] == exposure and receipt['input_before'] == receipt['input_after'], 'Exact observed request/input binding')
        captured = ordinary(receipt['quarantine_root'])
        need(captured == ordinary(Path(self.config['quarantine_root']) / phase), 'Exact operator capture directory')
        inventory = receipt['output_inventory']
        need(inventory['complete'] is True and set(inventory['files']) == {'predictions.npz', 'RESULT.json', 'OUTPUTS.json'},
             'Exact complete captured participant outputs')
        need(decode(read(captured / 'RESULT.json', 16384, inventory['files']['RESULT.json'])) ==
             {'schema': 'neural008_program_exit_v1', 'candidate_exit_code': 0}, 'Original programme exit envelope')
        body = read(captured / 'predictions.npz', 1048576, inventory['files']['predictions.npz'])
        return body, {'phase_id': phase, 'request': pin(encoded(request)), 'receipt': result['receipt_pin'],
                      'receipt_path': result['receipt_path'], 'captured_output': inventory['files']['predictions.npz'],
                      'producer_removed_before_capture': True, 'all_native_resources_closed': True,
                      'source': self.source, 'program': program_pin}


def complete(output, commitment, views, backend, source_pin, target_loader=None):
    """Trusted orchestration seam for generated controls; CLI always uses Native."""
    output = ordinary(output)
    submission = output / 'submission'
    submission.mkdir(mode=0o700)
    previous = pin(read(output / 'COMMIT.json', 32768))
    joins = []
    assessment = scorer()
    for arm in ARMS:
        source(source_pin)
        read(output / 'program.py', 200000, commitment['files']['program.py'])
        body, evidence = backend.run(arm, views[arm], commitment['files']['program.py'])
        # Stop/capture is already observed before even public-format parsing.
        need(evidence['producer_removed_before_capture'] is True and evidence['all_native_resources_closed'] is True
             and evidence['program'] == commitment['files']['program.py'] and evidence['source'] == source_pin,
             'Same programme and removed producer for each independent arm')
        source(source_pin)
        read(output / 'program.py', 200000, commitment['files']['program.py'])
        output_pin = publish(submission / (arm + '.npz'), body)
        need(output_pin == evidence['captured_output'], 'Captured bytes preserved without modification')
        assessment.adapter.validate_submission(submission / (arm + '.npz'), output_pin, assessment.SPEC)
        joined = {'schema': 'neural008_arm_join_v1', 'arm': arm, 'previous': previous, 'evidence': evidence,
                  'output': output_pin, 'private_loader_calls': 0}
        previous = publish(output / (arm + '.join.json'), encoded(joined))
        joins.append(previous)
    publish(submission / 'claims.json', read(output / 'claims.json', 16384, commitment['files']['claims.json']))
    # Persist the complete paired freeze before permitting even one target read.
    freeze = assessment.freeze_submission(submission)
    publish(output / 'PAIRED_FREEZE.json', encoded({'schema': 'neural008_paired_freeze_v1', 'joins': joins,
                                                'files': freeze, 'both_producers_removed': True}))
    result = assessment.assess(submission, target_loader)
    need(result['submission_freeze'] == freeze, 'No mutation between freeze and scoring')
    publish(output / 'ASSESSMENT.json', encoded(result))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('assets-root', 'program', 'method', 'claims', 'configuration', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--targets', type=Path, help='Optional operator-only original three-file private target directory')
    args = parser.parse_args(argv)
    started = time.monotonic()
    config = decode(read(args.configuration, 32768))
    source_pin = source(config['source'])
    committed = commit(args.program, args.method, args.claims, args.output)
    try:
        views = admit(args.assets_root)
        backend = Native(config, ordinary(args.output), (started, started + 150), source_pin)
        loader = None if args.targets is None else lambda: scorer().historical_targets(args.targets)
        complete(args.output, committed, views, backend, source_pin, loader)
    except BaseException as exc:
        publish(args.output / 'FAILURE.json', encoded({'schema': 'neural008_failed_attempt_v1', 'error_type': type(exc).__name__,
                'automatic_retry_authorized': False, 'native_cleanup': 'inspect exact provider receipt; do not assume absence',
                'private_targets_may_have_been_read': (args.output / 'PAIRED_FREEZE.json').exists() and args.targets is not None}))
        raise


if __name__ == '__main__':
    main()
