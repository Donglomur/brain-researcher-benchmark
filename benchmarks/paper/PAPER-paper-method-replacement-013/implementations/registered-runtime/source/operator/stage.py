"""One fresh case projection. Static files do not enforce execution isolation."""
import sys,argparse,hashlib,io
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'public'))
from contract import *
from array_io import array,finite
import numpy as np
from paper_asset import captured_paper

def segments(rows):
    starts=[]
    for i,r in enumerate(rows):
        if i==0 or r['recording']!=rows[i-1]['recording'] or r['start_tick']!=rows[i-1]['stop_tick']:starts.append(i)
    return starts+[len(rows)]

def npy_size(shape,dtype):
    b=io.BytesIO();np.lib.format.write_array_header_1_0(b,{'descr':dtype,'fortran_order':False,'shape':tuple(shape)})
    return len(b.getvalue())+int(np.prod(shape,dtype=object))*np.dtype(dtype).itemsize

def windows(rows,records,observations,name):
    """Future deterministic extraction of explicitly qualified source ticks."""
    vals=[None]*len(rows);groups={}
    for i,row in enumerate(rows):groups.setdefault(row['recording'],[]).append((i,row))
    source='neural' if name in ('neural_history','neural_current') else name
    for rid,selected in groups.items():
        r=records[rid]
        with array(observations,r['arrays'][source]) as a:
            for i,row in selected:
                t=row['start_tick'];b=t//10
                if name=='neural_history':value=a[t-30:t]
                elif name=='neural_current':value=a[t:t+10]
                elif name=='video':value=a[b-3:b+1]
                else:value=a[b]
                vals[i]=np.array(value,copy=True)
    return np.stack(vals)

def target_values(case,rows,records,observations):
    k=case['definition']['kind']
    if k=='counts':return windows(rows,records,observations,'neural_current')
    if k=='classification':return windows(rows,records,observations,'speed_class')
    speed=windows(rows,records,observations,'speed')
    return np.concatenate((speed,windows(rows,records,observations,'gaze')),axis=1) if k=='joint' else speed

def stage(q,target,observations,cid,arm,output,max_bytes,production=True):
    query(q,production);target_binding(q,target)
    require(arm in ARMS,'arm');out=fresh(output)
    c=next((c for c in q['cases'] if c['definition']['id']==cid),None);require(c is not None,'one known case')
    r={r['id']:r for r in target['bridge']['recordings']};captures={};modalities=visible_modalities(c['definition']);plan={};test_segments=None
    for split in ('train','validation','test'):
        rows=[x for x in rows_for(q,c) if x['split']==split];n=len(rows);neurons=q['cohorts'][c['definition']['cohort']]['neurons']
        for name in modalities:
            selected=rows
            outname=split+'_'+name+'.npy'
            if split=='test' and name=='neural_history' and c['definition']['kind']=='counts':
                test_segments=segments(rows);selected=[rows[i] for i in test_segments[:-1]];outname='test_initial_neural_history.npy'
            if name in ('neural_history','neural_current'):shape=[len(selected),30 if name=='neural_history' else 10,neurons];dtype='<i4'
            elif name=='video':
                dims={tuple(r[x['recording']]['arrays']['video']['shape'][1:]) for x in selected};require(len(dims)==1,'common frame geometry')
                shape=[n,4,*next(iter(dims))];dtype='|u1'
            else:shape=[n,2 if name=='gaze' else 1];dtype='<f8'
            plan[outname]={'shape':shape,'dtype':dtype,'rows':selected,'name':name,'bytes':npy_size(shape,dtype)}
        if split!='test':
            kind=c['definition']['kind'];shape=[n,10,neurons] if kind=='counts' else [n,3 if kind=='joint' else 1];dtype='<i4' if kind in ('counts','classification') else '<f8'
            plan[split+'_labels.npy']={'shape':shape,'dtype':dtype,'rows':rows,'name':None,'bytes':npy_size(shape,dtype)}
    if c['definition']['kind']=='counts' and test_segments is None:test_segments=segments([x for x in rows_for(q,c) if x['split']=='test'])
    publiccase={'schema':'neuroformer_case_v1','task_id':TASK,'case_id':cid,'definition':c['definition'],'policy':c['policy'],
      'output_shape':c['output_shape'],'class_centers':c['class_centers'],'visible_modalities':list(modalities),
      'row_order':'same as input arrays; private source indices withheld','test_labels_included':False,
      'test_rollout_segment_offsets':test_segments,'generation_history':'only initial true context at segment starts; update all subsequent neural context from own generated counts'}
    captures['CASE.json']=encode(publiccase)
    for name in ('TASK.md','PROTOCOL.json','PANEL.json','submission.schema.json','reference_linear.py','io_contract.py','DEPENDENCIES.md','requirements.txt'):
        captures[name]=capture(ROOT/'public'/name)
    captures.update(captured_paper(ROOT))
    if arm=='paper_data_official_code':
        from author_source import captured_source,captured_notices
        captures.update({'official_code/'+name:b for name,b in captured_source().items()})
        captures.update({'official_code/'+name:b for name,b in captured_notices().items()})
    planned_pins=[{'path':k,'bytes':p['bytes'],'sha256':'0'*64} for k,p in plan.items()]+[{'path':k,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for k,b in captures.items()]
    planned_view=encode({'schema':'neuroformer_view_v1','arm':arm,'case_id':cid,'files':planned_pins,'runtime_isolation_qualified':False})
    require(type(max_bytes) is int and sum(p['bytes'] for p in plan.values())+sum(map(len,captures.values()))+len(planned_view)<=max_bytes,'full projection cap before array reads')
    # Future staging memory is bounded by the explicit whole-view cap. No output
    # exists on admission failure; operator must budget that RAM separately.
    for name,p in plan.items():
        a=windows(p['rows'],r,observations,p['name']) if p['name'] else target_values(c,p['rows'],r,observations)
        require(list(a.shape)==p['shape'] and a.dtype.str==p['dtype'],'planned projection geometry')
        b=io.BytesIO();np.save(b,a,allow_pickle=False);captures[name]=b.getvalue();require(len(captures[name])==p['bytes'],'planned NPY size')
    pins=[{'path':k,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for k,b in captures.items()]
    view=encode({'schema':'neuroformer_view_v1','arm':arm,'case_id':cid,'files':pins,'runtime_isolation_qualified':False})
    require(type(max_bytes) is int and sum(map(len,captures.values()))+len(view)<=max_bytes,'full projection cap before writes')
    out.mkdir(mode=0o700)
    for k,b in captures.items():
        (out/k).parent.mkdir(parents=True,exist_ok=True)
        (out/k).write_bytes(b)
    (out/'VIEW.json').write_bytes(view)
    return json.loads(view)

def main():
    a=argparse.ArgumentParser(description=__doc__)
    for k in ('query','query-sha256','target','observations','case-id','arm','output'):a.add_argument('--'+k,required=True)
    a.add_argument('--max-bytes',type=int,required=True);x=a.parse_args();b=capture(x.query);require(hashlib.sha256(b).hexdigest()==x.query_sha256,'trusted query capture')
    stage(decode(b),load(x.target),x.observations,x.case_id,x.arm,x.output,x.max_bytes)
if __name__=='__main__':main()
