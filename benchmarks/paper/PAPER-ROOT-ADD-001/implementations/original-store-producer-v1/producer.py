"""Bounded original-language private store production, never candidate execution.

Original preparation is an explicit function requiring a frozen operator
admission. Generated prefix controls are separately marked and cannot publish
an original-complete store. Imports read pinned Python source only.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
import json
import math
import os
from pathlib import Path
import stat
import sys
import types
import uuid

import numpy as np

HERE = Path(__file__).resolve().parent
PINS = {
    'cache': ('original-private-cache-v1/cache.py', 'c122ff56a48627258f3641bed6458b7dde3603c63ad0ce57ee3199b48a3efa79'),
    'layout': ('original-protected-layout-v1/layout.py', '91921778d13071b4a8850dbda52b8ceaa581e6b2597382558110ce1692857aa9'),
    'inputs': ('original-inputs-v1/inputs.py', '9a363fb93293cfc5f9fc9caad9f61a708e42618dc0afc9a7a48d9f9d7f41436a'),
    'prediction': ('original-inputs-v1/prediction.py', '53476538f93cecea0c2bbcc1c1ff4da4d17ce34ee57fa56d69ae0d48003690e4'),
}
CENSUS_PIN = {'bytes':2026854, 'sha256':'3d2d46bbc6534b282f97d29c51b1961c8d284cf7a9894839fb851550b7549e37'}
PREPARATION_PIN = {'bytes':87379, 'sha256':'562f030780252caa93f51f4aac2a8fb766df0654513ca27a9f0f5e74aaee2578'}
GEOMETRY_PIN = {'bytes':58852, 'sha256':'3b9466d243a86fec32b99a6bf71816c90bd54ef45a292f3e475adce5eeb8e1e7'}
MAX_WORK = 4*1024**3
MAX_META = 64*1024**2
INDEX_CAPS = {'OBJECTS.jsonl':512, 'FEATURES.jsonl':640, 'JOBS.jsonl':512}
ORIGINAL_COUNTS = {'sessions':14,'jobs':58926,'software_callbacks':6776076,
                   'features':12516,'response_classes':1764,'response_shards':202407,
                   'candidate_objects':218451,'array_files':220243,'result_arrays_expected':224}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def integer(n, low=0, high=2**63-1):
    return type(n) is int and low <= n <= high


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',',':'), allow_nan=False)+'\n').encode()


def pin(raw):
    return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def _load(name, aliases=None):
    relative, digest = PINS[name]
    path = (HERE.parent/relative).resolve()
    with path.open('rb') as stream:
        raw = stream.read(131073)
    need(len(raw) <= 131072 and pin(raw)['sha256'] == digest, 'Pinned source dependency: '+name)
    module_name = '_language_private_cache_c122ff56' if name == 'cache' else '_language_store_'+name+'_'+digest[:12]
    if module_name in sys.modules:
        module = sys.modules[module_name]
        need(type(module) is types.ModuleType and module.__file__ == str(path)
             and getattr(module,'_authenticated_source_sha256',None) == digest, 'Conflicting trusted source module')
        return module
    module = types.ModuleType(module_name)
    module.__file__,module.__package__ = str(path),''
    sys.modules[module_name] = module
    prior = {}
    try:
        for key,value in (aliases or {}).items():
            prior[key] = sys.modules.get(key); sys.modules[key] = value
        exec(compile(raw,str(path),'exec',dont_inherit=True),module.__dict__)
        module._authenticated_source_sha256 = digest
    except BaseException:
        sys.modules.pop(module_name,None)
        raise
    finally:
        for key,value in prior.items():
            if value is None:
                sys.modules.pop(key,None)
            else:
                sys.modules[key] = value
    return module


C,L,I = _load('cache'),_load('layout'),_load('inputs')
O = _load('prediction',{'inputs':I})
V = C.V


def array_sha(value):
    need(type(value) is np.ndarray and value.dtype.str in ('<f8','<i8'), 'Primitive source array identity')
    return hashlib.sha256(value.tobytes(order='C')).hexdigest()


def read_metadata(path, expected):
    path = Path(path).absolute()
    need(not any(p.is_symlink() for p in (path,*path.parents)), 'No metadata symlink')
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size == expected['bytes'], 'Exact metadata extent')
    with path.open('rb') as stream:
        raw = stream.read(expected['bytes']+1)
    need(pin(raw) == expected, 'Frozen metadata SHA/extent')
    return raw


@dataclass(frozen=True)
class StorePlan:
    census_raw: bytes
    geometry_raw: bytes
    preparation_raw: bytes
    scope: str
    generated_job_limit: int | None


def _plan(plan, working_limit):
    need(type(plan) is StorePlan and integer(working_limit,1,MAX_WORK), 'Typed finite store plan')
    need(type(plan.census_raw) is bytes and len(plan.census_raw) <= 2097152
         and type(plan.geometry_raw) is bytes and len(plan.geometry_raw) <= 131072
         and type(plan.preparation_raw) is bytes and len(plan.preparation_raw) <= 262144,
         'Bounded immutable source metadata before parsing')
    need(8*(len(plan.census_raw)+len(plan.geometry_raw)+len(plan.preparation_raw))+8*1024**2 <= working_limit,
         'Complete metadata parse admission')
    original = plan.scope == 'original_full_source'
    need(original or plan.scope == 'generated_prefix_control', 'Explicit original or generated-prefix scope')
    if original:
        need(plan.generated_job_limit is None and pin(plan.census_raw) == CENSUS_PIN
             and pin(plan.geometry_raw) == GEOMETRY_PIN and pin(plan.preparation_raw) == PREPARATION_PIN,
             'Exact original census, geometry and Stage B preparation')
    else:
        need(integer(plan.generated_job_limit,1,4209), 'Explicit bounded generated prefix, never original completion')
    census,geometry,preparation = (L.parse(raw) for raw in (plan.census_raw,plan.geometry_raw,plan.preparation_raw))
    layout = L.plan_layout(census,geometry,require_full_roster=original)
    need(type(preparation) is dict and type(preparation.get('sessions')) is list
         and [r['session'] for r in preparation['sessions']] == [r['id'] for r in geometry['sessions']],
         'Exact prepared-source session roster')
    if original:
        need(preparation['schema'] == 'language-original-input-preparation/v1'
             and preparation['models_fitted'] == 0 and preparation['scientific_qualification'] is False,
             'Authenticated preparation, not a fitted scientific result')
        weights = preparation['population_weights']
        need([r['session'] for r in weights['rows']] == list(L.SESSIONS)
             and sum(r['count'] for r in weights['rows']) == 579,
             'Original self_FR header weights, never continuous-unit substitutes')
        for row in weights['rows']:
            need(row['receipt']['full_member_crc_verified'] is True
                 and row['receipt']['array_values_decoded'] is False,
                 'Original complete-byte/header weight authentication')
        need(layout['distinct_features'] == 12516 and layout['response_shards'] == 202407
             and layout['source_jobs'] == 58926 and layout['source_requests'] == 6776076,
             'Complete original store census')
    return census,geometry,preparation,layout


def response_source_rows(job, time_bins, permutation):
    rows = job['time_indices'].astype('<i8',copy=True)+min(job['lag_bins'],0)
    padding = rows < 0
    if job['field'] == 'time_shuffle' or job['field'].endswith('_shuffle'):
        rows[~padding] = permutation[rows[~padding]]
    rows[padding] = -1
    need(np.all(rows >= -1) and np.all(rows < time_bins), 'Exact source response-row lineage')
    return rows


def derive_lineage(job, expected, geometry, class_record, population, units, permutation):
    """Pure complete-source transformation proof; used by writer and controls."""
    need(all(job[k] == expected[k] for k in ('session','field','layer','lag_index','lag_bins')),
         'Canonical original field/layer/lag ordering')
    m,d = expected['rows'],expected['columns']
    need(type(job['x']) is np.ndarray and job['x'].dtype.str == '<f8' and job['x'].shape == (m,30)
         and type(job['y']) is np.ndarray and job['y'].dtype.str == '<f8' and job['y'].shape == (m,d)
         and np.isfinite(job['x']).all() and np.isfinite(job['y']).all(), 'Exact finite original job geometry')
    q,t = job['qid'],job['time_indices']
    C.B._maps(q,t,m)
    source_rows = response_source_rows(job,geometry['time_bins'],permutation)
    base_kind = 'units' if job['field'] == 'unit' else 'population'
    signature = {'session':geometry['id'],
        'source_response_member_sha256':class_record['signature']['source_response_member_sha256'],
        'source_transform':'centered3bin_units' if base_kind == 'units' else 'centered3bin_population_mean',
        'ordered_time_indices_sha256':array_sha(t),'ordered_qid_sha256':array_sha(q),
        'ordered_response_source_rows_sha256':array_sha(source_rows),'zero_padding_sentinel':-1,
        'rows':m,'held_qids':len(np.unique(q))}
    need(signature == class_record['signature'] and pin(encoded(signature))['sha256'] == expected['response_class'],
         'Exact source support/qid/response-lineage signature')
    labels,counts = np.unique(q,return_counts=True)
    roster = class_record['held_roster']
    need(len(labels) == roster['count'] and array_sha(labels.astype('<f8')) == roster['held_qid_sha256']
         and array_sha(counts.astype('<i8')) == roster['query_counts_sha256']
         and int(counts.min()) == roster['minimum_query_rows'] and int(counts.max()) == roster['maximum_query_rows'],
         'Complete original held labels/counts/order')
    base = units if base_kind == 'units' else population
    reconstructed = np.zeros((m,d),dtype='<f8')
    valid = source_rows >= 0
    reconstructed[valid] = base[source_rows[valid]]
    need(reconstructed.tobytes() == job['y'].tobytes(order='C'),
         'Byte-exact original target recovery from once/session bases and source lineage')
    return {'source_rows':source_rows,'base_kind':base_kind,'labels':labels,'counts':counts,
            'target_sha256':array_sha(reconstructed),'feature_array_sha256':array_sha(job['x'])}


class _Output:
    def __init__(self,root,limit):
        need(integer(limit,1), 'Finite exclusive output allocation')
        self.root = Path(root).absolute()
        need(not any(p.is_symlink() for p in self.root.parents), 'No output symlink ancestors')
        self.root.mkdir(mode=0o700)
        self.limit,self.charged,self.written,self.files = limit,0,0,0
        self.failed = False

    def path(self,relative):
        p = Path(relative)
        need(not p.is_absolute() and '..' not in p.parts, 'Private generated relative path only')
        path = self.root/p
        need(not any(x.is_symlink() for x in (path,*path.parents)), 'No output alias')
        path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        need(not any(x.is_symlink() for x in (path,*path.parents)), 'No output alias after directory creation')
        return path

    def reserve(self,size):
        need(not self.failed and integer(size) and self.charged+size <= self.limit,
             'Gross output allocation before attempted write')
        self.charged += size

    def write(self,relative,raw):
        need(type(raw) is bytes, 'Immutable output bytes')
        self.reserve(len(raw))
        path,fd = self.path(relative),None
        try:
            fd = os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
            with os.fdopen(fd,'wb',buffering=0) as stream:
                fd = None
                need(stream.write(raw) == len(raw), 'Complete exclusive file write')
                self.written += len(raw)
                os.fsync(stream.fileno()); os.fchmod(stream.fileno(),0o400)
            self.files += 1
        except BaseException:
            self.failed = True
            raise
        finally:
            if fd is not None:
                os.close(fd)
        return {'path':relative,**pin(raw)}


class _Index:
    def __init__(self,output,relative):
        self.output,self.relative,self.count,self.bytes = output,relative,0,0
        self.digest = hashlib.sha256()
        path = output.path(relative)
        fd = os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
        try:
            self.stream = os.fdopen(fd,'wb',buffering=0)
        except BaseException:
            os.close(fd)
            raise
        self.closed = False

    def add(self,value,cap):
        need(not self.closed and not self.output.failed, 'Open unfailed index')
        raw = encoded(value)
        need(len(raw) <= cap, 'Bounded individual private JSONL record')
        self.output.reserve(len(raw))
        try:
            need(self.stream.write(raw) == len(raw), 'Complete private index record')
            self.output.written += len(raw)
            self.digest.update(raw); self.bytes += len(raw); self.count += 1
        except BaseException:
            self.output.failed = True
            raise

    def close(self):
        if not self.closed:
            try:
                os.fsync(self.stream.fileno()); os.fchmod(self.stream.fileno(),0o400)
            finally:
                self.stream.close(); self.closed = True
            self.output.files += 1
        return {'path':self.relative,'bytes':self.bytes,'sha256':self.digest.hexdigest(),'records':self.count}


def _npy(value):
    need(type(value) is np.ndarray and value.dtype.str in ('<f8','<i8') and 1 <= value.ndim <= 2
         and all(n > 0 for n in value.shape) and np.isfinite(value).all(), 'Finite primitive store NPY')
    header = io.BytesIO()
    np.lib.format.write_array_header_1_0(header,{'descr':value.dtype.str,'fortran_order':False,'shape':value.shape})
    prefix = header.getvalue()
    need(len(prefix) == 128, 'Exact canonical 128-byte store NPY profile')
    return prefix+value.tobytes(order='C')


def _base_check(value,expected):
    need(list(value.shape) == expected['shape'] and value.dtype.str == expected['dtype']
         and array_sha(value) == expected['sha256_c_order'], 'Exact Stage B prepared response identity')


class _SessionWriter:
    def __init__(self,output,sid,geometry,row,prepared,working_limit,metadata_limit,job_limit,original):
        self.out,self.sid,self.geometry,self.row,self.prepared = output,sid,geometry,row,prepared
        self.working_limit,self.metadata_limit,self.job_limit,self.original = working_limit,metadata_limit,job_limit,original
        self.prefix = 'sessions/'+sid+'/'
        self.indexes = {}
        try:
            for name in ('OBJECTS.jsonl','FEATURES.jsonl','CLASSES.jsonl','JOBS.jsonl'):
                self.indexes[name] = _Index(output,self.prefix+name)
        except BaseException:
            output.failed = True
            self._close_indexes()
            raise
        self.ids,self.features,self.classes = set(),{},{}
        self.array_files = self.array_bytes = self.jobs = self.requests = self.shards = 0
        self.peak_working_admission = 0

    def _metadata(self):
        need(sum(index.bytes for index in self.indexes.values()) <= self.metadata_limit-65536,
             'Per-session cumulative metadata allocation with final-manifest reserve')

    def _add(self,name,value,cap):
        raw = encoded(value)
        need(len(raw) <= cap and sum(i.bytes for i in self.indexes.values())+len(raw) <= self.metadata_limit-65536,
             'Individual and cumulative metadata admission before writing')
        self.indexes[name].add(value,cap)

    def _close_indexes(self):
        first = None
        for index in self.indexes.values():
            try:
                index.close()
            except BaseException as exc:
                self.out.failed = True
                first = first or exc
        if first is not None:
            raise first

    def _array(self,value,role=None):
        extent = 128+value.nbytes
        need(extent <= V.MAX_OBJECT_BYTES and self.out.charged+extent <= self.out.limit,
             'Primitive object output extent before serialization')
        oid = 'obj-'+str(uuid.uuid4())
        need(oid not in self.ids, 'No opaque object collision')
        self.ids.add(oid)
        relative = ('objects/' if role else 'private/')+oid+'.npy'
        raw = _npy(value)
        need(len(raw) == extent, 'Exact primitive NPY byte extent')
        receipt = self.out.write(self.prefix+relative,raw)
        self.array_files += 1; self.array_bytes += extent
        item = {'path':relative,'bytes':extent,'sha256':receipt['sha256'],'shape':list(value.shape),
                'dtype':value.dtype.str,'fortran_order':False}
        if role is not None:
            spec = V.ObjectSpec(oid,relative,role,extent,receipt['sha256'],tuple(value.shape),value.dtype.str,False)
            self._add('OBJECTS.jsonl',spec.private_descriptor(),512)
            self._metadata()
            return oid,item
        return item

    def run(self,data):
        try:
            return self._run(data)
        except BaseException:
            self.out.failed = True
            raise
        finally:
            self._close_indexes()

    def _run(self,data):
        need(data['session'] == self.sid and data['geometry'] == self.geometry, 'Exact source session geometry')
        numeric = sum(v.nbytes for v in data.values() if type(v) is np.ndarray)
        n,u = self.geometry['time_bins'],self.geometry['units']
        # The existing reader's full 4*member+64MiB reserve is retained in this
        # joint declaration, plus source preprocessing, canonical output buffers,
        # three metadata copies and explicit miscellaneous working allowance.
        member_bytes = sum(v['bytes'] for v in data['input_receipts'].values()) if self.original else numeric
        reserve = 4*member_bytes+64*1024**2 + 6*8*n*(u+1)+4*8*n*30 +3*self.metadata_limit+32*1024**2
        need(reserve <= self.working_limit, 'Joint original-reader/preprocessing/writer/index admission')
        self.peak_working_admission = reserve
        need(not self.original or data['input_receipts'] == self.prepared['input_receipts'],
             'All thirteen fresh original inputs match accepted Stage B receipts')
        population,units = O.smooth_targets(data['fr'])
        _base_check(population,self.prepared['prepared_population_response'])
        _base_check(units,self.prepared['prepared_unit_responses'])
        bases = {'population':self._array(population),'units':self._array(units)}
        permutation = np.random.RandomState(20).permutation(np.arange(n,dtype='<i8'))
        expected = iter(L.iter_job_layout(self.row,self.geometry))
        try:
            for job in O.iter_jobs(data):
                if self.job_limit is not None and self.jobs == self.job_limit:
                    break
                planned = next(expected)
                cid,fkey = planned['response_class'],planned['feature_key_sha256']
                proof = derive_lineage(job,planned,self.geometry,self.row['support_classes'][cid],population,units,permutation)
                if fkey in self.features:
                    feature = self.features[fkey]
                    need(feature['key'] == planned['feature_key'] and feature['array_sha256'] == proof['feature_array_sha256'],
                         'Only byte-identical permitted X may share an object')
                else:
                    oid,_ = self._array(job['x'],'features')
                    feature = {'key_sha256':fkey,'key':planned['feature_key'],'object_id':oid,
                               'array_sha256':proof['feature_array_sha256']}
                    self._add('FEATURES.jsonl',feature,640); self.features[fkey] = feature
                if cid in self.classes:
                    item = self.classes[cid]
                    need(item['target_sha256'] == proof['target_sha256'], 'Identical response lineage must recover identical target bits')
                else:
                    qid_id,_ = self._array(job['qid'],'qid')
                    time_id,_ = self._array(job['time_indices'],'time')
                    source_rows = self._array(proof['source_rows'])
                    shards = []
                    for label,count in zip(proof['labels'],proof['counts']):
                        selected = job['qid'] == label
                        oid,_ = self._array(job['y'][selected],'responses')
                        shards.append({'held_f64le':np.asarray([label],dtype='<f8').tobytes().hex(),
                                       'object_id':oid,'rows':int(count)})
                    item = {'class_sha256':cid,'signature':self.row['support_classes'][cid]['signature'],
                            'qid_object':qid_id,'time_object':time_id,'source_rows':source_rows,
                            'base_kind':proof['base_kind'],'target_sha256':proof['target_sha256'],
                            'target_shape':list(job['y'].shape),'shards':shards}
                    self._add('CLASSES.jsonl',item,2048+128*len(shards))
                    self.classes[cid] = item; self.shards += len(shards)
                context = {k:job[k] for k in ('session','field','family','layer','lag_index','lag_bins')}
                self._add('JOBS.jsonl',{'ordinal':self.jobs,'context':context,
                    'feature_id':feature['object_id'],'response_class':cid},512)
                self.jobs += 1; self.requests += planned['held_qids']; self._metadata()
            need(self.jobs == (4209 if self.job_limit is None else self.job_limit), 'Complete declared source or generated-prefix traversal')
            if self.original:
                need(self.requests == self.row['source_requests'] and len(self.classes) == len(self.row['support_classes'])
                     and self.shards == self.row['proven_class_held_units'], 'Every original response class and held request')
            indexes = {name:index.close() for name,index in self.indexes.items()}
            manifest = {'schema':'language-original-private-session-store/v1','session':self.sid,
                'scope':'original_full_source' if self.original else 'generated_prefix_control',
                'geometry':self.geometry,'bases':bases,'indexes':indexes,
                'input_receipts':data['input_receipts'],'prepared_source':self.prepared,
                'counts':{'jobs':self.jobs,'software_callbacks':self.requests,'features':len(self.features),
                    'response_classes':len(self.classes),'response_shards':self.shards,
                    'candidate_objects':indexes['OBJECTS.jsonl']['records'],'array_files':self.array_files},
                'array_bytes':self.array_bytes,'metadata_limit':self.metadata_limit,
                'peak_working_admission':self.peak_working_admission,
                'scientific_qualification':False,'native_execution':False}
            raw = encoded(manifest)
            need(len(raw) <= 65536 and sum(i['bytes'] for i in indexes.values())+len(raw) <= self.metadata_limit,
                 'Bounded complete private session manifest')
            return self.out.write(self.prefix+'SESSION.json',raw),manifest
        except BaseException:
            self.out.failed = True
            raise
        finally:
            self._close_indexes()


def _produce(root,plan,load_session,*,working_limit,output_limit,metadata_limit,archive_receipts=None,source_read_charge=0):
    census,geometry,preparation,layout = _plan(plan,working_limit)
    need(integer(metadata_limit,65536,MAX_META), 'Finite per-session serialized metadata allocation')
    output = _Output(root,output_limit)
    original = plan.scope == 'original_full_source'
    preserved = {name:output.write(name,raw) for name,raw in (
        ('CENSUS.json',plan.census_raw),('GEOMETRY.json',plan.geometry_raw),('PREPARATION.json',plan.preparation_raw))}
    totals = {k:0 for k in ORIGINAL_COUNTS}
    sessions = []
    for g,row,prior in zip(geometry['sessions'],census['sessions'],preparation['sessions']):
        data = load_session(g['id'])
        writer = _SessionWriter(output,g['id'],g,row,prior,working_limit,metadata_limit,
                                plan.generated_job_limit,original)
        receipt,session = writer.run(data)
        sessions.append({'session':g['id'],'manifest':receipt,'counts':session['counts']})
        for key,value in session['counts'].items():
            totals[key] += value
        totals['sessions'] += 1
        totals['result_arrays_expected'] += 16
        del data,writer
    if original:
        need(totals == ORIGINAL_COUNTS, 'Every original store object/job/callback/output-contract count')
        need(sum(s['counts']['features'] for s in sessions) == layout['distinct_features'], 'Complete accepted feature-sharing layout')
    result = {'schema':'language-original-private-store/v1','scope':plan.scope,'counts':totals,
        'generated_job_limit':plan.generated_job_limit,'producer_source_sha256':pin(Path(__file__).read_bytes())['sha256'],
        'sessions':sessions,'preserved_metadata':preserved,'source_code':{k:v[1] for k,v in PINS.items()},
        'weights':preparation.get('population_weights'),'archive_receipts':archive_receipts,
        'logical_source_read_charge_bytes':source_read_charge() if callable(source_read_charge) else source_read_charge,
        'array_and_index_bytes_written_before_store_manifest':output.written,
        'gross_output_charge_before_store_manifest':output.charged,'files_before_store_manifest':output.files,
        'complete_original_store':original,'complete_benchmark_ready':False,'native_execution':False,
        'scientific_qualification':False,'population_unit_identity_join_authenticated':False}
    raw = encoded(result)
    need(len(raw) <= 131072, 'Bounded final private store manifest')
    receipt = output.write('STORE.json',raw)
    return {'store':receipt,'metadata':result,'gross_output_charge':output.charged,
            'written_bytes':output.written,'files':output.files,'scientific_qualification':False}


def prepare_generated(root,plan,sessions,*,working_limit,output_limit,metadata_limit):
    """Explicit small generated prefix control; never an original-complete store."""
    need(type(plan) is StorePlan and plan.scope == 'generated_prefix_control'
         and type(sessions) is dict and 0 < len(sessions) <= 14, 'Explicit generated-only operands')
    return _produce(root,plan,lambda sid:sessions[sid],working_limit=working_limit,
                    output_limit=output_limit,metadata_limit=metadata_limit)


def prepare_original(output_root,archive_paths,*,census_path,preparation_path,admission_bytes,
                     expected_admission_sha256,read_limit,working_limit,output_limit,metadata_limit):
    """Actual-data seam: explicit frozen operator admission before archive open.

    The hash binds the operator's already approved protocol content; it is not an
    authorization or native-attestation mechanism. The external orchestrator owns
    storage reservation, process lease, whole-stage deadline and runtime limits.
    """
    need(type(admission_bytes) is bytes and len(admission_bytes) <= 16384
         and pin(admission_bytes)['sha256'] == expected_admission_sha256, 'Frozen operator admission bytes')
    need(type(archive_paths) is dict and set(archive_paths) == {'data_processed.zip','DNN.zip','transcription.zip'},
         'Exact original numeric/archive input set')
    for limit in (read_limit,working_limit,output_limit,metadata_limit):
        need(integer(limit,1), 'Finite preparation allocation')
    actual = {'schema':'language-original-store-preparation-admission/v1',
        'producer_source_sha256':pin(Path(__file__).read_bytes())['sha256'],
        'census_sha256':CENSUS_PIN['sha256'],'preparation_sha256':PREPARATION_PIN['sha256'],
        'geometry_sha256':GEOMETRY_PIN['sha256'],'numpy_version':np.__version__,
        'archives':{k:str(Path(v).absolute()) for k,v in archive_paths.items()},
        'output':str(Path(output_root).absolute()),'read_limit':read_limit,'working_limit':working_limit,
        'output_limit':output_limit,'metadata_limit':metadata_limit,'model_execution':False,'native_execution':False}
    need(L.parse(admission_bytes) == actual and encoded(actual) == admission_bytes,
         'Exact canonical source/path/runtime/allocation admission before archive I/O')
    plan = StorePlan(read_metadata(census_path,CENSUS_PIN),
                     read_metadata(HERE.parent/'original-inputs-v1/source-bindings.json',GEOMETRY_PIN),
                     read_metadata(preparation_path,PREPARATION_PIN),'original_full_source',None)
    _,_,prior,_ = _plan(plan,working_limit)
    with I.ArchiveInputs(archive_paths,read_limit=read_limit,working_limit=working_limit) as reader:
        need(reader.archive_receipts == prior['archive_receipts'], 'Original archive SHA/MD5 match accepted Stage B before members')
        weights = reader.population_weights()
        need(weights == prior['population_weights'], 'Fresh original self_FR full-byte/header receipts')
        return _produce(output_root,plan,reader.load_session,working_limit=working_limit,
            output_limit=output_limit,metadata_limit=metadata_limit,
            archive_receipts=reader.archive_receipts,source_read_charge=lambda:reader.charged)
