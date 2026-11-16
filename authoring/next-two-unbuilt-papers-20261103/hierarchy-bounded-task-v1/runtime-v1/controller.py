"""One public hierarchy producer, durable absence/outcome, then the declared JSON grader."""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import argparse
import json
from pathlib import Path
import time
from support import ID, api, assets, grade_config, need, ordinary, read, runtime_manifest, save, verify_grade_config
from panel_recovery import inventory, recover
from files import freeze, pin


def main(args):
    run = args.run.absolute()
    manifest = runtime_manifest(run)
    freeze({'freeze_sha256':manifest['source_freeze_sha256']})
    lib = api()
    budget = lib['HostBudget'](run, 22000000, 8000000)
    result = {'candidate_id': ID, 'status': 'operator_error', 'handled_candidate_outcome': False,
              'private_grade_dispatched': False, 'private_reference_reads': 0,
              'all_workers_absent': False, 'candidate_program_executed': False,
              'external_model_calls': 0, 'scientific_success': None}
    try:
        need(time.monotonic() < args.work_end - 690, 'Full630s unit orchestration and60s grade room')
        end = min(args.work_end - 60, time.monotonic() + 630)
        result['candidate_program_executed'] = None
        value = lib['run_unit'](run / 'program.py', manifest['program_sha256'], manifest['unit'],
            run / 'unit', budget, end, end, None, ID, lambda *unused: None)
        result['candidate_program_executed'] = 'producer' in value
        logs = value.get('candidate_logs')
        if logs is not None:
            result['candidate_stdout'] = {'path': 'unit/execution.json', 'field': 'candidate_logs.stdout',
                'retained_utf8_pin': pin(logs['stdout'].encode('utf-8')),
                'captured_stdout_bytes': logs['captured_stdout_bytes'],
                'capture_truncated': logs['capture_truncated']}
        need(value['all_owned_absent'] is True, 'Producer cleanup completed')
        owned, errors = inventory(run)
        need(not errors, 'Exact resource inventory')
        absence = [recover(run, folder, item, lib['BaseEngine'](args.work_end - 60, folder, budget), budget)
                   for folder, item in owned]
        save(run / 'unit/independent_absence.json', {'resources': absence}, budget)
        need(len(absence) == 3 and all(r['absence_verified'] for r in absence), 'Three exact resources absent before private inputs')
        normal = ('unit_committed', 'invalid_unit_submission', 'output_boundary_rejected', 'candidate_program_failed')
        timeout = value['status'] == 'execution_failed_preserved' and value.get('candidate_wait_timed_out') is True
        need(value['status'] in normal or timeout, 'Infrastructure failure is not a candidate outcome')
        outcome = {'candidate_id': ID, 'program_sha256': manifest['program_sha256'], 'unit_status': value['status'],
                   'output': value.get('output'), 'all_unit_resources_absent': True,
                   'before_any_private_grade': True, 'producer_output_commit_sha256': value.get('commit_sha256')}
        result['outcome_commit_sha256'] = save(run / 'unit/outcome_commit.json', outcome, budget)
        result.update(unit_status=value['status'], all_workers_absent=True)
        if value['status'] != 'unit_committed':
            score = {'candidate_id': ID, 'status': 'candidate_timeout' if timeout else value['status'],
                     'primary_metric': None, 'private_reference_reads': 0, 'scientific_success': None}
        else:
            a = assets()
            save(run / 'invocation.json', {'schema_version':1,'candidate_id':ID,'submission':outcome['output'],
                'output_schema':{k:a['grader_sources']['OUTPUT_SCHEMA.json'][k] for k in ('bytes','sha256')},
                'references':{k:a['grader_sources']['REFERENCES.json'][k] for k in ('bytes','sha256')}}, budget)
            verify_grade_config(run)
            (run / 'metadata').mkdir(mode=0o755)
            result['private_grade_dispatched'] = True
            result['private_reference_reads'] = None  # Unknown until complete verified grade returns.
            graded = lib['run_grade'](run / 'unit/submission.json', 'ordinary', grade_config(run), run,
                                     budget, args.work_end, False)
            score = graded['result']
            need(score['status'] in ('scored', 'invalid_submission'),
                 'Central scored or public-invalid outcome, no performance/significance floor')
            result['private_reference_reads'] = score['private_reference_reads']
        # Full score precedes any fixed-control qualification predicate.
        if result['private_grade_dispatched']:
            body=ordinary(run/'grade/score.json',1000000)
            budget.write(run/'score.json',body,receipt=True,mode=0o444)
            result['result_sha256']=pin(body)['sha256']
        else:
            result['result_sha256']=save(run/'score.json',score,budget,1000000)
        result['status'] = score['status']
        result['handled_candidate_outcome'] = True
    except BaseException as error:
        result.update(status='operator_error', error=repr(error)[:2000])
    finally:
        save(run / 'controller_result.json', result, budget, 32768)
    return 0 if result['handled_candidate_outcome'] and result['all_workers_absent'] else 2


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--work-end', type=float, required=True)
    raise SystemExit(main(p.parse_args()))
