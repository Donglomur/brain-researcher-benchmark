"""Independent enclosing host process/daemon observer, with original clock custody."""
import os
from pathlib import Path
import resource
import selectors
import signal
import subprocess
import sys
import time

from core import Budget, capture, capture_new_protected, encoded, fresh, integer, need, parse, pin, publish
from engine import Engine, stop_owned
from schedule import full, author_episodes, candidate_phases, references, disposition


def command(args, journal_fd):
    return [sys.executable, '-I', '-B', str(Path(__file__).parent/'entry.py'), 'worker',
            '--repo', args.repo, '--bootstrap-bytes', str(args.bootstrap_bytes),
            '--bootstrap-sha256', args.bootstrap_sha256, '--manifest-bytes', str(args.manifest_bytes),
            '--manifest-sha256', args.manifest_sha256, '--authority', args.authority,
            '--authority-bytes', str(args.authority_bytes), '--authority-sha256', args.authority_sha256,
            '--original-origin', repr(args.original_origin), '--journal-fd', str(journal_fd)]


def event_closure(raw, producer_pin, source_pin, origin, deadline, producer):
    lines = raw.splitlines()
    need(lines and raw.endswith(b'\n'), 'complete durable journal records')
    events = []
    for index, body in enumerate(lines, 1):
        row = parse(body)
        need(type(row) is dict and set(row) == {'sequence', 'event'}
             and type(row['sequence']) is int and row['sequence'] == index
             and type(row['event']) is dict and type(row['event'].get('kind')) is str,
             'complete ordered durable event stream')
        events.append(row['event'])
    need(events[0]['kind'] == 'worker_started' and events[0]['source'] == source_pin
         and events[0]['original_origin'] == origin and events[0]['deadline'] == deadline,
         'original worker journal source/clock')
    need(events[-1]['kind'] == 'worker_completed' and events[-1]['producer'] == producer_pin
         and origin <= events[-1]['observed_end'] < deadline, 'natural completed source-bound worker journal')
    need(not any(e['kind'] in ('worker_failed', 'episode_failed', 'native_failed', 'provider_failed') for e in events),
         'no hidden failed phase/provider/tool in successful study')
    expected_episodes = [list(x) for x in author_episodes([{'ordinal': i} for i in range(1, 30)])]
    author_entered = [e for e in events if e['kind'] == 'episode_entered']
    author_completed = [e for e in events if e['kind'] == 'episode_completed']
    need([e['episode'] for e in author_entered] == [e['episode'] for e in author_completed] == expected_episodes,
         'exact ordered180 author episode membership; no duplicate or substituted context')
    need([r['episode'] for r in producer['authors']] == expected_episodes, 'producer contains same complete author study')
    for entered, completed, produced in zip(author_entered, author_completed, producer['authors']):
        need(entered['state']['episode'] == completed['state']['episode'] == produced['episode']
             and encoded(completed['state']) == encoded(produced['record']), 'same independent completed author record')
    session_ids = {}
    for row in producer['reference_outputs']:
        phase = row['phase']; ordinal = integer(phase['ordinal'], 1, 29)
        need(ordinal not in session_ids or session_ids[ordinal] == phase['session_id'], 'one session identity per ordinal')
        session_ids[ordinal] = phase['session_id']
    need(set(session_ids) == set(range(1, 30)) and len(set(session_ids.values())) == 29,
         'full29 source session identities for observed schedule')
    sessions = [{'ordinal': i, 'session_id': session_ids[i]} for i in range(1, 30)]
    expected_phases = {'candidate': candidate_phases(sessions), 'reference': references(sessions)}
    for actor, count in (('candidate', 870), ('reference', 145)):
        completed = [e for e in events if e['kind'] == 'phase_completed' and e['actor'] == actor]
        entered = [e for e in events if e['kind'] == 'phase_entered' and e['actor'] == actor]
        need([e['index'] for e in completed] == list(range(1, count+1))
             and [e['index'] for e in entered] == list(range(1, count+1))
             and all(type(e['index']) is int for e in entered+completed), 'complete disjoint phase indices')
        need(encoded([e['phase'] for e in entered]) == encoded([e['phase'] for e in completed])
             == encoded(expected_phases[actor]), 'exact full entered/completed phase schedule')
    natives = [e['result'] for e in events if e['kind'] == 'native_completed']
    attempted = [e for e in events if e['kind'] == 'native_intent']
    created = [e for e in events if e['kind'] == 'native_created']
    started = [e for e in events if e['kind'] == 'native_started']
    tool_count = sum(row['record']['tool_calls'] for row in producer['authors'])
    need(len(natives) == len(attempted) == len(created) == len(started) == 1015+tool_count,
         'all fixed and investigative native phases have complete operation chains')
    need(len({r['container'] for r in natives}) == len(natives), 'fresh native identities for all stages')
    chains = {}
    for order, event in enumerate(events):
        kind = event['kind']
        if kind not in ('native_intent', 'native_created', 'native_started', 'native_completed'):
            continue
        phase = event['result']['phase'] if kind == 'native_completed' else event['phase']
        chain = chains.setdefault(phase, {})
        need(kind not in chain, 'one intent/create/start/completion per exact phase')
        chain[kind] = (order, event)
    complete_kinds = ('native_intent', 'native_created', 'native_started', 'native_completed')
    native_by_phase = {}
    for phase, chain in chains.items():
        need(set(chain) == set(complete_kinds), 'no disconnected native operation chain')
        need([chain[k][0] for k in complete_kinds] == sorted(chain[k][0] for k in complete_kinds),
             'intent precedes create/start/natural completion')
        intent, create, start, completed = [chain[k][1] for k in complete_kinds]
        result = completed['result']
        need(create['container'] == start['container'] == result['container'], 'same created/started/completed container')
        need(intent['config']['Labels'] == {'neural060.run': producer['study_id'], 'neural060.phase': phase}
             and result['config'] == pin(encoded(intent['config'])), 'exact owned phase and configuration commitment')
        need(intent['original_origin'] == result['original_origin'] == origin
             and intent['cutoff'] == result['cutoff'] <= result['requested_cutoff'] == intent['requested_cutoff'] <= deadline
             and origin <= result['natural_end'] < result['cutoff'], 'original native phase clock')
        need(result['cpu_reservation'] == intent['cpu_reservation']
             and result['cpu_reservation']['execution_cutoff'] == result['cutoff']
             and integer(result['cpu_nanoseconds'], 1)
                 <= integer(result['cpu_reservation']['cpu_reserved_nanoseconds'], 1)
                 <= integer(result['cpu_reservation']['cpu_limit_nanoseconds'], 1),
             'native measured use within precommitted CPU reservation')
        need(result['watchdog']['watchdog_joined'] is True
             and result['watchdog']['timer_or_failure_stop_triggered'] is False,
             'independent phase watchdog joined without forced stop')
        native_by_phase[phase] = result
    completed_phase_events = [e for e in events if e['kind'] == 'phase_completed']
    for event in completed_phase_events:
        phase_id = event['actor']+'-'+str(event['index'])
        need(phase_id in native_by_phase and encoded(event['native']) == encoded(native_by_phase[phase_id]),
             'final phase record joins its exact native chain')
    for row in [*producer['candidate_outputs'], *producer['reference_outputs']]:
        for native_record in (row['native'], row['fit']['native']):
            phase = native_record['phase']
            need(phase in native_by_phase and encoded(native_record) == encoded(native_by_phase[phase]),
                 'producer fit/inference artifact records join the observed native chain')
    fixed_phases = {e['actor']+'-'+str(e['index']) for e in completed_phase_events}
    tool_phases = set(native_by_phase)-fixed_phases
    expected_tools = set()
    for row in producer['authors']:
        episode = tuple(row['episode'])
        for number in range(1, row['record']['tool_calls']+1):
            expected_tools.add('author-'+str(episode)+'-'+str(number))
    need(tool_phases == expected_tools, 'exact per-episode investigative native workload')
    requests = [e for e in events if e['kind'] == 'provider_attempted']
    usage = [e for e in events if e['kind'] == 'provider_usage_observed']
    responses = [e for e in events if e['kind'] == 'provider_completed']
    expected_calls = sum(row['record']['provider_calls'] for row in producer['authors'])
    need(len(requests) == len(usage) == len(responses) == expected_calls,
         'no missing/uncounted provider attempt or usage record')
    identity = lambda e: (tuple(e['episode']), e['ordinal'])
    expected_requests = [(tuple(r['episode']), i) for r in producer['authors']
                         for i in range(1, integer(r['record']['provider_calls'], 1)+1)]
    need([identity(e) for e in requests] == [identity(e) for e in usage]
         == [identity(e) for e in responses] == expected_requests,
         'provider request/usage/response exact episode and ordinal')
    need(all(a['response'] == b['response'] for a, b in zip(usage, responses)),
         'same observed provider response through usage and action admission')
    return {'events': len(events), 'native_phases': len(natives), 'tool_calls': tool_count,
            'provider_requests': expected_calls, 'observed_provider_tokens': sum(integer(e['prompt_tokens'])+integer(e['completion_tokens']) for e in usage),
            'actual_target_reads': 0, 'all_required_phases_closed': True}


def failure_prefix(raw):
    """Audit only complete valid journal prefix; never infer successful closure."""
    pieces = raw.splitlines(keepends=True)
    events = []; malformed = None; consumed = 0
    for number, piece in enumerate(pieces, 1):
        if not piece.endswith(b'\n'):
            malformed = 'partial_final_line'; break
        try:
            row = parse(piece)
            need(type(row) is dict and set(row) == {'sequence', 'event'}
                 and type(row['sequence']) is int and row['sequence'] == number
                 and type(row['event']) is dict and type(row['event'].get('kind')) is str,
                 'journal prefix schema/sequence')
        except (ValueError, TypeError, KeyError, UnicodeError):
            malformed = 'malformed_or_out_of_order_line'; break
        events.append(row['event']); consumed += len(piece)
    result = {'schema': 'neural060_failure_prefix_v1', 'complete_events': len(events),
              'last_complete_event': None if not events else events[-1],
              'unadmitted_tail': pin(raw[consumed:]), 'tail_disposition': malformed,
              'all_required_phases_closed': False}
    def count_group(entered, done, failed, expected):
        need(len(entered) == len(set(entered)) and len(done) == len(set(done))
             and len(failed) == len(set(failed)), 'no duplicate disposition identities')
        entered, done, failed = set(entered), set(done), set(failed)
        need(done <= entered <= expected and failed <= entered and not failed & done,
             'disjoint observed complete/failed/entered membership')
        result = disposition(len(expected), len(entered), len(done), len(failed))
        result['identities'] = {'completed': sorted(done, key=repr), 'failed': sorted(failed, key=repr),
                                'entered_incomplete': sorted(entered-done-failed, key=repr),
                                'unentered': sorted(expected-entered, key=repr)}
        return result
    for actor, total in (('candidate', 870), ('reference', 145)):
        try:
            entered = [integer(e['index'], 1, total) for e in events
                       if e['kind'] == 'phase_entered' and e.get('actor') == actor]
            done = [integer(e['index'], 1, total) for e in events
                    if e['kind'] == 'phase_completed' and e.get('actor') == actor]
            failures = [e['phase'] for e in events if e['kind'] == 'native_failed']
            need(all(type(x) is str for x in failures), 'typed native failure identity')
            failed = [i for i in entered if actor+'-'+str(i) in failures]
            result[actor] = count_group(entered, done, failed, set(range(1, total+1)))
        except (ValueError, TypeError, KeyError):
            result[actor] = {'status': 'malformed_phase_identity_requires_inspection'}
    try:
        expected = {tuple(x) for x in author_episodes([{'ordinal': i} for i in range(1, 30)])}
        groups = [[tuple(e['episode']) for e in events if e['kind'] == kind]
                  for kind in ('episode_entered', 'episode_completed', 'episode_failed')]
        result['authors'] = count_group(*groups, expected)
    except (ValueError, TypeError, KeyError):
        result['authors'] = {'status': 'malformed_episode_identity_requires_inspection'}
    result['known_provider_attempts'] = sum(e['kind'] == 'provider_attempted' for e in events)
    try:
        result['known_provider_observed_tokens'] = sum(integer(e['prompt_tokens'])+integer(e['completion_tokens'])
                                                      for e in events if e['kind'] == 'provider_usage_observed')
    except (ValueError, TypeError, KeyError):
        result['known_provider_observed_tokens'] = None
        result['provider_usage_error'] = 'malformed_usage_requires_inspection'
    result['usage_may_be_incomplete'] = True
    return result


def observe(args, sources, authority, qualification, budget):
    root = fresh(authority['observation_root'], budget)
    entry = str(sources.root/'entry.py')
    need(Path(entry).absolute() == Path(__file__).absolute().parent/'entry.py', 'same captured entry root')
    deadline, origin = budget.deadline, budget.origin
    close_deadline = deadline+integer(authority['observer_limits']['closeout_seconds'], 1)
    # Closeout is an explicitly selected failure/readback allowance. It never
    # relaxes the producer's original deadline or permits another producer run.
    close_budget = Budget(origin, close_deadline, authority['resources']['observer_read_bytes']-budget.read_bytes,
                          authority['resources']['observer_write_bytes']-budget.write_bytes)
    journal_path = root/'EVENTS.jsonl'
    fd = os.open(journal_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    child = None; timer_fired = False; natural_exit = False; exit_code = None
    buffers = {'stdout': bytearray(), 'stderr': bytearray()}
    stream_cap = integer(authority['observer_limits']['stream_bytes'], 1)
    log = []
    run_command = command(args, fd)
    publish(root/'INTENT.json', encoded({'schema': 'neural060_outer_intent_v1', 'command': run_command,
             'actual_outer_argv': list(sys.orig_argv), 'source': sources.pin, 'authority_pin':
             {'bytes': args.authority_bytes, 'sha256': args.authority_sha256},
             'original_origin': origin, 'original_deadline': deadline, 'closeout_deadline': close_deadline}), close_budget)
    before_usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    worker_start = budget.tick()
    failure = None
    try:
        child = subprocess.Popen(run_command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 pass_fds=(fd,), start_new_session=True, bufsize=0,
                                 env={'PATH': os.defpath, 'PYTHONHASHSEED': '0', 'PYTHONDONTWRITEBYTECODE': '1', 'LANG': 'C.UTF-8'})
        os.close(fd); fd = None
        selector = selectors.DefaultSelector()
        for name, stream in (('stdout', child.stdout), ('stderr', child.stderr)):
            os.set_blocking(stream.fileno(), False); selector.register(stream, selectors.EVENT_READ, name)
        while selector.get_map() or child.poll() is None:
            if time.monotonic() >= deadline:
                timer_fired = True
                raise TimeoutError('original enclosing study deadline expired')
            for key, _ in selector.select(min(0.1, max(0., deadline-time.monotonic()))):
                body = os.read(key.fd, 65536)
                if not body:
                    selector.unregister(key.fileobj)
                else:
                    close_budget.reserve_read(len(body))
                    need(len(buffers[key.data])+len(body) <= stream_cap, 'bounded enclosing process stream')
                    buffers[key.data].extend(body)
        exit_code = child.wait(timeout=max(0.001, deadline-time.monotonic()))
        worker_end = time.monotonic()
        natural_exit = exit_code == 0 and worker_end < deadline
        need(natural_exit, 'worker did not naturally succeed before original cutoff')
    except BaseException as error:
        failure = {'error_type': type(error).__name__, 'error': str(error)}
        worker_end = time.monotonic()
        if child is not None and child.poll() is None:
            try:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=max(0.001, close_deadline-time.monotonic()))
            except BaseException as close_error:
                failure['host_cleanup_error'] = type(close_error).__name__
        if child is not None:
            exit_code = child.poll()
    finally:
        if fd is not None:
            os.close(fd)
        if child is not None:
            for stream in (child.stdout, child.stderr):
                if stream is not None:
                    stream.close()
    after_usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    engine = Engine(authority['engine'], close_budget, log.append)
    owned = engine.owned(authority['study_id'], close_deadline)
    stop_records = []
    if not natural_exit or owned:
        stop_cutoff = min(close_deadline, time.monotonic()+integer(authority['observer_limits']['resource_stop_seconds'], 1))
        for item in owned:
            ident = item['Id']
            try:
                observed = engine.inspect(ident, stop_cutoff)
                labels = observed['Config']['Labels']
                need(labels.get('neural060.run') == authority['study_id']
                     and type(labels.get('neural060.phase')) is str, 'independently owned resource only')
                stop_records.append({'container': ident, 'result': stop_owned(engine, ident, authority['study_id'],
                                    labels['neural060.phase'], stop_cutoff, log.append)})
            except BaseException as error:
                stop_records.append({'container': ident, 'closed': False, 'error_type': type(error).__name__,
                                     'usage_and_resource_state_unknown': True})
        owned = engine.owned(authority['study_id'], close_deadline)
    # Precisely owned computation is stopped, but its containers/artifacts are
    # retained for inspection. No automatic retry, delete or success promotion.
    receipt = {'schema': 'neural060_outer_observation_v1', 'study_id': authority['study_id'],
               'runtime_source': sources.pin, 'original_origin': origin, 'original_deadline': deadline,
               'worker_start': worker_start, 'worker_end': worker_end, 'natural_exit': natural_exit,
               'exit_code': exit_code, 'timer_fired': timer_fired, 'owned_containers_after': [x['Id'] for x in owned],
               'command': run_command, 'actual_outer_argv': list(sys.orig_argv), 'qualifications': qualification,
               'failure': failure, 'host_child_user_cpu_s': after_usage.ru_utime-before_usage.ru_utime,
               'host_child_system_cpu_s': after_usage.ru_stime-before_usage.ru_stime,
               'host_child_maxrss_raw': after_usage.ru_maxrss,
               'host_maxrss_unit': authority['observer_limits']['rusage_maxrss_unit'],
               'daemon_observations': log,
               'closeout_deadline': close_deadline, 'resource_snapshot_before_final_receipt': close_budget.record(),
               'snapshot_excludes_following_receipt_publication': True, 'owned_stop_records': stop_records,
               'study_admitted': False}
    for name, body in buffers.items():
        receipt[name] = publish(root/(name+'.log'), bytes(body), close_budget, readonly=True)
    os.chmod(journal_path, 0o444)
    journal, journal_pin = capture_new_protected(journal_path, authority['observer_limits']['journal_bytes'], close_budget)
    receipt['journal'] = journal_pin
    receipt['failure_prefix'] = failure_prefix(journal)
    receipt['producer'] = None
    if natural_exit and not owned:
        try:
            producer_raw, producer_pin = capture_new_protected(Path(authority['attempt_root'])/'PRODUCER.json',
                                                              authority['resources']['producer_bytes'], close_budget)
            producer = parse(producer_raw)
            receipt['producer'] = producer_pin
            receipt['event_closure'] = event_closure(journal, producer_pin, sources.pin, origin, deadline, producer)
            close_budget.reserve_read(sum(x['bytes'] for x in sources.pins.values()))
            sources.recheck()
            receipt['study_admitted'] = True
            receipt['failure_prefix'] = None
        except BaseException as error:
            receipt['event_closure'] = None
            receipt['failure'] = {'error_type': type(error).__name__, 'error': str(error)}
    else:
        receipt['event_closure'] = None
        receipt['producer'] = None
    publish(root/'OUTER.json', encoded(receipt), close_budget, readonly=True)
    need(natural_exit and not owned and receipt['study_admitted'] is True and receipt['event_closure'] is not None,
         'failed/uncertain study retained; no complete benchmark result')
    return receipt
