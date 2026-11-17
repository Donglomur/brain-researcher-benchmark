"""Future isolated packet worker; saved closed fit002 outputs, never NWB or refits."""
import time
START = time.monotonic()
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
    # Cooperative85s compute; the exercised host90s attach bound remains authoritative.
    # This does not claim to preempt a NumPy call or replace host ownership/reaping.
    io.need(time.monotonic() < START + 85, 'Original cooperative packet compute deadline')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--contract', required=True); p.add_argument('--contract-sha256', required=True)
    p.add_argument('--out', required=True); args = p.parse_args()
    reads = dict(closed_receipt_read_attempts=0, closed_receipt_reads_completed=0,
                 saved_array_open_attempts=0, saved_array_captures_completed=0,
                 saved_archive_decodes_completed=0, passive_training_body_reads=0,
                 raw_nwb_reads=0, full_private_projection_body_reads=0)
    result = dict(schema='neural022_finite_packet_receipt_v1', status='packet_incomplete_preserved',
                  candidate_id='NEURAL-022', source_contract=None, source_worker_receipt=None,
                  generated_checks=None, generated_controls_started=False,
                  public_training_rows=0, public_query_rows=0, private_query_targets=0,
                  reused_reference_methods=[], models_fitted=0, new_predictions_computed=0,
                  passive_training_labels_read=0, raw_nwb_reads=0,
                  full_private_projection_body_read=False, empirical_input_counters=reads,
                  files={}, phase='public_packet', stage='source_admission', research_qualified=False, new_benchmark_IDs=0)
    rc = 2
    try:
        tick()
        contract, contract_pin = io.source_contract(args.contract, args.contract_sha256, candidate.strict, 'project.py')
        result.update(source_contract=contract_pin, source_worker_receipt=contract['closed_worker_receipt'],
                      stage='generated_controls', generated_controls_started=True)
        tick(); generated = controls.run(); tick()
        io.need(generated['count'] == contract['generated_checks']['count']
                and generated['names_sha256'] == contract['generated_checks']['names_sha256'],
                'Complete source-fixed generated controls before empirical input access')
        result['generated_checks'] = generated; result['stage'] = 'closed_receipt'
        reads['closed_receipt_read_attempts'] += 1
        receipt = candidate.strict(io.capture('/input/receipt.json', contract['closed_worker_receipt'], 65536))
        reads['closed_receipt_reads_completed'] += 1; tick()
        io.need(receipt['status'] == 'complete_private_projection_and62fit_reference'
                and receipt['all_predictions_committed_before_private_grade'] is True
                and receipt['qualified_ridge_fits'] == 62 and receipt['predictions'] == 644,
                'Actual closed reference stage and immutable prediction provenance')
        originals = {}
        io.need(set(contract['saved_inputs']) == {'active', 'query', 'target', 'references'},
                'Only four exact saved arrays; no passive training or raw source')
        for kind, item in contract['saved_inputs'].items():
            result['stage'] = 'saved_array_' + kind; tick()
            io.need(receipt['files'][item['original_filename']] == item['pin'], 'Actual receipt input commitment')
            reads['saved_array_open_attempts'] += 1
            raw = io.capture('/input/' + item['mount_name'], item['pin'], item['cap'])
            reads['saved_array_captures_completed'] += 1; tick()
            originals[kind] = io.npz(raw, io.schema(kind, candidate.METHODS))
            reads['saved_archive_decodes_completed'] += 1; tick()
        result['stage'] = 'sanitized_projection'
        active, query, cases, private = packet.sanitize(originals['active'], originals['query'],
                                                       originals['target'], originals['references'])
        result.update(public_training_rows=141, public_query_rows=92, private_query_targets=92)
        tick(); result['stage'] = 'unchanged_reference_score_check'
        candidate.fixed_scores(candidate.cases(cases), packet.private_lists(private), held_scorer.score,
                               contract['expected_fixed_reference'])
        result['reused_reference_methods'] = list(candidate.METHODS)
        tick(); result['stage'] = 'packet_publication'
        files = result['files']
        for name, values in (('training.npz', active), ('queries.npz', query), ('reference.private.npz', private)):
            tick()
            files[name] = io.output(args.out, name, io.encoded_npz(values), contract['packet_output_caps'][name])
        tick(); files['cases.json'] = io.output(args.out, 'cases.json', io.encoded_json(cases), 16384)
        task = io.capture(Path(args.contract).parent / 'TASK.md', contract['local_sources']['TASK.md'], 16384)
        tick(); files['TASK.md'] = io.output(args.out, 'TASK.md', task, 16384)
        io.need(sum(v['bytes'] for v in files.values()) + 65536 <= 1200000,
                'Complete packet publication reserve')
        tick(); result.update(status='complete_reused_closed_projection', stage='complete'); rc = 0
    except Exception as error:
        result.update(error=type(error).__name__ + ': ' + str(error)[:1200],
                      partial_progress_preserved=True)
    finally:
        result['worker_elapsed_seconds'] = time.monotonic() - START
        result['clock_scope'] = '85s cooperative compute /90s hard host attach; no reset after imports'
        # A failure here leaves partial outputs for outer recovery, not a fabricated receipt.
        io.need(result['worker_elapsed_seconds'] < 90, 'Original packet finalization deadline')
        pin = io.output(args.out, 'receipt.json', io.encoded_json(result), 65536)
        print(io.encoded_json({'status': result['status'], 'receipt': pin}).decode(), end='', flush=True)
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
