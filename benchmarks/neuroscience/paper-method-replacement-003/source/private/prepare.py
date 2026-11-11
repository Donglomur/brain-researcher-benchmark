"""Lazy deterministic projection of a trusted normalized C4 index, not raw-HDF5 analysis."""
import argparse,hashlib,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
from contract import *

def index(x,production=True):
    exact(x,('schema','source_revision','selection_sha256','pretraining_sha256','run_config_sha256','original_files','units','pretraining_units','exclusions','model_members_per_repeat'))
    need(x['schema']=='c4_normalized_index_v1' and x['source_revision']==REV,'normalized source identity')
    for k in ('selection_sha256','pretraining_sha256','run_config_sha256'):sha(x[k])
    need(type(x['original_files']) is list and len(x['original_files'])==5,'all five published originals')
    names=['C4_database_hull_unlabelled.h5','C4_database_lisberger.h5','C4_database_medina_unlabelled.h5','C4_database_hausser.h5','C4_database_hull_labelled.h5']
    sizes=[30589152758,41387556732,5950752328,43408452946,2268498044]
    md5s=['89c03497f029ffb60b02d323e084d57a','ae4977105191e53f860f0571f8d98c18','346a13f6fd6b1cb388efbc63a9cc690a','56a60394ebb2a0515a8509d74124ca9c','6928f38e1d3ef5d3f940d57d6003452d']
    for r,n,b,m in zip(x['original_files'],names,sizes,md5s):
        exact(r,('name','bytes','published_md5','sha256'));need(r['name']==n and type(r['bytes']) is int and r['bytes']==b and r['published_md5']==m,'published original identities');sha(r['sha256'])
    exact(x['units'],DOMAINS);allids=[]
    for d in DOMAINS:
        need(type(x['units'][d]) is list and len(x['units'][d])>0,'complete selected units')
        for u in x['units'][d]:
            exact(u,('unit_id','source_key','label','animal','session','lab','feature'))
            for k in ('unit_id','animal','session','lab'):ident(u[k])
            need(type(u['source_key']) is str and 1<=len(u['source_key'])<=256,'private original join')
            need(u['label'] in CLASSES,'five-class selection');feature_pin(u['feature']);allids.append(u['unit_id'])
    need(type(x['pretraining_units']) is list and (not production or len(x['pretraining_units'])>0),'complete nonempty production pretraining roster')
    for u in x['pretraining_units']:
        exact(u,('unit_id','feature'));ident(u['unit_id']);feature_pin(u['feature']);allids.append(u['unit_id'])
    need(len(allids)==len(set(allids)),'no labelled/query overlap in unsupervised training roster')
    need(type(x['exclusions']) is list,'explicit source exclusions')
    for u in x['exclusions']:exact(u,('source_key','reason'));need(all(type(v) is str and 1<=len(v)<=512 for v in u.values()),'source exclusion reason')
    q={'schema':'c4_query_v1','task_id':TASK,'source_revision':REV,'classes':list(CLASSES),'repeats':10,'input_index_sha256':digest(x),'selection_sha256':x['selection_sha256'],'pretraining_sha256':x['pretraining_sha256'],'run_config_sha256':x['run_config_sha256'],'scope':'full_selected_c4_mouse_monkey','domains':{d:{'unit_ids':[u['unit_id'] for u in x['units'][d]],'label_basis':'mouse_source_ground_truth' if d=='mouse_loo' else 'monkey_expert_reference','model_members_per_repeat':x['model_members_per_repeat'][d]} for d in DOMAINS}}
    query(q,production);t={'schema':'c4_target_v1','query_sha256':digest(q),'labels':{d:[u['label'] for u in x['units'][d]] for d in DOMAINS},'groups':{d:[{k:u[k] for k in ('animal','session','lab')} for u in x['units'][d]] for d in DOMAINS}};target(t,q);return q,t

def feature_pin(f):
    exact(f,('path','bytes','sha256'));need(type(f['path']) is str,'feature path');p=Path(f['path']);need(not p.is_absolute() and p.parts and all(v not in ('..','.') for v in p.parts),'relative feature path');need(type(f['bytes']) is int and 0<f['bytes']<=2_000_000,'feature byte cap');sha(f['sha256'])
def features(v):
    exact(v,('waveform','acg_3d','engineered','layer'))
    need(type(v['waveform']) is list and len(v['waveform'])==120,'120-sample conformed waveform')
    need(type(v['acg_3d']) is list and len(v['acg_3d'])==10 and all(type(r) is list and len(r)==201 for r in v['acg_3d']),'10 by 201 ACG before half-lag transform')
    for a in [v['waveform']]+v['acg_3d']:
        for z in a:number(z)
    need(type(v['engineered']) is dict and set(v['engineered'])==set(ENGINEERED_COLUMNS),'exact source combined engineered columns; no labels or identifiers')
    for k,z in v['engineered'].items():ident(k);number(z)
    need(v['layer'] in ('unknown','GCL','PCL','ML'),'anatomical layer');return v

def read_feature(root,u):
    f=u['feature'];path=Path(root)
    for part in Path(f['path']).parts:path=path/part;need(not path.is_symlink(),'no feature path symlinks')
    b=capture(path,2_000_000);need(len(b)==f['bytes'] and hashlib.sha256(b).hexdigest()==f['sha256'],'feature identity');return features(decode(b))
def project(x,case,reader,production=True):
    q,_=index(x,production);mouse=x['units']['mouse_loo'];monkey=x['units']['monkey_transfer']
    if case=='monkey_transfer':train=mouse;held=monkey
    else:
        need(case in q['domains']['mouse_loo']['unit_ids'],'selected LOO case');train=[u for u in mouse if u['unit_id']!=case];held=[u for u in mouse if u['unit_id']==case]
    # No source keys, target labels, animal names, lab names or native paths enter a query row.
    tr=[{'unit_id':u['unit_id'],'features':reader(u),'label':u['label']} for u in train]
    te=[{'unit_id':u['unit_id'],'features':reader(u)} for u in held]
    need(not set(u['unit_id'] for u in tr)&set(u['unit_id'] for u in te),'train/test separation')
    return {'schema':'c4_fold_v1','task_id':TASK,'query_sha256':digest(q),'case':case,'training':tr,'query':te,'pretraining_index_sha256':x['pretraining_sha256'],'pretraining_unit_ids':[u['unit_id'] for u in x['pretraining_units']]}
def main():
    a=argparse.ArgumentParser();a.add_argument('--index',required=True);a.add_argument('--index-sha256',required=True);a.add_argument('--feature-root',required=True);a.add_argument('--case',required=True);a.add_argument('--output',required=True);z=a.parse_args();fresh(z.output);b=capture(z.index);sha(z.index_sha256);need(hashlib.sha256(b).hexdigest()==z.index_sha256,'trusted normalized index');x=decode(b);index(x)
    # The cap is checked before reading feature bodies; bounded JSON overhead is checked on write.
    needed=x['units']['mouse_loo']+(x['units']['monkey_transfer'] if z.case=='monkey_transfer' else [])
    need(sum(u['feature']['bytes'] for u in needed)<=24_000_000,'lazy packet input bound; enlarge only by separately selected construction')
    save(z.output,project(x,z.case,lambda u:read_feature(z.feature_root,u)))
if __name__=='__main__':main()
