"""Forty isolated contexts of one frozen submitted program, then protected scoring.

This is a program task on processed morphology/coactivity measurements. Actual
Docker qualification and authentic execution require a separately reviewed run.
"""
import argparse
from pathlib import Path
import secrets
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import decode, dependencies, encoded, need, pin, read, write
from docker_backend import Deadline, DockerBackend


def validate_method(value, program):
    need(type(value) is dict and set(value) == {'schema', 'program', 'method',
         'same_method_across_views', 'training_only_selection', 'image_inventory_review_sha256',
         'method_review_sha256'} and value['schema'] == 'neural031_frozen_program_method_v1'
         and value['program'] == pin(program) and type(value['method']) is str
         and 0 < len(value['method']) <= 16384
         and value['same_method_across_views'] is True
         and value['training_only_selection'] is True,
         'Frozen program and explicit matched training-only method declaration required')
    for key in ('image_inventory_review_sha256', 'method_review_sha256'):
        digest = value[key]
        need(type(digest) is str and len(digest) == 64
             and all(c in '0123456789abcdef' for c in digest), 'External review digest required')
    return decode(encoded(value))


def execute(store_root, program_path, output_root, image_id, method_document, *,
            backend=None, clock=time.monotonic, _source=None, _generated=False):
    """Produce a closed all-context collection; this function has no target path.

    The private generated seam permits controlled command simulation and source
    descriptors. It is not a native runtime or source-authentication attestation.
    """
    deadline = Deadline(clock=clock, seconds=480)
    backend = DockerBackend() if backend is None else backend
    need(type(_generated) is bool and (_generated or
         (type(backend) is DockerBackend and backend.real_transport and _source is None)),
         'Production requires actual Docker transport and unchanged public source roster')
    root = Path(output_root)
    need(root.is_absolute() and not root.exists() and not root.is_symlink()
         and root.parent.is_dir(), 'Fresh absolute operator output directory required')
    program = read(program_path, 1048576)
    method = validate_method(method_document, program)
    program_pin = pin(program)
    root.mkdir(mode=0o700)
    frozen = root / 'submission.py'
    write(frozen, program, 1048576, 0o444)
    method_pin = write(root / 'method.json', encoded(method), 32768)
    contexts, predictions = root / 'contexts', root / 'predictions'
    contexts.mkdir(mode=0o700); predictions.mkdir(mode=0o700)
    delivery, endpoint, _ = dependencies()
    source = delivery.inputs() if _source is None else delivery.validate_inputs(_source)
    batch = secrets.token_hex(12)
    records = []
    try:
        deadline.left()
        backend.verify_image(image_id, deadline)
        support = delivery.load_support(store_root, source)
        for fold in range(20):
            for view, suffix in (('baseline', 'b'), ('neural', 'n')):
                deadline.left()
                read(frozen, 1048576, program_pin)
                context = contexts / f'fold{fold:02d}-{view}'
                exported = delivery.export_context(store_root, context, fold, view, source)
                need(set(p.name for p in context.iterdir()) == {'data.npz', 'manifest.json'},
                     'Selected context contains only two public files')
                expected = source['paired_views'][2 * fold + (view == 'neural')]
                for key, name in (('data', 'data.npz'), ('manifest', 'manifest.json')):
                    read(context / name, 262144, expected[key])
                context.chmod(0o555)
                spec = {'fold': fold, 'view': view, 'batch': batch,
                        'name': f'n031-{batch}-{fold:02d}-{suffix}', 'image': image_id,
                        'mounts': [(str(context / 'data.npz'), '/input/data.npz'),
                                   (str(context / 'manifest.json'), '/input/manifest.json'),
                                   (str(frozen), '/program/submission.py')],
                        'program_pin': program_pin, 'input_pins': {k: expected[k] for k in ('data', 'manifest')}}
                body = backend.run_context(spec, deadline)
                deadline.left()
                need(type(body) is bytes and 0 < len(body) <= 131072, 'Bounded completed context output')
                read(frozen, 1048576, program_pin)
                for key, name in (('data', 'data.npz'), ('manifest', 'manifest.json')):
                    read(context / name, 262144, expected[key])
                # The accepted all-output validator is called later. Strict JSON
                # parsing now rejects malformed captures without a target open.
                decode(body)
                directory = predictions / f'fold{fold:02d}' / view
                directory.mkdir(mode=0o700, parents=True)
                output_pin = write(directory / 'predictions.json', body, 131072)
                records.append({'fold': fold, 'view': view, 'container_name': spec['name'],
                                'program': program_pin, 'input_files': exported['files'],
                                'prediction': output_pin, 'producer_removed_before_commit': True})
        backend.absent_all(deadline)
        collected = delivery.collect(store_root, predictions, root / 'collection', source)
        # Includes final collection, validation and the last removal in the same
        # original480-second clock. Scoring is a later protected operation.
        deadline.left()
        bundle = decode(read(root / 'collection/submission.json', 6291456))
        endpoint.validate_all(bundle, support)
        read(frozen, 1048576, program_pin)
        receipt = {'schema': 'neural031_closed_program_batch_v1', 'candidate_id': 'NEURAL-031',
                   'status': 'complete', 'scope': 'generated_command_simulation' if _generated else 'actual_docker_execution',
                   'independent_runtime_qualification': False,
                   'batch_deadline_seconds': 480, 'batch_wall_seconds': deadline.elapsed(),
                   'contexts': records, 'same_program': program_pin, 'method': method_pin,
                   'method_declaration_is_independent_matched_procedure_proof': False,
                   'image_id': image_id, 'collection': collected, 'private_targets_opened': 0,
                   'producer_absence_observed_for_all_contexts': True,
                   'backend_events': backend.events}
        write(root / 'BATCH.json', encoded(receipt), 1048576)
        deadline.left()
        return receipt
    except BaseException as error:
        if (root / 'BATCH.json').exists():
            (root / 'BATCH.json').rename(root / 'UNACCEPTED_BATCH.json')
        failure = {'schema': 'neural031_failed_program_batch_v1', 'candidate_id': 'NEURAL-031',
                   'status': 'failed', 'completed_captures': len(records), 'error_type': type(error).__name__,
                   'error': str(error)[:2048], 'batch_wall_seconds': deadline.elapsed(),
                   'batch_deadline_seconds': 480, 'private_targets_opened': 0,
                   'scope': 'generated_command_simulation' if _generated else 'actual_docker_execution',
                   'backend_events': backend.events, 'automatic_retry': False}
        if not (root / 'FAILURE.json').exists():
            write(root / 'FAILURE.json', encoded(failure), 1048576)
        raise


def run_and_score(store_root, program_path, output_root, image_id, method_document,
                  target_path, targets_sha256, **kwargs):
    """Protected scorer opens targets only after this invocation closes all40."""
    need(type(targets_sha256) is str and len(targets_sha256) == 64
         and all(c in '0123456789abcdef' for c in targets_sha256), 'Independently frozen target digest required')
    receipt = execute(store_root, program_path, output_root, image_id, method_document, **kwargs)
    need(receipt['status'] == 'complete' and len(receipt['contexts']) == 40
         and receipt['producer_absence_observed_for_all_contexts'] is True,
         'Complete closed current invocation before private scoring')
    _, _, scorer = dependencies()
    root = Path(output_root)
    # The unchanged scorer independently validates the complete public bundle
    # before its first target open and requires the externally pinned target SHA.
    result = scorer.run(root / 'collection/support.json', root / 'collection/submission.json',
                        target_path, targets_sha256)
    write(root / 'SCORE.json', encoded(result), 1048576)
    return {'batch': receipt, 'score': result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store-root', required=True)
    parser.add_argument('--program', required=True)
    parser.add_argument('--output-root', required=True)
    parser.add_argument('--image-id', required=True)
    parser.add_argument('--method-json', required=True)
    parser.add_argument('--targets')
    parser.add_argument('--targets-sha256')
    args = parser.parse_args()
    need(bool(args.targets) == bool(args.targets_sha256), 'Both target path and independently frozen digest required')
    method = decode(read(args.method_json, 32768))
    values = (args.store_root, args.program, args.output_root, args.image_id, method)
    if args.targets:
        run_and_score(*values, args.targets, args.targets_sha256)
    else:
        execute(*values)


if __name__ == '__main__':
    main()
