"""Two fresh candidate containers, using exact Slice V2 owned Docker transport.

No import launches a process or reads scientific inputs. E is the authenticated
Slice executor module supplied by the controller, not an arbitrary plugin.
"""
import base64
import hashlib
import os
from pathlib import Path
import re
import time
import uuid
import failure_evidence as F

VOLUME = 335544320
PRED_CAP = 67108864
MODEL_CAP = 268435456
CHUNK = 4194304
SCRATCH = 4294967296
FAILURE_EVIDENCE_CAP = 8388608
VOLUME_OPTIONS = 'size=335544320,uid=65534,gid=65534,mode=0770,noexec,nosuid,nodev'
TMP_OPTIONS = 'rw,nosuid,nodev,noexec,size=4294967296'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def create_args(E, item, role, mounts, memory, image, phase):
    command = (['-I', '-B', '/trusted/holder.py', 'hold'] if role == 'holder' else
               ['-I', '-B', '/entry.py', str(memory), phase])
    argv = ['container', 'create', '--pull', 'never', '--name', item['name'],
            '--label', E.LABEL + '=' + item['owner'], '--cpus', '1',
            '--memory', str(memory), '--memory-swap', str(memory), '--pids-limit', '64',
            '--network', 'none', '--cgroupns', 'private', '--ipc', 'private',
            '--read-only', '--user', '65534:65534', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges', '--restart', 'no', '--log-driver', 'none',
            '--shm-size', '16777216', '--ulimit', 'core=0:0', '--ulimit', 'nofile=128:128',
            '--ulimit', 'fsize=268435456:268435456']
    if role == 'candidate':
        argv += ['--tmpfs', '/tmp:' + TMP_OPTIONS]
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        argv += ['--env', name + '=1']
    return argv + E.mounts_argv(mounts) + ['--entrypoint', 'python', image, *command]


def admit(E, value, item, role, mounts, memory, image, phase):
    E.owned(value, item, item['owner'])
    h, c = value['HostConfig'], value['Config']
    command = (['-I', '-B', '/trusted/holder.py', 'hold'] if role == 'holder' else
               ['-I', '-B', '/entry.py', str(memory), phase])
    need(value['Image'] == c['Image'] == image and c['User'] == '65534:65534' and
         c['Entrypoint'] == ['python'] and c['Cmd'] == command, 'exact image/user/command')
    need(h['Memory'] == h['MemorySwap'] == memory and h['NanoCpus'] == 1000000000 and
         h['PidsLimit'] == 64, 'exact memory CPU pids')
    need(h['NetworkMode'] == 'none' and h['ReadonlyRootfs'] is True and
         h['CgroupnsMode'] == 'private' and h['LogConfig']['Type'] == 'none' and
         h['IpcMode'] == 'private' and h.get('PidMode') in ('', 'private'), 'namespaces')
    need(h.get('Privileged') is False and not h.get('CapAdd') and not h.get('Devices') and
         not h.get('DeviceRequests') and h['CapDrop'] == ['ALL'] and
         'no-new-privileges' in h['SecurityOpt'] and h['RestartPolicy']['Name'] == 'no' and
         h['AutoRemove'] is False and h['ShmSize'] == 16777216, 'privilege restrictions')
    actual = {x['Destination']: (x['Type'], x['Name'] if x['Type'] == 'volume' else x['Source'], x['RW'])
              for x in value['Mounts']}
    need(len(value['Mounts']) == len(mounts) and
         actual == {k: (kind, str(p), rw) for k, (kind, p, rw) in mounts.items()}, 'exact mounts')
    need(all(not rw for kind, _, rw in mounts.values() if kind == 'bind'), 'host bindings read only')
    need(h.get('Tmpfs') in ({}, None) if role == 'holder' else
         h.get('Tmpfs') == {'/tmp': TMP_OPTIONS}, 'bounded scratch')
    limits = {x['Name']: (x['Soft'], x['Hard']) for x in h['Ulimits']}
    need(limits == {'core': (0, 0), 'nofile': (128, 128),
                    'fsize': (MODEL_CAP, MODEL_CAP)}, 'file limits')


def admit_inventory(value, phase):
    need(type(value) is dict and set(value) == {'schema', 'phase', 'files', 'directories', 'bytes'} and
         value['schema'] == 'gcamp8_stopped_inventory_v1' and value['phase'] == phase,
         'inventory type')
    fs, dirs = value['files'], value['directories']
    need(type(fs) is dict and 1 <= len(fs) <= 256 and type(dirs) is list and
         dirs == sorted(set(dirs)) and len(fs) + len(dirs) <= 512, 'inventory sizes')
    for name in list(fs) + dirs:
        p = Path(name)
        need(not p.is_absolute() and p.as_posix() == name and '..' not in p.parts and
             len(p.parts) <= 8 and len(name) <= 240 and '\\' not in name and
             all(ord(x) >= 32 and x not in ',\x7f' for x in name), 'state relative path')
    need(not set(fs) & set(dirs), 'file-directory conflict')
    for name, p in fs.items():
        need(type(p) is dict and set(p) == {'bytes', 'sha256'} and type(p['bytes']) is int and
             0 < p['bytes'] <= MODEL_CAP and re.fullmatch('[0-9a-f]{64}', p['sha256']), 'state pin')
        need(all(str(x) == '.' or str(x) in dirs for x in Path(name).parents), 'complete parent inventory')
    total = sum(p['bytes'] for p in fs.values())
    need(type(value['bytes']) is int and value['bytes'] == total <=
         (MODEL_CAP if phase == 'train' else PRED_CAP), 'total state extent')
    if phase == 'predict':
        need(set(fs) == {'prediction.json'} and dirs == [], 'exact prediction output')
    return value


def capture_prediction(E, d, holder, expected, path, end):
    """Bounded chunks from stopped, read-only tmpfs; authenticate full closed file."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    count = 0
    digest = hashlib.sha256()
    try:
        while count < expected['bytes']:
            raw = E.call(d, ['exec', holder['id'], 'python', '-I', '-B', '/trusted/holder.py',
                             'chunk', 'prediction.json', str(count), str(expected['bytes'])],
                         end, 'prediction_chunk', 5600000, 12)
            row = E.parse(raw)
            need(set(row) == {'name', 'offset', 'bytes', 'base64'} and
                 row['name'] == 'prediction.json' and type(row['offset']) is int and
                 row['offset'] == count and type(row['bytes']) is int and
                 row['bytes'] == min(CHUNK, expected['bytes'] - count), 'chunk identity')
            body = base64.b64decode(row['base64'], validate=True)
            need(len(body) == row['bytes'], 'chunk length')
            view = memoryview(body)
            while view:
                need(time.monotonic() < end, 'capture original deadline')
                n = os.write(fd, view)
                need(n > 0, 'complete capture write')
                view = view[n:]
            digest.update(body)
            count += len(body)
        os.fsync(fd)
    finally:
        os.close(fd)
    need({'bytes': count, 'sha256': digest.hexdigest()} == expected, 'full stopped output pin')
    return expected


def case(E, d, cfg, identity, program, train_mounts, query_mounts, output, sources, end, publish, ownership):
    """All owned resources close before a case can return a successful receipt.

    The Slice namespace/owner label is deliberately retained for exact reuse of
    its audited inventory/retire code. The task/phase receipts identify GCaMP8.
    """
    started = time.monotonic()
    end = min(end, started + cfg['train_seconds'] + cfg['predict_seconds'] + 2000)
    work_end = end - 120
    items, closures, phases = [], [], []
    prefix = 'slicetca-' + uuid.uuid4().hex[:24]
    prediction = None
    error = None
    original_error = None
    cleanup_errors = []
    original_evidence = None

    def item(role, kind):
        # Volume names retain the original regex, with a distinct prefix each.
        row = ownership.reserve(role)
        need(row['kind'] == kind and row['role'] == role, 'parent-owned exact resource role')
        items.append(row)
        publish('INTENT-' + role + '.json', {'task': 'PAPER-paper-method-047',
                'identity': identity, 'resource': row.copy()})
        return row

    def before(row):
        need(E.resource_inventory(d, row, row['owner'], work_end, 'before') == [], 'fresh owned resource')

    def container(row, role, mounts, memory, phase):
        before(row)
        ownership.attempt(row['role'])
        row['attempted'] = True
        value = E.call(d, create_args(E, row, role, mounts, memory, cfg['image'], phase),
                       work_end, 'create_' + role, 4096, 15).decode().strip()
        need(re.fullmatch('[a-f0-9]{64}', value), 'created container identity')
        row.update(id=value, acknowledged=True)
        ownership.ack(row['role'], value)
        admit(E, E.inspect(d, 'container', value, work_end, 'admit'), row, role,
              mounts, memory, cfg['image'], phase)

    def output_volume(phase):
        row = item(phase + '-volume', 'volume')
        before(row)
        ownership.attempt(row['role'])
        row['attempted'] = True
        result = E.call(d, ['volume', 'create', '--driver', 'local', '--label',
                           E.LABEL + '=' + row['owner'], '--opt', 'type=tmpfs', '--opt',
                           'device=tmpfs', '--opt', 'o=' + VOLUME_OPTIONS, row['name']],
                        work_end, 'create_volume', 4096).decode().strip()
        need(result == row['name'], 'volume acknowledgment')
        row['acknowledged'] = True
        ownership.ack(row['role'], result)
        v = E.inspect(d, 'volume', row['name'], work_end, 'volume_inspect')
        E.owned(v, row, row['owner'])
        need(v['Driver'] == 'local' and v['Options'] ==
             {'type': 'tmpfs', 'device': 'tmpfs', 'o': VOLUME_OPTIONS}, 'exact volume')
        hold = item(phase + '-holder', 'container')
        mounts = {'/trusted/holder.py': ('bind', sources / 'holder.py', False),
                  '/capture': ('volume', row['name'], False)}
        container(hold, 'holder', mounts, 134217728, phase)
        E.call(d, ['container', 'start', hold['id']], work_end, 'holder_start', 4096)
        need(E.parse(E.call(d, ['exec', hold['id'], 'python', '-I', '-B',
                               '/trusted/holder.py', 'ready'], work_end, 'holder_ready', 4096))
             == {'ready': True}, 'live bounded holder')
        return row, hold

    def inventory(hold, phase):
        raw = E.call(d, ['exec', hold['id'], 'python', '-I', '-B', '/trusted/holder.py',
                         'inventory', phase], work_end, 'state_inventory', 131072, 60)
        return admit_inventory(E.parse(raw), phase)

    def produce(phase, mounts, volume):
        row = item(phase + '-candidate', 'container')
        mounts = dict(mounts)
        mounts.update({'/program/program.py': ('bind', program, False),
                       '/entry.py': ('bind', sources / 'entry.py', False),
                       '/output': ('volume', volume['name'], True)})
        container(row, 'candidate', mounts, cfg['memory_bytes'], phase)
        begin = time.monotonic()
        deadline = min(work_end, begin + cfg[phase + '_seconds'])
        E.call(d, ['container', 'start', row['id']], deadline, phase + '_start', 4096)
        raw = d(['container', 'wait', row['id']], deadline, phase + '_wait', 4096)
        need(raw.strip() == b'0', 'natural candidate zero')
        v = E.inspect(d, 'container', row['id'], work_end, phase + '_exit')
        E.owned(v, row, row['owner'])
        s = v['State']
        need(s['Status'] == 'exited' and s['Running'] is False and s['Dead'] is False and
             s['Pid'] == 0 and s['ExitCode'] == 0 and s['OOMKilled'] is False, 'natural non-OOM exit')
        closed = E.retire(d, row, work_end)
        closures.append(closed)
        ownership.retired(row['role'], closed)
        items.remove(row)
        need(closed['closed'], 'producer removed before state access')
        phases.append({'phase': phase, 'start_monotonic': begin, 'deadline_monotonic': deadline,
                       'natural_exit': {k: s[k] for k in ('Status', 'Running', 'Dead', 'Pid', 'ExitCode', 'OOMKilled')},
                       'closed': closed})

    try:
        im = E.parse(E.call(d, ['image', 'inspect', cfg['image'], '--format', '{{json .}}'],
                            work_end, 'image', 131072))
        need(im['Id'] == cfg['image'] and not im['Config'].get('Volumes') and
             (not im['Config'].get('Healthcheck') or
              im['Config']['Healthcheck'].get('Test') == ['NONE']), 'explicit existing image')
        model_volume, model_holder = output_volume('train')
        produce('train', train_mounts, model_volume)
        model = inventory(model_holder, 'train')
        model_pin = publish('MODEL_SEAL.json', {'identity': identity, 'inventory': model,
                            'training_producer_closed': True, 'query_released': False,
                            'weights_retained_after_case': False})
        # Only this line grants the query process its matching query and sealed state.
        predict_mounts = dict(query_mounts)
        predict_mounts['/model'] = ('volume', model_volume['name'], False)
        pred_volume, pred_holder = output_volume('predict')
        produce('predict', predict_mounts, pred_volume)
        inv = inventory(pred_holder, 'predict')
        need(inventory(model_holder, 'train') == model, 'sealed model remained identical')
        prediction = capture_prediction(E, d, pred_holder, inv['files']['prediction.json'],
                                        output / 'prediction.json', work_end)
        publish('PREDICTION_CAPTURE.json', {'identity': identity, 'prediction': prediction,
                'model_seal': model_pin, 'all_transferred_state_in_model_manifest': True,
                'specified_training_algorithm_verified': False})
    except BaseException as exc:
        original_error = exc
        error = type(exc).__name__
    finally:
        for row in reversed(items):
            try:
                closed = E.retire(d, row, end)
                closures.append(closed)
                ownership.retired(row['role'], closed)
            except BaseException as exc:
                cleanup_errors.append(exc)
                closures.append({'kind': row['kind'], 'name': row['name'], 'closed': False,
                                 'error_type': type(exc).__name__})
    original_error_projection = None
    try:
        original_error_projection = F.describe_original_errors(
            ([original_error] if original_error is not None else []) + cleanup_errors)
    except BaseException as publication_error:
        cleanup_errors.append(publication_error)
    # At most one case aborts this controller; its original raw failures have
    # been precharged once by the complete-programme caller. Publication is
    # independent of every resource retirement and never replaces its error.
    if d.original_failures:
        try:
            original_evidence = F.persist(output / 'original-command-failures',
                                          d.original_failures, FAILURE_EVIDENCE_CAP, end)
            cleanup_errors.extend(original_evidence['publication_errors'])
        except BaseException as publication_error:
            cleanup_errors.append(publication_error)
    closed = all(x.get('closed') is True for x in closures)
    success = error is None and prediction is not None and len(phases) == 2 and closed and d.reaped
    success = success and time.monotonic() < end
    record = {'schema': 'gcamp8_two_phase_closed_case_v1', 'task_id': 'PAPER-paper-method-047',
              'identity': identity, 'status': 'captured' if success else 'failed',
              'error_type': error, 'prediction': prediction, 'phases': phases,
              'closures': closures, 'all_resources_closed': closed,
              'cli_groups_closed': d.reaped, 'commands': d.records,
              'original_command_evidence': (None if original_evidence is None else
                                           original_evidence['summary']),
              'original_body_and_retirement_error_evidence': original_error_projection,
              'elapsed_seconds': time.monotonic() - started,
              'original_deadline_monotonic': end, 'private_grade_started': False}
    try:
        publish('CASE_CLOSED.json', record)
    except BaseException as publication_error:
        cleanup_errors.append(publication_error)
        if original_error is None:
            original_error = publication_error
    # original_evidence and d retain the actual exception objects/raw buffers
    # through publication and this original raise. No cross-process Python
    # object identity is claimed for the structural on-disk projection.
    if original_error is not None:
        raise original_error
    if cleanup_errors:
        raise cleanup_errors[0]
    need(success, 'case failed; retain costs and refuse panel grading')
    return record
