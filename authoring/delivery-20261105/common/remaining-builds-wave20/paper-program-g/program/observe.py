"""Independent FIND036 host closure, deployed beside the reviewed program/common.py.

No benchmark launches on import. Fresh invocation owns one controller group only.
Source and selection capture precede launch; no target numeric artifact is read.
"""
import time
BOOT = time.monotonic()
import argparse, os, selectors, signal, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *

TERMINAL_CAP = 1048576
FINAL_RESERVE = 65536


def finite_clock(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_phase(phase, context, origin, deadline):
    need(type(phase) is dict and phase['schema'] == 'foraging_owned_phase_v1', 'phase schema')
    need(phase['context'] == context and phase['status'] == 'captured', 'complete corresponding phase')
    need(phase['natural_exit'] == {'Status': 'exited', 'Running': False, 'Dead': False,
         'Pid': 0, 'ExitCode': 0, 'OOMKilled': False}, 'natural producer state')
    need(phase['producer_closed_before_capture'] is True and phase['all_resources_closed'] is True
         and phase['cli_reaped'] is True and phase['private_scoring_called'] is False
         and phase['error'] is None, 'all owned phase closure flags')
    need(type(phase['closures']) is list and len(phase['closures']) == 3, 'all three resources closed')
    for closure in phase['closures']:
        need(closure['closed'] is True and closure['creation_outcome_unknown'] is False
             and closure['absence_observed'] is True, 'resource absence established')
    need(type(phase['command_records']) is list and phase['command_records'], 'durable CLI records required')
    clocks = [phase[k] for k in ('started', 'phase_work_deadline', 'phase_cleanup_deadline', 'finished')]
    need(all(finite_clock(t) for t in clocks) and phase['original_work_deadline'] == deadline,
         'phase original clock binding')
    start, work, end, finish = clocks
    need(origin <= start < work < end <= deadline and start <= finish < end,
         'complete phase within original phase/whole deadlines')
    descriptor(phase['artifacts'])
    need(type(phase['artifacts'].get('path')) is str, 'captured artifact locator without reading payload')


def validate_collection(doc, source, origin, deadline):
    need(type(doc) is dict and doc['schema'] == 'foraging_collection_v1' and doc['task_id'] == TASK,
         'complete FIND036 collection schema')
    need(doc['source'] == descriptor(source) and doc['original_origin'] == origin
         and doc['original_deadline'] == deadline and doc['all1320closed'] is True,
         'bound original source/clock collection')
    contexts, phases = doc['contexts'], doc['phases']
    need(type(contexts) is list and type(phases) is list and len(contexts) == len(phases) == 1320,
         'full1320 contexts and phases')
    expected = {(s, k, r, f) for s in {c['session_id'] for c in contexts}
                for k in ('native', 'fit', 'predict') for r in ('A', 'B', 'operator')
                for f in ((0,) if k == 'native' else range(1, 6))}
    keys = [(c['session_id'], c['kind'], c['role'], c['fold']) for c in contexts]
    need(len({k[0] for k in keys}) == 40 and len(set(keys)) == 1320 and set(keys) == expected,
         'complete forty-session three-role native/fit/predict product')
    need(len({c['id'] for c in contexts}) == 1320 and [c['index'] for c in contexts] == list(range(1320)),
         'complete unique phase identities and order')
    for context, phase in zip(contexts, phases):
        validate_phase(phase, context, origin, deadline)


def _reserve_final(budget, control):
    budget.tick()
    need(budget.write + FINAL_RESERVE <= budget.limits['write_bytes']
         and budget.retained + FINAL_RESERVE <= budget.limits['retained_bytes'],
         'reserved final-observation capacity')
    budget.reserve(control, FINAL_RESERVE)


def _write_reserved(path, body, budget):
    """Keep final receipt capacity unspent through every preceding owned write."""
    target = ordinary(path)
    additional = len(body) + 8192
    parent = target.parent
    while not parent.exists():
        additional += 8192
        parent = parent.parent
    need(budget.write + additional + FINAL_RESERVE <= budget.limits['write_bytes']
         and budget.retained + additional + FINAL_RESERVE <= budget.limits['retained_bytes'],
         'write must preserve final observation allocation')
    budget.reserve(parent, additional + FINAL_RESERVE)
    return write(target, body, budget)


def observe(selection_path, expected_hash):
    raw, envelope, budget = authority(selection_path, expected_hash, BOOT, 'outer_limits')
    required = {'schema', 'task_id', 'outer_limits', 'metadata_cap_bytes', 'controller_selection',
                'root_source', 'source_manifest', 'outer_control'}
    need(set(envelope) == required and envelope['schema'] == 'foraging_outer_selection_v1'
         and envelope['task_id'] == TASK, 'exact independent observer envelope')
    need(ordinary(envelope['root_source']) == Path(__file__).resolve().parent,
         'currently executing observer/common root equals independently selected source')
    cap = envelope['metadata_cap_bytes']
    need(type(cap) is int and cap > 0 and cap <= budget.limits['read_bytes']
         and cap <= budget.limits['retained_bytes'], 'explicit admitted metadata capacity')
    control = ordinary(envelope['outer_control'])
    need(not control.exists() and control.parent.is_dir(), 'fresh independent control directory')
    mkdir_owned(control, budget)
    _reserve_final(budget, control)
    child = sel = None
    buffers = {'out': bytearray(), 'err': bytearray()}
    eof = {'out': False, 'err': False}
    code = error = collection = post = derived_pin = work_end = root_selection_pin = None
    natural = absent = False
    closed_at = None
    snapshot = control / 'source'
    try:
        authority_body = read(envelope['controller_selection']['path'], envelope['controller_selection'], budget, cap)
        selected = parse(authority_body)
        root_selection_pin = pin(authority_body)
        need(selected['metadata_cap_bytes'] == cap and selected['root_source'] == envelope['root_source']
             and selected['source_manifest'] == envelope['source_manifest'], 'envelope/controller exact bindings')
        # Validate the complete controller clock/limit profile before deriving anything.
        controller_budget = Budget(selected['controller_limits'], BOOT)
        work_end = controller_budget.end
        need(work_end < budget.end and time.monotonic() < work_end, 'outer closure reserve after original work deadline')
        output = ordinary(selected['output'])
        need(control != output and control not in output.parents and output not in control.parents,
             'independent controller and observer output ownership')
        manifest_body = read(envelope['source_manifest']['path'], envelope['source_manifest'], budget, 1048576)
        manifest = parse(manifest_body)
        need(manifest['schema'] == 'foraging_program_source_v1' and manifest['task_id'] == TASK
             and type(manifest['files']) is dict and 1 <= len(manifest['files']) <= 128
             and {'observe.py', 'controller.py', 'common.py', 'adapter.py'} <= set(manifest['files']), 'exact complete runtime capture')
        for name, desc in manifest['files'].items():
            need(type(name) is str and name and not Path(name).is_absolute()
                 and '..' not in Path(name).parts and name != 'SOURCE_MANIFEST.json', 'ordinary source member')
            body = read(ordinary(envelope['root_source']) / name, desc, budget, 16777216)
            _write_reserved(snapshot / name, body, budget)
            _reserve_final(budget, control)
        _write_reserved(snapshot / 'SOURCE_MANIFEST.json', manifest_body, budget)
        for q in sorted(snapshot.rglob('*'), key=lambda q: len(q.parts), reverse=True):
            if q.is_dir():
                os.chmod(q, 0o555)
                sync(q)
        os.chmod(snapshot, 0o555)
        sync(snapshot)
        derived = {**selected, 'root_source': str(snapshot), 'source_manifest': {
            'path': str(snapshot / 'SOURCE_MANIFEST.json'), **descriptor(envelope['source_manifest'])}}
        derived_body = encode(derived)
        need(len(derived_body) <= cap, 'derived selection remains within admitted metadata capacity')
        derived_pin = _write_reserved(control / 'DERIVED_SELECTION.json', derived_body, budget)
        _write_reserved(control / 'DISPATCH.json', encode({
            'schema': 'foraging_outer_dispatch_v1', 'root_envelope': {'path': str(selection_path), **pin(raw)},
            'root_controller_selection': root_selection_pin, 'derived_selection': derived_pin,
            'source': descriptor(envelope['source_manifest']),
            'only_delta': ['root_source', 'source_manifest.path'], 'original_origin': BOOT,
            'original_deadline': work_end, 'outer_deadline': budget.end, 'no_retry': True,
        }), budget)
        _reserve_final(budget, control)
        need(budget.read + 2 * TERMINAL_CAP + cap + 1 <= budget.limits['read_bytes'],
             'remaining authority-read capacity includes streams and full collection')
        need(time.monotonic() < work_end, 'same original deadline before controller launch')
        command = [sys.executable, '-I', '-B', str(snapshot / 'controller.py'), '--selection',
                   str(control / 'DERIVED_SELECTION.json'), '--sha256', derived_pin['sha256'],
                   '--origin', str(BOOT)]
        child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, start_new_session=True, bufsize=0)
        _write_reserved(control / 'CHILD.json', encode({'pid': child.pid, 'pgid': child.pid,
              'original_origin': BOOT, 'spawn_to_persistence_gap_possible': True}), budget)
        sel = selectors.DefaultSelector()
        for label, stream in [('out', child.stdout), ('err', child.stderr)]:
            os.set_blocking(stream.fileno(), False)
            sel.register(stream, selectors.EVENT_READ, label)
        while sel.get_map():
            budget.tick()
            need(time.monotonic() < work_end, 'original controller completion deadline')
            for key, _ in sel.select(min(.1, max(0, work_end-time.monotonic()))):
                part = os.read(key.fileobj.fileno(), min(65536, TERMINAL_CAP + 1 - len(buffers[key.data])))
                if not part:
                    eof[key.data] = True
                    sel.unregister(key.fileobj)
                    continue
                budget.reading(len(part))
                buffers[key.data].extend(part)
                need(len(buffers[key.data]) <= TERMINAL_CAP, 'bounded controller stdout/stderr')
        code = child.wait(timeout=max(0, work_end-time.monotonic()))
        closed_at = time.monotonic()
        natural = True
        need(code == 0 and closed_at < work_end, 'natural controller exit0 before original deadline')
        try:
            os.killpg(child.pid, 0)
        except ProcessLookupError:
            absent = True
        need(absent and not buffers['err'], 'closed controller group and silent stderr')
        returned = parse(bytes(buffers['out']))
        need(set(returned) == {'collection', 'original_deadline', 'post_durability',
                              'requires_independent_outer_exit_admission'}, 'one exact controller summary')
        collection, post = returned['collection'], returned['post_durability']
        need(returned['requires_independent_outer_exit_admission'] is True
             and returned['original_deadline'] == work_end and finite_clock(post)
             and BOOT <= post <= closed_at < work_end, 'same original durable collection clock')
        need(ordinary(collection['path']) == output / 'COLLECTION.json', 'exact output collection path')
        collection_body = read(output / 'COLLECTION.json', collection, budget, cap)
        validate_collection(parse(collection_body), envelope['source_manifest'], BOOT, work_end)
    except BaseException as exc:
        error = {'type': type(exc).__name__, 'message': str(exc)[:512]}
    finally:
        if child is not None and not absent:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except BaseException as exc:
                error = error or {'type': type(exc).__name__, 'message': 'owned controller termination failed'}
            try:
                code = child.wait(timeout=max(0, min(1, budget.end-time.monotonic())))
            except BaseException:
                pass
        if sel is not None:
            sel.close()
        if child is not None:
            for stream in (child.stdout, child.stderr):
                if stream is not None:
                    stream.close()
    value = {
        'schema': 'foraging_outer_observation_v1', 'task_id': TASK,
        'source': descriptor(envelope['source_manifest']), 'root_envelope': pin(raw),
        'root_controller_selection': root_selection_pin, 'derived_selection': derived_pin,
        'collection': collection, 'natural_exit': natural, 'exit_code': code,
        'controller_pid': child.pid if child is not None else None,
        'owned_group_absent': absent, 'streams_eof': all(eof.values()),
        'original_origin': BOOT, 'original_deadline': work_end, 'outer_deadline': budget.end,
        'natural_exit_observed_at': closed_at,
        'stdout': pin(bytes(buffers['out'])), 'stderr': pin(bytes(buffers['err'])),
        'collection_durable_before_deadline': error is None and post is not None,
        'collection_post_durability': post, 'error': error,
        'outer_before_final_persistence': time.monotonic(),
        'resource_custody': 'all1320recordedclosures' if error is None else 'unknown; preserve prior resources and costs',
        'observed_logical_source_and_metadata_reads': budget.read,
        'observed_logical_writes_before_final_receipt': budget.write,
        'runtime_qualified': False, 'scientific_qualified': False,
    }
    receipt = persistence_error = None
    try:
        # No after-deadline or unbudgeted emergency write is called a durable success.
        receipt = write(control / 'OUTER.json', encode(value), budget)
    except BaseException as exc:
        persistence_error = {'type': type(exc).__name__, 'message': str(exc)[:512]}
    after = time.monotonic()
    success = error is None and receipt is not None and after < budget.end
    return {'observation': receipt, 'post_durability': after, 'original_deadline': budget.end,
            'success': success, 'persistence_error': persistence_error,
            'independent_root_terminal_admission_still_required': True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--selection', required=True)
    parser.add_argument('--sha256', required=True)
    args = parser.parse_args()
    try:
        result = observe(args.selection, args.sha256)
    except BaseException as exc:
        result = {'success': False, 'observation': None, 'original_origin': BOOT,
                  'error': {'type': type(exc).__name__, 'message': str(exc)[:512]},
                  'independent_root_terminal_admission_still_required': True}
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    raise SystemExit(0 if result['success'] else 2)


if __name__ == '__main__':
    main()
