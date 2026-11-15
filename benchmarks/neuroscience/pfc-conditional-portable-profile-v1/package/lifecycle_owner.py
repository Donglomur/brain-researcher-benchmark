"""Accepted lifecycle functions extracted without scientific diagnostic entrypoints."""
import time,hashlib,json,os,selectors,stat,subprocess
from pathlib import Path
START=time.monotonic()
IMAGE=None
DOCKER_ARGV=[]
COMMAND_ENV={}
OWNER_CAP=1048576
ORDINARY_CAP=524288
STREAM_CAP=32768
OUT=NAME=CID=PROFILE=OWNER=END=WORK_END=None
EVENTS=[]

def need(ok, why):
    if not ok:
        raise RuntimeError(why)


def ordinary(path):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts
         and not any(p.is_symlink() for p in (path, *path.parents)), 'ordinary absolute path')
    return path


def sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def retained():
    total = 0
    for path in OUT.iterdir():
        if path.name == 'output':
            need(path.is_dir() and not path.is_symlink(), 'ordinary owned worker output directory')
            continue
        st = path.lstat()
        need(stat.S_ISREG(st.st_mode) and st.st_nlink == 1, 'flat ordinary owner evidence')
        total += st.st_size
    return total


def save(name, value):
    body = value if isinstance(value, bytes) else (json.dumps(value, sort_keys=True, allow_nan=False)+'\n').encode()
    need(name == Path(name).name and 0 < len(name) < 128 and len(body) <= 131072,
         'finite owner evidence member')
    need(time.monotonic() < END and retained() + len(body) <= OWNER_CAP, 'owner horizon/retention cap')
    fd = os.open(OUT/name, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o400)
    try:
        offset = 0
        while offset < len(body):
            need(time.monotonic() < END, 'owner publication horizon')
            wrote = os.write(fd, body[offset:]); need(wrote > 0, 'complete evidence write'); offset += wrote
        os.fsync(fd)
    finally:
        os.close(fd)
    return {'path': str(OUT/name), 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def call(args, timeout=8, allowed=(0,), cleanup=False):
    number = len(EVENTS) + 1
    argv = [*DOCKER_ARGV, *args]
    begun = time.monotonic()
    deadline = min(begun + timeout, END - 2 if cleanup else WORK_END - (4 if args[:1] == ['start'] else 0))
    capture = {'stdout': bytearray(), 'stderr': bytearray()}
    received = {'stdout': 0, 'stderr': 0}
    eof = set(); issue = None; rc = None; proc = None
    selector = selectors.DefaultSelector()
    try:
        need(deadline > begun, 'original Docker call horizon')
        need(cleanup or retained() + 81920 <= ORDINARY_CAP, 'ordinary evidence reserve before call')
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, close_fds=True, env=COMMAND_ENV)
        for label, stream in (('stdout', proc.stdout), ('stderr', proc.stderr)):
            os.set_blocking(stream.fileno(), False); selector.register(stream, selectors.EVENT_READ, label)
        while selector.get_map() or proc.poll() is None:
            if time.monotonic() >= deadline:
                issue = 'deadline'; break
            for key, _ in selector.select(.025):
                label = key.data
                part = os.read(key.fileobj.fileno(), min(4096, STREAM_CAP-len(capture[label])+1))
                if not part:
                    eof.add(label); selector.unregister(key.fileobj); key.fileobj.close(); continue
                received[label] += len(part)
                left = STREAM_CAP-len(capture[label]); capture[label].extend(part[:left])
                if len(part) > left:
                    issue = 'stream_cap'; break
            if issue:
                break
        if issue and proc.poll() is None:
            proc.kill()
        rc = proc.wait(timeout=max(.01, min(1, END-time.monotonic()-1)))
    except BaseException as error:
        issue = issue or type(error).__name__
    finally:
        if proc is not None:
            if proc.poll() is None:
                proc.kill()
            try:
                rc = proc.wait(timeout=max(.01, min(1, END-time.monotonic()-1)))
            except BaseException as error:
                issue = issue or ('reap_' + type(error).__name__)
            for stream in (proc.stdout, proc.stderr):
                if stream is not None and not stream.closed:
                    stream.close()
        selector.close()
    outputs = {}
    for label, body in capture.items():
        outputs[label] = save('command-%02d.%s' % (number, label), bytes(body))
    event = {'argv': argv, 'returncode': rc, 'issue': issue, 'received': received,
             'observed_EOF': sorted(eof), 'complete': issue is None and eof == {'stdout', 'stderr'},
             'seconds': time.monotonic()-begun, 'outputs': outputs}
    EVENTS.append(event); save('CALL-%02d.json' % number, event)
    need(event['complete'] and rc in allowed, 'Docker call failed; original attempt retained')
    return rc, capture['stdout'].decode(), capture['stderr'].decode()


def inspect(identity, absent=False, cleanup=False):
    need(identity == NAME or sha(identity), 'only exact owned name or immutable ID inspect')
    fmt = '{"id":{{json .Id}},"name":{{json .Name}},"image":{{json .Image}},"state":{{json .State}},"memory":{{json .HostConfig.Memory}},"swap":{{json .HostConfig.MemorySwap}},"cpus":{{json .HostConfig.NanoCpus}},"network":{{json .HostConfig.NetworkMode}},"readonly":{{json .HostConfig.ReadonlyRootfs}},"mounts":{{json .Mounts}},"pids":{{json .HostConfig.PidsLimit}},"owner":{{json (index .Config.Labels "org.neurobench.owner")}},"tmpfs":{{json .HostConfig.Tmpfs}},"caps":{{json .HostConfig.CapDrop}},"security":{{json .HostConfig.SecurityOpt}},"args":{{json .Config.Cmd}},"entrypoint":{{json .Config.Entrypoint}}}'
    rc, stdout, stderr = call(['inspect', '--type=container', '--format', fmt, identity],
                              allowed=(0, 1) if absent else (0,), cleanup=cleanup)
    if rc == 1:
        need(absent and not stdout.strip() and 'no such' in stderr.lower() and identity in stderr,
             'exact requested container absence')
        return None
    return json.loads(stdout)


def owned(item):
    need(item['image'] == IMAGE and item['owner'] == OWNER and item['name'] == '/' + NAME
         and sha(item['id']), 'exact name/image/owner immutable-ID ownership')
    return item['id']


def cleanup_owned():
    result = {'name': NAME, 'cid_from_create': CID, 'owner': OWNER}
    if NAME is None:
        result['status'] = 'NO_CREATE_ATTEMPTED'; return result
    item = inspect(CID or NAME, absent=True, cleanup=True)
    if item is None:
        result['status'] = 'EXACT_SELECTED_RESOURCE_ABSENT'; return result
    identity = owned(item)
    need(CID is None or identity == CID, 'cleanup immutable ID equality')
    result.update(recovered_id=identity, state=item['state'])
    need(call(['rm', '-f', identity], cleanup=True)[1].strip() == identity, 'exact immutable-ID removal acknowledgement')
    need(inspect(identity, absent=True, cleanup=True) is None
         and inspect(NAME, absent=True, cleanup=True) is None, 'immutable ID and exact name both absent')
    result.update(status='OWNED_CONTAINER_REMOVED_AND_ABSENCE_VERIFIED', removed=True)
    return result


def output_inventory(root):
    total = 0; count = 0; pending = [root]
    while pending:
        need(time.monotonic() < END, 'bounded worker-output inventory horizon')
        directory = pending.pop()
        for path in directory.iterdir():
            st = path.lstat(); count += 1
            need(count <= 2048 and not stat.S_ISLNK(st.st_mode), 'finite alias-free worker inventory')
            if stat.S_ISDIR(st.st_mode):
                pending.append(path)
            else:
                need(stat.S_ISREG(st.st_mode) and st.st_nlink == 1, 'ordinary single-link worker output')
                total += st.st_size
                need(total <= PROFILE['worker_retention_bytes'], 'complete worker retention cap')
    return {'entries': count, 'bytes': total}

