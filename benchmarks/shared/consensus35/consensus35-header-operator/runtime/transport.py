"""Complete35 CONSENSUS primitive NPY-header range transport; no import-time I/O or automatic execution.

Adapted from pinned high-gamma range_client.py
fac5f668fdd7e123294741bee18c1526dc7a9ad9d856d3ff2013b84a0571c8e6.
Only fetch opens network connections. Every invocation must be independently
selected, including a fixed one-archive inventory, phase, budget and owner lifetime.
The transport proves no directory, biological, payload or full-MD5 result.
"""
import base64
import datetime
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import urljoin, urlsplit, unquote_to_bytes

MIB = 1024 * 1024
HEADER_CAP = 4096
HEADER_LINES = 64
URL_CAP = 2048
RAW_CAP = 16384
RAW_COUNT_CAP = 211
RAW_TOTAL_CAP = RAW_CAP * RAW_COUNT_CAP
RANGE_CAP = 4096
PINNED = ((60729664, 29600128, 'all_lm_cells.npy', 'https://ndownloader.figshare.com/files/60729664', 'ace8f1323cb8aa4f46f5b74c4c531468'), (60729643, 7528, 'all_times.npy', 'https://ndownloader.figshare.com/files/60729643', '36fc4b2c794750ce919391fd7fc27d33'), (60729697, 79920128, 'all_v1_cells.npy', 'https://ndownloader.figshare.com/files/60729697', 'a34c4dd7ff6c9a8d4b8648ad405ad805'), (60729679, 7480, 'stim_times.npy', 'https://ndownloader.figshare.com/files/60729679', 'b24c65450be74b9b051f8f12ab6b21cd'), (60729688, 14928, 'unique_ids.npy', 'https://ndownloader.figshare.com/files/60729688', '4a6837a2a00dd8079e92866138d5c875'), (60729727, 35616128, 'all_lm_cells.npy', 'https://ndownloader.figshare.com/files/60729727', 'bc22c5e119d9d8713198e5522d5e44d7'), (60729706, 6064, 'all_times.npy', 'https://ndownloader.figshare.com/files/60729706', '19b244f8c4c01385f1261c8e954b91cd'), (60729766, 102099328, 'all_v1_cells.npy', 'https://ndownloader.figshare.com/files/60729766', 'c17e1ebe480d8e8fb6fcad806eb9660e'), (60729748, 6016, 'stim_times.npy', 'https://ndownloader.figshare.com/files/60729748', '0b222093dd2ed929bb298fee9370c270'), (60729754, 12000, 'unique_ids.npy', 'https://ndownloader.figshare.com/files/60729754', 'e9781812bf27212097d0a16b7acf3044'), (60729880, 104400128, 'all_lm_cells.npy', 'https://ndownloader.figshare.com/files/60729880', 'db14927496e2d0680656b44390d9b262'), (60729799, 5928, 'all_times.npy', 'https://ndownloader.figshare.com/files/60729799', '85b738430faee68b5183ae57920d808b'), (60729868, 34800128, 'all_v1_cells.npy', 'https://ndownloader.figshare.com/files/60729868', 'c74aed89e45997950515882ef79e3651'), (60729832, 5880, 'stim_times.npy', 'https://ndownloader.figshare.com/files/60729832', 'b3d97e4f2b3481b85b37e5c44c0fdad1'), (60729844, 11728, 'unique_ids.npy', 'https://ndownloader.figshare.com/files/60729844', '145b9c0e0283818ed07cc758f9647a67'), (60729943, 109040128, 'all_lm_cells.npy', 'https://ndownloader.figshare.com/files/60729943', 'bb24a55f23a1f62e8b3312b70c294a8e'), (60729859, 5928, 'all_times.npy', 'https://ndownloader.figshare.com/files/60729859', 'eba29220de91037f81dc3bb9580e6553'), (60729958, 76560128, 'all_v1_cells.npy', 'https://ndownloader.figshare.com/files/60729958', '1d8f2aff41915538d341288179c33224'), (60729901, 5880, 'stim_times.npy', 'https://ndownloader.figshare.com/files/60729901', 'b3d97e4f2b3481b85b37e5c44c0fdad1'), (60729910, 11728, 'unique_ids.npy', 'https://ndownloader.figshare.com/files/60729910', '7785fb36a69f8fd90e0da3195c4465e7'), (60730006, 113523328, 'all_lm_cells.npy', 'https://ndownloader.figshare.com/files/60730006', '517d9a419784e4191ce67dc29d46dd64'), (60729922, 5920, 'all_times.npy', 'https://ndownloader.figshare.com/files/60729922', '28b406ac83dcdccc1c4c9fda86227c98'), (60729982, 13900928, 'all_v1_cells.npy', 'https://ndownloader.figshare.com/files/60729982', 'ea0b0107d271dc4bf2c90a61dc665d55'), (60729964, 5872, 'stim_times.npy', 'https://ndownloader.figshare.com/files/60729964', 'bad94da3e25d1f123efe95b02c0365fc'), (60729970, 11712, 'unique_ids.npy', 'https://ndownloader.figshare.com/files/60729970', 'e4c5618fb414ff9ea01c3d31228bd00b'), (60730066, 106131328, 'all_lm_cells.npy', 'https://ndownloader.figshare.com/files/60730066', '0e0a2acbc4c354faa99cc591589349a7'), (60729994, 5896, 'all_times.npy', 'https://ndownloader.figshare.com/files/60729994', '81e7949ee5f3c295523d5c237d59044b'), (60730087, 66908928, 'all_v1_cells.npy', 'https://ndownloader.figshare.com/files/60730087', 'e8bda1ded0aa4f63eebc223e5065b570'), (60730036, 5848, 'stim_times.npy', 'https://ndownloader.figshare.com/files/60730036', '404b38f031932da063bc17962a79f01f'), (60730045, 11664, 'unique_ids.npy', 'https://ndownloader.figshare.com/files/60730045', 'a6d63806869e00f3faf79a2f07d3ab56'), (60730096, 37376128, 'all_lm_cells.npy', 'https://ndownloader.figshare.com/files/60730096', '7d8a729890d0f91fb9f1c78ad89ca400'), (60730057, 5968, 'all_times.npy', 'https://ndownloader.figshare.com/files/60730057', '2bdca67741d72d2053be3f153bb5fcd2'), (60730114, 95776128, 'all_v1_cells.npy', 'https://ndownloader.figshare.com/files/60730114', '239dd7c1ce526cbcff3379e08a63a057'), (60730099, 5920, 'stim_times.npy', 'https://ndownloader.figshare.com/files/60730099', 'a79b2df4f4822bd97ede6dcde88d2af1'), (60730111, 11808, 'unique_ids.npy', 'https://ndownloader.figshare.com/files/60730111', '6832e928d6357ea0bb1295516a74e76d'))
FIELDS = ('file_id', 'bytes', 'filename', 'download_url', 'provider_computed_md5')
DEFAULTS = dict(responses=210, redirects=1, per_range=4096,
                wall_seconds=1470, request_seconds=15, socket_seconds=3)


class RangeError(ValueError):
    pass


def need(ok, message):
    if not ok:
        raise RangeError(message)


def encoded(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True,
                       separators=(',', ':'), allow_nan=False) + '\n').encode('ascii')


def diagnostic(exc):
    # Diagnostic text is not an HTTP original. Preserve its bounded prefix and
    # explicitly signal omitted text rather than mislabel it as a full error.
    raw = type(exc).__name__ + ': ' + str(exc)
    return raw if len(raw) <= 512 else raw[:512] + ' [diagnostic truncated]'


def strong_etag(value):
    return type(value) is str and len(value) <= 128 and bool(
        re.fullmatch(r'"[\x21\x23-\x7e\x80-\xff]*"', value))


def asset_projection(asset):
    need(type(asset) is dict and all(k in asset for k in FIELDS), 'asset fields')
    need(type(asset['file_id']) is int and type(asset['bytes']) is int,
         'asset integer types')
    return tuple(asset[k] for k in FIELDS)


def checked_url(url):
    need(type(url) is str and 0 < len(url) <= URL_CAP, 'URL length/type')
    need(all(33 <= ord(c) < 127 for c in url), 'URL ASCII/control restriction')
    need(not any(c in url for c in '#\\"<>`{}|^'), 'URL forbidden character')
    u = urlsplit(url)
    need(u.scheme == 'https' and u.netloc and u.port in (None, 443), 'HTTPS443 required')
    need('@' not in u.netloc and u.username is None and u.password is None, 'userinfo')
    host = u.hostname or ''
    need(bool(re.fullmatch(r'[a-z0-9]+(?:[a-z0-9.-]*[a-z0-9])?', host)), 'host syntax')
    need(host in ('ndownloader.figshare.com',
        '44c1cec316ec56bca76dfd65d2882b20.r2.cloudflarestorage.com'),
        'exact observed publisher/storage hosts only')
    return host, (u.path or '/') + ('?' + u.query if u.query else '')


AUTH_QUERY_FIELDS = frozenset(('X-Amz-Algorithm','X-Amz-Credential','X-Amz-Date',
    'X-Amz-Expires','X-Amz-SignedHeaders','X-Amz-Signature'))

def object_identity(url):
    """Pin opaque host/path/non-auth bytes; omit only explicit signing fields."""
    checked_url(url)
    u=urlsplit(url); names=set(); stable=[]
    for token in u.query.split('&') if u.query else []:
        need('=' in token, 'unambiguous query assignment')
        key,value=token.split('=',1)
        raw=unquote_to_bytes(key)
        need(raw and all(33<=b<127 for b in raw), 'ASCII query key')
        decoded=raw.decode('ascii')
        need(decoded not in names, 'duplicate query key')
        names.add(decoded)
        if decoded in AUTH_QUERY_FIELDS:
            need(key==decoded and value, 'unambiguous canonical auth query key')
        else:
            stable.append(token)
    return dict(scheme=u.scheme, authority=u.netloc, path=u.path or '/',
                non_auth_query=stable)

def storage_identity_allowed(url, expected, now=None):
    identity = object_identity(url)
    if identity != expected:
        return False
    pairs = {}
    for token in urlsplit(url).query.split('&'):
        key,value=token.split('=',1)
        pairs[key]=unquote_to_bytes(value).decode('ascii')
    if set(pairs) != AUTH_QUERY_FIELDS | {
            'response-content-disposition','response-content-type'}:
        return False
    if (pairs['X-Amz-Algorithm'] != 'AWS4-HMAC-SHA256'
            or pairs['X-Amz-Expires'] != '10'
            or pairs['X-Amz-SignedHeaders'] != 'host'
            or not re.fullmatch(r'[0-9a-f]{64}',pairs['X-Amz-Signature'])
            or not 1 <= len(pairs['X-Amz-Credential']) <= 512):
        return False
    try:
        signed=datetime.datetime.strptime(pairs['X-Amz-Date'],'%Y%m%dT%H%M%SZ').replace(
            tzinfo=datetime.timezone.utc).timestamp()
    except ValueError:
        return False
    return now is None or signed-2 <= now < signed+10

class _HeaderReader:
    """Bound original consumed status/header lines, including informational replies."""
    def __init__(self, raw):
        self.raw, self.captured, self.lines = raw, bytearray(), 0

    def readline(self, limit=-1):
        left = HEADER_CAP - len(self.captured)
        size = left + 1 if limit < 0 else min(limit, left + 1)
        need(size > 0, 'HTTP header cap')
        line = self.raw.readline(size)
        self.captured.extend(line)
        need(len(self.captured) <= HEADER_CAP, 'HTTP header cap; consumed prefix retained')
        if line not in (b'', b'\r\n', b'\n'):
            self.lines += 1
            need(self.lines <= HEADER_LINES, 'HTTP header/status line count')
        return line


class _Response(http.client.HTTPResponse):
    def begin(self):
        raw = self.fp
        self.header_capture = _HeaderReader(raw)
        self.fp = self.header_capture
        try:
            super().begin()
        finally:
            self.fp = raw


class _Connection(http.client.HTTPSConnection):
    def __init__(self, host, timeout):
        super().__init__(host, timeout=timeout)
        self.observed_response = None
        self.response_class = self._response

    def _response(self, *args, **kwargs):
        self.observed_response = _Response(*args, **kwargs)
        return self.observed_response


class RangeTransport:
    def __init__(self, output_root, assets, identities, phase='headers', limits=None,
                 connector=None, pins=None, clock=time.monotonic, write_fn=os.write,
                 utc_clock=time.time):
        need(type(assets) is list and len(assets) == 35, 'complete35 original-file inventory')
        projections = [asset_projection(a) for a in assets]
        need(len(set(projections)) == 35 and tuple(projections) == PINNED,
             'exact immutable ordered35-file inventory')
        need(phase == 'headers', 'only primitive-header inquiry')
        self.assets = {a[0]: a for a in PINNED}
        self.phase = phase
        self.limits = dict(DEFAULTS, body_bytes=143780)
        if limits is not None:
            need(type(limits) is dict and set(limits) <= set(self.limits), 'known limits')
            for key, value in limits.items():
                need(type(value) is int and 0 < value <= self.limits[key], 'limits may only narrow')
                self.limits[key] = value
        self.validators = {}
        need(pins is None, 'no invented prior target validators')
        need(type(identities) is dict and set(identities) == {a[0] for a in PINNED},
             'all35 externally pinned stable target identities')
        self.identities = identities
        for a in PINNED:
            identity=identities[a[0]]
            need(type(identity) is dict and set(identity) ==
                {'scheme','authority','path','non_auth_query'}
                and identity['scheme']=='https'
                and identity['authority']=='44c1cec316ec56bca76dfd65d2882b20.r2.cloudflarestorage.com'
                and identity['path']=='/figshare-com-storage/%d/%s' % (a[0],a[2])
                and type(identity['non_auth_query']) is list
                and len(identity['non_auth_query'])==2,
                'exact retained object identity, never a cached signed URL')
        self.stages={a[0]:0 for a in PINNED}
        self.widths,self.header_lengths={},{}
        self.utc_clock=utc_clock
        self.root = Path(output_root)
        need(self.root.is_absolute() and '..' not in self.root.parts, 'absolute output path')
        for p in (self.root, *self.root.parents):
            need(not p.is_symlink(), 'output symlink ancestry')
        self.root.mkdir(mode=0o700, exist_ok=False)
        self.connector, self.clock, self.write_fn = connector or _Connection, clock, write_fn
        self.started = clock()
        self.final_urls, self.ranges = {}, {}
        self.range_attempts = 0
        self.logical_range_requested_bytes = 0
        self.transactions = self.redirects = self.body_returned = self.body_written = 0
        self.metadata_written = self.raw_records = 0
        self.failed = self.closed = False
        self.errors, self.unpersisted_originals = [], {}
        self.successful_descriptors = self.failed_descriptors = 0

    def _alive(self, start=None):
        now = self.clock()
        need(now - self.started < self.limits['wall_seconds'], 'global elapsed deadline')
        if start is not None:
            need(now - start < self.limits['request_seconds'], 'request elapsed deadline')

    def _asset(self, asset):
        a = asset_projection(asset)
        need(self.assets.get(a[0]) == a, 'asset identity mismatch')
        return a

    def etag(self, asset):
        return self.validators.get(self._asset(asset)[0])

    def _metadata(self, name, value):
        raw = encoded(value)
        need(len(raw) <= RAW_CAP, 'complete raw metadata record exceeds16KiB')
        need(self.raw_records < RAW_COUNT_CAP and
             self.metadata_written + len(raw) <= RAW_TOTAL_CAP, 'raw metadata partition')
        self.raw_records += 1
        with (self.root / name).open('xb', buffering=0) as f:
            view = memoryview(raw)
            while view:
                n = f.write(view)
                need(type(n) is int and 0 < n <= len(view), 'metadata write')
                self.metadata_written += n
                view = view[n:]
            os.fsync(f.fileno())
        return len(raw)

    def _headers(self, response, record):
        cap = getattr(response, 'header_capture', None)
        pairs = response.getheaders()
        if cap is None:
            need(len(pairs) <= HEADER_LINES, 'invented header count')
            raw = (f'HTTP-INVENTED {response.status}\r\n'.encode('ascii') +
                   b''.join((k + ': ' + v + '\r\n').encode('latin1') for k, v in pairs) + b'\r\n')
            need(len(raw) <= HEADER_CAP, 'invented HTTP header cap')
            record['headers_representation'] = 'invented_connector_serialization'
        else:
            raw = bytes(cap.captured)
            record['headers_representation'] = 'original_status_and_header_lines'
        record['headers_base64'] = base64.b64encode(raw).decode('ascii')
        need(len(raw) <= HEADER_CAP and len(pairs) <= HEADER_LINES, 'HTTP header cap/count')
        out = {}
        for k, v in pairs:
            need(type(k) is str and type(v) is str and not any(c in k+v for c in '\r\n\x00'),
                 'header type/injection')
            out.setdefault(k.lower(), []).append(v)
        return out

    @staticmethod
    def _one(headers, key, required=False):
        vals = headers.get(key, [])
        need(len(vals) == 1 if required else len(vals) <= 1, 'unique header: ' + key)
        return vals[0] if vals else None

    def _transaction(self, a, url, start, count, label, redirects):
        self._alive()
        need(self.transactions < self.limits['responses'], 'HTTP transaction/response cap')
        need(self.raw_records + 2 <= RAW_COUNT_CAP, 'descriptor plus final report capacity')
        host, path = checked_url(url)
        if url != a[3]:
            need(storage_identity_allowed(url,self.identities[a[0]],self.utc_clock()),
                 'same object and fresh10-second signature before target dispatch')
        began = self.clock()
        self.transactions += 1
        index = self.transactions
        body_name, descriptor = f'HTTP_{index:03d}.bin', f'HTTP_{index:03d}.json'
        request_headers = {'Range': f'bytes={start}-{start+count-1}',
                           'Accept-Encoding': 'identity', 'User-Agent': 'CONSENSUS-NPY-Header-Metadata/1'}
        if a[0] in self.validators:
            request_headers['If-Match'] = self.validators[a[0]]
        rec = dict(index=index, file_id=a[0], label=label, request_url=url,
                   request_headers=request_headers, requested_start=start, requested_count=count,
                   request_issued=False, status='FAILED', response_status=None, body_file=body_name,
                   body_returned=0, body_written=0, response_closed=None, connection_closed=None,
                   body_closed=None, body_complete=False, closure_errors=[], body_intentionally_unread=True)
        # Bounded descriptors leave room for 4097 raw header bytes, a redirect URL,
        # hashes, closure metadata and one bounded diagnostic. No truncating originals.
        need(len(encoded(rec)) + ((HEADER_CAP+3)//3)*4 + URL_CAP + 2048 <= RAW_CAP,
             'request plus worst-case descriptor admission')
        digest = hashlib.sha256()
        blocks, connection, response, fd, error, outcome = [], None, None, None, None, None

        def keep(block):
            need(type(block) is bytes and len(block) <= count-rec['body_returned'],
                 'connector exceeded admitted read')
            before = rec['body_returned']
            blocks.append(block)
            digest.update(block)
            rec['body_returned'] += len(block)
            self.body_returned += len(block)
            off = 0
            try:
                while off < len(block):
                    n = self.write_fn(fd, memoryview(block)[off:])
                    need(type(n) is int and 0 < n <= len(block)-off, 'body write')
                    off += n
                    rec['body_written'] += n
                    self.body_written += n
            except BaseException as exc:
                rec['write_error'] = diagnostic(exc)
                # One positional custody pass is not an HTTP retry; failed state remains.
                try:
                    while off < len(block):
                        n = os.pwrite(fd, memoryview(block)[off:], before+off)
                        need(type(n) is int and 0 < n <= len(block)-off, 'custody recovery write')
                        off += n
                        rec['body_written'] += n
                        self.body_written += n
                except BaseException as recovery:
                    rec['recovery_error'] = diagnostic(recovery)
                    self.unpersisted_originals[body_name] = (before+off, block[off:])
                raise

        try:
            fd = os.open(self.root/body_name, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
            connection = self.connector(host, self.limits['socket_seconds'])
            self._alive(began)
            rec['request_issued'] = True
            connection.request('GET', path, headers=request_headers)
            self._alive(began)
            response = connection.getresponse()
            rec['response_status'] = response.status
            headers = self._headers(response, rec)
            self._alive(began)
            if response.status in (301,302,303,307,308):
                need(redirects < self.limits['redirects'], 'per-fetch redirect cap')
                location = self._one(headers, 'location', True)
                target = urljoin(url, location)
                checked_url(target)
                # Never rebind a pinned object to a different storage URL on a later fetch.
                need(storage_identity_allowed(target,self.identities[a[0]],self.utc_clock()),
                     'redirect object/query identity or signature time changed before request')
                rec['redirect_target_private'] = target
                self.redirects += 1
                rec['status'] = 'REDIRECT_BODY_UNREAD'
                outcome = ('redirect', target)
            else:
                need(response.status == 206, 'strict206; rejected body unread')
                need(storage_identity_allowed(url,self.identities[a[0]]),
                     'terminal object identity changed; body unread')
                need(self._one(headers,'content-range',True) ==
                     f'bytes {start}-{start+count-1}/{a[1]}', 'exact Content-Range')
                need(self._one(headers,'content-length',True) == str(count), 'exact Content-Length')
                enc = self._one(headers,'content-encoding')
                need(enc is None or enc.lower() == 'identity', 'identity Content-Encoding')
                need('transfer-encoding' not in headers, 'Transfer-Encoding forbidden')
                tag = self._one(headers,'etag',True)
                need(strong_etag(tag), 'strong first and subsequent ETag required')
                need(a[0] not in self.validators or tag == self.validators[a[0]], 'ETag changed')
                rec['strong_etag'] = tag
                rec['body_intentionally_unread'] = False
                while rec['body_returned'] < count:
                    self._alive(began)
                    amount = min(65536, count-rec['body_returned'])
                    try:
                        block = response.read(amount)
                    except http.client.IncompleteRead as incomplete:
                        if incomplete.partial:
                            keep(incomplete.partial)
                        raise
                    if block:
                        keep(block)
                    need(block, 'premature EOF')
                self._alive(began)
                rec['body_complete'] = True
                rec['status'] = 'EXACT_RANGE_RETURNED'
                outcome = ('range', (b''.join(blocks), tag))
        except BaseException as exc:
            error = exc
            rec['error'] = diagnostic(exc)
        finally:
            if response is None and connection is not None:
                response = getattr(connection,'observed_response',None)
            if response is not None and 'headers_base64' not in rec:
                capture = getattr(response,'header_capture',None)
                if capture is not None:
                    rec['headers_base64'] = base64.b64encode(bytes(capture.captured)).decode('ascii')
                    rec['headers_representation'] = 'original_consumed_header_prefix'
            if fd is not None:
                try:
                    os.fsync(fd)
                    rec['body_file_bytes'] = os.fstat(fd).st_size
                    rec['preservation_complete'] = (body_name not in self.unpersisted_originals and
                        rec['body_file_bytes'] == rec['body_returned'] == rec['body_written'])
                except BaseException as exc:
                    rec['closure_errors'].append('fsync/fstat: '+diagnostic(exc))
                try:
                    os.close(fd)
                    rec['body_closed'] = True
                except BaseException as exc:
                    rec['body_closed'] = False
                    rec['closure_errors'].append('body close: '+diagnostic(exc))
            for key,obj in (('response',response),('connection',connection)):
                if obj is not None:
                    try:
                        obj.close()
                        rec[key+'_closed'] = True
                    except BaseException as exc:
                        rec[key+'_closed'] = False
                        rec['closure_errors'].append(key+' close: '+diagnostic(exc))
            rec['returned_sha256'] = digest.hexdigest()
            rec['elapsed_seconds'] = self.clock()-began
            if rec['closure_errors'] or not rec.get('preservation_complete',False):
                error = error or RangeError('body custody/closure incomplete')
            if error is not None:
                rec['status'] = 'FAILED'
                rec.setdefault('error', diagnostic(error))
            try:
                self._metadata(descriptor,rec)
                self.successful_descriptors += 1
            except BaseException as exc:
                self.failed_descriptors += 1
                # Retain exact unserialized descriptor in memory on physical failure.
                self.unpersisted_originals[descriptor] = (0, encoded(rec))
                error = error or exc
            if error is not None:
                self.failed = True
                self.errors.append(diagnostic(error))
        if error is not None:
            raise error
        return outcome

    def fetch(self, asset, start, count, label):
        try:
            need(not self.failed and not self.closed, 'transport terminal after failure/close')
            a = self._asset(asset)
            need(type(start) is int and type(count) is int and 0 <= start < a[1] and
                 0 < count <= self.limits['per_range'] and start+count <= a[1], 'bounded integer range')
            need(type(label) is str and re.fullmatch(r'[A-Za-z0-9_.-]{1,48}',label), 'range label')
            need(self.body_returned+count <= self.limits['body_bytes'], 'aggregate body partition')
            index=next(i for i,x in enumerate(PINNED) if x[0]==a[0])
            stage=self.stages[a[0]]
            if stage==0:
                need((start,count,label)==(0,8,'f%02d-magic'%index),
                     'first range is exactly eight magic/version bytes')
            elif stage==1:
                need(all(x>=1 for x in self.stages.values()),
                     'all35 prefixes/validators before further header reads')
                need((start,count,label)==(8,self.widths[a[0]],'f%02d-length'%index),
                     'exact admitted length field')
            elif stage==2:
                need((start,count,label)==(8+self.widths[a[0]],self.header_lengths[a[0]],
                     'f%02d-header'%index),'exact decoded header extent')
            else:
                need(False,'one complete header per object')
            need(self.range_attempts < 105, 'complete35 three-range cap')
            need(self.logical_range_requested_bytes+count <=143780,
                 'aggregate requested entity bound including failed attempt')
            self.logical_range_requested_bytes+=count
            self.range_attempts += 1
            url, redirects = a[3], 0
            visited = set()
            while True:
                need(url not in visited, 'redirect cycle')
                visited.add(url)
                kind,result = self._transaction(a,url,start,count,label,redirects)
                if kind == 'redirect':
                    redirects += 1
                    url = result
                    continue
                body,tag = result
                self.validators[a[0]] = tag
                self.final_urls[a[0]] = url
                self.ranges[a[0]] = self.ranges.get(a[0],0)+1
                if stage==0:
                    need(body[:6]==b'\x93NUMPY' and tuple(body[6:]) in ((1,0),(2,0)),
                         'NPYv1/v2 magic only; stop before further bytes')
                    self.widths[a[0]]=2 if body[6]==1 else 4
                elif stage==1:
                    size=int.from_bytes(body,'little')
                    need(0<size<=4096 and 8+self.widths[a[0]]+size<=a[1],
                         'bounded header size before request')
                    self.header_lengths[a[0]]=size
                self.stages[a[0]]=stage+1
                return body
        except BaseException as exc:
            self.failed = True
            detail = diagnostic(exc)
            if not self.errors or self.errors[-1] != detail:
                self.errors.append(detail)
            raise

    def receipt(self):
        return dict(schema='consensus35-primitive-header-range-transport-v1', phase=self.phase,
            status='FAILED' if self.failed else 'RANGES_ONLY_NO_DIRECTORY_CLAIM',
            whole_original_hashes_verified=False, inventory_files=35,
            inventory_advertised_bytes=sum(a[1] for a in PINNED),
            transactions=self.transactions, redirects=self.redirects,
            logical_ranges=self.range_attempts, logical_range_requested_bytes=self.logical_range_requested_bytes,
            complete_header_objects=sum(x==3 for x in self.stages.values()),
            successful_ranges=sum(self.ranges.values()), files_with_successful_ranges=len(self.ranges),
            etags={str(k):v for k,v in sorted(self.validators.items())},
            body_returned_bytes=self.body_returned, body_written_bytes=self.body_written,
            raw_metadata_written_bytes=self.metadata_written, raw_metadata_records=self.raw_records,
            descriptors_written=self.successful_descriptors, descriptors_failed=self.failed_descriptors,
            unresolved_originals=[dict(file=k,offset=v[0],bytes=len(v[1]))
                                  for k,v in self.unpersisted_originals.items()],
            elapsed_seconds=self.clock()-self.started, limits=self.limits, errors=self.errors,
            retention_partitions=dict(range_bodies=self.limits['body_bytes'],
                raw_metadata=RAW_TOTAL_CAP,
                prospective_total=self.limits['body_bytes']+RAW_TOTAL_CAP),
            caveats=['Ranges alone establish no whole-archive MD5, member contents, directory or biological conclusion.',
                     'Content-Length parsed-body counts are not wire byte counts; no socket overrun proof.',
                     'Rejected/redirect bodies intentionally unread; consumed header prefixes retained.',
                     'Header cap4096 and URL cap2048 are refusal limits, not observed provider fit.',
                     'Prospective exact owner must enforce separately selected complete lifetime/resources; this transport is not an owner.',
                     'Only declared NPY magic/length/header ranges are requested; malformed data can leave unknown semantic prefix bytes, never interpreted numeric values.',
                     'Disk failure or external termination can leave incomplete custody; never auto-retry.'])

    def close(self):
        need(not self.closed, 'close already attempted')
        self.closed = True
        try:
            self._metadata('TRANSPORT_REPORT.json', self.receipt())
        except BaseException as exc:
            self.failed = True
            self.errors.append(diagnostic(exc))
            raise

    def __enter__(self):
        return self

    def __exit__(self, typ, exc, tb):
        self.close()
        return False
