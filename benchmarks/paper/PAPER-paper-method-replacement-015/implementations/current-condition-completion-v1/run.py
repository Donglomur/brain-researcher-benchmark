"""One complete 88-context fixed-control campaign, with an explicit whole clock.

This operator code creates real containers only when its CLI is deliberately
invoked. Source tests and a saved source descriptor are not execution authority.
"""
import argparse
import builtins
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys
import time
import types

HERE = Path(__file__).resolve().parent


def local_modules():
    """Avoid an ambient module named source/profile under isolated invocation."""
    modules = {}
    ordinary_import = builtins.__import__

    def own_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 0 and name in modules:
            return modules[name]
        return ordinary_import(name, globals, locals, fromlist, level)

    for name in ('source', 'profile', 'observer'):
        path = HERE / (name + '.py')
        module = types.ModuleType('_spinal_completion_' + name)
        module.__file__ = str(path)
        module.__dict__['__builtins__'] = dict(vars(builtins), __import__=own_import)
        if name == 'source':
            body = path.read_bytes()
        else:
            body = modules['source'].capture(path, 100_000)
        exec(compile(body, str(path), 'exec'), module.__dict__)
        modules[name] = module
    return types.SimpleNamespace(**modules)


def load_plan(path, expected_sha, source, profile):
    body = source.capture(path, 32_768)
    source.need(source.pin(body)['sha256'] == expected_sha, 'exact operator-selected plan')
    plan = profile.validate(source.decode(body))
    output = Path(plan['output'])
    for name in ('bank', 'assets'):
        original = Path(plan[name])
        source.need(output != original and output not in original.parents
                    and original not in output.parents, 'separate protected inputs and output tree')
    source.need(HERE not in output.parents and output not in HERE.parents,
                'attempt outside source checkout')
    return plan, body


def worker(plan, plan_pin, loaded, source, profile, deadline):
    """No new clock is granted in the child; all phases share parent's deadline."""
    def expired(signum, frame):
        raise TimeoutError('whole fixed-control worker deadline')

    source.need(deadline - time.monotonic() > 95, 'original worker cleanup window')
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, deadline - time.monotonic() - 95)
    root = Path(plan['output'])
    control = root / 'control'
    try:
        pair, contents = loaded.contract.freeze_pair(control, control, plan['purpose'], 'hz')
        loaded.contract.check_pair(pair, contents)
        # These are operator reads. No participant receives the private bank.
        bank = loaded.current.load_bank(Path(plan['bank']))
        assets = {arm: loaded.materials.capture_assets(Path(plan['assets']), arm)
                  for arm in loaded.contract.ARMS}
        selected = profile.runtime(plan, loaded.transport, loaded.completion_pin, plan_pin,
                                   deadline=deadline, now=time.monotonic())
        modules = loaded.contract.load_reused()
        docker = modules['runtime'].Docker(plan['docker'], Path(plan['docker_socket']))
        loaded.transport.run_pair(bank, assets, pair, contents, root / 'campaign', selected,
                                  loaded.delivery_pin, docker,
                                  other_reserve_bytes=plan['other_reserve_bytes'],
                                  source_checker=lambda: loaded.transport.verify_source(source.BASE_SHA))
        # The unchanged per-fold callback retains its512KiB source allowance.
        # New completion modules were already authenticated before label access
        # and execute from captured bytes; their complete closure is rechecked
        # here before this worker can attest success, then again by the parent.
        source.load_source(loaded.completion_pin['sha256'])
        source.need(time.monotonic() < deadline - 40, 'outer receipt/reaping window preserved')
        print(json.dumps({'complete': True, 'completion_source': loaded.completion_pin,
                          'delivery_source': loaded.delivery_pin, 'plan': plan_pin,
                          'folds': 88, 'scientific_scoring': False}, sort_keys=True))
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def outer(plan, plan_body, loaded, modules, began):
    source = modules.source
    root = Path(plan['output'])
    source.need(not root.exists() and not root.is_symlink(), 'fresh attempt namespace')
    source.need(not any(p.is_symlink() for p in root.parents), 'unlinked output ancestors')
    # This sideband has a separate fixed1MiB allowance in the prospective protocol.
    # It does not reset the unchanged campaign's2GiB managed-write accounting.
    source.need(root.parent.is_dir(), 'existing operator-owned output parent')
    source.need(__import__('shutil').disk_usage(root.parent).free >=
                loaded.transport.FLOOR + plan['other_reserve_bytes']
                + loaded.transport.RETAINED + 1024**2, 'whole prospective disk reserve')
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    source.save(root / 'PLAN.json', plan_body, 32768)
    control = root / 'control'
    control.mkdir(mode=0o700)
    control.chmod(0o700)
    source.save(control / 'program.py', source.capture(HERE / 'control/program.py', 32_768), 32768)
    plan_pin = source.pin(plan_body)
    deadline = began + plan['campaign_seconds']
    intent = {'schema': 'spinal_current_completion_intent_v1',
              'completion_source': loaded.completion_pin, 'delivery_source': loaded.delivery_pin,
              'plan': plan_pin, 'started_monotonic': began, 'deadline_monotonic': deadline,
              'all_88_contexts_required': True, 'automatic_retry': False,
              'engineering_control': True, 'scientific_scoring': False}
    source.save(root / 'INTENT.json', source.encoded(intent))
    argv = [sys.executable, '-I', '-B', str(HERE / 'run.py'),
            '--plan', str(root / 'PLAN.json'), '--plan-sha256', plan_pin['sha256'],
            '--source-sha256', loaded.completion_pin['sha256'],
            '--worker', '--deadline-monotonic', repr(deadline)]
    env = os.environ.copy()
    env.update({name: '1' for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS',
               'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'BLIS_NUM_THREADS')})
    stdout = stderr = b''
    observation = None
    try:
        stdout, stderr, observation = modules.observer.observe(argv, deadline, env)
        source.need(source.decode(stdout) == {'complete': True, 'completion_source': loaded.completion_pin,
                    'delivery_source': loaded.delivery_pin, 'plan': plan_pin,
                    'folds': 88, 'scientific_scoring': False}, 'exact worker completion response')
        source.load_source(loaded.completion_pin['sha256'])
        completion = loaded.transport.capture_completion(root / 'campaign', loaded.delivery_pin)
        value = source.decode(source.capture(root / 'campaign/WORKER_COMPLETE.json', 100_000, completion))
        manifest_pins = {arm: value['arms'][arm]['prediction_manifest'] for arm in loaded.contract.ARMS}
        for arm, expected in manifest_pins.items():
            source.capture(root / 'campaign' / arm / 'candidate/PREDICTIONS.json', 100_000, expected)
        source.need(not (root / 'campaign/FAILED.json').exists(), 'no contradictory campaign failure')
        source.need(time.monotonic() < deadline, 'original whole completion deadline')
        result = {'schema': 'spinal_current_completion_host_exit_v1',
                  'completion_source': loaded.completion_pin, 'delivery_source': loaded.delivery_pin,
                  'plan': plan_pin, 'worker_complete': completion, 'worker_observation': observation,
                  'candidate_manifests': manifest_pins, 'campaign_relative_path': 'campaign',
                  'stdout': source.pin(stdout), 'stderr': source.pin(stderr),
                  'folds': 88, 'eligible_recordings_per_arm': 116,
                  'engineering_control': True, 'scientific_scoring': False,
                  'external_observed_exit_zero_required': True,
                  'historical_paper_or_reference_qualification': False,
                  'elapsed_seconds': time.monotonic() - began}
        source.save(root / 'worker.stdout', stdout, modules.observer.PIPE_CAP)
        source.save(root / 'worker.stderr', stderr, modules.observer.PIPE_CAP)
        source.save(root / 'HOST_EXIT.json', source.encoded(result))
        print(json.dumps({'host_complete': True, 'folds': 88, 'scientific_scoring': False}))
        return result
    except BaseException as error:
        if isinstance(error, modules.observer.Failure):
            stdout, stderr, observation = error.stdout, error.stderr, error.observation
        for name, body in (('worker.stdout', stdout), ('worker.stderr', stderr)):
            if not (root / name).exists():
                source.save(root / name, body, modules.observer.PIPE_CAP)
        failure = {'schema': 'spinal_current_completion_failed_v1', 'error_type': type(error).__name__,
                   'worker_observation': observation, 'completion_claimed': False,
                   'container_absence_inferred': False, 'automatic_retry': False,
                   'stdout': source.pin(stdout), 'stderr': source.pin(stderr)}
        source.save(root / 'FAILED.json', source.encoded(failure))
        raise


def main():
    began = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--plan-sha256', required=True)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--deadline-monotonic', type=float, help=argparse.SUPPRESS)
    args = parser.parse_args()
    modules = local_modules()
    loaded = modules.source.load_source(args.source_sha256)
    plan, body = load_plan(args.plan, args.plan_sha256, modules.source, modules.profile)
    if args.worker:
        modules.source.need(args.deadline_monotonic is not None
                            and 0 < args.deadline_monotonic - time.monotonic() <= plan['campaign_seconds'],
                            'same inherited original deadline')
        worker(plan, modules.source.pin(body), loaded, modules.source, modules.profile, args.deadline_monotonic)
    else:
        modules.source.need(args.deadline_monotonic is None, 'only parent chooses deadline')
        outer(plan, body, loaded, modules, began)


if __name__ == '__main__':
    main()
