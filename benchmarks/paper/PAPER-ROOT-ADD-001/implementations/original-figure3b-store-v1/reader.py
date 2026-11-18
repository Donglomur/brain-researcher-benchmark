"""Private complete selected-task store reader; no candidate or native execution."""
from __future__ import annotations

import hashlib
from pathlib import Path
import struct

import numpy as np

import producer as s

p=s.p


class StoreReader(s.F.StoreReader):
    def __init__(self,root,*,expected_store_sha256,read_limit,working_limit):
        p.need(p.V.digest(expected_store_sha256) and p.integer(read_limit,1)
               and p.integer(working_limit,1,p.MAX_WORK),'Frozen selected store and finite reader allocation')
        self.root=Path(root).absolute()
        p.need(not any(x.is_symlink() for x in (self.root,*self.root.parents)) and self.root.is_dir(),'Ordinary selected store root')
        self.read_limit,self.working_limit=read_limit,working_limit
        self.read_charged,self.bytes_read,self.peak_working_admission=0,0,0
        self.failed,self.closed,self._iterating=False,False,False
        self._active=None;self._retained=0
        self._store_raw,self._store_stamp=self._read('STORE.json',{'sha256':expected_store_sha256},131072)
        self.store_sha256=expected_store_sha256;self._store=p.L.parse(self._store_raw)
        value=self._store
        p.need(type(value) is dict and value.get('schema')=='language-figure3b-private-store/v1'
               and value.get('scope') in (s.SCOPE,s.GENERATED_SCOPE) and value.get('selection_sha256')==s.SELECTION_SHA
               and value.get('scientific_qualification') is False and value.get('native_execution') is False
               and value.get('complete_original_store') is False and value.get('complete_benchmark_ready') is False,
               'Explicit complete selected task, never full-reproduction or native qualification')
        p.need(value.get('source_code')=={k:v[1] for k,v in p.PINS.items()}
               and value.get('full_source_dependencies')=={'producer.py':s.FULL_SHA,'reader.py':s.FULL_READER_SHA}
               and value.get('producer_source_sha256')==p.pin(Path(s.__file__).read_bytes())['sha256'],
               'Exact selected producer and accepted full-source dependency lineage')
        self.scope=value['scope']
        p.need(type(value.get('preserved_metadata')) is dict
               and set(value['preserved_metadata'])=={'CENSUS.json','GEOMETRY.json','PREPARATION.json'},'Complete source metadata operands')
        blobs={}
        for name,cap in (('CENSUS.json',2097152),('GEOMETRY.json',131072),('PREPARATION.json',262144)):
            identity=value['preserved_metadata'][name]
            s.F._file(identity,cap=cap);p.need(identity['path']==name,'Canonical source metadata path')
            blobs[name],_=self._read(name,identity,cap)
        original=self.scope==s.SCOPE
        p.need(value.get('source_plan_scope')==('original_full_source' if original else 'generated_prefix_control'),
               'Original selected scope requires complete original source metadata')
        self._plan=p.StorePlan(blobs['CENSUS.json'],blobs['GEOMETRY.json'],blobs['PREPARATION.json'],
            value['source_plan_scope'],value.get('generated_job_limit'))
        self._census,self._geometry,self._preparation,self._layout=s.selected_plan(self._plan,working_limit)
        self._retained=8*sum(len(v) for v in blobs.values())+8*1024**2;self._admit(0)
        p.need(value.get('layout')==self._layout and value.get('counts')==self._layout['counts']
               and value.get('complete_selected_store') is original,'Exact selected counts and scope proof')
        p.need(type(value.get('sessions')) is list
               and [r['session'] for r in value['sessions']]==[g['id'] for g in self._geometry['sessions']],
               'Every original session in canonical order')
        p.need(value.get('weights')==self._preparation.get('population_weights'),'Exact source weight receipts retained')

    def iter_sessions(self):
        p.need(not self.closed and not self.failed and not self._iterating,'One live selected session traversal')
        self._iterating=True
        try:
            self._stable('STORE.json',self._store_stamp)
            for ref,g,row,prepared,bound in zip(self._store['sessions'],self._geometry['sessions'],self._census['sessions'],
                                                self._preparation['sessions'],self._layout['sessions']):
                p.need(self._active is None,'Release previous selected session')
                session=SessionStore(self,ref,g,row,prepared,bound);self._active=session
                try:yield session
                finally:session.close();self._active=None
        except BaseException:
            self.failed=True;raise
        finally:self._iterating=False


class SessionStore(s.F.SessionStore):
    def __init__(self,parent,ref,geometry,census,prepared,bound):
        self.parent,self.session,self.geometry,self.census=parent,geometry['id'],geometry,census
        self.root=parent.root/'sessions'/self.session;self.prefix='sessions/'+self.session+'/'
        self.closed,self._iterating=False,False
        self._arrays,self._extra,self._index_raw,self._index_stamps={},0,{},{}
        try:self._initialize(ref,prepared,bound)
        except BaseException:
            parent.failed=True
            self.close()
            raise

    def _initialize(self,ref,prepared,bound):
        parent=self.parent
        s.F._file(ref['manifest'],cap=65536)
        p.need(ref['manifest']['path']==self.prefix+'SESSION.json','Canonical selected session manifest')
        raw,self._stamp=parent._read(ref['manifest']['path'],ref['manifest'],65536)
        self._manifest_raw=raw;self._manifest=p.L.parse(raw);m=self._manifest
        p.need(m['schema']=='language-figure3b-private-session-store/v1' and m['session']==self.session
               and m['scope']==parent.scope and m['selection_sha256']==s.SELECTION_SHA
               and m['geometry']==self.geometry and m['prepared_source']==prepared
               and m['counts']==ref['counts']==bound['counts'] and m['array_bytes']==bound['canonical_array_bytes']
               and m['scientific_qualification'] is False and m['native_execution'] is False,
               'Complete exact selected source session/preparation/extent join')
        p.need(set(m['indexes'])=={'OBJECTS.jsonl','FEATURES.jsonl','CLASSES.jsonl','JOBS.jsonl'}
               and p.integer(m['metadata_limit'],65536,p.MAX_META),'Complete bounded selected indexes')
        total=sum(i['bytes'] for i in m['indexes'].values())+len(raw)
        p.need(total<=m['metadata_limit'],'Complete selected session metadata extent')
        parent._admit(8*total+8*1024**2);self._extra=8*total+8*1024**2;parent._retained+=self._extra
        for name,identity in m['indexes'].items():
            s.F._file(identity,cap=m['metadata_limit'])
            p.need(identity['path']==self.prefix+name and p.integer(identity['records'],1,5783),'Finite selected private index')
            self._index_raw[name],self._index_stamps[name]=parent._read(identity['path'],identity,m['metadata_limit'])
        self._specs={}
        for item in self._records('OBJECTS.jsonl',512):
            p.need(type(item) is dict and set(item)=={'object_id','relative_path','role','bytes','sha256','shape','dtype','fortran_order'},
                   'Exact selected object spec')
            spec=p.V.ObjectSpec(item['object_id'],item['relative_path'],item['role'],item['bytes'],item['sha256'],
                                tuple(item['shape']),item['dtype'],item['fortran_order'])
            p.need(spec.object_id not in self._specs,'Unique selected object identity');self._specs[spec.object_id]=spec
        self._features={}
        for item in self._records('FEATURES.jsonl',640):
            p.need(type(item) is dict and set(item)=={'key_sha256','key','object_id','array_sha256'}
                   and p.pin(p.encoded(item['key']))['sha256']==item['key_sha256']
                   and item['object_id'] not in self._features and p.V.digest(item['array_sha256']), 'Exact selected feature key')
            p.need(self._specs[item['object_id']].role=='features','Selected feature cannot alias response object')
            self._features[item['object_id']]=item
        self._planned=s.selected_layout(self.census,self.geometry)
        expected_classes={j['response_class'] for j in self._planned}
        self._classes={};maximum_q=max(j['held_qids'] for j in self._planned)
        keys={'class_sha256','signature','qid_object','time_object','source_rows','base_kind','target_sha256','target_shape','shards'}
        for item in self._records('CLASSES.jsonl',2048+128*maximum_q):
            p.need(type(item) is dict and set(item)==keys,'Exact selected response-class record')
            cid=item['class_sha256']
            p.need(cid not in self._classes and cid in expected_classes
                   and item['signature']==self.census['support_classes'][cid]['signature']
                   and p.pin(p.encoded(item['signature']))['sha256']==cid
                   and item['base_kind']=='population' and p.V.digest(item['target_sha256']), 'Exact selected response source lineage')
            self._classes[cid]=item
        p.need(set(self._classes)==expected_classes and len(self._features)==1
               and len(self._specs)==m['counts']['candidate_objects'] and m['indexes']['JOBS.jsonl']['records']==3
               and set(m['bases'])=={'population'},'Exactly selected features/classes and one private population base')

    def _metadata_jobs(self):
        count=0
        for record in self._records('JOBS.jsonl',512):
            p.need(count<3 and set(record)=={'ordinal','context','feature_id','response_class'} and record['ordinal']==count,
                   'Canonical selected job record before any selected array read')
            planned=self._planned[count]
            context=p.C.B._context_snapshot(p.V.JobContext(**record['context']),1)
            p.need(all(getattr(context,k)==planned[k] for k in ('session','field','layer','lag_index','lag_bins'))
                   and record['response_class']==planned['response_class'],'Exact fixed source selection coordinate')
            feature=self._features[record['feature_id']]
            p.need(feature['key']==planned['feature_key'] and feature['key_sha256']==planned['feature_key_sha256'],
                   'Single source layer5 feature identity')
            yield record,planned,context
            count+=1
        p.need(count==3,'All three source cells, no favorable omission')

    def _selection(self,contexts):
        if contexts is None:return None
        p.need(type(contexts) in (tuple,list) and len(contexts)<=3,'Finite selected coordinate list, no arbitrary iterable')
        self.parent._admit(4096*len(contexts)+8192);wanted=set()
        for value in contexts:
            p.need(type(value) is dict and set(value)==set(s.CONTEXT_KEYS),'Primitive exact selected context')
            snap=p.C.B._context_snapshot(p.V.JobContext(**value),1)
            p.need(snap.session==self.session,'Selected coordinate belongs to source session')
            key=p.encoded(value);p.need(key not in wanted,'No duplicate selected coordinate');wanted.add(key)
        available={p.encoded(r['context']) for r,_,_ in self._metadata_jobs()}
        p.need(wanted<=available,'Every selected coordinate exists before array reads')
        return wanted

    def iter_jobs(self,include_targets=False,contexts=None):
        p.need(not self.closed and not self.parent.failed and not self._iterating and type(include_targets) is bool,
               'One live selected source job traversal')
        self._iterating=True
        try:
            for name,stamp in self._index_stamps.items():self.parent._stable(self.prefix+name,stamp)
            # Complete metadata verification occurs before the first array read.
            for _ in self._metadata_jobs():pass
            selected=self._selection(contexts);requests=0
            for record,planned,context in self._metadata_jobs():
                requests+=planned['held_qids']
                if selected is not None and p.encoded(record['context']) not in selected:continue
                item=self._classes[record['response_class']]
                q,t=self._candidate_array(item['qid_object']),self._candidate_array(item['time_object'])
                p.C.B._maps(q,t,planned['rows'])
                p.need(p.array_sha(q)==item['signature']['ordered_qid_sha256']
                       and p.array_sha(t)==item['signature']['ordered_time_indices_sha256'],'Original selected source map bytes')
                labels,counts=np.unique(q,return_counts=True)
                p.need(len(labels)==planned['held_qids'] and len(item['shards'])==len(labels),'Complete selected held roster')
                shards=[]
                for label,count,shard in zip(labels,counts,item['shards']):
                    p.need(set(shard)=={'held_f64le','object_id','rows'}
                           and shard['held_f64le']==struct.pack('<d',float(label)).hex() and shard['rows']==int(count),
                           'Exact selected held label bits/support')
                    spec=self._specs[shard['object_id']]
                    p.need(spec.role=='responses' and spec.shape==(int(count),1),'Exactly one population output in every shard')
                    shards.append(p.V.ResponseShard(float(label),spec.object_id,tuple(int(i) for i in np.flatnonzero(q==label))))
                vjob=p.V.FeatureJob(context,record['feature_id'],item['qid_object'],item['time_object'],tuple(shards),1)
                fspec=self._specs[record['feature_id']]
                p.need(fspec.shape==(planned['rows'],30) and item['target_shape']==[planned['rows'],1],'Exact selected feature/target shape')
                result={'context':dict(record['context']),'view_job':vjob,'qid':q,'time_indices':t,'outputs':1,
                    'support_class_sha256':record['response_class'],'target_sha256':item['target_sha256'],
                    'feature':{'sha256':fspec.sha256,'bytes':fspec.bytes,'fortran_order':fspec.fortran_order},
                    'feature_path':self.root/fspec.relative_path,'feature_spec':fspec.private_descriptor()}
                if include_targets:
                    rows=self._array(item['source_rows']);base=self._array(self._manifest['bases']['population'])
                    self.parent._admit(112*planned['rows']+8192)
                    p.need(rows.dtype.str=='<i8' and rows.shape==(planned['rows'],)
                           and p.array_sha(rows)==item['signature']['ordered_response_source_rows_sha256']
                           and np.all(rows>=-1) and np.all(rows<len(base))
                           and base.shape==(self.geometry['time_bins'],1),'Exact selected private response source rows/base')
                    p._base_check(base,self._manifest['prepared_source']['prepared_population_response'])
                    targets=np.zeros((len(rows),1),dtype='<f8');valid=rows>=0;targets[valid]=base[rows[valid]]
                    raw=targets.tobytes();p.need(hashlib.sha256(raw).hexdigest()==item['target_sha256'],'Recoverable exact selected target bytes')
                    result['targets']=np.frombuffer(raw,dtype='<f8').reshape(targets.shape)
                yield result
            p.need(requests==self._manifest['counts']['software_callbacks'],'Complete selected request cardinality')
        except BaseException:self.parent.failed=True;raise
        finally:self._iterating=False

    def close(self):
        if not self.closed:
            for name in ('_arrays','_index_raw','_specs','_features','_classes'):
                getattr(self,name,{}).clear()
            self.parent._retained-=self._extra;self._extra=0;self.closed=True
