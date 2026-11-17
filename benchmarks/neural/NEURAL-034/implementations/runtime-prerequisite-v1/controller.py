"""Original unit lifecycle for two explicitly generated inputs; no private grading."""
import argparse
import hashlib
import math
from pathlib import Path
import signal
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import support as s


def main():
    p = argparse.ArgumentParser(); p.add_argument('--fixture', required=True)
    p.add_argument('--fixture-sha256', required=True); p.add_argument('--work-end', type=float, required=True)
    p.add_argument('--whole-end', type=float, required=True); a = p.parse_args()
    root = Path(__file__).resolve().parents[2]
    body = s.read(a.fixture); s.need(s.pin(body)['sha256'] == a.fixture_sha256, 'Exact controller fixture')
    plan = s.decode(body); out = root / 'artifacts-build/runtime-prerequisite'
    api, _ = s.runtime(root, plan['source_freeze'])
    owner, _ = api.owner.expected(out)
    s.need(owner['child_argv'] == [sys.executable, *sys.argv] and math.isfinite(a.work_end) and
           math.isfinite(a.whole_end) and time.monotonic() < a.work_end < a.whole_end <= time.monotonic() + 115,
           'Exact activated controller and deadline')
    def stop(*unused):
        raise TimeoutError('Generated controller work deadline')
    signal.signal(signal.SIGALRM, stop)
    signal.setitimer(signal.ITIMER_REAL, max(.001, a.work_end - time.monotonic()))
    budget = api.HostBudget(out, limit=12 * 1024**2, reserve=2 * 1024**2)
    program = root / plan['program']['path']
    s.checked(root, plan['program'], 65536)
    results = []; previous = None
    try:
        for index, unit in enumerate(plan['units']):
            s.need(unit['unit_id'] == f'fixture-{index:02d}' and len(plan['units']) == 2,
                   'Exactly two ordered generated units')
            destination = out / unit['unit_id']
            result = api.unit.run_unit(program, plan['program']['sha256'], unit, destination,
                budget, a.work_end - 10, a.whole_end - 5, previous, 'NEURAL-034',
                lambda raw, active: api.assembler.validate(raw, active['expected_ids']))
            probe = s.validate_probe(result, index + 1)
            commitment = s.read(destination / 'commit.json', 100000)
            previous = hashlib.sha256(commitment).hexdigest()
            s.need(previous == result['commit_sha256'], 'Exact generated commitment')
            results.append({'unit_id': unit['unit_id'], 'probe': probe,
                            'commit_sha256': previous, 'producer': result['producer']})
        s.need(len({row['producer']['container_id'] for row in results}) == 2,
               'Separate immutable generated producers')
        s.save(out / 'controller_result.json', {'status': 'two_generated_units_closed', 'units': results,
            'generated_queries': 40, 'authentic_inputs': 0, 'scientific_scores': 0, 'runtime_qualified': False})
        return 0
    except BaseException as error:
        s.save(out / 'controller_failure.json', {'error': repr(error), 'completed_units': results,
                                               'runtime_qualified': False})
        return 2
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == '__main__':
    raise SystemExit(main())
