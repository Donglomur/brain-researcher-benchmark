"""Closed root, source and run coordinates; no scientific imports."""
import re
from pathlib import Path
HEX=re.compile(r'[0-9a-f]{64}')
def require(v,m):
 if not v:raise ValueError(m)
def exact(v,keys):require(type(v)is dict and set(v)==set(keys),'closed fields')
def uint(v,cap):require(type(v)is int and 0<=v<=cap,'UInt domain');return v
def pin(v):
 exact(v,['bytes','sha256']);uint(v['bytes'],16_000_000_000);require(type(v['sha256'])is str and HEX.fullmatch(v['sha256']),'SHA256');return v
def path(v):
 require(type(v)is str and v and not Path(v).is_absolute()and all(x not in ('','.','..')for x in v.split('/'))and '\\'not in v,'relative path');return v
def programme(v):
 exact(v,['schema','release','cohort','assets','key','source','environment','limits','programmes','execution_id'])
 require(v['schema']=='neural062.programme.v1'and v['release']=='visual-behavior-ophys1.1.0','release')
 require(type(v['execution_id'])is str and HEX.fullmatch(v['execution_id']),'opaque execution')
 for k in ['cohort','key']:
  exact(v[k],['path','pin']);path(v[k]['path']);pin(v[k]['pin'])
 require(v['cohort']['pin']=={'bytes':5834685,'sha256':'4bcc3017b4a28d16f39bd8962961472f1fa23d82097bcd19f3e45900b8792f74'},'unchanged full release cohort')
 require(v['key']['pin']['bytes']==32,'32byte operator key')
 require(type(v['assets'])is list and len(v['assets'])==1936,'all1936 authentic source bindings')
 seen=set()
 for a in v['assets']:
  exact(a,['experiment','path','bytes','blake2b_512']);require(type(a['experiment'])is str and a['experiment'].isdigit()and a['experiment']not in seen,'unique experiment');seen.add(a['experiment']);path(a['path']);uint(a['bytes'],4_000_000_000);require(a['bytes']>0 and type(a['blake2b_512'])is str and re.fullmatch('[a-f0-9]{128}',a['blake2b_512']),'BLAKE2b512')
 require(type(v['source'])is list and v['source'],'source inventory')
 for x in v['source']:exact(x,['path','pin']);path(x['path']);pin(x['pin'])
 require(len({x['path']for x in v['source']})==len(v['source']),'unique complete source paths')
 exact(v['environment'],['image','memory_bytes','cpus','pids','job_seconds'])
 require(type(v['environment']['image'])is str and re.fullmatch(r'[^\s]+@sha256:[0-9a-f]{64}',v['environment']['image']),'fixed OCI image digest')
 for k in ['memory_bytes','cpus','pids','job_seconds']:require(type(v['environment'][k])is int and v['environment'][k]>0,'integer resource')
 exact(v['limits'],['read_bytes','write_bytes','jobs','wall_seconds'])
 for n in v['limits'].values():require(type(n)is int and n>0,'positive overall limits')
 require(set(v['programmes'])=={'F','I'},'both precommitted modes')
 for x in v['programmes'].values():exact(x,['path','pin']);path(x['path']);pin(x['pin']);require(0<x['pin']['bytes']<=131072,'bounded precommitted program')
 return v
