"""Bounded private produced-store lineage reader, separate from candidate views.

Only allowed qid/time maps are read in the default job iterator. The explicit
include_targets path reconstructs private targets for later trusted scoring.
The parent coordinator owns candidate execution, FileStore/BundleCache, durable
authorities, and combined component/process budgets.
"""
from __future__ import annotations

import hashlib
import io
import math
import os
from pathlib import Path
import stat
import struct

import numpy as np

import producer as p


def _relative(value):
    p.need(type(value) is str and 0 < len(value) <= 160 and '\\' not in value
           and '\x00' not in value and not Path(value).is_absolute() and '..' not in Path(value).parts,
           'Bounded private relative path')
    return value


def _file(value, *, cap):
    p.need(type(value) is dict and set(value) >= {'path','bytes','sha256'}
           and p.integer(value['bytes'],1,cap) and p.V.digest(value['sha256']), 'Bounded exact file identity')
    _relative(value['path'])


class StoreReader:
    def __init__(self,root,*,expected_store_sha256,read_limit,working_limit):
        p.need(p.V.digest(expected_store_sha256) and p.integer(read_limit,1)
               and p.integer(working_limit,1,p.MAX_WORK), 'Frozen store and finite private reader allocations')
        self.root = Path(root).absolute()
        p.need(not any(x.is_symlink() for x in (self.root,*self.root.parents)) and self.root.is_dir(),
               'Ordinary produced store root')
        self.read_limit,self.working_limit = read_limit,working_limit
        self.read_charged,self.bytes_read,self.peak_working_admission = 0,0,0
        self.failed,self.closed,self._iterating = False,False,False
        self._active = None
        self._retained = 0
        self._store_raw,self._store_stamp = self._read('STORE.json',{'sha256':expected_store_sha256},131072)
        self.store_sha256 = expected_store_sha256
        self._store = p.L.parse(self._store_raw)
        s = self._store
        p.need(type(s) is dict and s.get('schema') == 'language-original-private-store/v1'
               and s.get('scope') in ('original_full_source','generated_prefix_control')
               and s.get('scientific_qualification') is False and s.get('native_execution') is False
               and s.get('complete_benchmark_ready') is False, 'Exact unqualified private store scope')
        p.need(s.get('source_code') == {k:v[1] for k,v in p.PINS.items()}
               and s.get('producer_source_sha256') == p.pin(Path(p.__file__).read_bytes())['sha256'],
               'Exact producer/source-code lineage')
        self.scope = s['scope']
        p.need(type(s.get('preserved_metadata')) is dict
               and set(s['preserved_metadata']) == {'CENSUS.json','GEOMETRY.json','PREPARATION.json'},
               'Complete frozen metadata operands')
        blobs = {}
        for name,cap in (('CENSUS.json',2097152),('GEOMETRY.json',131072),('PREPARATION.json',262144)):
            identity = s['preserved_metadata'][name]
            _file(identity,cap=cap); p.need(identity['path'] == name, 'Canonical preserved metadata path')
            blobs[name],_ = self._read(name,identity,cap)
        self._plan = p.StorePlan(blobs['CENSUS.json'],blobs['GEOMETRY.json'],blobs['PREPARATION.json'],
                                 self.scope,s.get('generated_job_limit'))
        self._census,self._geometry,self._preparation,self._layout = p._plan(self._plan,working_limit)
        self._retained = 8*sum(len(v) for v in blobs.values())+8*1024**2
        self._admit(0)
        p.need(type(s.get('sessions')) is list
               and [r['session'] for r in s['sessions']] == [g['id'] for g in self._geometry['sessions']],
               'Complete canonical private session order')
        if self.scope == 'original_full_source':
            p.need(s['counts'] == p.ORIGINAL_COUNTS and s['complete_original_store'] is True,
                   'Complete original source store cardinalities')
        else:
            p.need(s['complete_original_store'] is False, 'Generated prefix cannot become original-complete')
        p.need(s.get('weights') == self._preparation.get('population_weights'),
               'Exact original or explicitly generated weight receipt identity')

    @property
    def metadata(self):
        return p.L.parse(self._store_raw)

    @property
    def weights(self):
        return p.L.parse(p.encoded(self._store['weights']))

    def _admit(self,extra):
        p.need(not self.closed and not self.failed and p.integer(extra)
               and self._retained+extra <= self.working_limit, 'Joint private reader retained/temporary admission')
        self.peak_working_admission = max(self.peak_working_admission,self._retained+extra)

    def _path(self,relative):
        path = self.root/_relative(relative)
        p.need(not any(x.is_symlink() for x in (path,*path.parents)), 'No produced-store symlink path')
        return path

    def _read(self,relative,identity,cap):
        fd = None
        try:
            p.need(not self.closed and not self.failed, 'Live private store reader')
            path = self._path(relative)
            before = path.lstat()
            p.need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_mode & 0o222 == 0
                   and 0 < before.st_size <= cap and ('bytes' not in identity or before.st_size == identity['bytes']),
                   'Exact readonly single-link ordinary private file')
            self._admit(4*before.st_size+8192)
            p.need(self.read_charged+before.st_size+1 <= self.read_limit, 'Actual file plus EOF read admission')
            fd = os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
            with os.fdopen(fd,'rb',buffering=0) as stream:
                fd = None
                p.need(p.V._stamp(os.fstat(stream.fileno())) == p.V._stamp(before), 'Opened private file identity')
                self.read_charged += before.st_size+1
                raw = stream.read(before.st_size+1)
                self.bytes_read += len(raw)
                p.need(p.V._stamp(os.fstat(stream.fileno())) == p.V._stamp(path.lstat()) == p.V._stamp(before),
                       'Stable private file through authenticated read')
            p.need(len(raw) == before.st_size and hashlib.sha256(raw).hexdigest() == identity['sha256'],
                   'Exact private file extent and digest')
            return raw,p.V._stamp(before)
        except BaseException:
            self.failed = True
            raise
        finally:
            if fd is not None:
                os.close(fd)

    def _stable(self,relative,stamp):
        try:
            p.need(p.V._stamp(self._path(relative).lstat()) == stamp,
                   'Cached private source object identity changed')
        except BaseException:
            self.failed = True
            raise

    def iter_sessions(self):
        p.need(not self.closed and not self.failed and not self._iterating, 'One live session traversal')
        self._iterating = True
        try:
            self._stable('STORE.json',self._store_stamp)
            for ref,g,row,prepared in zip(self._store['sessions'],self._geometry['sessions'],
                                          self._census['sessions'],self._preparation['sessions']):
                p.need(self._active is None, 'Release preceding private session')
                session = SessionStore(self,ref,g,row,prepared)
                self._active = session
                try:
                    yield session
                finally:
                    session.close(); self._active = None
        except BaseException:
            self.failed = True
            raise
        finally:
            self._iterating = False

    def close(self):
        if self._active is not None:
            self._active.close(); self._active = None
        self.closed = True

    def private_metrics(self):
        return {'read_charged':self.read_charged,'bytes_read':self.bytes_read,
                'read_limit':self.read_limit,'working_limit':self.working_limit,
                'peak_working_admission':self.peak_working_admission,'retained_working_admission':self._retained,
                'failed':self.failed,'closed':self.closed,'native_execution':False,
                'scope':'Private metadata/maps/target reads; separate from FileStore and native feature staging.'}


class SessionStore:
    def __init__(self,parent,ref,geometry,census,prepared):
        self.parent,self.session,self.geometry,self.census = parent,geometry['id'],geometry,census
        self.root = parent.root/'sessions'/self.session
        self.prefix = 'sessions/'+self.session+'/'
        self.closed,self._iterating = False,False
        self._arrays,self._extra,self._index_raw,self._index_stamps = {},0,{},{}
        _file(ref['manifest'],cap=65536)
        p.need(ref['manifest']['path'] == self.prefix+'SESSION.json', 'Canonical session manifest path')
        raw,self._stamp = parent._read(ref['manifest']['path'],ref['manifest'],65536)
        self._manifest_raw = raw
        self._manifest = p.L.parse(raw)
        m = self._manifest
        p.need(m['schema'] == 'language-original-private-session-store/v1' and m['session'] == self.session
               and m['scope'] == parent.scope and m['geometry'] == geometry and m['prepared_source'] == prepared
               and m['counts'] == ref['counts'] and m['scientific_qualification'] is False
               and m['native_execution'] is False, 'Exact source session/preparation join')
        p.need(set(m['indexes']) == {'OBJECTS.jsonl','FEATURES.jsonl','CLASSES.jsonl','JOBS.jsonl'}
               and p.integer(m['metadata_limit'],65536,p.MAX_META), 'Complete bounded private indexes')
        total = sum(i['bytes'] for i in m['indexes'].values())+len(raw)
        p.need(total <= m['metadata_limit'], 'Complete session metadata extent')
        parent._admit(8*total+8*1024**2)
        self._extra = 8*total+8*1024**2
        parent._retained += self._extra
        for name,identity in m['indexes'].items():
            _file(identity,cap=m['metadata_limit'])
            p.need(identity['path'] == self.prefix+name and p.integer(identity['records'],1,218451),
                   'Canonical finite private index identity')
            self._index_raw[name],self._index_stamps[name] = parent._read(identity['path'],identity,m['metadata_limit'])
        self._specs = {}
        for item in self._records('OBJECTS.jsonl',512):
            p.need(type(item) is dict and set(item) == {'object_id','relative_path','role','bytes','sha256','shape','dtype','fortran_order'},
                   'Exact candidate-object spec schema')
            spec = p.V.ObjectSpec(item['object_id'],item['relative_path'],item['role'],item['bytes'],item['sha256'],
                                 tuple(item['shape']),item['dtype'],item['fortran_order'])
            p.need(spec.object_id not in self._specs, 'Unique candidate object identity')
            self._specs[spec.object_id] = spec
        self._features = {}
        for item in self._records('FEATURES.jsonl',640):
            p.need(set(item) == {'key_sha256','key','object_id','array_sha256'}
                   and p.pin(p.encoded(item['key']))['sha256'] == item['key_sha256']
                   and item['object_id'] not in self._features and p.V.digest(item['array_sha256']),
                   'Exact unique permitted-feature identity')
            spec = self._specs[item['object_id']]
            p.need(spec.role == 'features', 'Feature index cannot select a response object')
            self._features[item['object_id']] = item
        self._classes = {}
        maximum_q = max(c['held_roster']['count'] for c in census['support_classes'].values())
        for item in self._records('CLASSES.jsonl',2048+128*maximum_q):
            cid = item['class_sha256']
            p.need(cid not in self._classes and cid in census['support_classes']
                   and item['signature'] == census['support_classes'][cid]['signature']
                   and p.pin(p.encoded(item['signature']))['sha256'] == cid,
                   'Exact private response-class source lineage')
            self._classes[cid] = item
        p.need(len(self._specs) == m['counts']['candidate_objects'] and len(self._features) == m['counts']['features']
               and len(self._classes) == m['counts']['response_classes']
               and m['indexes']['JOBS.jsonl']['records'] == m['counts']['jobs'], 'Complete materialized session counts')
        p.need(set(m['bases']) == {'population','units'}, 'Exactly two private once/session target bases')

    @property
    def specs(self):
        p.need(not self.closed, 'Live private session')
        self.parent._admit(8192*len(self._specs))
        return tuple(p.C._spec_snapshot(s) for s in self._specs.values())

    def _records(self,name,cap):
        raw = self._index_raw[name]
        offset,count = 0,0
        while offset < len(raw):
            end = raw.find(b'\n',offset,min(len(raw),offset+cap))
            p.need(end >= offset, 'Bounded complete canonical JSONL record')
            line = raw[offset:end+1]
            value = p.L.parse(line)
            p.need(p.encoded(value) == line, 'Canonical private index serialization')
            yield value
            offset,count = end+1,count+1
        p.need(count == self._manifest['indexes'][name]['records'], 'Exact private index record count')

    def _array(self,identity):
        _file(identity,cap=p.V.MAX_OBJECT_BYTES)
        relative = self.prefix+identity['path']
        p.need(type(identity.get('shape')) in (list,tuple) and 1 <= len(identity['shape']) <= 2
               and all(p.integer(n,1,p.V.MAX_ROWS) for n in identity['shape'])
               and identity.get('dtype') in ('<f8','<i8') and identity.get('fortran_order') is False
               and identity['bytes'] == 128+math.prod(identity['shape'])*8, 'Canonical primitive array identity')
        key = relative
        if key in self._arrays:
            raw,stamp,frozen = self._arrays[key]
            p.need(frozen == p.encoded(identity), 'No private cached array rebind')
            self.parent._stable(relative,stamp)
        else:
            self.parent._admit(4*identity['bytes']+8192)
            raw,stamp = self.parent._read(relative,identity,p.V.MAX_OBJECT_BYTES)
            stream = io.BytesIO(raw)
            p.need(np.lib.format.read_magic(stream) == (1,0), 'Canonical primitive NPY1 only')
            shape,fortran,dtype = np.lib.format.read_array_header_1_0(stream,max_header_size=4096)
            p.need(list(shape) == list(identity['shape']) and fortran is False and dtype.str == identity['dtype']
                   and not dtype.hasobject and dtype.fields is None and dtype.subdtype is None and stream.tell() == 128,
                   'Exact private primitive header geometry')
            value = np.frombuffer(raw,dtype=dtype,offset=128).reshape(shape)
            p.need(np.isfinite(value).all(), 'Finite private primitive array')
            retained = len(raw)+2048
            self.parent._admit(retained)
            self.parent._retained += retained; self._extra += retained
            self._arrays[key] = raw,stamp,p.encoded(identity)
        return np.frombuffer(raw,dtype=identity['dtype'],offset=128).reshape(tuple(identity['shape']))

    def _candidate_array(self,object_id):
        spec = self._specs[object_id]
        return self._array({'path':spec.relative_path,'bytes':spec.bytes,'sha256':spec.sha256,
                            'shape':list(spec.shape),'dtype':spec.dtype,'fortran_order':spec.fortran_order})

    def _selection(self,contexts):
        if contexts is None:
            return None
        p.need(type(contexts) in (tuple,list) and len(contexts) <= 4209,
               'Finite primitive context selection; no arbitrary iterable')
        self.parent._admit(4096*len(contexts)+8192)
        wanted = set()
        keys = {'session','field','family','layer','lag_index','lag_bins'}
        for value in contexts:
            p.need(type(value) is dict and set(value) == keys, 'Exact primitive selector context')
            snap = p.C.B._context_snapshot(p.V.JobContext(**value),1)
            p.need(snap.session == self.session, 'Selector belongs to this source session')
            key = p.encoded(value)
            p.need(key not in wanted, 'No duplicate selected source coordinate')
            wanted.add(key)
        found = set()
        expected = iter(p.L.iter_job_layout(self.census,self.geometry))
        count = 0
        for record in self._records('JOBS.jsonl',512):
            planned = next(expected)
            p.need(set(record) == {'ordinal','context','feature_id','response_class'} and record['ordinal'] == count,
                   'Complete canonical schedule before selected array reads')
            context = p.C.B._context_snapshot(p.V.JobContext(**record['context']),planned['columns'])
            p.need(all(getattr(context,k) == planned[k] for k in ('session','field','layer','lag_index','lag_bins'))
                   and record['response_class'] == planned['response_class'], 'Selected coordinate matches source schedule')
            key = p.encoded(record['context'])
            if key in wanted:
                found.add(key)
            count += 1
        p.need(count == self._manifest['counts']['jobs'] and found == wanted,
               'Every selected coordinate exists before any array read')
        return wanted

    def iter_jobs(self,include_targets=False,contexts=None):
        p.need(not self.closed and not self.parent.failed and not self._iterating and type(include_targets) is bool,
               'One live private canonical job traversal')
        self._iterating = True
        try:
            for name,stamp in self._index_stamps.items():
                self.parent._stable(self.prefix+name,stamp)
            selected = self._selection(contexts)
            expected = iter(p.L.iter_job_layout(self.census,self.geometry))
            jobs,requests = 0,0
            for record in self._records('JOBS.jsonl',512):
                planned = next(expected)
                p.need(set(record) == {'ordinal','context','feature_id','response_class'} and record['ordinal'] == jobs,
                       'Exact canonical private job index')
                context = p.C.B._context_snapshot(p.V.JobContext(**record['context']),planned['columns'])
                p.need(all(getattr(context,k) == planned[k] for k in ('session','field','layer','lag_index','lag_bins'))
                       and record['response_class'] == planned['response_class'], 'Exact source job/response-class identity')
                feature = self._features[record['feature_id']]
                p.need(feature['key'] == planned['feature_key'] and feature['key_sha256'] == planned['feature_key_sha256'],
                       'Exactly one original feature job, never a layer union')
                jobs += 1; requests += planned['held_qids']
                if selected is not None and p.encoded(record['context']) not in selected:
                    continue
                item = self._classes[record['response_class']]
                q,t = self._candidate_array(item['qid_object']),self._candidate_array(item['time_object'])
                p.C.B._maps(q,t,planned['rows'])
                p.need(p.array_sha(q) == item['signature']['ordered_qid_sha256']
                       and p.array_sha(t) == item['signature']['ordered_time_indices_sha256'], 'Exact source row-map bytes')
                labels,counts = np.unique(q,return_counts=True)
                p.need(len(labels) == planned['held_qids'] and len(item['shards']) == len(labels), 'Complete held-shard roster')
                shards = []
                for label,count,shard in zip(labels,counts,item['shards']):
                    p.need(set(shard) == {'held_f64le','object_id','rows'}
                           and shard['held_f64le'] == struct.pack('<d',float(label)).hex() and shard['rows'] == int(count),
                           'Exact original held label bits and support')
                    spec = self._specs[shard['object_id']]
                    p.need(spec.role == 'responses' and spec.shape == (int(count),planned['columns']), 'Exact response shard width')
                    positions = tuple(int(i) for i in np.flatnonzero(q == label))
                    shards.append(p.V.ResponseShard(float(label),spec.object_id,positions))
                vjob = p.V.FeatureJob(context,record['feature_id'],item['qid_object'],item['time_object'],tuple(shards),planned['columns'])
                fspec = self._specs[record['feature_id']]
                p.need(fspec.shape == (planned['rows'],30), 'One full permitted source feature matrix')
                result = {'context':dict(record['context']),'view_job':vjob,'qid':q,'time_indices':t,
                    'outputs':planned['columns'],'support_class_sha256':record['response_class'],
                    'target_sha256':item['target_sha256'],
                    'feature':{'sha256':fspec.sha256,'bytes':fspec.bytes,'fortran_order':fspec.fortran_order},
                    'feature_path':self.root/fspec.relative_path,'feature_spec':fspec.private_descriptor()}
                if include_targets:
                    rows = self._array(item['source_rows'])
                    base = self._array(self._manifest['bases'][item['base_kind']])
                    self.parent._admit(6*planned['rows']*planned['columns']*8+64*planned['rows']+8192)
                    p.need(rows.dtype.str == '<i8' and rows.shape == (planned['rows'],)
                           and p.array_sha(rows) == item['signature']['ordered_response_source_rows_sha256']
                           and np.all(rows >= -1) and np.all(rows < len(base)), 'Exact private response-row lineage')
                    need_kind = 'units' if context.field == 'unit' else 'population'
                    p.need(item['base_kind'] == need_kind and base.shape == (self.geometry['time_bins'],planned['columns']),
                           'Original target kind and complete base geometry')
                    prior = self._manifest['prepared_source']['prepared_unit_responses' if need_kind == 'units' else 'prepared_population_response']
                    p._base_check(base,prior)
                    targets = np.zeros((len(rows),planned['columns']),dtype='<f8')
                    valid = rows >= 0; targets[valid] = base[rows[valid]]
                    target_raw = targets.tobytes()
                    p.need(hashlib.sha256(target_raw).hexdigest() == item['target_sha256'], 'Exact independently recoverable original target bytes')
                    result['targets'] = np.frombuffer(target_raw,dtype='<f8').reshape(targets.shape)
                yield result
            p.need(jobs == self._manifest['counts']['jobs'] and requests == self._manifest['counts']['software_callbacks'],
                   'Complete streamed session job/request accounting')
        except BaseException:
            self.parent.failed = True
            raise
        finally:
            self._iterating = False

    def close(self):
        if not self.closed:
            self._arrays.clear(); self._index_raw.clear()
            self._specs.clear(); self._features.clear(); self._classes.clear()
            self.parent._retained -= self._extra; self._extra = 0
            self.closed = True
