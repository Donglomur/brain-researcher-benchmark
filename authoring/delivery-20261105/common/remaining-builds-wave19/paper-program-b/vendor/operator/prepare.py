"""Deterministic input-only preparation. No prediction or scientific statistic."""
import argparse,csv,io,math,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
from delivery_io import need,read,decode,put,fresh,pin,resolve
from protocol import SESSIONS,FAMILIES,PROTOCOL_SHA,feature_member
from array_io import fresh_output


def numeric(raw,shape,allow_nan=False):
    f=io.BytesIO(raw);v=np.lib.format.read_magic(f)
    need(v in ((1,0),(2,0)),'Primitive NPY version')
    reader=np.lib.format.read_array_header_1_0 if v==(1,0) else np.lib.format.read_array_header_2_0
    observed,_,dtype=reader(f,max_header_size=4096)
    need(tuple(observed)==tuple(shape) and dtype.kind in 'iuf' and dtype.fields is None and
         f.tell()+math.prod(shape)*dtype.itemsize==len(raw),'Exact numeric header/payload extent')
    a=np.load(io.BytesIO(raw),allow_pickle=False,max_header_size=4096).astype(np.float64)
    need(not np.isinf(a).any() and (allow_nan or np.isfinite(a).all()),'Allowed finite/lexical-missing operands')
    return a


def prepare(selected,output):
    fresh_output(output);root=Path(selected)
    selection_raw=read(root/'SELECTION.json',1000000);sel=decode(selection_raw);need(sel['schema']=='language_selected_v1','Source selection')
    census=decode(read(Path(__file__).with_name('ACQUISITION.json'),500000))
    headers={r['member']:r for r in census['selected_members']}
    expected=set(headers)|{f'transcription/cleaned/{s}.csv' for s in SESSIONS}
    need(set(sel['files'])==expected,'Complete selected source pool')
    def get(name):
        r=sel['files'][name];need(r['path']==name,'Exact member path')
        return read(resolve(root,name),100000000,{k:r[k] for k in ('bytes','sha256')})
    out=fresh(output);design={'schema':'language_design_v1','protocol_sha256':PROTOCOL_SHA,'source_selection':pin(selection_raw),'sessions':{}}
    for s,g in SESSIONS.items():
        values={}
        for f,member in [('fr',f'data_processed/{s}/fr_matrix.npy'),('speaker',f'data_processed/{s}/speaker_matrix.npy')]+[(f,feature_member(s,f)) for f in FAMILIES]:
            a=numeric(get(member),headers[member]['shape'],f in ('sem_syn','word2vec','syn'))
            if f=='speaker':a=a[:,0];need(np.isin(a,[0,1]).all(),'Speaker column0 binary')
            elif f in FAMILIES:
                a=a.reshape(g['word_rows'],30,-1)
                if f in ('sem_syn','word2vec','syn'):
                    valid=~np.isnan(a[:,0,0]);need(np.isfinite(a[valid]).all(),'Author first-component lexical missingness rule')
                else:need(np.isfinite(a).all(),'Complete LLM PCA values')
            values[f]=a
        rows=list(csv.DictReader(io.StringIO(get(f'transcription/cleaned/{s}.csv').decode('utf-8-sig'))))
        need(len(rows)==g['word_rows'],'Word roster matches every feature row')
        timing=np.asarray([[float(r['start_time']),float(r['end_time'])] for r in rows]);qid_float=np.asarray([float(r['qid']) for r in rows])
        need(np.isfinite(timing).all() and np.all(timing>=0) and np.all(timing[:,1]>=timing[:,0]) and
             np.all(timing[:,1]*10<=g['time_bins']) and np.isfinite(qid_float).all() and np.all(qid_float==np.floor(qid_float)) and
             np.all((qid_float>=0)&(qid_float<99990)),'Finite in-clock word times and sentence identities')
        values['timing']=timing;values['qid']=qid_float.astype(np.int64)
        files={}
        for f,a in values.items():
            name=f'{s}.{f}.npy';target=out/name
            with target.open('xb') as stream:np.save(stream,a,allow_pickle=False)
            target.chmod(0o444);files[f]={'path':name,**pin(read(target,100000000)),'shape':list(a.shape)}
        design['sessions'][s]={'geometry':g,'files':files}
    put(out/'DESIGN.json',design,500000)


def load_session(root,design,s):
    result={}
    for f,r in design['sessions'][s]['files'].items():
        raw=read(resolve(root,r['path']),100000000,{k:r[k] for k in ('bytes','sha256')})
        result[f]=numeric(raw,r['shape'],f in ('sem_syn','word2vec','syn'))
    result['qid']=result['qid'].astype(np.int64)
    return result

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--selected',required=True);a.add_argument('--output',required=True);v=a.parse_args();prepare(v.selected,v.output)
