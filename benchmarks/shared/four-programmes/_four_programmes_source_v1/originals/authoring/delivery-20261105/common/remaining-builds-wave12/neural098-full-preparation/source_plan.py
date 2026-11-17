"""Complete externally selected source roster; no asset opened here."""
import hashlib
import json
from custody import need, relative


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=True, allow_nan=False) + '\n').encode('ascii')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def descriptor(row):
    need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'}, 'exact source descriptor')
    need(len(relative(row['path'])) <= 16, 'bounded source directory depth')
    need(type(row['bytes']) is int and 0 < row['bytes'] <= 2_000_000_000, 'canonical source file bound')
    h = row['sha256']
    need(type(h) is str and len(h) == 64 and all(x in '0123456789abcdef' for x in h), 'source hash')
    return row


def validate(plan, people, caps):
    need(type(plan) is dict and set(plan) == {'schema', 'participants'}
         and plan['schema'] == 'neural098-native-source-plan-v1', 'source plan schema')
    participants = plan['participants']
    need(type(participants) is dict and set(participants) == set(people) and len(people) == 33,
         'complete fixed33 source roster')
    files = {}; run_count = 0; groups = []
    def asset(row):
        descriptor(row)
        name = row['path']
        if name in files:
            need(files[name] == row, 'one pin per source path')
        else:
            files[name] = dict(row)
    def group(value, role):
        need(type(value) is dict and set(value) == {'entry', 'parts'}, 'exact complete split group')
        parts = value['parts']
        need(type(parts) is list and 0 < len(parts) <= 64, 'complete bounded split group')
        for row in parts:
            asset(row)
            # The selected author P04/P07 pipelines write ordinary .fif files.
            # Repacked gzip sources require a separately selected bounded ingress.
            need(row['path'].endswith('.fif'), 'ordinary author derivative FIF profile')
        paths = [r['path'] for r in parts]
        need(len(set(paths)) == len(paths) and value['entry'] == paths[0], 'ordered split closure entry')
        if role == 'events':
            need(len(paths) == 1, 'one complete source event FIF per run')
        groups.append((role, value))
    for person in people:
        item = participants[person]
        need(type(item) is dict and set(item) == {'epochs', 'runs', 'history', 'epoch_coordinates'},
             'exact full person source operands')
        need(item['epoch_coordinates'] in ('observed_retained_unscaled', 'observed_retained_transformed'),
             'explicit observed epoch coordinate history')
        asset(item['history'])
        need(item['history']['path'].endswith('.json') and item['history']['bytes'] <= 4_000_000,
             'bounded actual preprocessing history')
        group(item['epochs'], 'epochs')
        runs = item['runs']
        need(type(runs) is list and 0 < len(runs) <= 64, 'complete ordered run roster')
        ids = []
        for run in runs:
            need(type(run) is dict and set(run) == {'run', 'annot_raw', 'filtered_raw', 'events'},
                 'actual raw/event source roles')
            need(type(run['run']) is int and 0 < run['run'] <= 10**12, 'exact positive run ID')
            ids.append(run['run'])
            for role in ('annot_raw', 'filtered_raw', 'events'):
                group(run[role], role)
        need(len(ids) == len(set(ids)), 'distinct declared run IDs')
        run_count += len(runs)
    total = sum(row['bytes'] for row in files.values())
    need(len(files) <= caps['max_files'] and total <= caps['max_source_bytes']
         and run_count <= caps['max_runs'], 'whole cohort source reservation before asset reads')
    return {'files': files, 'groups': groups, 'source_bytes': total,
            'file_count': len(files), 'run_count': run_count}


RUNTIME_FILES = ('custody.py', 'driver.py', 'epoch_guard.py', 'native_capture.py', 'native_io.py',
                 'native_library.py', 'observe.py', 'publication.py', 'runtime.py',
                 'scientific_source.py', 'source_plan.py', 'worker.py', 'SOURCE_LOCK.json')


def source_manifest(value, base):
    need(type(value) is dict and set(value) == {'schema', 'files'}
         and value['schema'] == 'neural098-full-preparation-source-v1', 'exact worker source manifest')
    rows = value['files']
    need(type(rows) is list and len(rows) == len(RUNTIME_FILES), 'complete worker source closure')
    for row in rows: descriptor(row)
    need({v['path'] for v in rows} == {base + '/' + name for name in RUNTIME_FILES},
         'all and only frozen worker/observer source paths')


PHASE_RESERVATION = 132 * 2**30 + 16_000_000


def capacity(value, fd, *, initial):
    import os
    need(type(value) is dict and set(value) == {'schema', 'reservation_id', 'reserved_bytes',
        'other_reserved_bytes', 'floor_bytes'} and value['schema'] == 'neural098-complete-preparation-capacity-v1',
        'exact externally selected physical reservation')
    need(type(value['reservation_id']) is str and 0 < len(value['reservation_id']) <= 256,
         'root reservation identity')
    for key in ('reserved_bytes', 'other_reserved_bytes', 'floor_bytes'):
        need(type(value[key]) is int and 0 <= value[key] <= 2**60, 'exact capacity operand')
    need(value['reserved_bytes'] >= PHASE_RESERVATION and value['floor_bytes'] >= 2 * 2**30,
         'complete phase reservation and minimum2GiB physical floor')
    protected = value['floor_bytes'] + value['other_reserved_bytes']
    required = protected + (value['reserved_bytes'] if initial else 0)
    info = os.fstatvfs(fd)
    need(0 < info.f_frsize <= 4096 and 0 < info.f_bsize <= 4096, 'qualified bounded allocation-unit filesystem')
    need(info.f_bavail * info.f_frsize >= required, 'available physical capacity before complete preparation')
    return protected
