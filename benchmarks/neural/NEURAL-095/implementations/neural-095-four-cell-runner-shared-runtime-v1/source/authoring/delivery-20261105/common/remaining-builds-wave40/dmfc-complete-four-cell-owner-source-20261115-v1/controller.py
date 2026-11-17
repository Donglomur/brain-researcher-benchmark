"""Owned complete four-cell controller; one producer ABI and protected grade."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time
import types

sys.dont_write_bytecode = True
HERE = Path(__file__).absolute().parent
ROOT = HERE.parents[4]


def need(ok, message):
    if not ok:
        raise ValueError(message)


def capture(path, cap=262144):
    path = Path(path).absolute()
    need(all(not x.is_symlink() for x in (path, *path.parents)), 'ordinary controller bootstrap')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        a = os.fstat(fd)
        need(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and 0 < a.st_size <= cap, 'bounded bootstrap file')
        with os.fdopen(fd, 'rb', closefd=False) as f:
            body = f.read(cap + 1)
        b = os.fstat(fd)
        need(len(body) == a.st_size and all(getattr(a, k) == getattr(b, k) for k in
             ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')), 'stable bootstrap bytes')
    finally:
        os.close(fd)
    return body


def bootstrap(path, expected_sha):
    body = capture(path)
    need(hashlib.sha256(body).hexdigest() == expected_sha, 'exact selected config')
    value = json.loads(body); need(value['repository_root'] == str(ROOT), 'fixed repository')
    def checked(pin):
        need(not Path(pin['path']).is_absolute() and '..' not in Path(pin['path']).parts, 'relative frozen source')
        raw = capture(ROOT / pin['path'])
        need(len(raw) == pin['bytes'] and hashlib.sha256(raw).hexdigest() == pin['sha256'], 'exact controller bootstrap source')
        return raw
    freeze = json.loads(checked(value['successor_freeze']))
    need(freeze['entrypoint']['path'] == (HERE / 'entrypoint.py').relative_to(ROOT).as_posix(), 'fixed trusted entrypoint')
    source = checked(freeze['entrypoint'])
    module = types.ModuleType('_dmfc_owned_controller_entry'); module.__file__ = str(HERE / 'entrypoint.py')
    exec(compile(source, module.__file__, 'exec'), module.__dict__)
    return module.bootstrap(path, expected_sha)


def compose(config, stack, runtime, work_end):
    """Construct the real Study, keeping actors outside every numerical unit."""
    values = config.value; out = Path(values['output_root']); live = stack.live; api = stack.producer
    need(getattr(stack.actor_backend, 'live') is live, 'one injected accepted adapter')
    budget = runtime.HostBudget(out, values['host_budget']['artifact_bytes'], values['host_budget']['receipt_bytes'])
    original_write = live.write
    def budgeted_write(path, body, cap=1048576):
        budget.safe_destination(path); budget.check(len(body))
        return original_write(path, body, cap)
    live.write = budgeted_write  # Private loaded instance only; source file is immutable.
    executor = live.UnitExecutor(runtime.unit, budget, out / 'units', work_end,
        max_units=46, receipt_cap_bytes=values['host_budget']['receipt_bytes'])
    limits = api.Limits(api.Usage(**values['limits']['total']), api.Usage(**values['limits']['preparation']),
        values['limits']['wall_us'], values['limits']['preparation_wall_us'],
        values['limits']['max_memory_bytes'], values['limits']['response_bytes'])
    reservations = {key: api.Usage(**v) for key, v in values['reservation_policy'].items()}
    manifest = api.load_manifest(); identity = manifest['evaluator_only_assets']['identity']
    ids = tuple(live.decode(live.read(ROOT / identity['path'], (identity['bytes'], identity['sha256'])))['case_id'])
    need(len(ids) == 258 and len(set(ids)) == 258, 'all canonical assessment cases')
    tool_id = 'dmfc_predict@' + values['numerical_tool']['sha256']
    tools = {tool_id: config.numerical_source}; backends = []
    def actor_factory(started, deadline, backend):
        key = backend.mode + '__' + backend.view
        arm = out / 'arms' / key; arm.mkdir(mode=0o700)
        channel = stack.actor_backend.Channel(arm / 'arm.sock', stack.wire.Wire,
            stack.peer_uid, deadline / 1000000, limits.response_bytes)
        event_count = 0
        def event(name, **data):
            nonlocal event_count
            event_count += 1
            need(event_count <= 8, 'finite actor lifecycle event ledger')
            stack.entrypoint.durable(arm / ('event-%02d.json' % event_count),
                {'event': name, 'context': key, 'config_sha256': config.sha256, **data}, budget)
        session = types.SimpleNamespace(mode=key, started=started, limits=limits, _event=event)
        supervisor = stack.actor_runtime.Supervisor(config, stack, runtime, session, budget, work_end)
        try:
            stack.entrypoint.durable(out / 'invitations' / (key + '.json'), {
                'mode': key, 'socket': str(channel.path), 'token': channel.token,
                'candidate_deadline_us': deadline, 'actor_binding': values['actor']['arms'][key]}, budget)
        except BaseException:
            channel.close(); raise
        return supervisor, channel
    def backend_factory(mode, view):
        b = stack.actor_backend.ActorBackend(api=api, mode=mode, view=view, executor=executor,
            output=out / 'cells' / (mode + '__' + view), tools=tools, case_ids=ids,
            limits=limits, reservations=reservations, comparison_id=config.request_sha256,
            preparation_tool_id=tool_id, actor_factory=actor_factory)
        backends.append(b); return b
    sources = {mode: stack.captured_sources[values['actor']['arms'][mode + '__cue_only']['program']['path']]
               for mode in api.MODES}
    methods = dict.fromkeys(api.MODES, config.method_source)
    evaluator = live.PairedEvaluator(api=api, executor=executor, output=out / 'evaluator',
        deadline=work_end, cpu_reservation_us=reservations['tool'].cpu_us)
    study = api.Study(sources=sources, methods=methods, case_ids=ids, limits=limits,
        reservations=reservations, tool_ids=tuple(tools), backend_factory=backend_factory,
        evaluator=evaluator, comparison_id=config.request_sha256)
    return study, backends, budget


def run(config, stack, runtime, owner_directory, work_end, whole_end):
    out = Path(config.value['output_root'])
    need(Path(owner_directory) == out / 'owner' and time.monotonic() < work_end < whole_end,
         'original absolute whole/work horizons')
    owner, unused = runtime.owner.expected(out / 'owner')
    need(os.getpgrp() == owner['pgid'] and os.getppid() == owner['pid'] and owner['child_argv'] ==
         [sys.executable, str(Path(__file__).absolute()), *sys.argv[1:]], 'actual owned controller identity and argv')
    need(config.guard is not None, 'owned controller joined managed read ledger')
    result = {'schema': 'dmfc-complete-four-cell-controller-result/v1', 'config_sha256': config.sha256,
              'request_sha256': config.request_sha256, 'status': 'failed_preserved'}
    study, backends, budget = compose(config, stack, runtime, work_end)
    try:
        result['study_result'] = study.run()
        need(result['study_result']['status'] == 'four_cell_outputs_scored', 'full immutable study result')
        need(time.monotonic() < work_end, 'no late successful controller result')
        result['status'] = 'four_cell_outputs_scored'
    except BaseException as error:
        result['error_type'] = type(error).__name__
    finally:
        for backend in backends:
            try:
                need(all(backend.stop().values()), 'complete cell absence')
            except BaseException as error:
                result['status'] = 'failed_preserved'; result['cleanup_error_type'] = type(error).__name__
        result['managed_reads'] = config.guard.report()
        stack.entrypoint.durable(out / 'controller_result.json', result, budget)
    return 0 if result['status'] == 'four_cell_outputs_scored' else 2


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True); parser.add_argument('--config-sha256', required=True)
    parser.add_argument('--owner-directory', required=True)
    parser.add_argument('--work-deadline', type=float, required=True); parser.add_argument('--whole-deadline', type=float, required=True)
    args = parser.parse_args(argv)
    unused, config, stack, runtime = bootstrap(args.config, args.config_sha256)
    return run(config, stack, runtime, args.owner_directory, args.work_deadline, args.whole_deadline)


if __name__ == '__main__':
    raise SystemExit(main())
