"""ERP persistent stream, opaque neural frames, then producer-absent private grade."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
import uuid
from common import Engine, HostBudget, HERE, ROOT, need, regular, pin, lock, save, sync, strict, assets, output_hashes
from choice_profile import IMAGE, StreamEngine, mapping
from protocol import Gate, answer, decode, wire, wrapped
from stream import Stream
from preparation_admission import validate_preparation
import choice_recovery as recovery


def remove(run, folder, engine, budget):
    return [recovery.recover(run, f, row, engine, budget) for f, row in recovery.inventory(run) if f == folder]


def trusted(run, label, budget, end, environment, seconds):
    folder = run / label
    if label == 'grade':
        need(folder.is_dir() and {p.name for p in folder.iterdir()} == {'invocation.json', 'operator_assets.json'}, 'Exact grader precommit')
    else:
        folder.mkdir(mode=0o700)
    engine = StreamEngine(end, folder, budget)
    name = 'neural059-open-' + label + '-' + uuid.uuid4().hex
    record = {'label': label, 'status': 'started', 'trusted_work_extent_unknown': True}
    try:
        need(end - time.monotonic() >= seconds + 5, 'Full trusted attachment and removal allowance')
        _, record['boundary'] = engine.create_task(name, label, mapping(run, label), environment)
        need(end - time.monotonic() >= seconds + 3, 'Unshortened trusted attachment')
        reply = engine.run(['start', '--attach', name], timeout=seconds, cap=150000)
        budget.write(folder / 'stdout.json', reply.stdout, receipt=True, mode=0o444)
        save(folder / 'streams.json', {'returncode': reply.returncode, 'stderr': reply.stderr.decode(errors='replace')}, budget)
        report = strict(reply.stdout)
        record.update(status=report['status'], trusted_work_extent_unknown=False,
                      retained_report=pin(folder / 'stdout.json', 150000))
        state = engine.inspect('container', name)['State']
        need(state['Status'] == 'exited' and state['Running'] is False and state['Pid'] == 0
             and state['OOMKilled'] is False and state['ExitCode'] == reply.returncode and not reply.stderr,
             'Exact stopped trusted worker identity')
        need((label == 'prepare' and reply.returncode == 0 and report['status'] == 'choice_open_prediction_packet_prepared')
             or (label == 'grade' and (reply.returncode, report['status']) in ((0, 'scored'), (2, 'invalid_submission'))),
             'Trusted complete disposition')
        return report
    finally:
        try: record['cleanup'] = remove(run, folder, engine, budget)
        except BaseException as error: record['cleanup'] = [{'absence_verified': False, 'error': repr(error)[:1000]}]
        save(folder / 'execution.json', record, budget)
        need(record['cleanup'] and all(r['absence_verified'] for r in record['cleanup']), 'Trusted phase absent before next phase')


def participant(run, entries, budget, end, environment):
    folder = run / 'candidate'; folder.mkdir(mode=0o700)
    engine = StreamEngine(end, folder, budget); name = 'neural059-open-candidate-' + uuid.uuid4().hex
    gate = Gate(entries); stream = None; rows = []; journal = None
    result = {'status': 'started', 'queries_expected': 93, 'committed': 0, 'attach_cli_reaped': False,
              'stream_start_attempted': False, 'attach_dispatch_or_reaping_extent_unknown': False,
              'create_verified': False, 'infrastructure_failure': False, 'candidate_fit_count': None,
              'host_neural_vector_decodes': 0, 'private_grading_reads': 0, 'errors': []}
    try:
        need(end - time.monotonic() >= 65, 'Full60-second candidate and immediate removal')
        _, result['boundary'] = engine.create_task(name, 'candidate', mapping(run, 'candidate'), environment)
        result['create_verified'] = True
        need(end - time.monotonic() >= 63, 'Unshortened candidate wall allowance')
        candidate_end = time.monotonic() + 60
        result.update(stream_start_attempted=True, attach_dispatch_or_reaping_extent_unknown=True)
        stream = Stream(name, candidate_end)
        need(decode(stream.line()) == {'status': 'ready'}, 'Exact startup handshake')
        stream.send(wire({'protocol': 'NEURAL059-sequential-v1', 'status': 'initialize', 'queries': 93,
                          'probability': 'left', 'label_encoding': {'right': 0, 'left': 1}}))
        need(decode(stream.line()) == {'status': 'initialized', 'protocol': 'NEURAL059-sequential-v1'}, 'Exact protocol acknowledgement')
        path = folder / 'commits.jsonl'
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        journal = os.fdopen(fd, 'wb'); journal.flush(); os.fsync(journal.fileno()); sync(folder)
        for sequence, entry in enumerate(entries):
            need(time.monotonic() < candidate_end, 'Candidate deadline before reveal')
            frame = regular(run / 'prepared' / entry['frame']['name'], 30000)
            need(lock(frame) == {k: entry['frame'][k] for k in ('bytes', 'sha256')}, 'Exact current opaque prepared frame')
            nonce = uuid.uuid4().hex; request = gate.reveal(entry, nonce)
            need(not stream.out, 'No unsolicited or speculative response')
            body = wrapped(frame, entry['case_id'], nonce)
            revealed = time.monotonic(); stream.send(body)
            response = answer(stream.line(), request)
            need(time.monotonic() < candidate_end, 'Response admitted inside absolute candidate deadline')
            record = {'sequence': sequence, 'case_id': entry['case_id'], 'original_trial_index': entry['original_trial_index'],
                      'nonce': nonce, 'request_sha256': hashlib.sha256(body).hexdigest(),
                      'frame': entry['frame'], 'response': response, 'previous_commit': gate.previous,
                      'revealed': revealed, 'received': time.monotonic()}
            raw = wire(record); need(len(raw) <= 4096, 'Compact complete commit without neural vector copy')
            budget.check(len(raw), receipt=True)
            journal.write(raw); journal.flush(); os.fsync(journal.fileno())
            need(time.monotonic() < candidate_end, 'Durable commit before absolute candidate deadline')
            gate.commit(response, raw, lock(raw), True)
            rows.append(response); result['committed'] = len(rows)
        journal.close(); journal = None; path.chmod(0o444); sync(folder)
        stream.send(wire({'stop': True})); need(decode(stream.line()) == {'status': 'stopped'}, 'Explicit stop acknowledgement')
        stream.finish()
        need(time.monotonic() < candidate_end, 'Candidate shutdown completed inside absolute wall allowance')
        state = engine.inspect('container', name)['State']
        need(state['Status'] == 'exited' and state['Running'] is False and state['Pid'] == 0
             and state['ExitCode'] == 0 and state['OOMKilled'] is False and gate.position == 93 and gate.pending is None,
             'Complete protocol and normal candidate exit')
        result.update(status='complete', commit_file=pin(path, 400000), last_commit=gate.previous)
    except BaseException as error:
        result.update(status='invalid_or_failed_candidate', error=repr(error)[:1500])
        if not result['create_verified'] or stream is None:
            result.update(status='infrastructure_failure', infrastructure_failure=True)
    finally:
        if journal is not None:
            try: journal.close()
            except BaseException as error: result['errors'].append({'journal_close': repr(error)[:500]})
        if stream is not None:
            try:
                result.update(stream.close())
                result['attach_dispatch_or_reaping_extent_unknown'] = not result['attach_cli_reaped']
            except BaseException as error: result.update(attach_cli_reaped=False, attach_close_error=repr(error)[:1000])
            # Failed log writes never bypass independent exact Docker cleanup.
            for label, data in (('stdout', bytes(stream.stdout)), ('stderr', bytes(stream.stderr))):
                try: budget.write(folder / (label + '.bin'), data, receipt=True, mode=0o444)
                except BaseException as error: result['errors'].append({label + '_retention': repr(error)[:1000]})
        else:
            result.update(attach_cli_reaped=not result['stream_start_attempted'],
                          candidate_start_not_dispatched=not result['stream_start_attempted'],
                          attach_dispatch_or_reaping_extent_unknown=result['stream_start_attempted'])
        try: result['cleanup'] = remove(run, folder, engine, budget)
        except BaseException as error: result['cleanup'] = [{'absence_verified': False, 'error': repr(error)[:1000]}]
        result['all_owned_absent'] = bool(result['cleanup']) and all(r['absence_verified'] for r in result['cleanup'])
        if result['errors'] and result['status'] == 'complete': result['status'] = 'invalid_or_failed_candidate'
        if (folder / 'commits.jsonl').exists(): result['retained_commits'] = pin(folder / 'commits.jsonl', 400000, empty=True)
        save(folder / 'outcome.json', result, budget)
    return result, rows


def main(args):
    run = args.run; budget = HostBudget(run, 15000000, 2000000)
    result = {'status': 'started', 'private_grader_dispatched': False, 'private_targets_decoded': False,
              'trusted_count_decode_extent_unknown': False, 'candidate_fit_count': None,
              'new_reference_fits': 0, 'model_api_calls_by_controller': 0, 'host_neural_array_decodes': 0}
    try:
        engine = Engine(args.deadline, run, budget); reply = engine.run(['image', 'inspect', IMAGE], cap=65536)
        need(reply.returncode == 0, 'Existing exact image, no pulls')
        image = strict(reply.stdout)[0]; need(image['Id'] == IMAGE, 'Fixed existing image identity')
        environment = dict(row.split('=', 1) for row in image['Config']['Env'])
        save(run / 'image.json', {'image': IMAGE, 'environment': environment}, budget)
        (run / 'prepared').mkdir(mode=0o777); (run / 'prepared').chmod(0o777)
        need(args.deadline - time.monotonic() >= 130, 'Full preparation/candidate/grade windows remain')
        result['trusted_count_decode_extent_unknown'] = True
        prep = trusted(run, 'prepare', budget, time.monotonic() + 30, environment, 20)
        contract = strict(regular(HERE / 'PACKET_INTERFACE.json', 65536))
        files, total = output_hashes(run / 'prepared', contract['output_caps'])
        need(total <= 7100000, 'Complete bounded prepared packet')
        receipt = strict(regular(run / 'prepared/prepare_receipt.json', 128000))
        preparation = validate_preparation(prep, receipt, files, contract)
        result.update(trusted_count_decode_extent_unknown=False, preparation_receipt=files['prepare_receipt.json'],
                      preparation_admission=preparation)
        save(run / 'prepare/OUTPUT_HASHES.json', {'files': files, 'bytes': total, 'host_neural_array_decodes': 0}, budget, 100000)
        index = strict(regular(run / 'prepared/index.json', 100000))
        cases = strict(regular(run / 'prepared/cases.json', 16000))
        entries = index['query_order']; need([e['case_id'] for e in entries] == cases['case_ids'], 'Complete original93case order')
        for sequence, entry in enumerate(entries):
            need(entry['sequence'] == sequence and entry['frame']['name'] == f'query-{sequence:03d}.json'
                 and {k: entry['frame'][k] for k in ('bytes', 'sha256')} == files[entry['frame']['name']], 'Each current frame bound to original index')
        need(args.deadline - time.monotonic() >= 100, 'Full80candidate+20grade phase allowances')
        outcome, rows = participant(run, entries, budget, time.monotonic() + 80, environment)
        result['candidate'] = outcome
        need(outcome['all_owned_absent'] and outcome['attach_cli_reaped'] and not outcome['infrastructure_failure'],
             'Candidate/attach absence before private grading')
        committed = {'schema_version': 1, 'case_ids': [r['case_id'] for r in rows],
                     'probability_left': [r['probability_left'] for r in rows]}
        save(run / 'committed_probabilities.json', committed, budget, 32768)
        complete = outcome['status'] == 'complete' and len(rows) == 93
        final = committed if complete else {'schema_version': 1, 'case_ids': [], 'probability_left': []}
        saved_submission = save(run / 'probabilities.json', final, budget, 32768)
        result.update(protocol_complete=complete, committed_prediction_count=len(rows),
                      committed_probabilities=pin(run / 'committed_probabilities.json', 32768),
                      grader_submission_policy='all_committed' if complete else 'empty_protocol_invalid_panel; committed prefix retained')
        grade = run / 'grade'; grade.mkdir(mode=0o700)
        operator = {'schema_version': 1, 'candidate_id': 'NEURAL-059',
                    'public_cases': files['cases.json'], 'private_labels': files['labels.json'],
                    'private_references': files['references.json'], 'prepare_receipt': files['prepare_receipt.json'],
                    'reference_admission': assets()['reference_admission']}
        save(grade / 'operator_assets.json', operator, budget, 32768)
        save(grade / 'invocation.json', {'submission': {k: saved_submission[k] for k in ('bytes', 'sha256')},
                                        'producer_stopped_attested': True, 'protocol_complete': complete}, budget, 32768)
        need(args.deadline - time.monotonic() >= 20, 'Full private grading phase')
        result.update(private_grader_dispatched=True, private_targets_decoded=None)
        report = trusted(run, 'grade', budget, time.monotonic() + 20, environment, 10)
        need(type(report['private_label_decodes']) is int and report['private_label_decodes'] in (0, 1)
             and all(v is False for v in report['private_read_extent_unknown'].values()), 'Complete private-read accounting')
        result.update(status=report['status'], private_targets_decoded=report['private_label_decodes'] == 1,
                      score=pin(grade / 'stdout.json', 131072), candidate_chronology_verified=complete,
                      lawful_prefix_adaptation_allowed=True, fixed_model_only_enforced=False)
    except BaseException as error:
        result.update(status='failed_preserved', error=repr(error)[:1500])
    finally:
        # Only compact pins, never full scalar/ownership ledgers, in the outer join.
        save(run / 'result.json', result, budget, 65536)
    return int(result['status'] == 'failed_preserved')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--run', type=Path, required=True); parser.add_argument('--deadline', type=float, required=True)
    raise SystemExit(main(parser.parse_args()))
