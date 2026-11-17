"""Fixed native comparator fit/query entry. Requires separately selected native authority.
Only operator-produced, hash-bound state is deserialized; candidate state is never loaded.
"""
import argparse,copy,hashlib,json,pickle,random,sys,types
from pathlib import Path
from contract import Budget,encode,parse,pin,need,job_check,recipe,filename
def actual_api():
    import numpy as np,torch,cebra
    from importlib.metadata import version
    need(version('cebra')=='0.4.0','fixed prospective CEBRA release')
    import cebra.integrations.sklearn.cebra as estimator
    import cebra.solver.base as solver
    for module,digest in [(estimator,'26241ffc6bd67dede69661e71dbae357cc4312102fbfed082ecf7ba7e38ee218'),(solver,'d1892045f7eab57c9b3758a4584db02c5de327b4a68f6a49a934bc977f289e17')]:
        need(hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()==digest,'exact CEBRA implementation')
    sys.path.insert(0,str(Path(__file__).parent/'author_source'))
    sys.path.insert(0,str(Path(__file__).parent/'author_source/examples/rat_hippocampus'))
    import MARBLE
    from rat_utils import convert_spikes_to_rates
    return {'np':np,'torch':torch,'cebra':cebra,'marble':MARBLE,'convert':convert_spikes_to_rates}
def array(raw,shape,api,interface):
    h=interface.npy_header(raw,shape)
    return api['np'].frombuffer(raw,dtype=h['dtype'],offset=h['offset']).reshape(shape).copy()
def embedding(raw,job,api):
    np=api['np'];out=np.asarray(raw,dtype='<f4')
    need(out.shape==(job['input_shape'][0]-1,job['coordinate']['dimension'])and np.isfinite(out).all(),'complete finite embedding')
    import io
    stream=io.BytesIO();np.save(stream,out,allow_pickle=False);return stream.getvalue()
def rng_profile(api):
    t=api['torch'];cuda=t.cuda;available=cuda.is_available()
    count=cuda.device_count()if available else 0
    return {'python':list(sys.version_info[:3]),'numpy':api['np'].__version__,'torch':t.__version__,
            'cuda_available':available,'current_device':cuda.current_device()if available else None,
            'devices':[{'ordinal':i,'name':cuda.get_device_name(i),'capability':list(cuda.get_device_capability(i))}for i in range(count)]}
def capture_rng(api):
    t=api['torch'];profile=rng_profile(api)
    return {'schema':'post_fit_rng_v1','profile':profile,'python':random.getstate(),'numpy':api['np'].random.get_state(),
            'torch_cpu':t.get_rng_state(),'torch_cuda':t.cuda.get_rng_state_all()if profile['cuda_available']else[]}
def restore_rng(value,api):
    need(set(value)=={'schema','profile','python','numpy','torch_cpu','torch_cuda'}and value['schema']=='post_fit_rng_v1','closed RNG schema')
    need(value['profile']==rng_profile(api),'same RNG software/device profile')
    need(len(value['torch_cuda'])==len(value['profile']['devices']),'complete per-device RNG state')
    random.setstate(value['python']);api['np'].random.set_state(value['numpy']);api['torch'].set_rng_state(value['torch_cpu'])
    if value['profile']['cuda_available']:api['torch'].cuda.set_rng_state_all(value['torch_cuda'])
def construction(graph):
    v={'signal_width':int(graph.x.shape[1]),'position_width':int(graph.pos.shape[1]),'degree':float(graph.degree),
       'dim_man':int(graph.dim_man)if hasattr(graph,'dim_man')else None}
    constructor_view(v) # same validation before retention
    return v
def constructor_view(v):
    from math import isfinite
    need(set(v)=={'signal_width','position_width','degree','dim_man'},'exact training construction fields')
    need(all(type(v[k])is int and v[k]>0 for k in('signal_width','position_width'))and type(v['degree'])in(int,float)and isfinite(v['degree'])and v['degree']>=0,'training construction geometry')
    need(v['dim_man']is None or(type(v['dim_man'])is int and v['dim_man']>0),'training manifold width')
    # Original fixed diffusion=False constructor reads only these metadata fields.
    # No synthetic tensor/graph enters either original scientific transform.
    out=types.SimpleNamespace(x=types.SimpleNamespace(shape=(0,v['signal_width'])),pos=types.SimpleNamespace(shape=(0,v['position_width'])),degree=v['degree'])
    if v['dim_man']is not None:out.dim_man=v['dim_man']
    return out
def fit(job,input_root,output,budget,interface,api):
    c=job_check(job,'fit');np=api['np'];torch=api['torch'];output=Path(output)
    state=output/'state';emb=output/'embeddings';state.mkdir();emb.mkdir()
    raw=budget.read(Path(input_root)/'neural.npy',job['input']['bytes'],job['input'])
    train=array(raw,job['input_shape'],api,interface)
    labels=None
    if job['labels']is not None:
        raw=budget.read(Path(input_root)/'labels.npy',job['labels']['bytes'],job['labels'])
        labels=array(raw,(job['input_shape'][0],3),api,interface)
    random.seed(0);np.random.seed(0);torch.manual_seed(0)
    if torch.cuda.is_available():torch.cuda.manual_seed_all(0)
    work=state/'native';work.mkdir()
    native_params=None;training_construction=None
    if c['method']=='marble':
        graph,_,pca=api['convert'](train.T,pca_n=20 if c['dimension']==32 else 10,kernel_width=10)
        model=api['marble'].net(graph,params=recipe(c))
        model.fit(graph,outdir=str(work))
        need(model.training is False,'original MARBLE fit must finish in eval mode')
        result=model.transform(graph).emb.detach().cpu().numpy()
        rng=capture_rng(api);training_construction=construction(graph)
        native_params=copy.deepcopy(model.params)
        model_path=work/('best_model_'+model.timestamp+'.pth')
        # Native fit chooses this exact checkpoint; no latest-directory search.
        pca_raw=pickle.dumps(pca);budget.write(state/'training_pca.pkl',pca_raw)
        pca_pin=pin(pca_raw)
    else:
        model=api['cebra'].CEBRA(**recipe(c))
        if labels is None:model.fit(train)
        else:model.fit(train,labels)
        result=model.transform(train)[:-1]
        rng=capture_rng(api)
        model_path=work/'model.pt'
        model.save(str(model_path),backend='sklearn')
        pca_pin=None
    rng_raw=pickle.dumps(rng);need(len(rng_raw)<=job['limits']['rng_member_bytes'],'bounded full post-fit RNG state')
    rng_pin=budget.write(state/'post_fit_rng.pkl',rng_raw)
    model_raw=budget.read(model_path,job['limits']['model_member_bytes'])
    out_pin=budget.write(emb/filename(c,'fit'),embedding(result,job,api))
    receipt={'schema':'marble_comparator_state_v1','coordinate':c,'protocol':job['protocol'],'source':job['source'],'recipe':recipe(c),
             'training_input':job['input'],'training_labels':job['labels'],'training_embedding':out_pin,
             'checkpoint':{'relative':str(model_path.relative_to(state)),**pin(model_raw)},'pca':pca_pin,
             'rng':rng_pin,'rng_profile':rng['profile'],'training_construction':training_construction,
             'native_params':native_params,'model_mode':'eval','serialization':'marble-selected-best+PCA'if c['method']=='marble'else'cebra-0.4.0-sklearn',
             'historical_replay':False,'native_parity_qualified':False}
    encoded=encode(receipt);need(len(encoded)<=job['limits']['state_metadata_bytes'],'bounded full state metadata')
    budget.write(state/'STATE.json',encoded)
    return receipt
def query(job,input_root,state_root,output,budget,interface,api):
    c=job_check(job,'query');state=Path(state_root);output=Path(output);(output/'embeddings').mkdir()
    raw=budget.read(state/'STATE.json',job['limits']['state_metadata_bytes'],job['closure']['state_metadata'])
    closed=parse(raw)
    for k,v in [('schema','marble_comparator_state_v1'),('coordinate',c),('protocol',job['protocol']),('source',job['source']),('recipe',recipe(c)),('model_mode','eval')]:
        need(closed.get(k)==v,'closed fit identity '+k)
    need(closed['training_embedding']==job['closure']['training_embedding'],'original training output identity')
    cp=closed['checkpoint'];need(cp['relative'].startswith('native/')and Path(cp['relative']).name==cp['relative'][7:],'exact checkpoint member')
    expected={k:cp[k]for k in('bytes','sha256')};budget.read(state/cp['relative'],job['limits']['model_member_bytes'],expected)
    raw=budget.read(Path(input_root)/'neural.npy',job['input']['bytes'],job['input'])
    test=array(raw,job['input_shape'],api,interface)
    rng=pickle.loads(budget.read(state/'post_fit_rng.pkl',job['limits']['rng_member_bytes'],closed['rng']))
    need(rng['profile']==closed['rng_profile'],'RNG metadata/body identity')
    if c['method']=='marble':
        need(closed['serialization']=='marble-selected-best+PCA'and closed['pca']is not None,'MARBLE closed state')
        pca=pickle.loads(budget.read(state/'training_pca.pkl',closed['pca']['bytes'],closed['pca']))
        model=api['marble'].net(constructor_view(closed['training_construction']),loadpath=str(state/cp['relative']))
        expected_params=closed['native_params']
        need(model.params==expected_params,'all restored fit architecture parameters')
        model.eval()
        need(model.training is False,'explicit restored eval mode')
        restore_rng(rng,api)
        graph,_,_=api['convert'](test.T,pca=pca,kernel_width=10)
        result=model.transform(graph).emb.detach().cpu().numpy()
    else:
        need(closed['serialization']=='cebra-0.4.0-sklearn'and closed['pca']is None and closed['native_params']is None and closed['training_construction']is None,'CEBRA closed state')
        model=api['cebra'].CEBRA.load(str(state/cp['relative']),backend='sklearn')
        need(model.get_params()==recipe(c) or all(model.get_params().get(k)==v for k,v in recipe(c).items()),'restored fixed estimator recipe')
        restore_rng(rng,api)
        result=model.transform(test)[:-1] # original transform calls eval, never fit
    # Read-only mounts/identity checks do not prove arbitrary code has no in-RAM adaptation.
    budget.read(state/cp['relative'],job['limits']['model_member_bytes'],expected)
    budget.write(output/'embeddings'/filename(c,'query'),embedding(result,job,api))
    return {'coordinate':c,'fit_state':job['closure'],'semantic_no_refit_proven':False,'native_parity_qualified':False}
def main():
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=('fit','query'),required=True);p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--state',type=Path)
    a=p.parse_args();raw=(a.input/'JOB.json').read_bytes();need(len(raw)<=65536,'bounded operator job');job=parse(raw);job_check(job,a.phase)
    b=Budget(job['limits']['read_bytes'],job['limits']['write_bytes']);b.charge('read',len(raw))
    import interface
    api=actual_api()
    if a.phase=='fit':need(a.state is None,'no state before fit');fit(job,a.input,a.output,b,interface,api)
    else:need(a.state is not None,'fit state required');query(job,a.input,a.state,a.output,b,interface,api)
if __name__=='__main__':main()

