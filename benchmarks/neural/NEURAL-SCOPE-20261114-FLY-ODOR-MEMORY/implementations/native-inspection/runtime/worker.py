"""Fixed gated producer/auditor child of the reviewed Fly owner."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time


def main(request_path, stage):
    resource.setrlimit(resource.RLIMIT_CPU, (450, 450))
    started = time.monotonic()
    def interrupted(signum, frame): raise TimeoutError('worker selected horizon')
    for sig in (signal.SIGALRM, signal.SIGTERM, signal.SIGINT, signal.SIGXCPU):
        signal.signal(sig, interrupted)
    signal.alarm(595)
    spec = importlib.util.spec_from_file_location('fly_fixed_owner', Path(__file__).with_name('owner.py'))
    owner = importlib.util.module_from_spec(spec); spec.loader.exec_module(owner)
    gate_body = sys.stdin.buffer.read(4097)
    owner.need(len(gate_body) <= 4096, 'bounded work gate')
    gate = json.loads(gate_body, object_pairs_hook=owner.strict_pairs)
    owner.need(set(gate) == {'owner_pid', 'request_sha256', 'stage'} and stage in ('PRODUCE', 'AUDIT')
               and gate['stage'] == stage and gate['owner_pid'] == os.getppid()
               and os.getpid() == os.getpgrp(), 'registered owner work gate')
    req, body = owner.read_request(request_path, fresh=False)
    digest = hashlib.sha256(body).hexdigest()
    owner.need(gate['request_sha256'] == digest, 'request gate identity')
    base = owner.module('fly_admitted_small_owner', req['base_owner'])
    status, error = 'failed_partial_preserved', None
    try:
        for row in req['sources']: base.blob(row)
        # The auditor authenticates all four exact successor consumer modules.
        auditor = owner.module('fly_independent_auditor', req['auditor'])
        consumer = auditor.load_consumer()
        class Guard(consumer.Budget):
            def check(self):
                super().check()
                if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss > 184549376:
                    raise MemoryError('observed worker peak guard')
        budget = Guard(wall_seconds=590)
        if stage == 'PRODUCE':
            result = consumer.inspect_archive(req['archive']['path'], req['operand_plan']['path'],
                str(Path(req['output'])/'census.jsonl'), optional_path=req['optional_plan']['path'], budget=budget)
        else:
            result = auditor.audit_archive(req['archive']['path'], req['operand_plan']['path'],
                str(Path(req['output'])/'census.jsonl'), optional_path=req['optional_plan']['path'], budget=budget)
            auditor.write_result(str(Path(req['output'])/'audit.json'), result)
        budget.check()
        status = 'complete'
    except BaseException as exc:
        error = dict(type=type(exc).__name__, code=str(exc)[:128] if isinstance(exc, auditor.AuditError)
                     else 'bounded_stage_refusal') if 'auditor' in locals() else dict(type=type(exc).__name__)
        raise
    finally:
        signal.alarm(0)
        usage = resource.getrusage(resource.RUSAGE_SELF)
        base.write(Path(req['owner_output'])/(stage+'_RESULT.json'), dict(status=status, error=error,
            stage=stage, pid=os.getpid(), pgid=os.getpgrp(), parent_pid=os.getppid(), request_sha256=digest,
            elapsed_seconds=time.monotonic()-started, cpu_user_seconds=usage.ru_utime,
            cpu_system_seconds=usage.ru_stime, observed_maxrss_bytes_macos=usage.ru_maxrss,
            hard_aggregate_rss_enforced=False, scientific_admission=False,
            result=result if status == 'complete' else None))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(); parser.add_argument('--request', required=True)
    parser.add_argument('--stage', choices=('PRODUCE', 'AUDIT'), required=True)
    args = parser.parse_args(); main(args.request, args.stage)
