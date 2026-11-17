"""Future isolated grader: complete public validation before any private packet read."""
import time
START = time.monotonic()
CPU_START = time.process_time()
import argparse
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import candidate
import held_scorer
import io_support as io
import packet
import controls


def tick():
    io.need(time.monotonic() - START < 80 and time.process_time() - CPU_START < 20,
            'Inherited grader phase/CPU cooperative backstop; enclosing80s phase and20/22CPU limit govern')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--contract', required=True); p.add_argument('--contract-sha256', required=True)
    p.add_argument('--inputs', required=True); p.add_argument('--inputs-sha256', required=True)
    p.add_argument('--out', required=True); args = p.parse_args()
    tick(); contract, contract_pin = io.source_contract(args.contract, args.contract_sha256, candidate.strict, 'grade.py')
    path = Path(args.inputs)
    inputs = candidate.strict(io.capture(path, {'bytes': path.lstat().st_size,
                            'sha256': args.inputs_sha256}, 32768))
    io.need(set(inputs) == {'schema', 'source_contract', 'packet_receipt', 'candidate',
                            'candidate_resources_absent', 'prediction_commit_before_private_grade'}
            and inputs['schema'] == 'neural022_finite_grade_inputs_v1'
            and inputs['source_contract'] == contract_pin
            and inputs['candidate_resources_absent'] is True
            and inputs['prediction_commit_before_private_grade'] is True,
            'Exact source and root-observed stopped candidate commitment; not self-authorizing')
    tick(); generated = controls.run(); tick()
    io.need(generated['count'] == contract['generated_checks']['count']
            and generated['names_sha256'] == contract['generated_checks']['names_sha256'],
            'Complete source-fixed generated controls before empirical packet access')
    receipt = candidate.strict(io.capture('/packet/receipt.json', inputs['packet_receipt'], 65536))
    io.need(receipt['schema'] == 'neural022_finite_packet_receipt_v1'
            and receipt['status'] == 'complete_reused_closed_projection'
            and receipt['source_contract'] == contract_pin
            and receipt['source_worker_receipt'] == contract['closed_worker_receipt']
            and receipt['models_fitted'] == receipt['new_predictions_computed'] == 0,
            'Exact committed reused packet receipt; runtime separately verifies its actual closure')
    public = candidate.strict(io.capture('/public/cases.json', receipt['files']['cases.json'], 16384))
    raw = io.capture('/submission/predictions.json', inputs['candidate'], candidate.MAX_SUBMISSION_BYTES)
    reads = dict(private_identity_attempts=0, private_identity_checks_completed=0,
                 private_body_open_attempts=0, private_body_capture_completed=0,
                 private_archive_decodes_completed=0, private_target_arrays_read=0,
                 private_reference_arrays_read=0)
    def load_private():
        tick()
        reads['private_identity_attempts'] += 1
        reads['private_body_open_attempts'] += 1
        body = io.capture('/private/reference.npz', receipt['files']['reference.private.npz'], 65536)
        reads['private_identity_checks_completed'] += 1
        reads['private_body_capture_completed'] += 1
        value = io.npz(body, io.schema('private', candidate.METHODS))
        reads.update(private_archive_decodes_completed=1, private_target_arrays_read=1,
                     private_reference_arrays_read=7)
        tick(); return packet.private_lists(value)
    result = candidate.evaluate(raw, public, load_private, held_scorer.score,
                                contract['expected_fixed_reference'])
    result.update(schema='neural022_finite_candidate_score_v1', submission_commitment=inputs['candidate'],
                  source_contract=contract_pin, packet_receipt=inputs['packet_receipt'],
                  generated_checks=generated, candidate_code_executed_by_grader=False,
                  empirical_private_read_counters=reads)
    if result['status'] == 'invalid_submission':
        io.need(not any(reads.values()) and result['private_target_loads'] == 0,
                'Malformed final row rejected before all private target/reference body operations')
    tick()
    result['worker_elapsed_seconds'] = time.monotonic() - START
    result['clock_scope'] = 'Controls included in inherited80s enclosing grade phase and20/22CPU limit; no new allowance'
    pin = io.output(args.out, 'score.json', io.encoded_json(result), 65536)
    print(io.encoded_json({'status': result['status'], 'score': pin,
                          'private_target_loads': result['private_target_loads']}).decode(),
          end='', flush=True)


if __name__ == '__main__':
    main()
