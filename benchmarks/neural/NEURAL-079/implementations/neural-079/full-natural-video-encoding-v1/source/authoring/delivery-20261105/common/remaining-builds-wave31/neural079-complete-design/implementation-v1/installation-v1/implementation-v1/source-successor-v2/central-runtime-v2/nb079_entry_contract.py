"""Pure captured-entry grammar and complete orchestration allocation contract."""
import copy
import hashlib
import json
from pathlib import PurePosixPath


CAPTURE_STUB = r"""import os,sys,stat,time,hashlib
v=sys.argv
if len(v)<10 or v[9]!='--independently-enabled':raise ValueError('inactive captured entry')
p,n,h,m=v[1],int(v[2]),v[3],int(v[4]);c=[int(x) for x in v[5:9]]
if not(0<=n<=m and m>0 and len(h)==64 and all(x in '0123456789abcdef' for x in h) and 0<=c[0]<c[1]<c[2]<c[3]):raise ValueError('selected entry extent/clock')
if not(p.startswith('/') and '\x00' not in p and all(x not in ('','.','..') for x in p.split('/')[1:])):raise ValueError('entry canonical path')
def tick():
 if not c[0]<=time.monotonic_ns()<c[1]:raise ValueError('original entry cutoff')
tick();d=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);f=None;e=None;raw=b'';count=0
try:
 for x in p.split('/')[1:-1]:
  z=os.open(x,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=d);old,d=d,z;os.close(old)
 tick();f=os.open(p.split('/')[-1],os.O_RDONLY|os.O_NOFOLLOW,dir_fd=d);a=os.fstat(f)
 if not(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and a.st_size==n):raise ValueError('ordinary exact captured entry')
 pieces=[]
 while True:
  tick();b=os.read(f,min(65536,n-count+1))
  if not b:break
  count+=len(b)
  if count>n:raise ValueError('captured entry grew')
  pieces.append(b)
 raw=b''.join(pieces);z=os.fstat(f)
 if not count==n or hashlib.sha256(raw).hexdigest()!=h or (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns)!=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns):raise ValueError('changed captured entry')
except BaseException as x:e=x
finally:
 for fd in ([f] if f is not None else [])+[d]:
  try:os.close(fd)
  except BaseException as x:
   if e is None:e=x
   else:e.add_note('Secondary capture close: '+type(x).__name__)
if e is not None:
 e.nb079_capture_prefix={'actual_read_bytes':count,'maximum_read_bytes':n+1,'complete':False}
 raise e
tick();sys.argv=[p]+v[9:];g={'__name__':'__main__','__file__':p,'__package__':None,'_CAPTURED_ENTRY_PIN':{'bytes':n,'sha256':h},'_CAPTURED_ENTRY_CLOCK':c,'_CAPTURED_ENTRY_READ_BYTES':n+1}
exec(compile(raw,p,'exec'),g)
"""

DIMENSIONS = ('source_read_bytes', 'data_read_bytes', 'write_bytes', 'log_bytes',
              'process_starts', 'validation_calls', 'logical_float_slots')
ROWS = ('central_preparation', 'prelude', 'observer', 'authority', 'feeder')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def fields(value, names):
    require(type(value) is dict and set(value) == set(names), 'exact contract fields')


def integer(value, minimum=0):
    require(type(value) is int and value >= minimum, 'finite non-Boolean integer')
    return value


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('ascii')


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def descriptor(item):
    fields(item, ('path', 'pin')); fields(item['pin'], ('bytes', 'sha256'))
    integer(item['pin']['bytes'])
    path = item['path']; digest = item['pin']['sha256']
    require(type(path) is str and path.startswith('/') and str(PurePosixPath(path)) == path
            and '..' not in PurePosixPath(path).parts and '\x00' not in path, 'canonical path')
    require(type(digest) is str and len(digest) == 64 and
            all(c in '0123456789abcdef' for c in digest), 'exact SHA256')


def clock(value):
    fields(value, ('origin', 'scientific', 'closeout', 'outer'))
    values = [integer(value[k]) for k in ('origin', 'scientific', 'closeout', 'outer')]
    require(all(a < b for a, b in zip(values, values[1:])), 'one original increasing clock')
    return values


def capture_argv(python, prelude, maximum_source_bytes, original_clock, arguments):
    descriptor(python); descriptor(prelude); integer(maximum_source_bytes, 1)
    require(prelude['pin']['bytes'] <= maximum_source_bytes, 'whole captured entry extent')
    require(type(arguments) is list and arguments and
            arguments[0] == '--independently-enabled', 'disabled before capture effects')
    require(all(type(x) is str and '\x00' not in x for x in arguments), 'literal entry arguments')
    return [python['path'], '-I', '-S', '-B', '-c', CAPTURE_STUB, prelude['path'],
            str(prelude['pin']['bytes']), prelude['pin']['sha256'], str(maximum_source_bytes),
            *map(str, clock(original_clock)), *arguments]


def validate_capture_argv(argv, python, prelude, original_clock):
    require(type(argv) is list and len(argv) > 14, 'complete captured-entry grammar')
    descriptor(python); descriptor(prelude); clock(original_clock)
    require(argv[:7] == [python['path'], '-I', '-S', '-B', '-c', CAPTURE_STUB, prelude['path']],
            'exact literal source-owned capture stub, no arbitrary Python command')
    require(argv[7] == str(prelude['pin']['bytes']) and argv[8] == prelude['pin']['sha256']
            and argv[9].isdecimal() and int(argv[9]) >= prelude['pin']['bytes'] and int(argv[9]) > 0,
            'complete exact source operand and positive selected extent')
    require(argv[10:14] == list(map(str, clock(original_clock))) and
            argv[14] == '--independently-enabled', 'same original pre-preparation interval')
    require(argv == capture_argv(python, prelude, int(argv[9]), original_clock, argv[14:]),
            'exact command reconstruction')
    return argv


def vector(value):
    fields(value, DIMENSIONS)
    return {k: integer(v) for k, v in value.items()}


def authority_mapping(counters, kind):
    """Conservative explicit charge mapping; no overlapping physical total."""
    fields(counters, ('read_bytes', 'write_bytes', 'log_bytes', 'attempts', 'pending_bytes'))
    for value in counters.values():
        integer(value, 1)
    require(kind in ('authority', 'feeder'), 'fixed external source role')
    # read_bytes contains complete metadata and, for feeder, opaque source bytes.
    # The complete ceiling is conservatively reserved in BOTH logical categories
    # for feeder; this duplication is explicit and is never a unique-byte claim.
    return dict(source_read_bytes=counters['read_bytes'],
                data_read_bytes=counters['read_bytes'] if kind == 'feeder' else 0,
                write_bytes=counters['write_bytes'], log_bytes=counters['log_bytes'],
                process_starts=1, validation_calls=counters['attempts'], logical_float_slots=0)


def validate_orchestration(value, source_pin, original_clock):
    fields(value, ('schema', 'source_pin', 'original_clock', 'rows', 'whole'))
    require(value['schema'] == 'nb079_complete_orchestration_allocation_v1' and
            value['source_pin'] == source_pin and value['original_clock'] == original_clock,
            'one independently selected whole orchestration allocation')
    clock(original_clock); fields(value['rows'], ROWS); whole = vector(value['whole'])
    total = {k: 0 for k in DIMENSIONS}
    for role, row in value['rows'].items():
        fields(row, ('role', 'selection', 'allocation'))
        require(row['role'] == role and type(row['selection']) is dict, 'fixed row/selection')
        capacity = vector(row['allocation'])
        if role in ('central_preparation', 'prelude'):
            fields(row['selection'], ('schema', 'role', 'original_clock',
                'source_pin', 'owners', 'roots', 'allocation', 'encoding', 'limits', 'maximum_attempts'))
            require(row['selection']['schema'] == 'nb079_entry_bootstrap_v2' and
                    row['selection']['role'] == role and row['selection']['allocation'] == capacity
                    and row['selection']['original_clock'] == original_clock and
                    row['selection']['source_pin'] == source_pin, 'exact earlier entry row')
        elif role == 'observer':
            # Exact Qc.bootstrap object is subsequently joined by actual consumer.
            require(row['selection']['allocation'] == capacity and
                    row['selection']['original_clock'] == original_clock, 'exact observer row')
        else:
            fields(row['selection'], ('counters', 'files', 'maximum_requests', 'poll_ns'))
            require(capacity == authority_mapping(row['selection']['counters'], role),
                    'explicit conservative external counter mapping')
        if role != 'prelude':
            require(capacity['process_starts'] >= 1, 'named real launch has declared capacity')
        for key in DIMENSIONS:
            total[key] += capacity[key]
    require(all(whole[k] >= total[k] for k in DIMENSIONS), 'whole covers all five source rows')
    return {'required': total, 'whole': whole,
            'boundary': 'logical reservations only; observer launches the already-counted original finalizer/prelude, not an extra PID; central_preparation and observer share one central process; authority/feeder starts and waits require their external original observations; existing scientific allocation and external launcher costs remain separately reported, never summed as unique processes'}


def selected_row(value, role, selection):
    require(role in ROWS and value['rows'][role]['selection'] == selection,
            'same actual selected producer/consumer row before effects')
    return copy.deepcopy(value['rows'][role]['allocation'])
