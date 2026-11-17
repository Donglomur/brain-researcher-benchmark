"""Future original29 input preparation. This file does not launch acquisition."""
import argparse,importlib.util,json,os,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
from support import validate_cohort,partition,native_shape_support
HERE=Path(__file__).resolve().parent

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def save_array(path,array,budget):
    import numpy as np
    need(array.dtype==np.dtype('float64') and np.isfinite(array).all(),'finite prospectivefloat64 array')
    budget.reserve(path.parent,array.nbytes+131072);budget.writing(array.nbytes+131072)
    with open(path,'xb') as f:np.lib.format.write_array(f,array,allow_pickle=False);f.flush();os.fsync(f.fileno())
    return captured(path,budget,array.nbytes+131072)

def prepare_all(root,raw_pins,output,limits,origin,array_ceiling,expanded_ceiling,budget=None,source_bodies=None,source_manifest=None):
    """Full original roster, source numeric preprocessing, development-only moments.

    Caller must bind this exact source/environment externally. No candidate input
    is opened here and no fit/prediction/scorer is invoked.
    """
    import numpy as np
    budget=budget if budget is not None else Budget(limits,origin);need(source_bodies is not None and source_manifest is not None,'independently bound preparation source');out=ordinary(output);need(not out.exists() and out.parent.is_dir(),'fresh preparation output');out.mkdir(mode=0o700)
    sessions=validate_cohort(parse(source_bodies['COHORT.json']));assets=parse(source_bodies['ASSETS.json'])['assets'];need(set(raw_pins)=={s['session_id'] for s in sessions},'all29 exactoriginal pins')
    prov=load('ci_provision',HERE/'native-source/operator/provision.py');panels=load('ci_panels',HERE/'native-source/operator/panels.py');records=[]
    for s,asset in zip(sessions,assets):
        sid=s['session_id'];need(asset['session_id']==sid,'source orderedasset join');source=ordinary(root)/asset['filename'];expected=raw_pins[sid];read(source,expected,budget,expected['bytes'],retain=False)
        budget.reading(expected['bytes']+expanded_ceiling);census=prov.inspect_file(source,asset,expanded_ceiling,prov.decoded_fields(s['modality']));need(census['sha256']==expected['sha256'],'publisher+operator identityjoin')
        budget.reading(expected['bytes']+expanded_ceiling)  # Separate NPZ decoding/materialization pass.
        f2,f3,x,y=panels.load_panels(root,s,array_ceiling);geom=panels.geometry(s,census['sha256'],f2,f3,x,y);native_shape_support(geom,s);part=partition(geom['n_fig3'],geom['t_fig3']);d=part['development_end']
        n,t=f3.shape;budget.reserve(out,8*n*(t+d+2)+8*131072);need(8*n*(t+d+2)<=array_ceiling,'full forecast transformation memory component; no cropping')
        raw=np.asarray(f3,dtype=np.float64);mu=raw[:,:d].mean(axis=1);scale=0.001+raw[:,:d].std(axis=1,ddof=0);need(np.isfinite(mu).all() and np.isfinite(scale).all() and (scale>0).all(),'finite development moments')
        z=(raw-mu[:,None])/scale[:,None];case=out/sid;case.mkdir(mode=0o700)
        pins={name:save_array(case/name,value,budget) for name,value in [('full.npy',z),('development.npy',np.ascontiguousarray(z[:,:d])),('mean.npy',mu),('scale.npy',scale)]}
        record={'session_id':sid,'source_original':{'path':str(source),**descriptor(expected)},'native_geometry':geom,'partition':part,'prepared':{k:{'path':str(case/k),**v} for k,v in pins.items()},'source_ephys_eligibility_transductive':s['modality']=='ephys','upstream_temporal_preprocessing_causality_qualified':False,'forecast_dtype':'float64','normalization_prefix_stop':d,'normalization_epsilon':0.001,'source_neuron_population_preserved':True}
        write(case/'PREPARATION.json',encode(record),budget);records.append(record);del f2,f3,x,y,raw,z,mu,scale
    value={'schema':'critical_init_full29_prepared_v1','task_id':TASK,'source':descriptor(source_manifest),'records':records,'all_originals_verified':True,'no_original_population_reduction':True,'scientific_execution':False,'input_preparation_only':True,'native_reference_qualified':False,'original_origin':origin,'finished':time.monotonic(),'managed_reads':budget.read,'managed_write_charge':budget.write,'retained_charge':budget.retained}
    receipt=write(out/'PREPARED.json',encode(value),budget);return {'receipt':receipt,'post_durability':time.monotonic(),'original_deadline':budget.end,'requires_external_natural_exit_admission':True}

def main():
    p=argparse.ArgumentParser();p.add_argument('--authority',required=True);p.add_argument('--authority-sha256',required=True);p.add_argument('--origin',type=float,required=True);a=p.parse_args();raw,v,budget=authority(a.authority,a.authority_sha256,a.origin)
    need(v['schema']=='critical_init_original_preparation_authority_v1' and v['selected_by_root']is True and v['exclusive_operator_custody']is True and v['source_environment_qualified_for_preparation']is True,'separate authentic input preparation authority')
    need(ordinary(v['root_source'])==HERE,'preparation executes selected local source');bodies,source=authenticate_source(HERE,v['source_manifest'],budget,{'prepare.py','common.py','support.py','COHORT.json','ASSETS.json','native-source/operator/provision.py','native-source/operator/panels.py'});result=prepare_all(v['data_root'],v['raw_pins'],v['output'],v['limits'],a.origin,v['array_ceiling_bytes'],v['expanded_ceiling_bytes'],budget,bodies,source);print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
