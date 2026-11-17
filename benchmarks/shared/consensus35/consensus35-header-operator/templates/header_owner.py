"""Complete35 NPY header inquiry; source-inert until explicit root selection.

Reuses accepted bounded metadata ownership and canonical redirect range transport.
Only primitive NPY magic/length/header ranges are proposed; no numerical payload.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import ssl
import stat
import sys
import time
import types
import urllib.error
import urllib.request

MIB = 1048576
GIB = 1024 * MIB
BODY_CAP = 0
OUTSIDE_HOST = 1342177280
OUTSIDE_DISK = 17368612864
MEMORY_FLOOR = OUTSIDE_HOST + 128 * MIB + GIB
DISK_FLOOR = OUTSIDE_DISK + 16 * MIB + GIB
OUTPUT = Path('/UNCONFIGURED/producer')
READS = 0
LIMITS = {
    "actual_continuous_wall_seconds": 1500, "owner_CPU_seconds": 5,
    "worker_CPU_seconds": 30, "probe_CPU_seconds": 5,
    "actual_total_CPU_seconds": 40, "owner_host_bytes": 64*MIB,
    "worker_host_bytes": 64*MIB, "whole_host_bytes": 128*MIB,
    "owner_explicit_read_bytes": 4*MIB, "worker_explicit_read_bytes": 4*MIB,
    "actual_retention_bytes": 8*MIB, "whole_retention_bytes": 16*MIB,
    "maximum_HEADs": 0, "maximum_GETs": 210, "logical_ranges": 105, "returned_entity_bytes": 143780,
    "raw_bytes": 8*MIB, "raw_files": 512, "raw_member_bytes": 262144,
    "independent_audit_CPU_seconds": 10, "independent_audit_wall_seconds": 90,
    "independent_audit_read_bytes": 12*MIB, "independent_audit_host_bytes": 128*MIB,
    "whole_actual_and_audit_CPU_seconds": 50,
    "whole_actual_and_audit_wall_seconds": 1590
}


def need(ok, message):
    if not ok:
        raise ValueError(message)



def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=False, allow_nan=False) + '\n').encode()



def read_pin(row, cap=262144):
    global READS
    p = Path(row['path'])
    need(p.is_absolute() and '..' not in p.parts and
         not any(x.is_symlink() for x in (p, *p.parents)), 'ordinary source path')
    s = p.lstat()
    need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and
         s.st_size == row['bytes'] <= cap, 'bounded complete source')
    READS += s.st_size
    need(READS <= 4 * MIB, 'owner or worker explicit source-read partition')
    b = p.read_bytes()
    need(len(b) == row['bytes'] and hashlib.sha256(b).hexdigest() == row['sha256'], 'source pin')
    return b



def put(path, value, cap=262144):
    b = value if type(value) is bytes else encoded(value)
    need(len(b) <= cap, 'bounded retained member')
    with path.open('xb') as f:
        f.write(b)
        f.flush()
        os.fsync(f.fileno())
    path.chmod(0o400)
    return {'path': str(path), 'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()}



def local_record(path, cap=262144):
    global READS
    s = path.lstat()
    need(not path.is_symlink() and stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and
         s.st_size <= cap, 'bounded ordinary owned metadata')
    READS += s.st_size
    need(READS <= 4 * MIB, 'owner metadata/source-read partition')
    raw = path.read_bytes()
    need(len(raw) == s.st_size, 'complete owned metadata')
    return json.loads(raw), {'path': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}



def module(row):
    b = read_pin(row)
    m = types.ModuleType('_consensus_head_' + Path(row['path']).stem)
    m.__file__ = row['path']
    exec(compile(b, row['path'], 'exec'), m.__dict__)
    return m



def singleton(headers, name, required=True):
    values = [str(v) for k, v in headers if k.lower() == name.lower()]
    need(len(values) == 1 if required else len(values) <= 1, 'single ' + name)
    return values[0] if values else None



class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, hdrs, newurl):
        return None



def authenticate(binding_pin):
    b = json.loads(read_pin(binding_pin))
    need(b['schema'] == 'consensus-original35-header-owner-binding-v1'
         and b['execution_authority'] is True and b['automatic_retry'] is False,
         'explicit root-selected once operation; inert source cannot dispatch')
    need(set(b['sources']) == {'closer','engine','fuse','guard','policy','monitor',
                              'operands','protocol','targets','range_transport','header_protocol'}, 'exact existing runtime/source operands')
    need(b['limits'] == LIMITS and b['output_path'] == str(OUTPUT), 'complete fixed operation envelope')
    need(type(b['observer_cpu_reserved_slots']) is int
         and 2 <= b['observer_cpu_reserved_slots'] <= 64,
         'root-selected current CPU reservation count before actual dispatch')
    need(type(b['root_authority']) is str and 0 < len(b['root_authority']) <= 4096,
         'explicit root operation selection')
    need(Path(b['owner']['path']).resolve() == Path(__file__).resolve(), 'exact selected owner path')
    read_pin(b['owner'])
    need(str(Path(sys.executable).resolve()) == b['python']['path'], 'exact selected Python')
    read_pin(b['python'])
    need(b['outside_host_bytes'] == OUTSIDE_HOST and b['outside_disk_bytes'] == OUTSIDE_DISK,
         'literal prospective reservations; fresh gate remains required')
    need(b['memory_floor_bytes'] == MEMORY_FLOOR and b['disk_floor_bytes'] == DISK_FLOOR,
         'unchanged margin with own128MiB and16MiB retention')
    for row in b['sources'].values():
        read_pin(row)
    return b




def capacity(binding, output, until):
    # Reuse only the accepted probe/closure primitives, not another task's floor.
    sources = binding['sources']
    body = read_pin(sources['guard'])
    tree = ast.parse(body)
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    names = {'need', 'alarm', 'check_active', 'encoded', 'put', 'close_group', 'probe'}
    nodes = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    nodes += [n for n in main.body if isinstance(n, ast.FunctionDef) and n.name in names]
    env = {'__name__': '_marmoset_existing_capacity_probe'}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), sources['guard']['path'], 'exec'), env)
    policy = module(sources['policy'])
    result = {'deadline_alarm_observed': False, 'probe_admissions': [], 'probe_body_bytes': 0, 'probes': []}
    env.update(guard=output, deadline=min(time.monotonic() + 45, until - 15), owned={}, result=result)
    (output / 'PROBES').mkdir(mode=0o700)
    before_children = resource.getrusage(resource.RUSAGE_CHILDREN)
    probe_cpu = 0.0
    rows, failure = [], None
    try:
        for name, argv in policy.PROBES:
            if name == 'pressure-2':
                time.sleep(.2)
            row = env['probe'](name, list(argv))
            rows.append(row)
            usage = resource.getrusage(resource.RUSAGE_CHILDREN)
            probe_cpu = usage.ru_utime + usage.ru_stime - before_children.ru_utime - before_children.ru_stime
            need(probe_cpu <= 5, 'capacity-probe child CPU partition')
            need(row['complete'], 'complete fresh capacity ' + name)
        values = {name: policy.receipt(row, name, argv)
                  for row, (name, argv) in zip(rows, policy.PROBES)}
        need(len(rows) == 8 and all(int(a['ended_monotonic_ns']) <= int(b['started_monotonic_ns'])
             for a, b in zip(rows, rows[1:])), 'complete ordered8 probes')
        need(int(rows[5]['started_monotonic_ns']) - int(rows[4]['ended_monotonic_ns']) >= 200000000,
             'separated second sample')
        memory = policy.integer(values['sysctl-memory'], 'memory')
        cores = policy.integer(values['sysctl-cores'], 'cores')
        pressure = [policy.integer(values['pressure-' + str(i)], 'pressure') for i in (1, 2)]
        snapshots = [policy.vm_snapshot(values['vm-stat-' + str(i)], memory) for i in (1, 2)]
        cpu = [policy.cpu_cores(values['ps-cpu-' + str(i)]) for i in (1, 2)]
        fs = os.statvfs(output)
        free = fs.f_bavail * fs.f_frsize
        checks = {'both_normal': pressure == [1, 1],
                  'same_page_size': snapshots[0]['page_bytes'] == snapshots[1]['page_bytes'],
                  'headroom': min(x['potential_headroom_bytes'] for x in snapshots) >= MEMORY_FLOOR,
                  'pageouts_unchanged': snapshots[0]['pageouts'] == snapshots[1]['pageouts'],
                  'swapouts_unchanged': snapshots[0]['swapouts'] == snapshots[1]['swapouts'],
                  'CPU_with_selected_reserved_slots': max(cpu) + binding['observer_cpu_reserved_slots'] <= cores,
                  'disk': free >= DISK_FLOOR}
        result.update(checks=checks, passed=all(checks.values()), snapshots=snapshots,
                      pressure=pressure, cpu_samples=[str(x) for x in cpu], cores=cores,
                      memory_floor_bytes=MEMORY_FLOOR, disk_floor_bytes=DISK_FLOOR,
                      disk_free_bytes=free, outside_host_bytes=OUTSIDE_HOST,
                      outside_disk_bytes=OUTSIDE_DISK, own_host_bytes=128 * MIB,
                      own_retention_bytes=16 * MIB, margin_bytes=GIB,
                      heuristic_not_guaranteed=True, unknown_outside_growth=True,
                      reserved_CPU_slots=binding['observer_cpu_reserved_slots'])
    except BaseException as exc:
        failure = {'type': type(exc).__name__, 'message': str(exc)[:512]}
        result.update(passed=False, error=failure)
    finally:
        result['physical_closure'] = policy.physical_closure(result['probe_admissions'], rows)
        result['waited_probe_CPU_seconds'] = probe_cpu
        result['probe_CPU_partition_seconds'] = 5
        result['probe_CPU_partition_passed'] = probe_cpu <= 5
        result['observed_unix'] = time.time()
        receipt = put(output / 'CAPACITY.json', result)
    need(result['passed'] and result['physical_closure']['all_probe_groups_absent'], 'fresh capacity refused')
    return receipt



def worker(binding_pin, gate_sha, parent, until):
    b=authenticate(binding_pin)
    fuse=module(b['sources']['fuse'])
    fuse.accept_gate(gate_sha,parent,min(until,time.monotonic()+2))
    need(os.getpid()==os.getpgrp()==os.getsid(0),'fresh owned worker session')
    resource.setrlimit(resource.RLIMIT_CPU,(30,30))
    start,cpu=time.monotonic(),time.process_time()
    monitor_module=module(b['sources']['monitor'])
    transport=None
    outcome={'schema':'consensus35-header-worker-outcome-v1','complete':False,
             'pid':os.getpid(),'group_id':os.getpgrp(),'array_decoding':False,
             'scientific_readiness':False}
    def guard():
        need(time.monotonic()<until and time.process_time()-cpu<30,'worker CPU/time ceiling')
    def snapshot():
        return {'sequence':0,'source_recorded_bytes':READS,
                'admitted_byte_work':0 if transport is None else transport.logical_range_requested_bytes,
                'pending_source_read_requested_bytes':0,
                'phase':'canonicalGET-and-bounded-NPY-header-only'}
    monitor=monitor_module.DurableMonitor(64*MIB,fuse.rss_bytes,snapshot,
             OUTPUT/'MONITOR_START.json',OUTPUT/'MONITOR_OUTCOME.json','intake')
    try:
        with monitor:
            rows=module(b['sources']['protocol']).validate_operands(json.loads(read_pin(b['sources']['operands'])))
            target_doc=json.loads(read_pin(b['sources']['targets']))
            need(target_doc['schema']=='consensus35_retained_target_identity_projection_v1'
                 and target_doc['from_complete_accepted_HEAD_inquiry'] is True
                 and target_doc['current_validator_or_download_authority'] is False,
                 'retained35 identity scope, not cached target admission')
            targets=target_doc['targets']
            need(len(targets)==35 and all(
                (x['index'],x['file_id'],x['declared_bytes'],x['canonical_download_url'])==
                (r['index'],r['file_id'],r['bytes'],r['canonical_download_url'])
                for x,r in zip(targets,rows)),'exact all35 retained route joins')
            identities={x['file_id']:x['identity'] for x in targets}
            assets=[dict(file_id=r['file_id'],bytes=r['bytes'],
                    filename=r['relative_path'].split('/')[-1],
                    download_url=r['canonical_download_url'],
                    provider_computed_md5=r['published_computed_md5']) for r in rows]
            transport_module=module(b['sources']['range_transport'])
            with transport_module.RangeTransport(OUTPUT/'HTTP',assets,identities) as transport:
                report=module(b['sources']['header_protocol']).collect(rows,transport)
                guard()
                outcome['complete35_headers']=put(OUTPUT/'COMPLETE35_HEADERS.json',report,262144)
            outcome['transport']=transport.receipt()
        outcome['monitor']=monitor.receipt()
        outcome['complete']=True
    except BaseException as exc:
        outcome['error']={'type':type(exc).__name__,'message':str(exc)[:1024]}
    finally:
        outcome.update(elapsed_seconds=time.monotonic()-start,cpu_seconds=time.process_time()-cpu,
            source_read_bytes=READS,peak_rss_bytes=fuse.rss_bytes(),
            HTTP_transactions=0 if transport is None else transport.transactions,
            logical_ranges=0 if transport is None else transport.range_attempts,
            returned_entity_bytes=0 if transport is None else transport.body_returned,
            numeric_payload_ranges_requested=0)
        put(OUTPUT/'WORKER_OUTCOME.json',outcome)
    return 0 if outcome['complete'] else 1



def owner(binding_pin):
    started, cpu = time.monotonic(), time.process_time()
    b = authenticate(binding_pin)
    need(not OUTPUT.exists() and not any(p.is_symlink() for p in OUTPUT.parents), 'fresh literal once namespace')
    OUTPUT.mkdir(mode=0o700)
    # The gated worker must inherit its30-second hard cap. The owner keeps a
    # five-second soft cap and lowers its own hard cap immediately after spawn.
    resource.setrlimit(resource.RLIMIT_CPU, (5, 30))
    put(OUTPUT / 'OWNER_BIRTH.json', {'pid': os.getpid(), 'group_id': os.getpgrp(),
        'session_id': os.getsid(0), 'started_unix': time.time(), 'started_monotonic': started,
        'binding': binding_pin, 'actual_count': 1, 'retry': False,
        'root_authority': b['root_authority']})
    fuse_module = module(b['sources']['fuse'])
    engine = module(b['sources']['engine'])
    closer = module(b['sources']['closer'])
    until = started + 1500
    outcome = {'schema': 'consensus35-header-owner-outcome-v1', 'complete': False,
               'capacity_admitted': False, 'worker_dispatched': False, 'automatic_retry': False}
    with fuse_module.WallFuse(until, owner_rss_limit=64 * MIB) as fuse:
        try:
            outcome['capacity'] = capacity(b, OUTPUT, until)
            outcome['capacity_admitted'] = True
            capacity_at = time.monotonic()
            gate = os.urandom(32).hex().encode() + b'\n'
            gate_sha = hashlib.sha256(gate).hexdigest()
            work_until = until - 8
            argv = [b['python']['path'], '-I', '-S', '-B', str(Path(__file__).resolve()),
                    '--worker', binding_pin['path'], str(binding_pin['bytes']), binding_pin['sha256'],
                    gate_sha, str(os.getpid()), repr(work_until)]
            def born(child):
                fuse.add(child)
                resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
                need(os.getpgid(child.pid) == child.pid, 'owned new worker group')
                need(time.monotonic() - capacity_at <= 15, 'fresh admission before worker gate')
                put(OUTPUT / 'WORKER_BIRTH.json', {'pid': child.pid, 'group_id': child.pid,
                    'owner_pid': os.getpid(), 'argv': argv, 'gate_sha256': gate_sha,
                    'observed_unix': time.time(), 'observed_monotonic': time.monotonic()})
            outcome['worker_dispatched'] = True
            process = engine.run_owned(argv, OUTPUT, {'PATH': '/usr/bin:/bin', 'LANG': 'C',
                'LC_ALL': 'C'}, until - 2, OUTPUT / 'worker.stdout', OUTPUT / 'worker.stderr',
                closer, work_until=work_until, stream_cap=65536, on_spawn=born,
                on_closed=fuse.closed, start_gate=gate)
            outcome['process'] = put(OUTPUT / 'PROCESS.json', process)
            if process['complete'] is True:
                record, outcome['worker_outcome'] = local_record(OUTPUT / 'WORKER_OUTCOME.json')
                monitor_start, _ = local_record(OUTPUT / 'MONITOR_START.json', 8192)
                monitor_end, _ = local_record(OUTPUT / 'MONITOR_OUTCOME.json', 8192)
                diagnostic = module(b['sources']['monitor']).interpret(monitor_start, monitor_end,
                    'intake', process['pid'], 64 * MIB, 4 * MIB, 4 * MIB + 143780, 0)
                need(record['complete'] is True and 'error' not in record and
                     record['pid'] == record['group_id'] == process['pid'] and
                     diagnostic['classification'] == 'closed' and
                     record['monitor']['diagnostic_outcome'] == monitor_end,
                     'closed successful worker and exact durable monitor outcome')
                outcome['complete'] = True
        except BaseException as exc:
            outcome['error'] = {'type': type(exc).__name__, 'message': str(exc)[:1024]}
        finally:
            outcome['last_owned_cleanup'] = fuse.close_remaining(until - .25)
            if outcome['last_owned_cleanup']:
                outcome['complete'] = False
    outcome.update(elapsed_seconds=time.monotonic() - started, cpu_seconds=time.process_time() - cpu,
                   peak_rss_bytes=fuse_module.rss_bytes(), source_read_bytes=READS,
                   owner_pid=os.getpid(), owner_group_id=os.getpgrp())
    outcome['retained_files'] = [{'path': str(p.relative_to(OUTPUT)), 'bytes': p.stat().st_size}
        for p in sorted(OUTPUT.rglob('*')) if p.is_file()]
    outcome['retained_bytes_before_outcome'] = sum(x['bytes'] for x in outcome['retained_files'])
    need(outcome['retained_bytes_before_outcome'] < 8 * MIB, 'actual partition preserves8MiB source/peer allowance')
    pin = put(OUTPUT / 'OWNER_OUTCOME.json', outcome)
    print(json.dumps({'complete': outcome['complete'], 'outcome': pin,
                      'worker_dispatched': outcome['worker_dispatched'],
                      'target_routes_approved': False, 'header_ranges_authorized': False}))
    return 0 if outcome['complete'] else 1



def main():
    need(len(sys.argv) in (5, 8), 'exact owner or gated worker argv')
    selected = {'path': sys.argv[2], 'bytes': int(sys.argv[3]), 'sha256': sys.argv[4]}
    previous = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    cancellation_started = False
    def cancelled(signum, frame):
        nonlocal cancellation_started
        if cancellation_started:
            return
        cancellation_started = True
        raise InterruptedError('route operation cancelled by signal ' + str(signum))
    for sig in previous:
        signal.signal(sig, cancelled)
    try:
        if sys.argv[1] == '--owner':
            need(len(sys.argv) == 5, 'owner argv')
            need(os.getpid() == os.getpgrp() == os.getsid(0), 'same-process owned outer session')
            return owner(selected)
        need(sys.argv[1] == '--worker' and len(sys.argv) == 8, 'worker argv')
        return worker(selected, sys.argv[5], int(sys.argv[6]), float(sys.argv[7]))
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


if __name__ == '__main__':
    raise SystemExit(main())
