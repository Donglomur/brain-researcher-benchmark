"""Selected native staging or complete public-output validation; never private gold."""
import importlib.metadata,json,os,signal,sys,time,types
from pathlib import Path
from common import need,capture,decode,encode,short,KEYS,FILES,PRED,VIEW,write,path

def main(args,loader,bodies,manifest,source):
    import argparse
    a=argparse.ArgumentParser();a.add_argument('--mode',choices=('stage','collect'),required=True);a.add_argument('--collection',required=True);a.add_argument('--output',required=True);a.add_argument('--result',required=True);a.add_argument('--key');a.add_argument('--seconds',required=True,type=int);a.add_argument('--source-sha256',required=True);v=a.parse_args(args)
    need(1<=v.seconds<=7200 and source['sha256']==v.source_sha256,'trusted phase bounds');origin=time.monotonic()
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('native phase deadline')));signal.setitimer(signal.ITIMER_REAL,v.seconds)
    lock=decode(bodies['LOCK.json']);need(sys.version_info[:3]==(3,11,13),'fixed trusted Python')
    for name,want in lock['expected_dependencies'].items():need(importlib.metadata.version(name)==want,'fixed task dependencies')
    collection=path(v.collection);raw,_=capture(collection/'COLLECTION.json',131072,lock['collection_manifest']);m=decode(raw)
    table={x['target']:{'bytes':x['bytes'],'sha256':x['sha256']}for x in m['files']}
    need(all(table.get(n)==p for n,p in lock['collection_files'].items()),'fixed collection member bindings')
    opraw,_=capture(collection/'operator.py',131072,table['operator.py']);op=types.ModuleType('_neural076_portable_operator');op.__file__=str(collection/'operator.py');exec(compile(opraw,op.__file__,'exec'),op.__dict__)
    binding,pinned=op.start(collection,lock['collection_manifest']['sha256'])
    if v.mode=='stage':
        need(v.key in KEYS,'full fixed context');person,roi,family=v.key.split('/')
        arg=types.SimpleNamespace(output=v.output,person=person,roi=roi,family=family,output_cap=VIEW)
        result=op.stage(collection,'neural076',binding,pinned,arg)
        need(set(result['candidate_files'])==FILES,'exact staged files')
        result={'schema':'neural076_trusted_stage_v1','key':v.key,'stage':result,'source':source}
    else:
        need(v.key is None,'complete collection only');src=op.Sources(collection,'neural076',binding,pinned);art=src.module('artifacts')
        public=decode(pinned('packages/neural076/private/operator/public_manifest.json',4*2**20));art.public_contract(public)
        root=path(v.output);names={p.name for p in root.iterdir()};need(names=={key.replace('/','__')+'.npz'for key in KEYS},'complete flat650 files only')
        rows=[]
        for key in KEYS:
            need(time.monotonic()<origin+v.seconds,'complete validation deadline');person,roi,family=key.split('/');name=key.replace('/','__')+'.npz';p=root/name
            _,before=capture(p,PRED,body=False);array,sha=art.load(p,public['people'][person]['imagery_ids']+public['people'][person]['perception_ids'],public['unit_ids'][family],before['sha256']);del array
            _,after=capture(p,PRED,before,body=False);need(sha==before['sha256'],'validator captured same file');rows.append({'key':key,'path':name,'prediction':after})
        result={'schema':'neural076_complete_public_validation_v1','source':source,'source_design_sha256':lock['source_design_sha256'],'parts':rows,'gold_opened':False,'scientific_scoring':False}
    need(time.monotonic()<origin+v.seconds,'publication within native deadline');write(path(v.result),encode(result),262144)
    signal.setitimer(signal.ITIMER_REAL,0);return 0
