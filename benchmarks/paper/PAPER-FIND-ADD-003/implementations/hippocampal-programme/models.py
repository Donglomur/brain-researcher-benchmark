"""Private inert model admission and fresh per-record local inference."""
from pathlib import Path
import time
from core import WINDOWS,encoded,identity,need
from safe_io import array,capture,child,new_json,pin,strict,npy_header
from graph.runtime import validate,evaluate


def expected_inputs(family,channels):
    result={}
    if family!='clock_prior':result={'values':{'shape':[channels,15],'dtype':'float64'},'missing':{'shape':[channels,15],'dtype':'bool'}}
    if family!='neural':result['clock']={'shape':[5],'dtype':'float64'}
    return result


def admit(root,files,family,channels,policy,deadline):
    need('MODEL.json' in files,'Every model has an inert envelope')
    raw=capture(child(root,'MODEL.json'),policy['max_model_bytes'],files['MODEL.json']);model=strict(raw)
    need(type(model) is dict and set(model)=={'schema','family','graph','arrays','input_shapes','training_provenance'} and model['schema']=='h_model_v1' and model['family']==family,'Exact model/family envelope')
    need(model['input_shapes']==expected_inputs(family,channels),'Identical admitted family/channel support')
    constants={};total=len(raw);names=set()
    for name,d in model['arrays'].items():
        need(type(d) is dict and set(d)=={'path','bytes','sha256','shape','dtype'} and d['path'] not in names,'Unique inert array descriptor')
        names.add(d['path']);expected={k:d[k] for k in ('bytes','sha256')}
        need(files.get(d['path'])==expected,'Complete captured model array pin')
        total+=d['bytes'];need(total<=policy['max_model_bytes'],'Full model cap before reading constants')
        body=capture(child(root,d['path']),policy['max_array_bytes'],expected);h=npy_header(body)
        need(list(h['shape'])==d['shape'] and h['descr']==d['dtype'] and d['dtype'] in ('<f8','|u1'),'Typed primitive model constants')
        constants[name]={'shape':d['shape'],'dtype':'bool' if d['dtype']=='|u1' else 'float64'}
    limits={**policy['graph_limits'],'deadline':deadline}
    plan=validate(model['graph'],constants,model['input_shapes'],limits)
    return model,{'schema':'h_model_admission_v1','model_pin':pin(raw),'complete_model_bytes':total,'plan':plan,'output_kind':'finite threshold-centered scalar margin; class1 iff>=0','runtime_qualification':False}


def load_constants(root,model,policy):
    import numpy as np
    constants={}
    for name,d in model['arrays'].items():
        x=array(root,d,policy['max_array_bytes'])
        if d['dtype']=='|u1':
            need(np.all((x==0)|(x==1)),'Boolean constant exact0/1');x=x.astype(bool)
        else:need(np.all(np.isfinite(x)),'Finite typed constants')
        constants[name]=x
    return constants


def evaluate_model(model_root,model_files,query_root,family,role,case,channels,policy,deadline,output):
    import numpy as np
    model,admission=admit(model_root,model_files,family,channels,policy,deadline)
    constants=load_constants(model_root,model,policy)
    raw=capture(child(query_root,'QUERIES.json'),policy['max_query_metadata_bytes']);q=strict(raw)
    need(q['case']==case and len(q['records'])==100,'Full twenty-trial/five-window query set')
    records=q['records'];need(len({(r['trial'],r['window']) for r in records})==100,'Unique complete query coordinates')
    neural=array(query_root,q['arrays']['neural'],policy['max_query_array_bytes']);nuisance=array(query_root,q['arrays']['nuisance'],policy['max_query_array_bytes'])
    need(neural.shape[0]==100 and neural.shape[2]==15 and nuisance.shape==(100,2,15),'Full local input geometry')
    result=[]
    for i,r in enumerate(records):
        need(time.monotonic()<deadline,'Original phase deadline before every local inference')
        if family=='neural':values=neural[i]
        elif family=='nuisance_clock':values=nuisance[i]
        elif family in ('combined','shuffled_combined'):values=np.concatenate([neural[i],nuisance[i]],axis=0)
        else:values=None
        inputs={}
        if values is not None:
            need(not np.isinf(values).any(),'Infinite query is not missingness');missing=np.isnan(values)
            inputs={'values':np.asarray(np.where(missing,0,values),dtype='float64'),'missing':np.asarray(missing,dtype=bool)}
        if family!='neural':inputs['clock']=np.eye(5,dtype='float64')[r['window']]
        actual_shapes={k:{'shape':list(x.shape),'dtype':'bool' if x.dtype==np.dtype('bool') else 'float64'} for k,x in inputs.items()}
        need(actual_shapes==model['input_shapes'],'Actual per-record family input equals previously admitted exact shape/type')
        # evaluate snapshots immutable constants/inputs and creates a new workspace.
        # Neither query labels/IDs nor another record is passed to the graph.
        try:
            score=evaluate(model['graph'],constants,inputs,{**policy['graph_limits'],'deadline':deadline})
            if type(score) is dict:score=score['margin']
            score=float(score);need(np.isfinite(score),'Finite admitted decision margin')
            row={'status':'finite','margin':score,'prediction':int(score>=0),'reason':None}
        except Exception as error:row={'status':'failed','margin':None,'prediction':None,'reason':type(error).__name__+': '+str(error)[:300]}
        result.append({**r,**row})
    need(time.monotonic()<deadline,'Original phase deadline after final local inference')
    report={'schema':'h_private_prediction_v1','case':case,'role':role,'family':family,'model_admission':admission,'records':result,'complete':all(r['status']=='finite' for r in result),'fresh_query_workspace':True,'scientific_qualification':False}
    new_json(Path(output)/'PREDICTIONS.json',report);new_json(Path(output)/'RESULT.json',{'schema':'h_evaluation_result_v1','complete':report['complete'],'records':100,'prediction_path':'PREDICTIONS.json'})
    return report
