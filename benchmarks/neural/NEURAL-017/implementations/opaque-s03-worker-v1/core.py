"""Narrow, repository-usable binding for the original full-support S03 worker.

Only project_views is admitted. Existing numerical source is captured by exact
identity; no reference/scoring branch or general campaign entry is exposed.
"""
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time
import types

BINDINGS_PIN={'bytes': 2160, 'sha256': '3bc37ceff333b6f92ad5456ec8c7b86e8f0ecd5b9508d03fdabeb6cffc4509b8'}
PUBLIC_CAP=256*2**20
ARCHIVE_CAP=512*2**20
WRITE_CAP=6*2**30
READ_CAP=8*2**30
CONDITIONS=('intact','within_condition_shuffle','context_only','training_rate_only','metadata_neutral')
NLB_ROLES=('contracts','arrays','programme','views','opaque_s03','worker')
INPUT_NAMES={'input/export_receipt','input/opaque_public','input/original_shuffle','input/original_split',
 'input/original_support','input/private_binding','input/protected_shuffle_seed',
 'opaque/handoff','opaque/shuffle','opaque/split','opaque/support'}
OUTPUTS={c+'_'+kind:c+'_'+kind+'.npz'for c in CONDITIONS for kind in ('training','query')}
OUTPUTS.update(support='support.json',protected_map='protected_map.npz')


def need(ok,why):
    if not ok:raise ValueError(why)


def encode(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n').encode()


def decode(body):
    def pairs(items):
        out={}
        for key,value in items:
            need(key not in out,'Unique JSON fields');out[key]=value
        return out
    return json.loads(body,object_pairs_hook=pairs,
        parse_constant=lambda _ :(_ for _ in ()).throw(ValueError('Finite JSON')))


def byte_pin(body):return {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}


def snapshot(path,expected,cap):
    """Retained stable single-file snapshot primitive; no cumulative raw cache."""
    path=Path(path).absolute()
    need(all(not p.is_symlink()for p in (path,*path.parents)),'Unlinked selected file')
    before=path.lstat()
    need(stat.S_ISREG(before.st_mode)and before.st_nlink==1 and 0<before.st_size<=cap,'Bounded ordinary selected file')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb')as stream:body=stream.read(before.st_size+1);after=os.fstat(stream.fileno())
    stamp=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    need(stamp(before)==stamp(after)==stamp(path.lstat())and len(body)==before.st_size,'Stable complete snapshot')
    need(byte_pin(body)==expected,'Selected content identity')
    return body


def load_sources(component_root,dependency_root):
    """Only six pinned NLB modules; package search path is deliberately empty."""
    root=Path(component_root);deps=Path(dependency_root)
    manifest=decode(snapshot(root/'SOURCE_BINDINGS.json',BINDINGS_PIN,65536))
    need(manifest['schema']=='NLB017_S03_dependency_bindings_v1','Exact dependency contract')
    rows={r['role']:r for r in manifest['source_files']}
    need(set(rows)==set(NLB_ROLES)|{'delivery'}and len(rows)==len(manifest['source_files']),'Exact numerical source closure')
    prefix='_nlb017_s03_selected'
    need(not any(n==prefix or n.startswith(prefix+'.')for n in sys.modules),'No preloaded selected source package')
    package=types.ModuleType(prefix);package.__path__=[];sys.modules[prefix]=package
    modules={}
    for role in (*NLB_ROLES,'delivery'):
        row=rows[role];relative=Path(row['path'])
        need(not relative.is_absolute()and '..'not in relative.parts,'Fixed relative dependency')
        path=deps/relative;body=snapshot(path,{k:row[k]for k in ('bytes','sha256')},262144)
        name=prefix+'.'+role;module=types.ModuleType(name);module.__file__=str(path);module.__package__=prefix
        sys.modules[name]=module;setattr(package,role,module)
        exec(compile(body,str(path),'exec'),module.__dict__);modules[role]=module
    return types.SimpleNamespace(**modules,source_rows=rows,prefix=prefix)


def compilation(value):
    need(value['schema']=='NLB017_opaque_S03_compilation_v1'and value['stage']=='S03'
         and value['conditions']==list(CONDITIONS)and value['complete_training_trials']==1721
         and value['complete_query_trials']==574,'Original complete S03 compilation')
    need(value['full_campaign_compiled']is False and value['E_products_issued']is False
         and value['native_or_scientific_qualified']is False
         and value['requires_independent_authority_and_runtime']is True,'No inferred campaign authority')
    rows=value['initial_artifacts'];need(type(rows)is list and len(rows)==11,'Exact11input roster')
    table={r['name']:r['pin']for r in rows}
    need(set(table)==INPUT_NAMES and len({r['pin']['path']for r in rows})==11,'Distinct fixed input roles')
    for row in rows:
        expected_role='public_training'if row['name']=='input/opaque_public'else 'protected_shuffle_seed'if row['name']=='input/protected_shuffle_seed'else 'operator_private_metadata'
        need(row['role']==expected_role,'Original input custody role')
    request=value['request'];need(set(request)=={'role','body'}and request['role']=='project_views','Only original projection worker role')
    names={'public':'input/opaque_public','planned_support':'opaque/support','shuffle_commitment':'opaque/shuffle',
           'protected_shuffle_seed':'input/protected_shuffle_seed','opaque_handoff':'opaque/handoff'}
    need(request['body']=={k:table[v]for k,v in names.items()},'Exact resolved request descriptors')
    expected_outputs={c+'_'+kind:{'name':'prepared/'+c+'/'+kind,'role':'public_'+kind}
        for c in CONDITIONS for kind in ('training','query')}
    expected_outputs.update(support={'name':'prepared/support','role':'metadata'},
        protected_map={'name':'prepared/private_map','role':'protected_seed'})
    need(value['outputs']==expected_outputs and value['action']['outputs']==expected_outputs
         and value['action']['role']=='project_views'and value['action']['job']=='prepare/views',
         'Exact12product union and original custody roles')
    return table


class GuardedInputs:
    def __init__(self,store,table):
        self.store=store;self.table={d['path']:d for d in table.values()}
        self.seed_descriptor=table['input/protected_shuffle_seed'];self.seed=None
    def read(self,d,cap):
        need(self.table.get(d['path'])==d,'No undeclared operand read')
        raw=self.store.read(d,cap)
        if d==self.seed_descriptor:
            need(len(raw)==32,'Existing protected seed');self.seed=raw
        return raw
    def json(self,d,cap=8*2**20):return decode(self.read(d,cap))


def array_digest(array):
    import numpy as np
    value=np.asarray(array);h=hashlib.sha256()
    if value.ndim==0:h.update(value.tobytes(order='C'))
    else:
        for start in range(0,len(value),16):h.update(value[start:start+16].tobytes(order='C'))
    return h.hexdigest()


def array_info(value):
    return {'shape':list(value.shape),'dtype':value.dtype.str,'nbytes':value.nbytes,'sha256':array_digest(value)}


def admit_public(sources,input_root,public_pin,expected_fingerprint):
    """Return compact reference metadata/hashes, never retain the public array."""
    import numpy as np
    raw=snapshot(Path(input_root)/public_pin['path'],{k:public_pin[k]for k in ('bytes','sha256')},PUBLIC_CAP)
    packet=sources.arrays.load_arrays(raw,sources.delivery.PUBLIC_KEYS,cap=PUBLIC_CAP)
    del raw
    sources.delivery.validate_public(packet,expected_fingerprint)
    info={k:array_info(v)for k,v in packet.items()}
    query_rows=[array_digest(packet['eval_counts_heldin'][i])for i in range(574)]
    totals=np.asarray(packet['train_counts_heldout'],dtype=np.float64).sum(axis=(0,1))
    summary={'arrays':info,'query_row_sha256':query_rows,'rate_totals':array_info(totals),
        'bin_opportunities':array_info(np.asarray(1721*140)),
        'public_fingerprint':expected_fingerprint,'decoded_array_nbytes':sum(v.nbytes for v in packet.values())}
    # The worker will independently recapture/reload the exact public operand.
    # This function returns no array, raw archive or view object.
    del totals,packet
    return summary


def expected_fields(condition,kind,sources):
    if condition=='training_rate_only':
        return {'train_count_totals','train_bin_opportunities','heldout_unit_ids'}if kind=='training'else {
            'eval_trial_ids','heldout_unit_ids','bin_left_edges_ms','eval_valid_mask'}
    fields=set(sources.views.BASE_T if kind=='training'else sources.views.BASE_Q)
    if condition=='context_only':fields-={'train_counts_heldin','eval_counts_heldin','heldin_unit_ids'}
    return fields


def validate_view(sources,packet,condition,kind,summary,donor):
    need(set(packet)==expected_fields(condition,kind,sources),'Exact physical information-view field union')
    for name,array in packet.items():
        expected=summary['rate_totals']if name=='train_count_totals'else summary['bin_opportunities']if name=='train_bin_opportunities'else summary['arrays'][name]
        need(list(array.shape)==expected['shape']and array.dtype.str==expected['dtype'],'Full original shape/type: '+name)
        if condition=='within_condition_shuffle'and name=='eval_counts_heldin':
            need([array_digest(array[i])for i in range(574)]==[summary['query_row_sha256'][int(i)]for i in donor],
                 'Exact original query donor content, no new shuffle or dropped trial')
        else:need(array_digest(array)==expected['sha256'],'Exact original view content: '+name)


def validate_products(sources,input_store,output_root,products,planned,summary,table,seed):
    """Sequential private validation; release every decoded/archive before next."""
    import numpy as np
    need(set(products)==set(OUTPUTS),'Complete original12products')
    for name,d in products.items():need(d['path']==OUTPUTS[name],'Exact owned output filename')
    original=input_store.json(table['input/original_support']);commitment=input_store.json(table['input/original_shuffle'])
    binding=input_store.json(table['input/private_binding'])
    # Deterministic validation of the already-produced protected map. This
    # repeats the frozen rule, never draws or selects a replacement seed.
    physical=sources.views.shuffle_map(seed,original,commitment)
    aliases=binding['core']['axes']['eval_trial_ids']['opaque_in_source_order']
    order=np.asarray(sorted(range(574),key=aliases.__getitem__),dtype=np.int64)
    inverse=np.empty(574,dtype=np.int64);inverse[order]=np.arange(574)
    expected_donor=inverse[physical[order]]
    def captured(name,cap):
        d=products[name];return snapshot(Path(output_root)/d['path'],{k:d[k]for k in ('bytes','sha256')},cap)
    raw=captured('protected_map',ARCHIVE_CAP);map_packet=sources.arrays.load_arrays(raw,{'donor_index'},cap=ARCHIVE_CAP);del raw
    donor=map_packet['donor_index'];need(donor.dtype==np.int64 and donor.shape==(574,)
        and np.array_equal(donor,expected_donor),'Same protected donor map under exact opaque conjugation')
    donor=donor.copy();del map_packet
    raw=captured('support',2*2**20);support=decode(raw);del raw
    need(support=={**planned,'panel_fingerprint':summary['public_fingerprint']},'Exact full supported output identity')
    checks={}
    for condition in CONDITIONS:
        for kind in ('training','query'):
            name=condition+'_'+kind;raw=captured(name,ARCHIVE_CAP)
            packet=sources.arrays.load_arrays(raw,expected_fields(condition,kind,sources),cap=ARCHIVE_CAP);del raw
            validate_view(sources,packet,condition,kind,summary,donor)
            checks[name]={'decoded_array_nbytes':sum(a.nbytes for a in packet.values()),'fields':sorted(packet),
                'complete_support':True,'original_content_verified':True}
            del packet
    return {'views':checks,'same_seed_and_donor_relation':True,'full_support':True,
            'array_validation_scope':'all10viewarchives, protectedmap and support; sequential snapshots'}


def run_projection(sources,compiled,input_root,output_root,expected_fingerprint,deadline,*,clock=time.monotonic):
    """One original S03 role; no model, reference, target, score or seed producer."""
    table=compilation(compiled);C=sources.contracts
    for d in table.values():C.descriptor(d)
    need(table['input/protected_shuffle_seed']['bytes']==32,'Existing seed descriptor')
    need(clock()<deadline,'Original S03 deadline before admission')
    summary=admit_public(sources,input_root,table['input/opaque_public'],expected_fingerprint)
    need(clock()<deadline,'Original deadline after complete public admission')
    custody=C.Custody('opaque_S03_projection')
    budget=C.Budget(dict(cpu_seconds=160,read_bytes=READ_CAP,write_bytes=WRITE_CAP,
        stream_bytes=65536,model_tokens=0,created_files=16,tool_calls=0),deadline,clock=clock,custody=custody)
    inputs=GuardedInputs(C.Store(Path(input_root),budget,custody),table)
    outputs=C.Store(Path(output_root),budget,custody)
    planned=inputs.json(table['opaque/support']);C.need(sources.programme.planned_support(planned),'Full planned support')
    events=[]
    def trace(event):
        need(len(events)<4 and len(encode(event))<=4096,'Bounded source projection events');events.append(event)
    # Fixed role checked above; unselected lazy reference/scoring imports have
    # no package source path and cannot be resolved by this captured loader.
    products=sources.worker.execute(compiled['request'],inputs,outputs,trace)
    need(inputs.seed is not None,'Original worker consumed the existing protected seed')
    validation=validate_products(sources,inputs,output_root,products,planned,summary,table,inputs.seed)
    budget.guard();custody.raise_if_failed()
    need(len(events)==1 and events[0]['same_fixed_map_for_all_arms']is True,'Original full-view trace')
    return {'schema':'NLB017_owned_S03_result_v1','products':products,'validation':validation,
        'public_admission':{'fingerprint':expected_fingerprint,'decoded_array_nbytes':summary['decoded_array_nbytes'],
                            'captured_bytes_independently_validated_before_worker':True},
        'support':{'training_trials':1721,'query_trials':574,'bins':140,'bin_ms':5,'observed_units':137,'withheld_units':45},
        'events':events,'source_budget_used':dict(budget.used),'source_budget_reserved':dict(budget.reserved),
        'custody':custody.snapshot(),'seed_generated':False,'protected_seed_body_published':False,
        'full_campaign_admitted':False,'scientific_score_produced':False,'participant_executed':False,
        'native_understanding_established':False,'benchmark_ready':False}
