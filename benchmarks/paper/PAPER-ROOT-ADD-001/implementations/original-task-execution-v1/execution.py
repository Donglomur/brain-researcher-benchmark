"""Private original-task collection/recovery. No native call occurs on import.

The executable mode is explicitly admitted and selected; this module does not
choose a practical provider or narrow the selected original scientific scope.
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import struct
import sys
import time

import numpy as np

HERE = Path(__file__).resolve().parent
JOIN_SHA = '1b4878289929fec97f6b89d99f7fcb3edf995142cd3966da8aab47c75faf3d0a'
CACHE_SHA = 'c122ff56a48627258f3641bed6458b7dde3603c63ad0ce57ee3199b48a3efa79'
REQUEST = struct.Struct('<8sQ32s32sQ')
LENGTH = struct.Struct('<Q')
assert REQUEST.size == 88
MAX_META = 8192
MAX_ROWS = 144111


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


def finite_json(value):
    if isinstance(value,dict):
        return {str(k):finite_json(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):
        return [finite_json(v) for v in value]
    if isinstance(value,(float,np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value,np.integer):
        return int(value)
    return value


def close_owned(*resources):
    """Attempt every owned cleanup even if an earlier close fails."""
    errors=[]
    for resource in resources:
        if resource is not None:
            try:
                resource.close()
            except BaseException as exc:
                errors.append(exc)
    if errors:
        raise RuntimeError('Owned cleanup failure; all close operations attempted') from errors[0]


def integer(value, low=0, high=2**63-1):
    return type(value) is int and low <= value <= high


def load_pinned(name, folder, filename, expected):
    path = HERE.parent / folder / filename
    raw = path.read_bytes()
    need(len(raw) <= 262144 and sha(raw) == expected, 'Exact reviewed private source required')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


J = load_pinned('_language_execution_join_1b487828', 'original-compact-scoring-join-v1', 'join.py', JOIN_SHA)
C = load_pinned('_language_execution_cache_c122ff56', 'original-private-cache-v1', 'cache.py', CACHE_SHA)


def ordinary_root(path, *, fresh=False):
    path = Path(path).absolute()
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'No private path symlinks')
    if fresh:
        path.mkdir(mode=0o700)
    need(path.is_dir(), 'Ordinary private directory required')
    return path


def stamp(info):
    return tuple(getattr(info, k) for k in ('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns'))


class Meter:
    """One nonrefundable logical allowance, admitted before each operation."""
    def __init__(self, limit):
        need(integer(limit, 1), 'Finite positive cumulative allowance')
        self.limit, self.charged = limit, 0

    def charge(self, amount):
        need(integer(amount) and self.charged+amount <= self.limit, 'Cumulative allocation exhausted before operation')
        self.charged += amount


class AuthorityWriter:
    """Two private streams retain exact frozen authorities without repeated maps.

    Qid/time maps stay in the authenticated source store. The unchanged JSON
    authority is reconstructed from canonical base metadata and88B held records.
    """
    def __init__(self, root, run, *, output_limit, working_limit):
        self.root = ordinary_root(root, fresh=True)
        self.run, self.binding = J._run_snapshot(run, working_limit)
        self.meter, self.working = Meter(output_limit), working_limit
        self.streams = {}
        try:
            for name in ('META.bin','REQUESTS.bin'):
                fd = os.open(self.root/name, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
                self.streams[name] = os.fdopen(fd, 'wb', buffering=0)
        except BaseException:
            self.close()
            raise
        self.hashes = {name:hashlib.sha256() for name in self.streams}
        self.sizes = {name:0 for name in self.streams}
        self.jobs = self.requests = 0
        self.trace = hashlib.sha256()
        self.failed = self.finished = False

    def _write(self, name, raw):
        self.meter.charge(len(raw))
        count = self.streams[name].write(raw)
        need(count == len(raw), 'Complete authority write; short write is retained failure')
        self.hashes[name].update(raw); self.sizes[name] += count

    def append(self, job):
        need(not self.failed and not self.finished, 'Unfailed authority writer')
        try:
            a, _, _ = J._job_snapshot(self.run, job, self.working)
            need(self.jobs < self.binding['jobs']
                 and tuple(a['coordinates'][k] for k in J.P.CONTEXT_KEYS) == self.run.contexts[self.jobs],
                 'Canonical original authority order')
            need(self.requests+len(a['requests']) <= self.binding['requests'], 'Original request count before authority write')
            base = {key:value for key,value in a.items() if key != 'requests'}
            raw = encoded({'base':base,'requests':len(a['requests'])})
            need(len(raw) <= MAX_META, 'Bounded private per-job metadata')
            total = LENGTH.size+len(raw)+REQUEST.size*len(a['requests'])
            need(self.meter.charged+total <= self.meter.limit, 'Complete authority frame admitted before any write')
            self._write('META.bin', LENGTH.pack(len(raw))+raw)
            for row in a['requests']:
                self._write('REQUESTS.bin', REQUEST.pack(bytes.fromhex(row['held_f64le']),row['query_rows'],
                    bytes.fromhex(row['request_sha256']),bytes.fromhex(row['bundle_sha256']),row['bundle_bytes']))
            self.trace.update(job.authority_json)
            self.jobs += 1; self.requests += len(a['requests'])
        except BaseException:
            self.failed = True
            raise

    def finish(self):
        need(not self.failed and not self.finished and self.jobs == self.binding['jobs']
             and self.requests == self.binding['requests'], 'Complete frozen authority roster before publication')
        self.close()
        self.finished = True
        return {'schema':'language-durable-frozen-authorities/v1','run_binding_sha256':sha(self.run.binding_json),
                'jobs':self.jobs,'requests':self.requests,'ordered_authority_sha256':self.trace.hexdigest(),
                'files':{name:{'bytes':self.sizes[name],'sha256':self.hashes[name].hexdigest()} for name in self.sizes},
                'output_bytes_charged':self.meter.charged,'maps_recovered_from_authenticated_store':True}

    def close(self):
        errors=[]
        for name, stream in getattr(self, 'streams', {}).items():
            if not stream.closed:
                try:
                    stream.close()
                except BaseException as exc:
                    errors.append(exc)
                try:
                    os.chmod(self.root/name,0o400)
                except BaseException as exc:
                    errors.append(exc)
        if errors:
            raise RuntimeError('Authority writer cleanup failed; every stream attempted') from errors[0]


class AuthorityReader:
    """Stream authenticated authority frames; no target exposure or bundle replay."""
    def __init__(self, root, run, receipt, *, receipt_sha256, read_limit, working_limit):
        self.root = ordinary_root(root)
        self.run,self.binding = J._run_snapshot(run,working_limit)
        need(type(receipt) is dict and sha(encoded(receipt)) == receipt_sha256,
             'Externally pinned exact authority receipt')
        need(receipt.get('schema') == 'language-durable-frozen-authorities/v1'
             and receipt.get('run_binding_sha256') == sha(run.binding_json)
             and receipt.get('jobs') == self.binding['jobs'] and receipt.get('requests') == self.binding['requests']
             and receipt.get('maps_recovered_from_authenticated_store') is True
             and set(receipt.get('files',{})) == {'META.bin','REQUESTS.bin'}, 'Complete authority receipt binding')
        self.receipt = J.P.parse(encoded(receipt))
        self.working,self.meter = working_limit,Meter(read_limit)
        self.streams,self.stamps = {},{}
        self.jobs = self.requests = 0
        self.failed = self.finished = False
        self.trace = hashlib.sha256()
        try:
            for name in ('META.bin','REQUESTS.bin'):
                entry = self.receipt['files'][name]
                need(set(entry) == {'bytes','sha256'} and integer(entry['bytes'],1), 'Bounded authority file receipt')
                J.P.digest(entry['sha256'])
                maximum = self.binding['jobs']*(MAX_META+8) if name == 'META.bin' else self.binding['requests']*REQUEST.size
                need(entry['bytes'] <= maximum, 'Exact aggregate authority upper bound before open')
                self.meter.charge(entry['bytes']+1)
                path = self.root/name
                fd = os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
                stream = os.fdopen(fd,'rb',buffering=0)
                self.streams[name] = stream
                before = os.fstat(fd)
                need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_mode & 0o222 == 0
                     and before.st_size == entry['bytes'], 'Ordinary readonly exact authority stream')
                h = hashlib.sha256(); remaining = entry['bytes']
                while remaining:
                    raw = stream.read(min(65536,remaining))
                    need(raw, 'No truncated authority stream')
                    h.update(raw); remaining -= len(raw)
                need(stream.read(1) == b'' and h.hexdigest() == entry['sha256'], 'Full authority stream authentication')
                need(stamp(before) == stamp(os.fstat(fd)) == stamp(path.lstat()), 'Stable authority authentication')
                self.stamps[name] = stamp(before)
                stream.seek(0)
        except BaseException:
            self.failed = True; self.close(); raise

    def _read(self,name,size):
        self.meter.charge(size)
        stream = self.streams[name]
        raw = stream.read(size)
        need(len(raw) == size, 'Exact authority frame read')
        return raw

    def _stable(self):
        # Trusted immutable host: check the two owned descriptors once per job,
        # not two stat calls per88B held record. Full hashes were authenticated
        # before recovery and the complete reconstructed authority trace closes.
        for name,stream in self.streams.items():
            need(stamp(os.fstat(stream.fileno())) == self.stamps[name]
                 and stamp((self.root/name).lstat()) == self.stamps[name], 'Authenticated authority identity unchanged')

    def next_job(self, *, qid, time_indices):
        need(not self.failed and not self.finished and self.jobs < self.binding['jobs'], 'Next original authority frame')
        try:
            self._stable()
            length = LENGTH.unpack(self._read('META.bin',LENGTH.size))[0]
            need(1 <= length <= MAX_META, 'Metadata extent before parsing')
            raw = self._read('META.bin',length)
            frame = J.P.parse(raw)
            need(type(frame) is dict and set(frame) == {'base','requests'} and encoded(frame) == raw
                 and type(frame['base']) is dict and 'requests' not in frame['base']
                 and integer(frame['requests'],2,MAX_ROWS)
                 and self.requests+frame['requests'] <= self.binding['requests'], 'Bounded complete authority frame')
            need(frame['requests']*2048+MAX_META*4+8*1024**2 <= self.working, 'Authority reconstruction workspace')
            need(type(qid) is np.ndarray and type(time_indices) is np.ndarray
                 and qid.dtype == np.dtype('<f8') and time_indices.dtype == np.dtype('<i8')
                 and qid.shape == time_indices.shape and qid.ndim == 1 and 2 <= len(qid) <= MAX_ROWS,
                 'Primitive source maps before copying')
            requests = []
            request_raw = self._read('REQUESTS.bin',REQUEST.size*frame['requests'])
            for held,query,request,bundle,size in REQUEST.iter_unpack(request_raw):
                requests.append({'held_f64le':held.hex(),'query_rows':query,'request_sha256':request.hex(),
                                 'bundle_sha256':bundle.hex(),'bundle_bytes':size})
            frame['base']['requests'] = requests
            job = J.FrozenJob(encoded(frame['base']),qid.tobytes(order='C'),time_indices.tobytes(order='C'))
            authority,_,_ = J._job_snapshot(self.run,job,self.working)
            need(tuple(authority['coordinates'][key] for key in J.P.CONTEXT_KEYS) == self.run.contexts[self.jobs],
                 'Canonical authority recovery order')
            self._stable()
            self.jobs += 1; self.requests += len(requests); self.trace.update(job.authority_json)
            return job
        except BaseException:
            self.failed = True; raise

    def finish(self):
        need(not self.failed and not self.finished and self.jobs == self.binding['jobs']
             and self.requests == self.binding['requests']
             and self.trace.hexdigest() == self.receipt['ordered_authority_sha256'], 'Complete exact frozen authority recovery')
        for name,stream in self.streams.items():
            self.meter.charge(1)
            need(stream.read(1) == b'' and stamp(os.fstat(stream.fileno())) == self.stamps[name], 'No authority suffix or mutation')
        self._stable()
        self.finished = True
        return {'jobs':self.jobs,'requests':self.requests,'read_bytes_charged':self.meter.charged,
                'exact_authority_recovered':True,'scientific_qualification':False}

    def close(self):
        errors=[]
        for stream in getattr(self,'streams',{}).values():
            if not stream.closed:
                try:
                    stream.close()
                except BaseException as exc:
                    errors.append(exc)
        if errors:
            raise RuntimeError('Authority reader cleanup failed; every stream attempted') from errors[0]


LIMIT_KEYS = {'working_bytes','cache_working_bytes','cache_read_bytes','cache_payload_bytes','cache_metadata_bytes',
              'cache_entries','bundle_bytes','frozen_bundle_bytes','dispatched_bundle_bytes','packed_output_bytes',
              'authority_output_bytes','authority_read_bytes','packed_read_bytes','receipt_output_bytes',
              'result_output_bytes','wall_seconds'}


def limits_snapshot(limits):
    need(type(limits) is dict and set(limits) == LIMIT_KEYS
         and all(integer(v,1) for v in limits.values()), 'Exact finite original execution allocations')
    need(limits['working_bytes'] <= 1024**3 and limits['cache_working_bytes'] <= 1024**3,
         'Existing component working ceilings remain unchanged')
    need(limits['bundle_bytes'] <= J.B.MAX_BUNDLE_BYTES, 'Existing compact bundle ceiling')
    return dict(limits)


def save_json(root,name,value,meter):
    raw = encoded(value)
    need(len(raw) <= 4*1024**2 and type(name) is str and '/' not in name and name.endswith('.json'), 'Bounded named receipt')
    meter.charge(len(raw))
    path = root/name
    with path.open('xb') as stream:
        os.chmod(path,0o600)
        need(stream.write(raw) == len(raw), 'Complete receipt write')
    os.chmod(path,0o400)
    return {'bytes':len(raw),'sha256':sha(raw)}


def collect(reader, provider, run, output_root, *, limits, clock=time.monotonic):
    """Concrete canonical store->privatecache->provider->packed collection route.

    reader/provider are trusted operator objects. Production CLI must construct
    only the pinned implementations after exact external admission. Generated
    controls inject a fake provider and never imply native isolation.
    """
    cap = limits_snapshot(limits)
    root = ordinary_root(output_root,fresh=True)
    receipts = Meter(cap['receipt_output_bytes'])
    freeze_bytes,dispatch_bytes,cache_reads = Meter(cap['frozen_bundle_bytes']),Meter(cap['dispatched_bundle_bytes']),0
    started = clock(); need(type(started) in (float,int) and np.isfinite(started),'Finite monotonic clock')
    deadline = started+cap['wall_seconds']
    def live():
        now = clock(); need(np.isfinite(now) and started <= now <= deadline,'Whole campaign deadline; no reset per callback')
    writer = authority = None
    history = []
    jobs = requests = 0
    try:
        need(reader.store_sha256 == J._binding(run)['store_sha256'], 'Frozen source store before provider use')
        save_json(root,'RUN.json',J.P.parse(run.binding_json),receipts)
        writer = J.CompactWriter(root/'packed',run,output_limit=cap['packed_output_bytes'],
                                 working_limit=cap['working_bytes'],byte_limit=cap['bundle_bytes'])
        authority = AuthorityWriter(root/'authorities',run,output_limit=cap['authority_output_bytes'],working_limit=cap['working_bytes'])
        for session in reader.iter_sessions():
            live()
            store = C.FileStore(session.root,session.specs,read_limit=cap['cache_read_bytes']-cache_reads,
                                working_limit=cap['cache_working_bytes'],max_objects=len(session.specs))
            cache = C.BundleCache(store,payload_limit=cap['cache_payload_bytes'],entry_limit=cap['cache_entries'],
                                  metadata_limit=cap['cache_metadata_bytes'],bundle_byte_limit=cap['bundle_bytes'])
            try:
                for item in session.iter_jobs(include_targets=False):
                    live()
                    need('targets' not in item, 'Collection reader excludes full private target matrix')
                    job = item['view_job']
                    def bundle(held):
                        live(); raw = cache.get(job,held); freeze_bytes.charge(len(raw)); return raw
                    frozen = J.freeze_job(run,context=item['context'],qid=item['qid'],time_indices=item['time_indices'],
                        outputs=job.output_columns,support_class_sha256=item['support_class_sha256'],
                        target_sha256=item['target_sha256'],feature=item['feature'],bundle_for_held=bundle,
                        byte_limit=cap['bundle_bytes'],working_limit=cap['working_bytes'],
                        max_bundle_bytes=cap['frozen_bundle_bytes']-freeze_bytes.charged)
                    authority.append(frozen)
                    writer.begin_job(frozen)
                    handle = provider.prepare_feature(item['feature_path'],item['feature_spec'],rows=len(item['qid']))
                    try:
                        for held in np.unique(item['qid']):
                            live(); raw = cache.get(job,float(held)); dispatch_bytes.charge(len(raw))
                            public = writer.request(raw)
                            prediction,closure = provider.run_request(handle,raw,public)
                            live()
                            writer.accept(request_id=public.public_id,raw_prediction=prediction,closure=closure)
                            requests += 1
                    finally:
                        provider.release_feature(handle)
                    writer.finish_job(); jobs += 1
            finally:
                cache_reads += store.read_charged
                history.append({'session':session.session,'files':store.private_metrics(),'bundles':cache.private_metrics()})
                session.close()
                del cache,store
        live()
        provider_receipt = provider.finish()
        joined = writer.finish(); authorities = authority.finish()
        close_owned(provider,writer,authority,reader)
        need(freeze_bytes.charged == dispatch_bytes.charged == joined['frozen_bundle_bytes'], 'Complete global two-pass bundle accounting')
        result = {'schema':'language-original-task-collection/v1','scope':J._binding(run)['scope'],
                  'run_binding_sha256':sha(run.binding_json),'jobs':jobs,'software_callbacks':requests,
                  'join':joined,'authorities':authorities,'provider':provider_receipt,'session_caches':history,
                  'frozen_bundle_bytes':freeze_bytes.charged,'dispatched_bundle_bytes':dispatch_bytes.charged,
                  'cache_read_bytes_charged':cache_reads,'elapsed_seconds':clock()-started,
                  'protected_execution_qualified':False,'scientific_qualification':False}
        identity = save_json(root,'COLLECTION.json',result,receipts)
        return result,identity
    except BaseException as exc:
        # Preserve partial streams; only a successful full route publishes COLLECTION.
        failure = {'schema':'language-original-task-failure/v1','jobs_completed':jobs,'requests_completed':requests,
                   'error_type':type(exc).__name__,'error':str(exc)[:512],
                   'frozen_bundle_bytes_charged':freeze_bytes.charged,'dispatched_bundle_bytes_charged':dispatch_bytes.charged,
                   'complete':False,'scientific_qualification':False}
        try:
            save_json(root,'FAILURE.json',failure,receipts)
        except BaseException:
            pass
        raise
    finally:
        close_owned(provider,writer,authority,reader)


def write_panel(root,panel,limit,live=lambda:None):
    """Persist all224 original-format arrays with a finite separate allowance."""
    out = ordinary_root(root/'result_llm',fresh=True)
    meter,files = Meter(limit),{}
    J.SOURCE_PANEL.validate_panel(panel)
    for session in J.L.SESSIONS:
        live()
        folder = ordinary_root(out/session,fresh=True)
        for field,name in J.SOURCE_PANEL.SOURCE_FILES.items():
            live()
            value = panel[session][field]
            need(type(name) is str and '/' not in name and name.endswith('.npy'),'Original result basename')
            need(value.nbytes+8192 <= meter.limit-meter.charged,'Result extent admitted before serialization')
            buffer = io.BytesIO(); np.save(buffer,value,allow_pickle=False); raw = buffer.getvalue()
            meter.charge(len(raw))
            with (folder/name).open('xb') as stream:
                os.chmod(folder/name,0o600)
                need(stream.write(raw) == len(raw),'Complete original result write')
            os.chmod(folder/name,0o400)
            files[f'{session}/{name}'] = {'bytes':len(raw),'sha256':sha(raw)}
    need(len(files) == 224,'Every original result array persisted')
    return {'files':files,'output_bytes_charged':meter.charged}


def recover(reader, run, output_root, collection, *, collection_sha256, limits,
            summarize=False, permutation_budget=0, expected_numpy_version=None, expected_scipy_version=None,
            clock=time.monotonic):
    """Independent saved-output traversal; no bundle reconstruction/candidate calls."""
    cap = limits_snapshot(limits)
    started=clock()
    need(type(started) in (float,int) and np.isfinite(started),'Finite recovery monotonic clock')
    deadline=started+cap['wall_seconds']
    def live():
        now=clock()
        need(np.isfinite(now) and started<=now<=deadline,'Whole recovery deadline; indivisible numeric work also needs external hard timeout')
    root = ordinary_root(output_root)
    need(type(collection) is dict and sha(encoded(collection)) == collection_sha256
         and collection.get('schema') == 'language-original-task-collection/v1'
         and collection.get('run_binding_sha256') == sha(run.binding_json)
         and reader.store_sha256 == J._binding(run)['store_sha256'], 'Exact complete source/collection receipt binding')
    authorities = packed = None
    full = J._binding(run)['scope'] == 'original_full_source'
    need(full or summarize is False, 'Generated controls cannot invoke the original full scientific summary')
    generated = []
    try:
        live()
        authorities = AuthorityReader(root/'authorities',run,collection['authorities'],
            receipt_sha256=sha(encoded(collection['authorities'])),read_limit=cap['authority_read_bytes'],working_limit=cap['working_bytes'])
        panel = J.OriginalPanel(run,working_limit=cap['working_bytes']) if full else None
        packed = J.CompactReader(root/'packed',run,collection['join'],receipt_sha256=sha(encoded(collection['join'])),
                                read_limit=cap['packed_read_bytes'],working_limit=cap['working_bytes'])
        for session in reader.iter_sessions():
            live()
            try:
                for item in session.iter_jobs(include_targets=True):
                    live()
                    frozen = authorities.next_job(qid=item['qid'],time_indices=item['time_indices'])
                    a = J.P.parse(frozen.authority_json)
                    need(a['context'] == item['context'] and a['target_sha256'] == item['target_sha256']
                         and a['support_class_sha256'] == item['support_class_sha256'] and a['feature'] == item['feature'],
                         'Recovered authority joins the same original store row/feature/target identity')
                    score = packed.score_job(frozen,item['targets'])
                    live()
                    if full:
                        panel.add(frozen,score['correlations'])
                    else:
                        need(len(generated) < 8,'Only bounded tiny generated recovery fixtures')
                        generated.append({'context':score['context'],'correlations':score['correlations'].tolist()})
            finally:
                session.close()
        authority_receipt,packed_receipt = authorities.finish(),packed.finish()
        live()
        if full:
            if summarize:
                values = panel.summarize(reader.weights,permutation_budget=permutation_budget,
                    expected_numpy_version=expected_numpy_version,expected_scipy_version=expected_scipy_version)
                live()
            else:
                values = {'source_array_shapes':{s:{f:list(a.shape) for f,a in fields.items()} for s,fields in panel.finish().items()},
                          'full_inference_executed':False}
            arrays = write_panel(root,panel.panel,cap['result_output_bytes'],live)
        else:
            values = {'generated_scores':generated,'full_inference_executed':False}
            arrays = None
        result = {'schema':'language-original-task-recovery/v1','scope':J._binding(run)['scope'],
                  'collection_sha256':collection_sha256,'authorities':authority_receipt,'packed':packed_receipt,
                  'result':values,'original_result_arrays':arrays,
                  'protected_execution_qualified':False,'scientific_qualification':False}
        close_owned(authorities,packed,reader)
        live()
        result=finite_json(result)
        identity = save_json(root,'RECOVERY.json',result,Meter(cap['receipt_output_bytes']))
        return result,identity
    finally:
        close_owned(authorities,packed,reader)
