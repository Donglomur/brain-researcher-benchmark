"""Fixed Fly native inspection then independent audit; no native selection here."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import signal
import stat
import sys
import time

DYNAMIC = {'selected', 'selected_at_unix_ns', 'outside_host_bytes',
           'outside_disk_bytes', 'other_selected_cpu_slots', 'root_decision'}


def need(ok, why):
    if not ok:
        raise ValueError(why)


def strict_pairs(items):
    result = {}
    for key, value in items:
        need(key not in result, 'duplicate request key')
        result[key] = value
    return result


def read_request(path, *, fresh=True):
    source = Path(__file__).absolute().parent
    with (source/'REQUEST_TEMPLATE.json').open('rb') as handle:
        template = json.loads(handle.read(65537), object_pairs_hook=strict_pairs)
    p = Path(path); s = p.lstat()
    need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and stat.S_IMODE(s.st_mode) == 0o600
         and s.st_size <= 65536, 'private ordinary bounded request')
    with p.open('rb') as handle:
        body = handle.read(65537)
    need(len(body) <= 65536, 'request extent')
    req = json.loads(body, object_pairs_hook=strict_pairs)
    need(set(req) == set(template), 'exact fixed request schema')
    need(all(req[k] == template[k] for k in template if k not in DYNAMIC), 'fixed request fields')
    need(req['selected'] is True, 'authentic operation not selected')
    for name in ('selected_at_unix_ns', 'outside_host_bytes', 'outside_disk_bytes', 'other_selected_cpu_slots'):
        need(type(req[name]) is int and req[name] >= 0, 'exact booking integer')
    if fresh:
        need(0 <= time.time_ns()-req['selected_at_unix_ns'] <= 120000000000, 'fresh root selection required')
    need(type(req['root_decision']) is dict and set(req['root_decision']) == {'path', 'bytes', 'sha256'},
         'root decision identity required')
    need(type(req['root_decision']['bytes']) is int and 0 < req['root_decision']['bytes'] <= 262144,
         'bounded root decision')
    return req, body


def module(name, row):
    p = Path(row['path']); s = p.lstat()
    need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and s.st_size == row['bytes'] <= 262144, 'exact ordinary source')
    body = p.read_bytes()
    need(hashlib.sha256(body).hexdigest() == row['sha256'], 'source hash')
    spec = importlib.util.spec_from_file_location(name, p)
    result = importlib.util.module_from_spec(spec)
    exec(compile(body, str(p), 'exec'), result.__dict__)
    return result


def capacity(memory, disk, req):
    host = req['outside_host_bytes']+req['own_host_bytes']+1073741824
    storage = req['outside_disk_bytes']+req['own_retention_bytes']+1073741824
    return dict(memory_potential_bytes=memory, disk_available_bytes=disk,
                host_floor_bytes=host, disk_floor_bytes=storage, passed=memory >= host and disk >= storage,
                interpretation='Free plus file-backed pages is a heuristic, not guaranteed reclaimable RAM.',
                own_serial_cpu_slots=1, outside_selected_cpu_slots=req['other_selected_cpu_slots'],
                source_helpers_cpu_nonzero=True)


def final_products(output, audit):
    root = Path(output); s = root.lstat()
    need(stat.S_ISDIR(s.st_mode) and stat.S_IMODE(s.st_mode) == 0o700, 'private product directory')
    need({p.name for p in root.iterdir()} == {'census.jsonl', 'audit.json'}, 'exact complete products')
    rows = []; total = 0
    for name, cap in (('census.jsonl', 67108864), ('audit.json', 65536)):
        p = root/name; st = p.lstat()
        need(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and stat.S_IMODE(st.st_mode) == 0o600
             and st.st_size <= cap, 'private bounded ordinary product')
        sha = hashlib.sha256(); count = 0
        with p.open('rb') as handle:
            while True:
                block = handle.read(65536)
                if not block: break
                count += len(block); sha.update(block)
        need(count == st.st_size, 'product extent changed')
        after = p.lstat()
        need(all(getattr(st, k) == getattr(after, k) for k in
                 ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')),
             'product custody changed')
        rows.append(dict(file=name, bytes=count, sha256=sha.hexdigest())); total += count
    need(audit['status'] == 'PASS' and audit['files'] == 42 and audit['trials'] == 1345
         and audit['fields_compared'] == 32280 and audit['full_source_and_report_comparison'] is True,
         'independent complete source comparison')
    need(audit['schema'] == 'fly-independent-native-joins-source-report-audit-v2' and
         audit['optional_fields_compared'] == 470 and audit['optional_absent_slots'] == 2220 and
         audit['source_join_diagnostics_compared'] == 1345 and
         audit['optional_plan_sha256'] == 'e25d53f30c0404164f89553cf414c92c145bcb33eec341973cd4a43dc88ac034',
         'complete optional and diagnostic comparison')
    need(audit['scientific_admission'] is False and audit['physical_offset_inference'] is False
         and audit['animal_inference'] is False, 'scientific holds')
    need(audit['report'] == {k: rows[0][k] for k in ('bytes', 'sha256')}, 'complete report identity join')
    return dict(files=rows, hash_read_bytes=total, scientific_admission=False)


def run_sequence(run, validate):
    """One fixed ordered pair; the second stage is impossible after first refusal."""
    for label in ('PRODUCE', 'AUDIT'):
        result = run(label)
        need(result['complete'], 'owned stage did not close completely')
        validate(label, result)


def main(request_path):
    started = time.monotonic()
    resource.setrlimit(resource.RLIMIT_CPU, (30, 450))
    req, request_body = read_request(request_path)
    need(os.getpid() == os.getpgrp(), 'outer owner must have its own process group')
    base = module('fly_admitted_small_owner', req['base_owner'])
    base.blob(req['root_decision'])
    root, output = Path(req['owner_output']), Path(req['output'])
    for p in (root, output):
        need(not p.exists() and not p.is_symlink(), 'fresh exact namespaces required')
    root.mkdir(mode=0o700)
    result = dict(status='failed_partial_preserved', owner_pid=os.getpid(), owner_pgid=os.getpgrp(),
                  request_sha256=hashlib.sha256(request_body).hexdigest(), stages=[], error=None,
                  scientific_admission=False, hard_aggregate_rss_enforced=False)
    signals = []

    def interrupted(signum, frame):
        signals.append(signum); signal.alarm(0)
        raise TimeoutError('owner interruption')

    for sig in (signal.SIGALRM, signal.SIGINT, signal.SIGTERM, signal.SIGXCPU):
        signal.signal(sig, interrupted)
    signal.alarm(1260)
    try:
        for row in req['sources']:
            base.blob(row)
        runner = base.module('fly_admitted_process_owner', req['process_owner'])
        closer = base.module('fly_admitted_process_closer', req['process_closer'])
        env = {'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C', 'PYTHONDONTWRITEBYTECODE': '1'}

        def birth(label):
            return lambda child: base.write(root/(label+'_BIRTH.json'),
                dict(pid=child.pid, pgid=child.pid, parent_pid=os.getpid(),
                     registered_before_work_gate=label != 'VM'))

        vm = runner.run_owned(['/usr/bin/vm_stat'], root, env, started+10,
            root/'vm.stdout', root/'vm.stderr', closer, work_until=started+5,
            stream_cap=16384, on_spawn=birth('VM'), signals=signals)
        result['stages'].append(vm); need(vm['complete'], 'fresh capacity observation failed')
        disk = os.statvfs(root)
        gate = capacity(base.memory_potential((root/'vm.stdout').read_text()), disk.f_bavail*disk.f_frsize, req)
        gate['observed_at_unix_ns'] = time.time_ns(); result['capacity'] = gate
        base.write(root/'CAPACITY.json', gate)
        if not gate['passed']:
            result['status'] = 'capacity_refused_no_native_inspection'
            return 2
        output.mkdir(mode=0o700)

        def run(label):
            gate_body = (json.dumps(dict(owner_pid=os.getpid(), request_sha256=result['request_sha256'], stage=label))+'\n').encode()
            begin = time.monotonic()
            owned = runner.run_owned([req['python'], '-I', '-S', '-B', req['worker']['path'],
                '--request', str(request_path), '--stage', label], root, env,
                min(started+1240, begin+610), root/(label+'.stdout'), root/(label+'.stderr'), closer,
                work_until=min(started+1220, begin+600), stream_cap=16384,
                on_spawn=birth(label), start_gate=gate_body, signals=signals)
            result['stages'].append(owned)
            return owned

        def validate(label, owned):
            record = json.loads((root/(label+'_RESULT.json')).read_bytes())
            need(record['status'] == 'complete' and record['pid'] == owned['pid'] and
                 record['stage'] == label and record['request_sha256'] == result['request_sha256'], 'worker completion join')
            need(record['observed_maxrss_bytes_macos'] <= 201326592, 'worker observed memory allowance exceeded')
            result[label.lower()] = record

        run_sequence(run, validate)
        audit = json.loads((output/'audit.json').read_bytes())
        result['products'] = final_products(output, audit)
        result['independent_audit'] = audit
        need(time.monotonic() < started+1240, 'whole owner horizon')
        result['status'] = 'complete_native_inspection_and_independent_audit_owned_closed'
        return 0
    except BaseException as exc:
        result['error'] = dict(type=type(exc).__name__, code=str(exc)[:256])
        return 1
    finally:
        signal.alarm(0)
        own = resource.getrusage(resource.RUSAGE_SELF); children = resource.getrusage(resource.RUSAGE_CHILDREN)
        result.update(elapsed_seconds=time.monotonic()-started,
            owner_cpu_seconds=own.ru_utime+own.ru_stime, all_reaped_child_cpu_seconds=children.ru_utime+children.ru_stime,
            observed_owner_maxrss_bytes_macos=own.ru_maxrss, signals=signals)
        if own.ru_maxrss > 67108864:
            result['status'] = 'failed_owner_observed_memory_allowance'
        if own.ru_utime+own.ru_stime > 35:
            result['status'] = 'failed_owner_observed_cpu_allowance'
        base.write(root/'OWNER_RESULT.json', result)
        print(json.dumps(dict(status=result['status'], owner_pid=os.getpid(), result=str(root/'OWNER_RESULT.json'))))
        if own.ru_maxrss > 67108864 or own.ru_utime+own.ru_stime > 35:
            raise SystemExit(1)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(); parser.add_argument('--request', required=True)
    sys.exit(main(parser.parse_args().request))
