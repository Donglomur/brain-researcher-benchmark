"""Exact per-person role views. Preparation projections never become actor mounts."""
from pathlib import Path
from core import need,relative,descriptor,encoded,pin,parse,canonical
from contracts import exact,opaque,identities,projection
from artifacts import mount_files


def admit_view(value,world,person):
    exact(value,('schema','world','person','sessions','channels','files','source','protocol','preparation'),'minimized case view')
    need(value['schema']=='neural042_view_v1'and value['world']==world and value['person']==person,'exact admitted case/world')
    opaque(person);identities(value['sessions'])
    for k in ('source','protocol','preparation'):descriptor(value[k])
    need(type(value['channels'])is list and type(value['files'])is dict,'explicit channel/file inventory')
    ids=[];expected={}
    for ch in value['channels']:
        exact(ch,('id','session','metadata')if world=='A'else('id','session','metadata','lfp','rates'),'world-specific capabilities')
        identity=opaque(ch['id']);ids.append(identity);need(ch['session']in value['sessions'],'channel/session join')
        for key,name in [('metadata','CHANNEL.json')]+([]if world=='A'else[('lfp','lfp.npy'),('rates','rates.npy')]):
            row=ch[key];exact(row,('path','pin'),'exact individual permitted file');descriptor(row['pin'])
            need(row['path']==identity+'/'+name,'no alternate case/file operand');expected[row['path']]=row['pin']
    need(ids==sorted(ids)and len(ids)==len(set(ids))and value['files']==expected,'full exact sorted case files; no extra roots or answers')
    return value


def case(proj,world,person,a,artifacts):
    projection(proj);row=next(x for x in proj['views']if x['world']==world and x['person']==person)
    need(row['path']==world+'/'+person+'/VIEW.json','fixed prepared namespace')
    path=Path(a['roots']['packet'])/relative(row['path'])
    value=admit_view(artifacts.json(path,row['pin'],a['resources']['view_metadata_bytes']),world,person)
    need(value['source']==proj['source']and value['protocol']==proj['protocol']and value['preparation']==proj['preparation'],'same complete prepared lineage')
    sessions=sorted(s['id']for s in proj['sessions']if s['person']==person)
    expected=sorted(c for s in proj['sessions']if s['person']==person for c in s['eligible_channels'])
    need(value['sessions']==sessions and [x['id']for x in value['channels']]==expected,'no selected-channel/session shrinkage')
    mounts=mount_files(path.parent,value,'/inputs/case',artifacts)if value['files']else[]
    # Zero eligible channels still has its actual manifest and is a complete case.
    mounts.append({'source':str(path),'destination':'/inputs/case/VIEW.json','pin':row['pin'],'bytes_cap':row['pin']['bytes']})
    return {'world':world,'person':person,'root':str(path.parent),'view':value,'pin':row['pin'],'mounts':mounts}
