"""Original Figure3b selected compact/packed/original-score join.

This module does not execute a candidate or attest a sandbox. The operator owns
prepared-source and target provenance, immutable feature assertions and provider
lifecycle verification. Closure JSON is attributed evidence, never OS proof.
This additive successor preserves the full join's row/closure/scoring machinery
but binds exactly42 selected source jobs and5685 software requests. These are not
API/process counts. The full224-array reproduction component remains unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct
import sys
import types

import numpy as np

HERE = Path(__file__).resolve().parent
PINS = {
    'bundle': ('../original-compact-bundles-v1/bundle.py', 'a54bdb02d3d9d0be74bafaab3503175a6eaf867ee5299b97c5983bc2ea30a8a7'),
    'packed': ('../original-protected-layout-v1/packed.py', '9e0f651ddd5ca14211a310628e986c40dd5929a643b8199ad7ece4a0e5e3b3d0'),
    'layout': ('../original-protected-layout-v1/layout.py', '91921778d13071b4a8850dbda52b8ceaa581e6b2597382558110ce1692857aa9'),
    'inputs': ('../original-inputs-v1/inputs.py', '9a363fb93293cfc5f9fc9caad9f61a708e42618dc0afc9a7a48d9f9d7f41436a'),
    'prediction': ('../original-inputs-v1/prediction.py', '53476538f93cecea0c2bbcc1c1ff4da4d17ce34ee57fa56d69ae0d48003690e4'),
    'endpoint': ('../original-figure3b-improvement-v1/improvement.py', 'bbf81e3f3f8a82edfbeb8005de6b52d335e21d674e3798238a5f8a14555c3afa'),
    'parent_join': ('../original-compact-scoring-join-v1/join.py', '1b4878289929fec97f6b89d99f7fcb3edf995142cd3966da8aab47c75faf3d0a'),
}
FULL_JOBS, FULL_REQUESTS = 42, 5685
ORIGINAL_SCOPE = 'original_figure3b_improvement'
MAX_ROWS, MAX_COLUMNS = 144111, 82
MAX_WORKING = 1024**3
SOURCE_CONTEXT_KEYS = ('session', 'field', 'family', 'layer', 'lag_index', 'lag_bins')


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


def _load(name, aliases=None):
    relative, expected = PINS[name]
    path = HERE/relative
    with path.open('rb') as stream:
        raw = stream.read(131073)
    need(len(raw) <= 131072 and sha(raw) == expected, 'Exact reviewed source dependency: '+name)
    module = types.ModuleType('_language_compact_join_'+name+'_'+expected[:12])
    module.__file__, module.__package__ = str(path), ''
    sys.modules[module.__name__] = module
    saved = {}
    try:
        for key, value in (aliases or {}).items():
            saved[key] = sys.modules.get(key)
            sys.modules[key] = value
        exec(compile(raw, str(path), 'exec', dont_inherit=True), module.__dict__)
    finally:
        for key, value in saved.items():
            if value is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = value
    return module


B, P, L = _load('bundle'), _load('packed'), _load('layout')
_INPUTS = _load('inputs')
ORIGINAL = _load('prediction', {'inputs': _INPUTS})
ENDPOINT = _load('endpoint')
FULL_CONTEXT_SHA = sha(b''.join(P.encoded(row) for row in ENDPOINT.coordinates()))
with (HERE/PINS['parent_join'][0]).open('rb') as _parent_source:
    need(sha(_parent_source.read(65537)) == PINS['parent_join'][1], 'Exact unchanged full-join predecessor')
del _parent_source


def _integer(value, low, high):
    return type(value) is int and low <= value <= high


def _work(limit, required):
    need(_integer(limit, 1, MAX_WORKING) and required <= limit, 'Complete finite logical working admission')


def _source_context(context):
    need(type(context) is dict and set(context) == set(SOURCE_CONTEXT_KEYS), 'Exact primitive original context keys')
    for name in SOURCE_CONTEXT_KEYS[:3]:
        need(type(context[name]) is str and 0 < len(context[name]) <= 32, 'Bounded primitive original context')
    need(all(type(context[k]) is int for k in SOURCE_CONTEXT_KEYS[3:]), 'Primitive source layer/lag coordinates')
    need(ENDPOINT.is_selected(context),'Only original Figure3b population/layer5/lag17–19 coordinates')
    return B.V.JobContext(**context)


def _coordinates(context):
    c = _source_context(context)
    fields = [row[0] for row in L.specs()]
    return dict(session_index=L.SESSIONS.index(c.session), field_index=fields.index(c.field),
                layer=c.layer, lag_index=c.lag_index, lag_bins=c.lag_bins)


def _context_from_coordinates(row):
    need(type(row) is dict and set(row) == set(P.CONTEXT_KEYS)
         and all(type(v) is int for v in row.values()), 'Exact source coordinate record')
    need(0 <= row['session_index'] < 14 and 0 <= row['field_index'] < 16, 'Source session/field range')
    field, family, _, _, lags, layers = L.specs()[row['field_index']]
    need(0 <= row['layer'] < layers and 0 <= row['lag_index'] < len(lags)
         and row['lag_bins'] == lags[row['lag_index']], 'Exact source layer and lag, not only broad ranges')
    result = dict(session=L.SESSIONS[row['session_index']], field=field, family=family,
                  layer=row['layer'], lag_index=row['lag_index'], lag_bins=row['lag_bins'])
    need(ENDPOINT.is_selected(result),'Exactly selected Figure3b source coordinate')
    return result


@dataclass(frozen=True)
class FrozenRun:
    binding_json: bytes
    contexts: tuple


def _binding(run):
    need(type(run) is FrozenRun and type(run.binding_json) is bytes and len(run.binding_json) <= 8192,
         'Bounded immutable private run binding')
    value = P.parse(run.binding_json)
    expected = {'schema','scope','store_sha256','candidate_sha256','schedule_sha256',
                'provider_source_sha256','condition','job_context_sha256','jobs','requests','sources'}
    need(type(value) is dict and set(value) == expected and encoded(value) == run.binding_json
         and value['schema'] == 'language-compact-join-run/v1'
         and value['scope'] in (ORIGINAL_SCOPE, 'generated_engineering_control')
         and value['condition'] in ('paper_data','paper_data_author_code'), 'Exact canonical run schema/condition')
    for key in ('store_sha256','candidate_sha256','schedule_sha256','provider_source_sha256','job_context_sha256'):
        P.digest(value[key])
    need(value['sources'] == {k:v[1] for k,v in PINS.items()}, 'Exact unchanged scientific/source-code bindings')
    need(_integer(value['jobs'],1,FULL_JOBS) and _integer(value['requests'],2*value['jobs'],FULL_REQUESTS),
         'Finite complete job/software-callback declarations')
    if value['scope'] == ORIGINAL_SCOPE:
        need((value['jobs'],value['requests'],value['job_context_sha256']) == (FULL_JOBS,FULL_REQUESTS,FULL_CONTEXT_SHA),
             'Complete selected42 source jobs/5685 requests/context order required')
    return value


def _run_snapshot(run, working_limit):
    value = _binding(run)
    _work(working_limit, value['jobs']*2048 + 8*1024**2)
    need(type(run.contexts) is tuple and len(run.contexts) == value['jobs'], 'Bounded immutable complete context roster')
    digest, contexts, prior = hashlib.sha256(), [], None
    for coordinate in run.contexts:
        need(type(coordinate) is tuple and len(coordinate) == 5 and all(type(n) is int for n in coordinate),
             'Primitive immutable job coordinate tuple')
        row = dict(zip(P.CONTEXT_KEYS,coordinate))
        _context_from_coordinates(row)
        order = coordinate[:4]
        need(prior is None or prior < order, 'Canonical source context order without duplicates')
        prior = order
        digest.update(P.encoded(row)); contexts.append(coordinate)
    need(digest.hexdigest() == value['job_context_sha256'], 'Complete frozen context digest')
    return FrozenRun(run.binding_json,tuple(contexts)), value


def make_run(*, store_sha256, candidate_sha256, schedule_sha256, provider_source_sha256,
             condition, working_limit, generated_contexts=None, generated_requests=None):
    """Freeze canonical job coordinates, never a global request or bundle list."""
    original = generated_contexts is None
    if original:
        need(generated_requests is None, 'Original source request count cannot be overridden')
        count, requests = FULL_JOBS, FULL_REQUESTS
        _work(working_limit,count*2048+8*1024**2)
        rows = ENDPOINT.coordinates()
    else:
        need(type(generated_contexts) in (tuple,list) and 0 < len(generated_contexts) <= FULL_JOBS,
             'Explicit bounded generated context roster')
        count, requests = len(generated_contexts), generated_requests
        _work(working_limit,count*2048+8*1024**2)
        rows = generated_contexts
    contexts, h = [], hashlib.sha256()
    for row in rows:
        _context_from_coordinates(row)
        contexts.append(tuple(row[k] for k in P.CONTEXT_KEYS)); h.update(P.encoded(row))
    value = dict(schema='language-compact-join-run/v1',
                 scope=ORIGINAL_SCOPE if original else 'generated_engineering_control',
                 store_sha256=store_sha256,candidate_sha256=candidate_sha256,schedule_sha256=schedule_sha256,
                 provider_source_sha256=provider_source_sha256,condition=condition,
                 job_context_sha256=h.hexdigest(),jobs=count,requests=requests,
                 sources={k:v[1] for k,v in PINS.items()})
    run = FrozenRun(encoded(value),tuple(contexts))
    return _run_snapshot(run,working_limit)[0]


@dataclass(frozen=True)
class FrozenJob:
    authority_json: bytes
    qid_bytes: bytes
    time_bytes: bytes


def _feature(feature, rows):
    need(type(feature) is dict and set(feature) == {'sha256','bytes','fortran_order'}, 'One immutable-feature assertion')
    P.digest(feature['sha256'])
    need(_integer(feature['bytes'],rows*30*8+1,rows*30*8+8192) and type(feature['fortran_order']) is bool,
         'Bounded one-feature primitive NPY identity')
    return dict(feature)


def _maps(qid,times,working_limit,base=0):
    need(type(qid) is np.ndarray and type(times) is np.ndarray and qid.dtype == np.dtype('<f8')
         and times.dtype == np.dtype('<i8') and qid.ndim == times.ndim == 1
         and qid.shape == times.shape and 2 <= len(qid) <= MAX_ROWS, 'Exact primitive original row maps')
    _work(working_limit,base+512*len(qid)+1024**2)
    B._maps(qid,times,len(qid))
    labels = np.unique(qid)
    need(len(labels) >= 2, 'No empty/one-group source test bypass')
    return labels


def freeze_job(run, *, context, qid, time_indices, outputs, support_class_sha256, feature,
               target_sha256, bundle_for_held, byte_limit, working_limit, max_bundle_bytes):
    """Stream one bundle at a time; retain only one job's private ID roster.

    Callback-return bytes are conservatively charged before validation. Provider
    transport, reconstruction and later dispatch rereads require separate meters.
    The callback and supplied feature/source assertions are operator-private.
    """
    binding = _binding(run)
    run = FrozenRun(run.binding_json,())
    c = _source_context(context)
    context = {k:getattr(c,k) for k in SOURCE_CONTEXT_KEYS}
    need(_integer(outputs,1,MAX_COLUMNS) and (c.field == 'unit' or outputs == 1), 'Original target width')
    need(outputs == 1,'Original selected endpoint has exactly one population response')
    P.digest(support_class_sha256); P.digest(target_sha256)
    need(callable(bundle_for_held) and _integer(max_bundle_bytes,1,2**63-1), 'Finite cumulative bundle-return admission')
    B._limits(byte_limit,working_limit)
    labels = _maps(qid,time_indices,working_limit)
    base = 512*len(qid)+2048*len(labels)+1024**2
    _work(working_limit,base+8*byte_limit)
    feature = _feature(feature,len(qid))
    qbytes,tbytes = qid.tobytes(),time_indices.tobytes()
    q = np.frombuffer(qbytes,dtype='<f8'); t = np.frombuffer(tbytes,dtype='<i8')
    roster, charged = [], 0
    for label in labels:
        raw = bundle_for_held(float(label))
        need(type(raw) is bytes and len(raw) <= byte_limit, 'Bounded immutable callback bundle')
        charged += len(raw)
        need(charged <= max_bundle_bytes, 'Cumulative bundle bytes before parsing')
        decoded = B.decode_bundle(raw,byte_limit=byte_limit,working_limit=working_limit-base)
        need(decoded.qid.tobytes() == qbytes and decoded.time_indices.tobytes() == tbytes
             and decoded.output_columns == outputs and struct.pack('<d',decoded.held_qid) == struct.pack('<d',float(label)),
             'Bundle exact source maps/output/ordered held-qid join')
        descriptor = B.make_descriptor(raw,c,feature_sha256=feature['sha256'],feature_bytes=feature['bytes'],
            feature_fortran_order=feature['fortran_order'],byte_limit=byte_limit,working_limit=working_limit-base)
        roster.append({'held_f64le':struct.pack('<d',float(label)).hex(),
                       'query_rows':len(decoded.query_positions),'request_sha256':descriptor.public_id,
                       'bundle_sha256':sha(raw),'bundle_bytes':len(raw)})
    value = {'schema':'language-compact-frozen-job/v1','run_binding_sha256':sha(run.binding_json),
             'context':dict(context),'coordinates':_coordinates(context),'rows':len(q),'outputs':outputs,
             'support_class_sha256':support_class_sha256,'feature':feature,
             'target_sha256':target_sha256,
             'qid_sha256':sha(qbytes),'time_sha256':sha(tbytes),'requests':roster,
             'bundle_bytes_charged':charged,'scope':binding['scope']}
    raw = encoded(value)
    need(len(raw) <= 1024*len(labels)+8192, 'Bounded one-job authority metadata')
    result = FrozenJob(raw,qbytes,tbytes)
    _job_snapshot(run,result,working_limit)
    return result


def _job_snapshot(run,job,working_limit):
    binding = _binding(run)
    need(type(job) is FrozenJob and type(job.authority_json) is bytes
         and len(job.authority_json) <= MAX_ROWS*1024+8192
         and type(job.qid_bytes) is bytes and type(job.time_bytes) is bytes
         and len(job.qid_bytes) == len(job.time_bytes) and 16 <= len(job.qid_bytes) <= 8*MAX_ROWS,
         'Bounded immutable private job before parsing')
    _work(working_limit,4*len(job.authority_json)+64*len(job.qid_bytes)+1024**2)
    a = P.parse(job.authority_json)
    need(type(a) is dict and set(a) == {'schema','run_binding_sha256','context','coordinates','rows','outputs',
         'support_class_sha256','feature','target_sha256','qid_sha256','time_sha256','requests','bundle_bytes_charged','scope'}
         and encoded(a) == job.authority_json and a['schema'] == 'language-compact-frozen-job/v1'
         and a['run_binding_sha256'] == sha(run.binding_json) and a['scope'] == binding['scope'],
         'Exact job/run/source binding')
    need(_integer(a['rows'],2,MAX_ROWS) and a['rows']*8 == len(job.qid_bytes)
         and _integer(a['outputs'],1,MAX_COLUMNS), 'Exact frozen geometry')
    c = _source_context(a['context'])
    need(a['coordinates'] == _coordinates(a['context']) and (c.field == 'unit' or a['outputs'] == 1), 'Exact source context/output join')
    need(a['outputs'] == 1,'Exact selected population width')
    _feature(a['feature'],a['rows']); P.digest(a['support_class_sha256']); P.digest(a['target_sha256'])
    need(a['qid_sha256'] == sha(job.qid_bytes) and a['time_sha256'] == sha(job.time_bytes), 'Exact private map identity')
    q,t = np.frombuffer(job.qid_bytes,dtype='<f8'),np.frombuffer(job.time_bytes,dtype='<i8')
    labels = _maps(q,t,working_limit,base=4*len(job.authority_json))
    need(type(a['requests']) is list and len(a['requests']) == len(labels), 'Complete ordered held roster')
    total = 0
    for row,label in zip(a['requests'],labels):
        need(type(row) is dict and set(row) == {'held_f64le','query_rows','request_sha256','bundle_sha256','bundle_bytes'}
             and row['held_f64le'] == struct.pack('<d',float(label)).hex()
             and type(row['query_rows']) is int and row['query_rows'] == int(np.count_nonzero(q == label)),
             'Every original nonempty held request in exact sorted order')
        P.digest(row['request_sha256']); P.digest(row['bundle_sha256'])
        extent = B.HEADER.size+16*len(q)+8*(len(q)-row['query_rows'])*a['outputs']
        need(type(row['bundle_bytes']) is int and row['bundle_bytes'] == extent, 'Exact per-held bundle geometry')
        total += extent
    need(type(a['bundle_bytes_charged']) is int and a['bundle_bytes_charged'] == total, 'Complete one-job bundle accounting')
    need(len({r['request_sha256'] for r in a['requests']}) == len(labels), 'Distinct complete compact request identities')
    return a,q,t


def _packed_bindings(binding):
    return {k:binding[k] for k in ('store_sha256','candidate_sha256','schedule_sha256','job_context_sha256','condition')}


class CompactWriter:
    """Private state machine: freeze -> descriptor -> trusted closure -> raw NPY."""
    def __init__(self,root,run,*,output_limit,working_limit,byte_limit):
        self.run,self.binding = _run_snapshot(run,working_limit)
        B._limits(byte_limit,working_limit)
        self.working,self.byte_limit = working_limit,byte_limit
        self.fixed = self.binding['jobs']*2048+8*1024**2
        self.packed = P.PackedWriter(root,**_packed_bindings(self.binding),
            expected_job_contexts=[dict(zip(P.CONTEXT_KEYS,c)) for c in self.run.contexts],
            expected_jobs=self.binding['jobs'],expected_requests=self.binding['requests'],
            output_limit=output_limit,working_limit=working_limit-self.fixed)
        self.active,self.ready,self.failed,self.finished = None,None,False,False
        self.trace = hashlib.sha256()
        self.dispatched_bundle_bytes = self.frozen_bundle_bytes = 0

    def _live(self):
        need(not self.failed and not self.finished, 'Unfailed unfinished compact collector')

    def _poison(self):
        self.failed = True
        self.packed.failed = True

    def begin_job(self,job):
        self._live()
        try:
            need(self.active is None, 'Finish current source job before another')
            a,q,t = _job_snapshot(self.run,job,self.working-self.fixed)
            extent = a['rows']*a['outputs']*8
            retained = 4*len(job.authority_json)+128*a['rows']+1024**2
            _work(self.working,self.fixed+retained+self.packed.fixed_working+4*extent+512*a['rows']+1024**2)
            self.packed.begin_job(context=a['coordinates'],qid=q,time_indices=t,outputs=a['outputs'],
                support_class_sha256=a['support_class_sha256'],
                expected_request_hashes=tuple(r['request_sha256'] for r in a['requests']))
            job = FrozenJob(job.authority_json,job.qid_bytes,job.time_bytes)
            self.active = (job,a,0)
            self.frozen_bundle_bytes += a['bundle_bytes_charged']
        except BaseException:
            self._poison(); raise

    def request(self,raw_bundle):
        """Revalidate actual dispatched bytes against the pre-frozen compact ID."""
        self._live()
        try:
            need(self.active is not None and self.ready is None, 'One pending original request at a time')
            _,a,index = self.active
            need(index < len(a['requests']), 'No duplicate or extra held request')
            row = a['requests'][index]
            need(type(raw_bundle) is bytes and len(raw_bundle) == row['bundle_bytes'] <= self.byte_limit,
                 'Bounded exact selected bundle before dispatch hashing')
            self.dispatched_bundle_bytes += len(raw_bundle)
            need(sha(raw_bundle) == row['bundle_sha256'], 'Dispatch bytes match frozen permitted bundle')
            retained = self.fixed+self.packed.fixed_working+4*len(self.active[0].authority_json)+128*a['rows']+a['rows']*a['outputs']*8+1024**2
            _work(self.working,retained+4*len(raw_bundle)+64*a['rows']+32768)
            f = a['feature']
            public = B.make_descriptor(raw_bundle,_source_context(a['context']),feature_sha256=f['sha256'],
                feature_bytes=f['bytes'],feature_fortran_order=f['fortran_order'],
                byte_limit=self.byte_limit,working_limit=self.working-retained)
            need(public.public_id == row['request_sha256'], 'Recomputed exact frozen compact ID')
            self.ready = public.public_id
            return public
        except BaseException:
            self._poison(); raise

    def accept(self,*,request_id,raw_prediction,closure):
        self._live()
        try:
            need(self.active is not None and self.ready is not None and type(request_id) is str
                 and request_id == self.ready, 'Only the exact dispatched compact request can return')
            need(type(closure) is dict and closure.get('provider_source_sha256') == self.binding['provider_source_sha256'],
                 'Frozen trusted provider source binding before prediction parsing')
            job,a,index = self.active
            held = struct.unpack('<d',bytes.fromhex(a['requests'][index]['held_f64le']))[0]
            self.packed.accept(held_qid=held,request_sha256=request_id,raw_prediction=raw_prediction,closure=closure)
            self.active,self.ready = (job,a,index+1),None
        except BaseException:
            self._poison(); raise

    def finish_job(self):
        self._live()
        try:
            need(self.active is not None and self.ready is None
                 and self.active[2] == len(self.active[1]['requests']), 'Every original held request closed before job completion')
            result = self.packed.finish_job()
            self.trace.update(self.active[0].authority_json)
            self.active = None
            return result
        except BaseException:
            self._poison(); raise

    def finish(self):
        self._live()
        try:
            need(self.active is None and self.ready is None, 'No incomplete source job/request')
            manifest = self.packed.finish()
            self.finished = True
            return {'schema':'language-compact-scoring-join/v1','run_binding_sha256':sha(self.run.binding_json),
                    'scope':self.binding['scope'],'jobs':manifest['jobs'],'requests':manifest['requests'],
                    'ordered_job_authority_sha256':self.trace.hexdigest(),
                    'packed_manifest_sha256':sha(P.encoded(manifest)),
                    'frozen_bundle_bytes':self.frozen_bundle_bytes,'dispatched_bundle_bytes':self.dispatched_bundle_bytes,
                    'software_callback_requests_not_AI_API_calls':True,
                    'provider_journal_independently_verified':False,'protected_execution_qualified':False,
                    'scientific_qualification':False}
        except BaseException:
            self._poison(); raise

    def close(self):
        try:
            self.packed.close()
        except BaseException:
            self.failed = True; raise


class CompactReader:
    """Authenticate saved private packed files and recover unchanged Pearson scores."""
    def __init__(self,root,run,receipt,*,receipt_sha256,read_limit,working_limit):
        self.run,self.binding = _run_snapshot(run,working_limit)
        expected = {'schema','run_binding_sha256','scope','jobs','requests','ordered_job_authority_sha256',
                    'packed_manifest_sha256','frozen_bundle_bytes','dispatched_bundle_bytes',
                    'software_callback_requests_not_AI_API_calls','provider_journal_independently_verified',
                    'protected_execution_qualified','scientific_qualification'}
        need(type(receipt) is dict and set(receipt) == expected, 'Bounded exact private join receipt keys')
        for name in ('schema','scope'):
            need(type(receipt[name]) is str and 0 < len(receipt[name]) <= 64, 'Primitive bounded receipt label')
        for name in ('run_binding_sha256','ordered_job_authority_sha256','packed_manifest_sha256'):
            P.digest(receipt[name])
        for name in ('jobs','requests','frozen_bundle_bytes','dispatched_bundle_bytes'):
            need(_integer(receipt[name],1,2**63-1), 'Finite primitive receipt count')
        for name in ('software_callback_requests_not_AI_API_calls','provider_journal_independently_verified',
                     'protected_execution_qualified','scientific_qualification'):
            need(type(receipt[name]) is bool, 'Primitive receipt qualification flag')
        P.digest(receipt_sha256)
        raw = encoded(receipt)
        need(len(raw) <= 8192 and sha(raw) == receipt_sha256, 'Frozen exact private compact-join receipt')
        r = self.receipt = P.parse(raw)
        need(set(r) == expected and r['schema'] == 'language-compact-scoring-join/v1'
             and r['run_binding_sha256'] == sha(run.binding_json) and r['scope'] == self.binding['scope']
             and r['jobs'] == self.binding['jobs'] and r['requests'] == self.binding['requests']
             and r['software_callback_requests_not_AI_API_calls'] is True
             and all(r[k] is False for k in ('provider_journal_independently_verified','protected_execution_qualified','scientific_qualification')),
             'Complete frozen private source/receipt scope')
        P.digest(r['ordered_job_authority_sha256']); P.digest(r['packed_manifest_sha256'])
        need(_integer(r['frozen_bundle_bytes'],1,2**63-1)
             and r['dispatched_bundle_bytes'] == r['frozen_bundle_bytes'], 'Complete freeze/dispatch byte accounting')
        self.working,self.fixed = working_limit,self.binding['jobs']*2048+8*1024**2
        self.packed = P.PackedReader(root,manifest_sha256=r['packed_manifest_sha256'],
            bindings=_packed_bindings(self.binding),expected_jobs=self.binding['jobs'],expected_requests=self.binding['requests'],
            read_limit=read_limit,working_limit=working_limit-self.fixed)
        self.trace,self.jobs,self.bundle_bytes,self.failed,self.finished = hashlib.sha256(),0,0,False,False

    def score_job(self,job,targets):
        need(not self.failed and not self.finished, 'Unfailed complete recovery traversal')
        try:
            a,q,t = _job_snapshot(self.run,job,self.working-self.fixed)
            need(self.jobs < self.binding['jobs'] and tuple(a['coordinates'][k] for k in P.CONTEXT_KEYS) == self.run.contexts[self.jobs],
                 'Exact next globally frozen source score job')
            need(type(targets) is np.ndarray and targets.dtype == np.dtype('<f8')
                 and targets.shape == (a['rows'],a['outputs']), 'Complete private original-order float64 target matrix')
            metadata = 4*len(job.authority_json)+128*a['rows']+1024**2
            packed_workspace = 4*(targets.nbytes+len(a['requests'])*P.REQUEST.size)+512*a['rows']+1024**2
            scoring_workspace = 8*targets.nbytes+64*a['rows']+1024**2
            _work(self.working,self.fixed+metadata+max(packed_workspace,scoring_workspace)+4*1024**2)
            target_raw = targets.tobytes(order='C')
            need(sha(target_raw) == a['target_sha256'], 'Exact private frozen target bytes before scoring')
            targets = np.frombuffer(target_raw,dtype='<f8').reshape(targets.shape)
            need(np.isfinite(targets).all(), 'No target dropping or empty-score substitute')
            predictions = self.packed.next_job(qid=q,time_indices=t,expected_context=a['coordinates'],
                expected_request_hashes=tuple(r['request_sha256'] for r in a['requests']),
                support_class_sha256=a['support_class_sha256'])
            values = ORIGINAL.pooled_pearson(targets,predictions)
            self.trace.update(job.authority_json); self.jobs += 1; self.bundle_bytes += a['bundle_bytes_charged']
            return {'context':a['context'],'correlations':values,'predictions':predictions,
                    'scientific_qualification':False}
        except BaseException:
            self.failed = True; self.packed.failed = True; raise

    def finish(self):
        need(not self.failed and not self.finished, 'Unfailed unfinished private reader')
        try:
            need(self.trace.hexdigest() == self.receipt['ordered_job_authority_sha256']
                 and self.bundle_bytes == self.receipt['frozen_bundle_bytes'], 'Exact complete recovered compact authority/accounting trace')
            result = self.packed.finish(); self.finished = True
            return {**result,'compact_request_identity_join_verified':True,
                    'scope':self.binding['scope'],'scientific_qualification':False}
        except BaseException:
            self.failed = True; self.packed.failed = True; raise

    def close(self):
        try:
            self.packed.close()
        except BaseException:
            self.failed = True; raise


class SelectedPanel:
    """All42 selected population correlations, never a224-array/full-paper claim.

    Use the trusted CompactReader output and retain complete recovery evidence.
    This accumulator alone cannot authenticate supplied correlations or a host.
    """
    def __init__(self,run,*,working_limit):
        self.run,self.binding = _run_snapshot(run,working_limit)
        need(self.binding['scope'] == ORIGINAL_SCOPE,'Original selected endpoint refuses generated scope')
        self.fixed = self.binding['jobs']*2048+8*1024**2
        _work(working_limit,self.fixed+42*2048+1024**2)
        self.working,self.next,self.requests = working_limit,0,0
        self.failed,self.finished,self.scores = False,False,[]

    def add(self,job,correlations):
        try:
            need(not self.failed and not self.finished and self.next < FULL_JOBS,'Next unfailed selected coordinate')
            a,_,_ = _job_snapshot(self.run,job,self.working-self.fixed-42*2048)
            need(tuple(a['coordinates'][k] for k in P.CONTEXT_KEYS) == self.run.contexts[self.next],
                 'No dropped/reordered/duplicate selected source score')
            need(self.requests+len(a['requests']) <= FULL_REQUESTS,'Selected held-request count before assignment')
            need(a['outputs'] == 1 and type(correlations) is np.ndarray
                 and correlations.dtype == np.dtype('<f8') and correlations.shape == (1,)
                 and not np.isinf(correlations).any()
                 and np.all(np.abs(correlations[np.isfinite(correlations)]) <= 1),
                 'One exact population Pearson; undefined remains NaN')
            value=float(correlations[0])
            self.scores.append({'context':dict(a['context']), 'pearson_r':None if np.isnan(value) else value})
            self.next += 1;self.requests += len(a['requests'])
        except BaseException:
            self.failed = True
            raise

    def finish(self,*,source_support_sha256,prediction_run_sha256):
        try:
            need(not self.failed and not self.finished and self.next == FULL_JOBS
                 and self.requests == FULL_REQUESTS,'All42 selected scores and5685 held requests required')
            P.digest(source_support_sha256);P.digest(prediction_run_sha256)
            packet={'schema':'language-original-figure3b-scores/v1','role':'candidate',
                    'selection_sha256':sha(ENDPOINT.encoded(ENDPOINT.selection())),
                    'source_support_sha256':source_support_sha256,'prediction_run_sha256':prediction_run_sha256,
                    'scores':P.parse(encoded(self.scores)),'execution_qualified':False}
            ENDPOINT._packet(packet,'candidate')
            self.finished=True
            return packet
        except BaseException:
            self.failed=True
            raise
