"""Concrete prospective full468 source controller. Disabled without exact selection.

Construction tests use invented adapters only. This module never supplies a model,
reference, execution grant or a passing scientific result.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import stat
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import control as C
import runtime as R
from ownership_client import Client


def bootstrap(repo, selected_source):
    raw = C.read(HERE / 'SOURCE_MANIFEST.json', 65536, selected_source)
    manifest = C.parse(raw)
    C.need(manifest['task_id'] == C.TASK and manifest['source_only'] is True, 'source manifest')
    for name, expected in manifest['runtime_files'].items():
        C.read(HERE / name, 1000000, expected)
    bindings = C.parse(C.read(HERE / 'BINDINGS.json', 1000000))
    E = C.source(repo, bindings['slice_executor'], 'gcamp_slice_transport')
    T = C.source(repo, bindings['transport'], 'gcamp_input_catalog')
    P = C.source(repo, bindings['stager_process'], 'gcamp_stager_process')
    return bindings, E, T, P


def attest(cfg, source_pin, bindings, programs):
    a = C.parse(C.read(cfg['authoring_receipt']['path'], 65536, C.only_pin(cfg['authoring_receipt'])))
    r = C.parse(C.read(cfg['runtime_receipt']['path'], 65536, C.only_pin(cfg['runtime_receipt'])))
    abi_pin = C.pin(C.read(HERE / 'CANDIDATE_ABI.md', 65536))
    C.need(a.get('template_not_evidence') is False and
           a['schema'] == 'gcamp8_separate_author_contexts_v1' and a['task_id'] == C.TASK and
           a['source'] == source_pin and a['programs'] == programs and
           set(a['contexts']) == {'A', 'B'} and a['contexts']['A'] != a['contexts']['B'] and
           all(type(x) is str and 1 <= len(x) <= 256 for x in a['contexts'].values()) and
           a['empirical_inputs_released_to_authors'] is False and
           a['cross_context_exchange'] is False and a['prior_exposure_limitations_declared'] is True and
           a['candidate_abi'] == abi_pin and a['candidate_abi_supplied_to_both_contexts'] is True and
           a['allowed_source_catalog'] == C.only_pin(bindings['view_files']),
           'separate operator-attested source-only author contexts')
    C.need(r.get('template_not_evidence') is False and
           r['schema'] == 'gcamp8_future_runtime_custody_v1' and r['source'] == source_pin and
           r['image'] == cfg['image'] and r['python'] == cfg['python'] and
           r['docker'] == cfg['docker'] and r['socket'] == cfg['socket'] and
           r['candidate_memory_bytes'] == cfg['memory_bytes'] and
           r['host_source_immutable'] is True and r['image_runtime_checked'] is True and
           r['full_selected_reservation_bytes'] >= C.RETAIN and
           r['other_reserved_bytes'] == cfg['other_reserved_bytes'], 'future runtime custody')
    C.need(set(r['executable_pins']) == {'python', 'docker'}, 'exact executable custody pins')
    return {'authoring': C.only_pin(cfg['authoring_receipt']), 'runtime': C.only_pin(cfg['runtime_receipt']),
            'executable_pins': r['executable_pins'],
            'candidate_abi': abi_pin,
            'authoring_evidence_is_operator_attestation_not_forensic_blindness': True}


def stage(Catalog, T, P, plan, root, folder, sources, cfg, end):
    """Same pinned stager and independent full inventory as admitted construction."""
    folder.mkdir(mode=0o700)
    view = folder / 'view'
    deadline = min(end - 120, time.monotonic() + cfg['stage_seconds'])
    argv = [cfg['python'], '-I', '-B', str(sources / 'stage_view.py'), '--root', str(root),
            '--output', str(view), '--neuron', plan['identity'][0], '--track', plan['identity'][1],
            '--view', plan['identity'][2]]
    stdout, observed = P.run(argv, deadline, min(end, deadline + 40),
                             {'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C',
                              'PYTHONDONTWRITEBYTECODE': '1'})
    terminal = T.strict(stdout)
    C.need(terminal == {'view': plan['identity'][2], 'track': plan['identity'][1],
           'neuron_id': plan['identity'][0], 'training_neurons': len(plan['packet']['training_ids']),
           'files': len(plan['entries']), 'target_reads': 0, 'scientific_calls': 0}, 'stager exact terminal')
    proof = T.verify_view(view, plan)
    files, dirs = T.inventory(view)
    for name in files:
        p = view / name
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
            os.fchmod(fd, 0o444)
        finally:
            os.close(fd)
    for name in dirs:
        (view / name).chmod(0o555)
    view.chmod(0o555)
    C.write(folder / 'STAGE.json', C.encoded({'identity': plan['identity'], 'inventory': proof,
            'process': observed, 'stager': C.only_pin(Catalog.lock['files']['private/stage_view.py']),
            'source_read_bytes': plan['source_read_bytes'], 'verified_write_bytes': plan['output_bytes']}))
    return view


def trusted_command(P, argv, seconds, end):
    deadline = min(end - 45, time.monotonic() + seconds)
    stdout, record = P.run(argv, deadline, min(end, deadline + 40),
                          {'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C',
                           'PYTHONDONTWRITEBYTECODE': '1', 'OPENBLAS_NUM_THREADS': '1',
                           'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1'})
    C.need(stdout == b'', 'trusted scientific CLI has no stdout')
    return record


def _run(repo, export, selection, selection_pin, output, started, outer_state, ownership):
    cfg = C.validate_selection(C.parse(C.read(selection, 65536, selection_pin)))
    end = started + C.whole_seconds(cfg)
    repo, export, output = map(C.path, (repo, export, output))
    C.need(not os.path.lexists(output) and output.parent.is_dir() and
           not output.is_relative_to(export) and not export.is_relative_to(output), 'fresh disjoint output')
    C.capacity(output, cfg['other_reserved_bytes'])
    bindings, E, T, P = bootstrap(repo, cfg['source'])
    lock = T.strict(C.read(repo / bindings['transport_lock']['path'], 65536,
                           C.only_pin(bindings['transport_lock'])))
    catalog = T.Catalog(export, lock)
    identities = [list(x) for x in catalog.identities()]
    C.need(len(identities) == 468 and len(catalog.ids) == 117, 'full released cohort')
    ownership.programme(identities)
    programs = {a: C.read(cfg['programs'][a]['path'], 131072, C.only_pin(cfg['programs'][a]))
                for a in ('A', 'B')}
    for raw in programs.values():
        C.need('\0' not in raw.decode('utf-8'), 'UTF8 Python program')
    program_pins = {a: C.pin(raw) for a, raw in programs.items()}
    prerequisites = attest(cfg, cfg['source'], bindings, program_pins)
    C.need(stat.S_ISSOCK(C.path(cfg['socket']).stat().st_mode), 'selected existing Docker socket')
    for executable in (cfg['python'], cfg['docker']):
        C.need(C.path(executable).is_file() and os.access(executable, os.X_OK), 'existing exact executable path')
    for key in ('python', 'docker'):
        E.opaque_pin(cfg[key], prerequisites['executable_pins'][key], 268435456)
    output.mkdir(mode=0o700)
    outer_state['owned_output'] = output
    for name in ('programs', 'source', 'transient', 'cases', 'grades'):
        (output / name).mkdir(mode=0o755 if name in ('source', 'programs') else 0o700)
    for arm, raw in programs.items():
        C.write(output / 'programs' / (arm + '.py'), raw, 131072)
    # Both immutable programs and their source-only author-context attestations
    # are durable before any empirical data are staged.
    C.write(output / 'COMMITMENT.json', C.encoded({'schema': 'gcamp8_full117_commitment_v1',
            'task_id': C.TASK, 'source': cfg['source'], 'selection': selection_pin,
            'programs': program_pins, 'identities': identities, 'prerequisites': prerequisites,
            'whole_seconds': C.whole_seconds(cfg), 'candidate_image': cfg['image']}))
    for name in ('entry.py', 'holder.py', 'trusted_worker.py', 'CANDIDATE_ABI.md'):
        C.write(output / 'source' / name, C.read(HERE / name, 1000000))
    for name in ('stage_view.py', 'interface.py'):
        key = 'private/' + name
        C.write(output / 'source' / name, C.read(export / key, 1000000, C.only_pin(lock['files'][key])))
    # stage_view resolves its metadata beside __file__; capture only catalog
    # metadata. Numeric target arrays remain solely in the original export.
    for name in ('ASSETS.json', 'VIEW_FILES.json', 'prepared/PREPARED.json'):
        dest = output / 'source' / name
        dest.parent.mkdir(exist_ok=True)
        C.write(dest, C.read(export / ('private/' + name), 1000000,
                            C.only_pin(lock['files']['private/' + name])))
    states = [{'identity': x, 'status': 'unstarted'} for x in identities]
    records = []
    # The first failed case aborts; reserve its original raw evidence once,
    # including hashing/capture, inside the unchanged managed ceilings.
    charged_reads = 550000000 + 2 * R.FAILURE_EVIDENCE_CAP
    charged_writes = 10000000 + R.FAILURE_EVIDENCE_CAP
    signal.setitimer(signal.ITIMER_REAL, max(.001, end - time.monotonic()))
    try:
        for i, identity in enumerate(identities):
            ownership.begin(i, identity)
            C.need(time.monotonic() < end - 120, 'campaign closure reserve')
            C.capacity(output, cfg['other_reserved_bytes'],
                       200000000 + C.PRED_CAP + 2000000 + R.FAILURE_EVIDENCE_CAP)
            plan = catalog.plan(*identity)
            C.need(plan['output_bytes'] <= 200000000, 'one complete input view')
            # Managed source/transport/hash service only. Arbitrary program
            # rereads, tmpfs churn, libraries/image pages are not byte-bounded.
            charged_reads += 4 * plan['output_bytes'] + 2 * R.MODEL_CAP + 4 * C.PRED_CAP + 2000000
            charged_writes += plan['output_bytes'] + C.PRED_CAP + 2000000
            C.need(charged_reads <= C.READ_RESERVE and charged_writes <= C.WRITE_RESERVE,
                   'full cumulative managed reservation')
            states[i]['status'] = 'started'
            transient = output / 'transient' / f'{i:04d}'
            proof = output / 'cases' / f'{i:04d}'
            proof.mkdir(mode=0o700)
            case_end = min(end - 120, time.monotonic() + cfg['stage_seconds'] +
                           cfg['train_seconds'] + cfg['predict_seconds'] + 2600)
            publish = lambda name, value: C.write(proof / name, C.encoded(value), 1000000)
            publish('RESERVATION.json', {'identity': identity, 'index': i,
                    'input_two_pass_read_bytes': plan['source_read_bytes'],
                    'input_write_bytes': plan['output_bytes'], 'retained_prediction_cap': C.PRED_CAP,
                    'model_tmpfs_cap': R.MODEL_CAP, 'original_case_deadline': case_end,
                    'candidate_training_seconds': cfg['train_seconds'],
                    'candidate_prediction_seconds': cfg['predict_seconds'],
                    'cumulative_managed_read_reserved': charged_reads,
                    'cumulative_managed_write_reserved': charged_writes,
                    'failure_is_not_refunded': True})
            view = stage(catalog, T, P, plan, export, transient, output / 'source', cfg, case_end)
            train_packet = proof / 'TRAIN_PACKET.json'
            C.write(train_packet, C.encoded(C.training_packet(plan['packet'])))
            train, query = C.phase_inputs(plan, view, train_packet, output / 'source/CANDIDATE_ABI.md')
            record = R.case(E, E.Docker(cfg['docker'], cfg['socket']), cfg, identity,
                            output / 'programs' / (identity[2] + '.py'), train, query,
                            proof, output / 'source', case_end - 400, publish, ownership)
            expected = {row['target']: C.only_pin(row) for row in plan['files']}
            retirement = C.retire_view(view, expected, proof, case_end)
            record['input_retired'] = True
            record['retirement'] = retirement
            publish('OUTCOME.json', record)
            records.append(record)
            states[i]['status'] = 'captured'
            ownership.finish()
            C.capacity(output, cfg['other_reserved_bytes'])
        # Every producer/model/holder/CLI group has closed and every input view
        # is retired before the first trusted target is opened by grade.py.
        barrier = C.barrier(identities, records)
        C.write(output / 'PRODUCER_BARRIER.json', C.encoded(barrier))
        charged_reads += C.GRADING_READ
        C.need(charged_reads <= C.READ_RESERVE, 'complete private-grading read reservation')
        for name, desc in bindings['scientific_sources'].items():
            C.read(export / name, 1000000, C.only_pin(desc))
        for arm in ('A', 'B'):
            (output / 'grades' / arm).mkdir(mode=0o700)
        for i, identity in enumerate(identities):
            n, track, arm = identity
            submission = output / 'cases' / f'{i:04d}' / 'prediction.json'
            C.read(submission, C.PRED_CAP, records[i]['prediction'])
            destination = output / 'grades' / arm / (track + '-' + n + '.json')
            observation = trusted_command(P, [cfg['python'], '-I', '-B', str(output / 'source/trusted_worker.py'),
                str(export / 'private/grade.py'),
                '--neuron', n, '--track', track, '--view', arm, '--submission', str(submission),
                '--output', str(destination)], cfg['grade_seconds'], end)
            C.write(output / 'cases' / f'{i:04d}' / 'GRADE_EXIT.json', C.encoded(observation))
            C.read(destination, 65536)
        for arm in ('A', 'B'):
            destination = output / ('SUMMARY-' + arm + '.json')
            observation = trusted_command(P, [cfg['python'], '-I', '-B', str(output / 'source/trusted_worker.py'),
                    str(export / 'private/aggregate.py'),
                    '--grades', str(output / 'grades' / arm), '--output', str(destination), '--view', arm], 60, end)
            C.read(destination, 16000000)
            C.write(output / ('AGGREGATE_EXIT-' + arm + '.json'), C.encoded(observation))
        C.need(time.monotonic() < end, 'original whole completion deadline')
        C.capacity(output, cfg['other_reserved_bytes'])
        return C.write(output / 'COLLECTION.json', C.encoded({'schema': 'gcamp8_full117_collection_v1',
             'task_id': C.TASK, 'status': 'pending_independent_root_outer_exit_admission',
             'cases': 468, 'neurons': 117, 'tracks': 2, 'arms': ['A', 'B'],
             'source': cfg['source'], 'selection': selection_pin, 'programs': program_pins,
             'elapsed_before_collection': time.monotonic() - started,
             'whole_seconds': C.whole_seconds(cfg), 'historical105_reproduced': False,
             'managed_read_reserved_bytes': charged_reads,
             'managed_write_reserved_bytes': charged_writes,
             'scientific_qualification_added': False}))
    except BaseException as error:
        try:
            C.write(output / 'FAILURE.json', C.encoded({'error_type': type(error).__name__,
                    'all468_slots': states, 'private_grading_permitted_after_partial': False,
                    'managed_read_reserved_bytes': charged_reads,
                    'managed_write_reserved_bytes': charged_writes,
                    'partial_artifacts_and_all_costs_retained': True, 'automatic_retry': False}))
        except BaseException:
            pass
        raise


def run(repo, export, selection, selection_pin, output, ownership_fd, original_endpoint):
    """The preflight clock and termination handler precede even selection reads."""
    started = time.monotonic()
    state = {'owned_output': None}
    ownership = Client(ownership_fd, original_endpoint)
    primary, result, cleanup_errors = None, None, []
    old_alarm = signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('original controller clock')))
    old_term = signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(InterruptedError('controller termination')))
    signal.setitimer(signal.ITIMER_REAL, 1200)
    try:
        result = _run(repo, export, selection, selection_pin, output, started, state, ownership)
    except BaseException as error:
        primary = error
        owned = state['owned_output']
        if owned is not None and not os.path.lexists(owned / 'FAILURE.json'):
            try:
                C.write(owned / 'FAILURE.json', C.encoded({'error_type': type(error).__name__,
                        'stage': 'outer_preflight_or_publication', 'success_not_admitted': True,
                        'partial_artifacts_and_costs_retained': True}))
            except BaseException:
                pass
    finally:
        for cleanup in (ownership.close, lambda: signal.setitimer(signal.ITIMER_REAL, 0),
                        lambda: signal.signal(signal.SIGALRM, old_alarm),
                        lambda: signal.signal(signal.SIGTERM, old_term)):
            try:
                cleanup()
            except BaseException as error:
                cleanup_errors.append(error)
                if primary is None:
                    primary = error
    if primary is not None:
        raise primary
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, required=True)
    p.add_argument('--export', type=Path, required=True)
    p.add_argument('--selection', type=Path, required=True)
    p.add_argument('--selection-bytes', type=int, required=True)
    p.add_argument('--selection-sha256', required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--ownership-fd', type=int, required=True)
    p.add_argument('--original-endpoint', type=float, required=True)
    a = p.parse_args()
    print(json.dumps(run(a.repo, a.export, a.selection,
                        {'bytes': a.selection_bytes, 'sha256': a.selection_sha256}, a.output,
                        a.ownership_fd, a.original_endpoint)))


if __name__ == '__main__':
    main()
