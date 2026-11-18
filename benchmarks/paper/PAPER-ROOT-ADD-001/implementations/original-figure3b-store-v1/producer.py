"""Explicit Figure 3b store, preserving the complete 14-session selected task.

No original payload is opened on import. The accepted full-source producer is
unchanged; its bounded writer primitives and exact source derivation are reused.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import types

import numpy as np

HERE = Path(__file__).resolve().parent
FULL_SHA = 'cd2600b8702b53486016cad8d9228050c710cc40510413f283a05f23a708b101'
FULL_READER_SHA = '58383fa148f160e3743b4696180a66ab5560a1939c45df408e9e667143c40a85'
SELECTION_SHA = '4038501cc3050e8bbd7f1968c05768f9a0ed0322725f9e167466b694965cb762'
SCOPE = 'original_figure3b_improvement'
GENERATED_SCOPE = 'generated_figure3b_store_control'
LAGS = (17,18,19)
CONTEXT_KEYS = ('session','field','family','layer','lag_index','lag_bins')
ORIGINAL_COUNTS = {'sessions':14,'jobs':42,'software_callbacks':5685,'features':14,
    'response_classes':42,'response_shards':5685,'candidate_objects':5783,'array_files':5839,
    'selected_score_cells_expected':42}


def _load(filename,digest,aliases=None):
    path = HERE.parent/'original-store-producer-v1'/filename
    with path.open('rb') as stream: raw=stream.read(131073)
    if len(raw)>131072 or hashlib.sha256(raw).hexdigest()!=digest:
        raise ValueError('Pinned complete-source store dependency')
    name='_language_figure3b_full_'+digest[:12]
    if name in sys.modules:
        module=sys.modules[name]
        if type(module) is not types.ModuleType or module.__file__!=str(path) or getattr(module,'_authenticated_source_sha256',None)!=digest:
            raise ValueError('Conflicting trusted source module')
        return module
    module=types.ModuleType(name);module.__file__,module.__package__=str(path),''
    sys.modules[name]=module;prior={}
    try:
        for key,value in (aliases or {}).items():
            prior[key]=sys.modules.get(key);sys.modules[key]=value
        exec(compile(raw,str(path),'exec',dont_inherit=True),module.__dict__)
        module._authenticated_source_sha256=digest
    except BaseException:
        sys.modules.pop(name,None);raise
    finally:
        for key,value in prior.items():
            if value is None:sys.modules.pop(key,None)
            else:sys.modules[key]=value
    return module


p = _load('producer.py',FULL_SHA)
F = _load('reader.py',FULL_READER_SHA,{'producer':p})
C,V,O,L,I = p.C,p.V,p.O,p.L,p.I
need,encoded,pin,integer = p.need,p.encoded,p.pin,p.integer


def selected_layout(row,geometry):
    rows=[]
    for item in L.iter_job_layout(row,geometry):
        if item['field']=='population' and item['layer']==5 and item['lag_index'] in LAGS:
            need(item['lag_bins']==item['lag_index']-20 and item['columns']==1,'Exact fixed Figure3b coordinate')
            rows.append(item)
    need(len(rows)==3 and [r['lag_index'] for r in rows]==list(LAGS), 'All three fixed source lags')
    return tuple(rows)


def selected_plan(source_plan,working_limit):
    census,geometry,preparation,_ = p._plan(source_plan,working_limit)
    counts={k:0 for k in ORIGINAL_COUNTS}
    array_bytes=0; session_bounds=[]
    for g,row in zip(geometry['sessions'],census['sessions']):
        jobs=selected_layout(row,g)
        features={j['feature_key_sha256']:j for j in jobs}
        classes={j['response_class']:j for j in jobs}
        need(len(features)==1 and len(classes)==3,'One shared selected X and three distinct target lineages/session')
        shards=sum(j['held_qids'] for j in classes.values())
        objects=len(features)+2*len(classes)+shards
        arrays=objects+len(classes)+1
        # Exact canonical array extents; per-class shard rows partition M.
        body=sum(128+240*j['rows'] for j in features.values()) + (128+8*g['time_bins'])
        body+=sum(3*(128+8*j['rows'])+128*j['held_qids']+8*j['rows'] for j in classes.values())
        local={'jobs':3,'software_callbacks':sum(j['held_qids'] for j in jobs),'features':len(features),
            'response_classes':len(classes),'response_shards':shards,'candidate_objects':objects,'array_files':arrays}
        for key,value in local.items():counts[key]+=value
        counts['sessions']+=1;counts['selected_score_cells_expected']+=3
        array_bytes+=body
        metadata=(objects*512+len(features)*640+len(classes)*2048+shards*128+3*512+65536)
        session_bounds.append({'session':g['id'],'counts':local,'canonical_array_bytes':body,
            'metadata_upper_bytes':metadata,'cache_constructor_preflight_bytes':objects*8192})
    original=source_plan.scope=='original_full_source'
    need(not original or counts==ORIGINAL_COUNTS,'Complete selected14-session/42-cell/5685-request roster')
    root_metadata=len(source_plan.census_raw)+len(source_plan.geometry_raw)+len(source_plan.preparation_raw)+131072
    return census,geometry,preparation,{'schema':'language-figure3b-store-layout/v1',
        'scope':SCOPE if original else GENERATED_SCOPE,'selection_sha256':SELECTION_SHA,'counts':counts,
        'sessions':session_bounds,'canonical_array_bytes':array_bytes,
        'metadata_upper_bytes':root_metadata+sum(r['metadata_upper_bytes'] for r in session_bounds),
        'logical_output_upper_bytes':array_bytes+root_metadata+sum(r['metadata_upper_bytes'] for r in session_bounds),
        'file_count':counts['array_files']+5*counts['sessions']+4,
        'source_input_loading':'Unchanged full13-member/session input loader; all actual archive/member reads charged.',
        'scientific_qualification':False,'native_execution':False}


def iter_selected_jobs(data,population=None):
    """Reuse exact original kernels; materialize only layer5 and lags-3,-2,-1."""
    if population is None:population,_=O.smooth_targets(data['fr'])
    feature=data['context'];qid=data['qid'];timing=data['timing']
    need(type(feature) is np.ndarray and feature.dtype.str=='<f8' and feature.shape==(len(qid),30,33)
         and np.isfinite(feature[:,:,5]).all(),'Exact supplied contextual PCA layer5; no refit')
    x,q=O.format_words(timing,qid,feature[:,:,5],len(population))
    for lag_index in LAGS:
        xx,yy,qq,t=O.lag_rows(population,x,data['speaker'][:,0],q,lag_index-20)
        yield {'session':data['session'],'field':'population','family':'context','layer':5,
            'lag_index':lag_index,'lag_bins':lag_index-20,'x':xx,'y':yy,'qid':qq,'time_indices':t}


class _SessionWriter(p._SessionWriter):
    def _run(self,data):
        need(data['session']==self.sid and data['geometry']==self.geometry,'Exact selected source session geometry')
        numeric=sum(v.nbytes for v in data.values() if type(v) is np.ndarray)
        n,u=self.geometry['time_bins'],self.geometry['units']
        members=sum(v['bytes'] for v in data['input_receipts'].values()) if self.original else numeric
        # Retain the full source loader/preprocessing conservative declaration.
        reserve=4*members+64*1024**2+6*8*n*(u+1)+4*8*n*30+3*self.metadata_limit+32*1024**2
        need(reserve<=self.working_limit,'Joint full-input/selected-output workspace before preprocessing')
        self.peak_working_admission=reserve
        need(not self.original or data['input_receipts']==self.prepared['input_receipts'],
             'Every original input agrees with Stage B; selection does not substitute data')
        population,units=O.smooth_targets(data['fr'])
        p._base_check(population,self.prepared['prepared_population_response'])
        p._base_check(units,self.prepared['prepared_unit_responses'])
        bases={'population':self._array(population)}
        permutation=np.random.RandomState(20).permutation(np.arange(n,dtype='<i8'))
        planned_jobs=selected_layout(self.row,self.geometry)
        for job,planned in zip(iter_selected_jobs(data,population),planned_jobs):
            cid,fkey=planned['response_class'],planned['feature_key_sha256']
            proof=p.derive_lineage(job,planned,self.geometry,self.row['support_classes'][cid],population,units,permutation)
            need(proof['base_kind']=='population','No unrelated unit base in selected store')
            if fkey in self.features:
                feature=self.features[fkey]
                need(feature['key']==planned['feature_key'] and feature['array_sha256']==proof['feature_array_sha256'],
                     'Only byte-identical selected source X sharing')
            else:
                oid,_=self._array(job['x'],'features')
                feature={'key_sha256':fkey,'key':planned['feature_key'],'object_id':oid,'array_sha256':proof['feature_array_sha256']}
                self._add('FEATURES.jsonl',feature,640);self.features[fkey]=feature
            need(cid not in self.classes,'Exactly three distinct selected response classes')
            qid_id,_=self._array(job['qid'],'qid');time_id,_=self._array(job['time_indices'],'time')
            source_rows=self._array(proof['source_rows']);shards=[]
            for label,count in zip(proof['labels'],proof['counts']):
                oid,_=self._array(job['y'][job['qid']==label],'responses')
                shards.append({'held_f64le':np.asarray([label],dtype='<f8').tobytes().hex(),'object_id':oid,'rows':int(count)})
            item={'class_sha256':cid,'signature':self.row['support_classes'][cid]['signature'],
                'qid_object':qid_id,'time_object':time_id,'source_rows':source_rows,'base_kind':'population',
                'target_sha256':proof['target_sha256'],'target_shape':list(job['y'].shape),'shards':shards}
            self._add('CLASSES.jsonl',item,2048+128*len(shards));self.classes[cid]=item;self.shards+=len(shards)
            self._add('JOBS.jsonl',{'ordinal':self.jobs,'context':{k:job[k] for k in CONTEXT_KEYS},
                'feature_id':feature['object_id'],'response_class':cid},512)
            self.jobs+=1;self.requests+=planned['held_qids'];self._metadata()
        need(self.jobs==3 and len(self.features)==1 and len(self.classes)==3
             and self.shards==self.requests==sum(j['held_qids'] for j in planned_jobs),'Complete fixed selected session')
        indexes={name:index.close() for name,index in self.indexes.items()}
        manifest={'schema':'language-figure3b-private-session-store/v1','session':self.sid,
            'scope':SCOPE if self.original else GENERATED_SCOPE,'selection_sha256':SELECTION_SHA,
            'geometry':self.geometry,'bases':bases,'indexes':indexes,'input_receipts':data['input_receipts'],
            'prepared_source':self.prepared,'counts':{'jobs':3,'software_callbacks':self.requests,'features':1,
                'response_classes':3,'response_shards':self.shards,'candidate_objects':indexes['OBJECTS.jsonl']['records'],
                'array_files':self.array_files},'array_bytes':self.array_bytes,'metadata_limit':self.metadata_limit,
            'peak_working_admission':self.peak_working_admission,'scientific_qualification':False,'native_execution':False}
        raw=encoded(manifest)
        need(len(raw)<=65536 and sum(r['bytes'] for r in indexes.values())+len(raw)<=self.metadata_limit,
             'Bounded complete selected session manifest')
        return self.out.write(self.prefix+'SESSION.json',raw),manifest


def _produce(root,source_plan,load_session,*,working_limit,output_limit,metadata_limit,archive_receipts=None,source_read_charge=0):
    census,geometry,preparation,layout=selected_plan(source_plan,working_limit)
    need(integer(metadata_limit,65536,p.MAX_META),'Finite selected per-session metadata allocation')
    output=p._Output(root,output_limit);original=source_plan.scope=='original_full_source'
    preserved={name:output.write(name,raw) for name,raw in (
        ('CENSUS.json',source_plan.census_raw),('GEOMETRY.json',source_plan.geometry_raw),('PREPARATION.json',source_plan.preparation_raw))}
    totals={k:0 for k in ORIGINAL_COUNTS};sessions=[]
    for g,row,prior,bound in zip(geometry['sessions'],census['sessions'],preparation['sessions'],layout['sessions']):
        data=load_session(g['id'])
        writer=_SessionWriter(output,g['id'],g,row,prior,working_limit,metadata_limit,None,original)
        receipt,session=writer.run(data)
        need(session['counts']==bound['counts'] and session['array_bytes']==bound['canonical_array_bytes'],
             'Exact selected census-derived output geometry and array-byte extent')
        sessions.append({'session':g['id'],'manifest':receipt,'counts':session['counts']})
        for key,value in session['counts'].items():totals[key]+=value
        totals['sessions']+=1;totals['selected_score_cells_expected']+=3
        del data,writer
    need(totals==layout['counts'],'Complete selected schedule; no favorable missing session/cell')
    result={'schema':'language-figure3b-private-store/v1','scope':layout['scope'],'selection_sha256':SELECTION_SHA,
        'source_plan_scope':source_plan.scope,'generated_job_limit':source_plan.generated_job_limit,
        'producer_source_sha256':pin(Path(__file__).read_bytes())['sha256'],
        'full_source_dependencies':{'producer.py':FULL_SHA,'reader.py':FULL_READER_SHA},
        'source_code':{k:v[1] for k,v in p.PINS.items()},'counts':totals,'sessions':sessions,
        'preserved_metadata':preserved,'weights':preparation.get('population_weights'),'layout':layout,
        'archive_receipts':archive_receipts,
        'logical_source_read_charge_bytes':source_read_charge() if callable(source_read_charge) else source_read_charge,
        'array_and_index_bytes_written_before_store_manifest':output.written,
        'gross_output_charge_before_store_manifest':output.charged,'files_before_store_manifest':output.files,
        'complete_selected_store':original,'complete_original_store':False,'complete_benchmark_ready':False,
        'native_execution':False,'scientific_qualification':False,'population_unit_identity_join_authenticated':False}
    raw=encoded(result);need(len(raw)<=131072,'Bounded selected root manifest')
    need(output.written+len(raw)<=layout['logical_output_upper_bytes'] and output.files+1==layout['file_count'],
         'Complete bounded selected store files and logical bytes before publication')
    receipt=output.write('STORE.json',raw)
    return {'store':receipt,'metadata':result,'gross_output_charge':output.charged,'written_bytes':output.written,
            'files':output.files,'scientific_qualification':False}


def prepare_generated(root,source_plan,sessions,*,working_limit,output_limit,metadata_limit):
    need(type(source_plan) is p.StorePlan and source_plan.scope=='generated_prefix_control'
         and type(sessions) is dict and 0<len(sessions)<=14,'Generated source operands cannot qualify selected original scope')
    return _produce(root,source_plan,lambda sid:sessions[sid],working_limit=working_limit,
        output_limit=output_limit,metadata_limit=metadata_limit)


def prepare_original(output_root,archive_paths,*,census_path,preparation_path,admission_bytes,
                     expected_admission_sha256,read_limit,working_limit,output_limit,metadata_limit):
    need(type(admission_bytes) is bytes and len(admission_bytes)<=16384
         and pin(admission_bytes)['sha256']==expected_admission_sha256,'Frozen selected preparation admission')
    need(type(archive_paths) is dict and set(archive_paths)=={'data_processed.zip','DNN.zip','transcription.zip'},
         'Unchanged original input archives')
    for limit in (read_limit,working_limit,output_limit,metadata_limit):need(integer(limit,1),'Finite selected preparation allocation')
    actual={'schema':'language-figure3b-store-preparation-admission/v1','scope':SCOPE,'selection_sha256':SELECTION_SHA,
        'producer_source_sha256':pin(Path(__file__).read_bytes())['sha256'],
        'full_producer_sha256':FULL_SHA,'census_sha256':p.CENSUS_PIN['sha256'],
        'preparation_sha256':p.PREPARATION_PIN['sha256'],'geometry_sha256':p.GEOMETRY_PIN['sha256'],
        'numpy_version':np.__version__,'archives':{k:str(Path(v).absolute()) for k,v in archive_paths.items()},
        'output':str(Path(output_root).absolute()),'read_limit':read_limit,'working_limit':working_limit,
        'output_limit':output_limit,'metadata_limit':metadata_limit,'model_execution':False,'native_execution':False}
    need(L.parse(admission_bytes)==actual and encoded(actual)==admission_bytes,'Exact selected source/runtime/path/budget admission before archive I/O')
    plan=p.StorePlan(p.read_metadata(census_path,p.CENSUS_PIN),
        p.read_metadata(HERE.parent/'original-inputs-v1/source-bindings.json',p.GEOMETRY_PIN),
        p.read_metadata(preparation_path,p.PREPARATION_PIN),'original_full_source',None)
    _,_,prior,_=selected_plan(plan,working_limit)
    with I.ArchiveInputs(archive_paths,read_limit=read_limit,working_limit=working_limit) as source:
        need(source.archive_receipts==prior['archive_receipts'],'Same complete original archives as accepted Stage B')
        need(source.population_weights()==prior['population_weights'],'Original full-byte/header weight receipts preserved')
        return _produce(output_root,plan,source.load_session,working_limit=working_limit,
            output_limit=output_limit,metadata_limit=metadata_limit,archive_receipts=source.archive_receipts,
            source_read_charge=lambda:source.charged)
