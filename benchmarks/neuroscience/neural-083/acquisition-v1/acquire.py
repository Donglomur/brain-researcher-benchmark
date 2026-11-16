"""Fixed full108 OpenBMI acquisition. No import-time acquisition or network.

An acquisition receipt records downloaded byte identity, not scientific validity.
Only the CLI can select production transport; tests inject invented responses.
"""
import argparse
import base64
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import resource
import signal
import stat
import time
from urllib.parse import urlsplit

ROSTER_PIN = {'bytes': 37092, 'sha256': '03cc17f8ca4ff5581158f0e32c93af3207732fcf492680ccba229530b7b4c392'}
ROWS_SHA256 = '4a7370127c658965651af96a52ffe4c601cbaac47e0db6a142a616b3140ca7a3'
TOTAL_BYTES = 64847432285
CHUNK = 65536
METADATA_CAP = 4 * 1024**2
BASE = 'https://s3.ap-northeast-1.wasabisys.com/gigadb-datasets/live/pub/10.5524/100001_101000/100542/'


class Refused(ValueError):
    pass


def need(ok, message):
    if not ok:
        raise Refused(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=True, allow_nan=False) + '\n').encode('ascii')


def pin(body):
    return dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())


def diagnostic(error):
    value = type(error).__name__ + ': ' + str(error)
    return value if len(value) <= 512 else value[:512] + ' [truncated diagnostic]'


def directory(path):
    """Open each absolute ancestor by dirfd, refusing symlinks at every step."""
    raw = os.fspath(path)
    need(type(raw) is str and raw.startswith('/') and '\x00' not in raw,
         'absolute path required')
    parts = raw.split('/')[1:]
    need(parts and all(p and p not in ('.', '..') for p in parts), 'canonical path components')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in parts:
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = nxt
        return fd
    except BaseException:
        os.close(fd)
        raise


def capture(path, expected, cap):
    need(type(expected) is dict and set(expected) == {'bytes', 'sha256'}, 'exact metadata pin')
    need(type(expected['bytes']) is int and 0 < expected['bytes'] <= cap and
         type(expected['sha256']) is str and re.fullmatch('[a-f0-9]{64}', expected['sha256']),
         'bounded metadata pin')
    p = Path(path)
    parent = directory(str(p.parent))
    fd = None
    try:
        fd = os.open(p.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        first = os.fstat(fd)
        need(stat.S_ISREG(first.st_mode) and first.st_nlink == 1 and
             first.st_size == expected['bytes'], 'ordinary single-link exact metadata extent')
        body = bytearray()
        while len(body) < first.st_size:
            block = os.read(fd, min(CHUNK, first.st_size - len(body)))
            need(block, 'truncated metadata')
            body.extend(block)
        last = os.fstat(fd)
        now = os.stat(p.name, dir_fd=parent, follow_symlinks=False)
        fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        need(all(getattr(first, k) == getattr(last, k) == getattr(now, k) for k in fields),
             'metadata changed during capture')
        need(pin(body) == expected, 'metadata digest mismatch')
        return bytes(body)
    finally:
        if fd is not None:
            os.close(fd)
        os.close(parent)


def metadata(path, expected, cap):
    return json.loads(capture(path, expected, cap))


# Capture and authenticate the one local helper without depending on sys.path.
HTTP_PIN = {'bytes':1758, 'sha256':'f9b620d63654ffd144fa711b94d23cf0e3ced6dbb45336c10e2180a54fbfdb97'}
_helper_path = str(Path(__file__).absolute().with_name('bounded_http.py'))
_helper_namespace = {'__name__':'neural083_pinned_http', '__file__':_helper_path}
exec(compile(capture(_helper_path, HTTP_PIN, 32768), _helper_path, 'exec'), _helper_namespace)
_Connection = _helper_namespace['_Connection']
HEADER_CAP, HEADER_LINES = _helper_namespace['HEADER_CAP'], _helper_namespace['HEADER_LINES']


def roster(path):
    value = metadata(path, ROSTER_PIN, 131072)
    need(value['schema'] == 'neural083_publisher_acquisition_roster_v1', 'roster schema')
    rows = value['files']
    need(len(rows) == 108, 'all108 objects required')
    for row, (person, session) in zip(rows, ((p, s) for p in range(1, 55) for s in (1, 2))):
        rel = f'session{session}/s{person}/sess{session:02d}_subj{person:02d}_EEG_MI.mat'
        need(set(row) == {'person', 'session', 'path', 'bytes', 'url', 'publisher_md5'} and
             row['person'] == person and row['session'] == session and row['path'] == rel,
             'exact complete ordered identity')
        need(type(row['bytes']) is int and 0 < row['bytes'] <= 700000000 and
             row['url'] == BASE + rel and re.fullmatch('[a-f0-9]{32}', row['publisher_md5']),
             'fixed HTTPS object identity, extent and publisher MD5')
    need(sum(r['bytes'] for r in rows) == TOTAL_BYTES, 'full original extent')
    return value


class Ops:
    write = staticmethod(os.write)
    fsync = staticmethod(os.fsync)
    link = staticmethod(os.link)
    unlink = staticmethod(os.unlink)


class Output:
    """Fresh private output tree; all operations stay anchored to owned dirfds."""
    def __init__(self, path, ops=None):
        self.path = Path(path)
        self.ops = ops or Ops()
        self.parent = directory(str(self.path.parent))
        self.fd = None
        self.created = {}
        self.metadata_written = 0
        try:
            need(self.path.name not in ('', '.', '..'), 'fresh output name')
            os.mkdir(self.path.name, 0o700, dir_fd=self.parent)
            self.fd = os.open(self.path.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                              dir_fd=self.parent)
            self.identity = (os.fstat(self.fd).st_dev, os.fstat(self.fd).st_ino)
            self.ops.fsync(self.parent)
        except BaseException:
            self.close()
            raise

    def check(self):
        st = os.stat(self.path.name, dir_fd=self.parent, follow_symlinks=False)
        need(stat.S_ISDIR(st.st_mode) and (st.st_dev, st.st_ino) == self.identity,
             'owned output root replaced')

    def subdir(self, relative):
        self.check()
        fd = os.dup(self.fd)
        prefix = []
        try:
            for name in relative.split('/') if relative else []:
                need(re.fullmatch('[A-Za-z0-9_-]+', name), 'fixed relative directory')
                prefix.append(name)
                key = '/'.join(prefix)
                if key not in self.created:
                    os.mkdir(name, 0o700, dir_fd=fd)
                    self.ops.fsync(fd)
                nxt = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                try:
                    identity = (os.fstat(nxt).st_dev, os.fstat(nxt).st_ino)
                    if key in self.created:
                        need(identity == self.created[key], 'owned child directory replaced')
                    else:
                        self.created[key] = identity
                except BaseException:
                    os.close(nxt)
                    raise
                os.close(fd)
                fd = nxt
            return fd
        except BaseException:
            os.close(fd)
            raise

    def publish(self, fd, parent, temporary, final, size):
        need(os.fstat(fd).st_size == size and os.fstat(fd).st_nlink == 1, 'written file extent/link')
        os.fchmod(fd, 0o400)
        self.ops.fsync(fd)
        self.check()
        # link is atomic and fails if final already exists. No replacement rename.
        self.ops.link(temporary, final, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
        self.ops.fsync(parent)
        self.ops.unlink(temporary, dir_fd=parent)
        self.ops.fsync(parent)
        original = os.fstat(fd)
        result = os.stat(final, dir_fd=parent, follow_symlinks=False)
        need(stat.S_ISREG(result.st_mode) and result.st_nlink == original.st_nlink == 1 and
             (result.st_dev, result.st_ino, result.st_size) ==
             (original.st_dev, original.st_ino, size), 'published inode/extent/link')
        return dict(device=result.st_dev, inode=result.st_ino, bytes=result.st_size,
                    mode=stat.S_IMODE(result.st_mode), mtime_ns=result.st_mtime_ns,
                    ctime_ns=result.st_ctime_ns, nlink=result.st_nlink)

    def put(self, relative, value, cap=16384):
        body = encoded(value)
        need(len(body) <= cap and self.metadata_written + len(body) <= METADATA_CAP,
             'finite metadata partition')
        self.metadata_written += len(body)
        p = Path(relative)
        parent = self.subdir('' if str(p.parent) == '.' else p.parent.as_posix())
        fd = None
        try:
            tmp = p.name + '.partial'
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=parent)
            offset = 0
            while offset < len(body):
                n = self.ops.write(fd, memoryview(body)[offset:])
                need(type(n) is int and 0 < n <= len(body) - offset, 'metadata write progress')
                offset += n
            self.publish(fd, parent, tmp, p.name, len(body))
            return dict(path=relative, **pin(body))
        finally:
            if fd is not None:
                os.close(fd)
            os.close(parent)

    def close(self):
        for key in ('fd', 'parent'):
            value = getattr(self, key, None)
            if value is not None:
                os.close(value)
                setattr(self, key, None)


def headers(response, record):
    pairs = response.getheaders()
    capture = getattr(response, 'header_capture', None)
    if capture is None:
        raw = encoded(pairs)
        record['header_representation'] = 'invented_test_pairs'
    else:
        raw = bytes(capture.captured)
        record['header_representation'] = 'original_status_and_header_lines'
    record['headers_base64'] = base64.b64encode(raw).decode('ascii')
    need(len(raw) <= HEADER_CAP and len(pairs) <= HEADER_LINES, 'HTTP header cap')
    result = {}
    for key, value in pairs:
        need(type(key) is str and type(value) is str and
             not any(c in key + value for c in '\r\n\x00'), 'HTTP header type/injection')
        result.setdefault(key.lower(), []).append(value)
    return result


def one(mapping, key, required=False):
    values = mapping.get(key, [])
    need(len(values) == 1 if required else len(values) <= 1, 'unique HTTP header: ' + key)
    return values[0] if values else None


def fetch(row, output, ordinal, limits, deadline, *, connector=_Connection, clock=time.monotonic):
    """One full fixed object; failures are terminal and retain incomplete files."""
    need(row['url'] == BASE + row['path'], 'exact publisher URL; no redirects')
    url = urlsplit(row['url'])
    need(url.scheme == 'https' and url.netloc == 's3.ap-northeast-1.wasabisys.com' and
         not url.query and not url.fragment, 'fixed public HTTPS origin')
    started = clock()
    end = min(deadline, started + limits['request_seconds'])
    def alive():
        need(clock() < end, 'acquisition deadline')
    rec = dict(schema='neural083_object_acquisition_v1', ordinal=ordinal,
               person=row['person'], session=row['session'], path=row['path'], url=row['url'],
               expected_bytes=row['bytes'], expected_md5=row['publisher_md5'], status='FAILED',
               received_bytes=0, written_bytes=0, response_status=None, closure_errors=[])
    parent = output.subdir(str(Path(row['path']).parent))
    name = Path(row['path']).name
    temporary = name + '.partial'
    fd = response = connection = None
    error = None
    md5, sha256 = hashlib.md5(usedforsecurity=False), hashlib.sha256()
    def keep(block, maximum):
        need(type(block) is bytes, 'bytes response required')
        rec['received_bytes'] += len(block)
        need(0 < len(block) <= maximum, 'bounded response read')
        offset = 0
        while offset < len(block):
            alive()
            n = output.ops.write(fd, memoryview(block)[offset:])
            need(type(n) is int and 0 < n <= len(block) - offset, 'body write progress')
            # Digest only bytes whose successful write count was returned.
            piece = memoryview(block)[offset:offset+n]
            md5.update(piece)
            sha256.update(piece)
            offset += n
            rec['written_bytes'] += n
    try:
        alive()
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=parent)
        connection = connector(url.hostname, min(limits['socket_seconds'], max(0.001, end-clock())))
        alive()
        connection.request('GET', url.path, headers={'Accept-Encoding':'identity',
                           'User-Agent':'NEURAL083-Full108-Acquisition/1'})
        alive()
        response = connection.getresponse()
        rec['response_status'] = response.status
        values = headers(response, rec)
        need(response.status == 200, 'only200 accepted; redirect/error body unread')
        need(one(values, 'content-length', True) == str(row['bytes']), 'exact Content-Length')
        need('transfer-encoding' not in values and one(values, 'content-encoding') in (None, 'identity'),
             'identity, Content-Length-framed body required')
        while rec['received_bytes'] < row['bytes']:
            alive()
            maximum = min(CHUNK, row['bytes'] - rec['received_bytes'])
            try:
                block = response.read(maximum)
            except http.client.IncompleteRead as exc:
                if exc.partial:
                    keep(exc.partial, maximum)
                raise
            need(block, 'premature EOF')
            keep(block, maximum)
        alive()
        tail = response.read(1)
        need(type(tail) is bytes, 'bytes EOF sentinel required')
        rec['received_bytes'] += len(tail)
        rec['eof_probe_bytes'] = len(tail)
        need(len(tail) <= 1, 'bounded EOF sentinel')
        need(tail == b'', 'natural end of framed response required')
        alive()
        need(rec['written_bytes'] == row['bytes'] and md5.hexdigest() == row['publisher_md5'],
             'complete written extent and publisher MD5')
    except BaseException as exc:
        error = exc
    finally:
        if response is None and connection is not None:
            response = getattr(connection, 'observed_response', None)
        if response is not None and 'headers_base64' not in rec:
            capture = getattr(response, 'header_capture', None)
            if capture is not None:
                rec['headers_base64'] = base64.b64encode(bytes(capture.captured)).decode('ascii')
                rec['header_representation'] = 'original_consumed_header_prefix'
        for label, obj in (('response', response), ('connection', connection)):
            if obj is not None:
                try:
                    obj.close()
                except BaseException as exc:
                    rec['closure_errors'].append(label + ': ' + diagnostic(exc))
                    error = error or exc
        rec['confirmed_write_md5'] = md5.hexdigest()
        rec['confirmed_write_sha256'] = sha256.hexdigest()
        try:
            if fd is not None:
                if error is None:
                    alive()
                    rec['publication'] = output.publish(fd, parent, temporary, name, row['bytes'])
                else:
                    output.ops.fsync(fd)
                rec['physical_file_bytes'] = os.fstat(fd).st_size
        except BaseException as exc:
            error = error or exc
            rec['closure_errors'].append('file durability/publication: ' + diagnostic(exc))
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except BaseException as exc:
                    error = error or exc
                    rec['closure_errors'].append('file close: ' + diagnostic(exc))
            os.close(parent)
        rec['elapsed_seconds'] = clock() - started
        if error is None:
            rec['status'] = 'DURABLE_COMPLETE'
        else:
            rec['error'] = diagnostic(error)
        try:
            descriptor = output.put(f'receipts/{ordinal:03d}.json', rec)
        except BaseException as exc:
            raise Refused('receipt publication failed; preserved files are not admitted') from exc
    if error is not None:
        raise Refused('object failed; see retained receipt') from error
    return rec, descriptor


def acquire(rows, output, limits, *, connector=_Connection, clock=time.monotonic, deadline=None):
    need(len(rows) == 108, 'full108 only')
    need(hashlib.sha256(encoded(rows)).hexdigest() == ROWS_SHA256,
         'exact complete publisher roster required before transport')
    return _acquire_rows(rows, output, limits, connector=connector, clock=clock,
                         publisher_bound=True, deadline=deadline)


def _acquire_rows(rows, output, limits, *, connector, clock=time.monotonic,
                  publisher_bound=False, deadline=None):
    """Internal streaming mechanism; invented controls never emit admissible manifests."""
    need(len(rows) == 108, 'full108 only')
    if publisher_bound:
        need(hashlib.sha256(encoded(rows)).hexdigest() == ROWS_SHA256, 'publisher binding')
    if deadline is None:
        deadline = clock() + limits['whole_seconds']
    need(clock() < deadline, 'original acquisition deadline exhausted before transport')
    files, receipts = [], []
    try:
        for ordinal, row in enumerate(rows, 1):
            record, receipt = fetch(row, output, ordinal, limits, deadline,
                                    connector=connector, clock=clock)
            files.append({k:row[k] for k in ('person', 'session', 'path', 'bytes')} |
                         {'sha256':record['confirmed_write_sha256']})
            receipts.append(receipt)
        need(len({r['sha256'] for r in files}) == 108, 'distinct complete source hashes')
        manifest_name = 'verified-sources.json' if publisher_bound else 'generated-sources.json'
        manifest = output.put(manifest_name,
                              {'schema':'neural083_verified_sources_v1' if publisher_bound else
                               'neural083_generated_control_sources_v1', 'files':files}, cap=65536)
        return output.put('COMPLETE.json', dict(schema='neural083_full108_acquisition_v1',
                          status='DURABLE_COMPLETE' if publisher_bound else 'GENERATED_CONTROL_ONLY',
                          roster=ROSTER_PIN if publisher_bound else None, records=108,
                          selected_rows_sha256=hashlib.sha256(encoded(rows)).hexdigest(),
                          body_bytes=sum(r['bytes'] for r in rows), manifest=manifest,
                          receipts=receipts, scientific_qualified=False), cap=65536)
    except BaseException as exc:
        try:
            output.put('FAILED.json', dict(schema='neural083_failed_acquisition_v1',
                       completed_objects=len(files), error=diagnostic(exc), retry_selected=False))
        except BaseException as custody:
            exc.add_note('Failure receipt could not be persisted: ' + diagnostic(custody))
        raise


def install_limits(cpu_seconds, whole_seconds):
    """Do not raise an inherited CPU or wall allocation in this dedicated CLI."""
    deadline = time.monotonic() + whole_seconds
    soft, hard = resource.getrlimit(resource.RLIMIT_CPU)
    ceiling = min(x for x in (soft, hard, cpu_seconds) if x != resource.RLIM_INFINITY)
    resource.setrlimit(resource.RLIMIT_CPU, (ceiling, hard))
    def expired(*_):
        raise TimeoutError('whole acquisition wall deadline')
    signal.signal(signal.SIGALRM, expired)
    inherited, _ = signal.getitimer(signal.ITIMER_REAL)
    after_read = time.monotonic()
    if inherited > 0:
        if after_read + inherited > deadline:
            raise TimeoutError('inherited timer not provably within requested window; unchanged')
        return deadline  # Never re-arm an active inherited timer.
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError('acquisition wall allowance exhausted during limit setup')
    signal.setitimer(signal.ITIMER_REAL, remaining)
    return deadline  # Relative arming has syscall latency; I/O uses this original deadline.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--roster', required=True)
    parser.add_argument('--request', required=True)
    parser.add_argument('--request-bytes', required=True, type=int)
    parser.add_argument('--request-sha256', required=True)
    args = parser.parse_args()
    source = roster(args.roster)
    request_pin = {'bytes':args.request_bytes, 'sha256':args.request_sha256}
    request = metadata(args.request, request_pin, 16384)
    need(set(request) == {'schema','execution_authorized','output_root','whole_seconds',
         'request_seconds','socket_seconds','cpu_seconds','minimum_free_bytes','owner_receipt'}, 'request fields')
    need(request['schema'] == 'neural083_acquisition_request_v1' and
         request['execution_authorized'] is True, 'separate actual root execution selection required')
    for key, maximum in [('whole_seconds',43200),('request_seconds',3600),('socket_seconds',30),('cpu_seconds',3600)]:
        need(type(request[key]) is int and 0 < request[key] <= maximum, 'finite request limit: '+key)
    need(request['socket_seconds'] <= request['request_seconds'] <= request['whole_seconds'], 'nested deadlines')
    need(type(request['minimum_free_bytes']) is int and request['minimum_free_bytes'] >= TOTAL_BYTES+METADATA_CAP,
         'full storage reservation plus metadata required')
    need(type(request['owner_receipt']) is dict and request['owner_receipt'].get('hard_memory_bytes') == 128*1024**2
         and request['owner_receipt'].get('aggregate_cpu_seconds') == request['cpu_seconds'],
         'explicit externally enforced owner declaration required; not enforced by this field')
    parent = directory(str(Path(request['output_root']).parent))
    try:
        space = os.fstatvfs(parent)
        need(space.f_bavail*space.f_frsize >= request['minimum_free_bytes'], 'fresh free-storage gate')
    finally:
        os.close(parent)
    deadline = install_limits(request['cpu_seconds'], request['whole_seconds'])
    output = None
    try:
        need(time.monotonic() < deadline, 'original acquisition deadline before output')
        output = Output(request['output_root'])
        output.put('REQUEST.json', dict(request=request, request_pin=request_pin, roster_pin=ROSTER_PIN))
        result = acquire(source['files'], output, request, deadline=deadline)
        print(json.dumps(result, sort_keys=True))
    finally:
        if output is not None:
            output.close()
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == '__main__':
    main()
