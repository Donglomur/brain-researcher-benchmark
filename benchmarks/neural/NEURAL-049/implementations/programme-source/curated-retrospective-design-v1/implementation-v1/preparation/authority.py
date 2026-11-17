"""Source-bound external qualification admission before original operands/effects."""
from pathlib import Path
from . import contracts as c
from .storage import root,disjoint,bootstrap

ROSTER_PIN={'bytes': 15248, 'sha256': 'd40b7d1e197d30c8e895d35d86dd567e7927bb16e72a9e136ade168784b09a51'}

FIELDS={'schema','status','origin','deadline','limits','source_root','output_root','metadata_root',
        'protected_roots','source_closure','roster','sources','axes','environment','qualifications','module_D'}

def admit(path,expected,budget,store):
    a,base=bootstrap(path,expected,budget)
    c.need(type(a) is dict and set(a)==FIELDS and a['schema']=='neural049_prepare_authority_v1', 'exact prepare authority schema')
    c.need(a['status']=='selected_qualified_prepare' and type(a['module_D']) is bool,'inactive/unqualified authority')
    c.need(c.typed_equal(a['limits'],budget.limits),'inherited all caps')
    c.need(type(a['protected_roots']) is list and len(a['protected_roots'])>=1,'explicit protected root inventory')
    c.need(type(a['environment']) is dict and set(a['environment'])=={'numpy','h5py','memory_profile'}
           and all(type(a['environment'][k]) is str and a['environment'][k] for k in ('numpy','h5py')), 'exact native versions')
    c.artifact(a['environment']['memory_profile']);c.artifact(a['source_closure']);c.artifact(a['roster'])
    c.need(a['roster']['pin']==ROSTER_PIN,'exact immutable held55 source roster')
    metadata=root(a['metadata_root']);c.need(metadata==base,'authority and pinned metadata share admitted root')
    src=root(a['source_root']);out=root(a['output_root'],False)
    protected=[root(p) for p in a['protected_roots']]
    disjoint(src,out,metadata,*protected)
    selection={k:v for k,v in a.items() if k!='qualifications'}
    selection_pin=c.pin_bytes(c.canonical(selection))
    q=a['qualifications'];c.need(type(q) is dict and set(q)==set(c.QUALIFICATIONS),'complete preparation qualification set')
    for name in c.QUALIFICATIONS:c.artifact(q[name])
    budget.reserve(sum(d['pin']['bytes'] for d in q.values())*12+
                   (a['source_closure']['pin']['bytes']+a['roster']['pin']['bytes']+a['environment']['memory_profile']['pin']['bytes'])*12+65536,
                   'retained external qualification/source/roster metadata')
    for name in c.QUALIFICATIONS:
        receipt=store.json(metadata,q[name])
        c.need(type(receipt) is dict and receipt.get('schema')=='neural049_independent_qualification_v1'
               and receipt.get('status')=='qualified' and receipt.get('check')==name
               and c.typed_equal(receipt.get('selection'),selection_pin),'selection-bound independent qualification '+name)
        c.need(receipt.get('independent_producer') is not None and type(receipt.get('evidence')) is list
               and len(receipt['evidence'])>0,'qualification evidence lineage')
        c.artifact(receipt['external_completion'])
        for e in receipt['evidence']: c.artifact(e)
        # Authority's root-approved receipt pins are trust anchors; source-only helper cannot
        # authenticate an external producer/signature merely by accepting these JSON fields.
    closure=store.json(metadata,a['source_closure'])
    c.need(closure.get('schema')=='neural049_preparation_source_closure_v1' and closure.get('files'), 'qualified source closure')
    c.need(c.typed_equal(closure.get('environment'),a['environment']), 'source/environment closure')
    roster=store.json(metadata,a['roster'])
    rows=roster.get('sources');c.need(roster.get('schema')=='neural049_held_roster_v1' and type(rows) is list and len(rows)==55,'full held source roster')
    sources=a['sources'];c.need(type(sources) is list and len(sources)==55,'all55 selected sources')
    keys=[];by={}
    for row,s in zip(rows,sources):
        c.need(type(s) is dict and set(s)=={'person','day','path','pin','geometry'},'source descriptor fields')
        c.artifact({'path':s['path'],'pin':s['pin']})
        key=(s['person'],s['day']);c.need(key not in by,'unique source person/day');keys.append(key);by[key]=s
        c.need(key==(row['person'],row['day']) and s['path']==row['source_path']
               and s['pin']=={'bytes':row['advertised_bytes'],'sha256':row['held_metadata_payload_sha256_not_reverified']},'exact original roster identity')
        c.need(type(s['geometry']) is dict and s['geometry'].get('schema')==c.SCHEMA,'selected original schema')
    c.need(len({x[0] for x in keys})==12 and all(sum(p==f'{i:02}' for p,d in keys)==n
           for i,n in enumerate([4,4,4,5,3,5,5,5,5,5,5,5],1)), 'full12person day census')
    axes=a['axes'];c.need(type(axes) is dict and set(axes)=={x[0] for x in keys},'complete person axes')
    for person,axis in axes.items():
        c.need(type(axis) is list and 0<len(axis)<=budget.limits['channels'] and len(axis)==len(set(axis)), 'full unique channel axis')
        for item in axis:c.opaque(item)
    for person,axis in axes.items():
        mapped={item['axis_id'] for s in sources if s['person']==person for item in s['geometry']['channel_map']}
        c.need(mapped==set(axis),'exact full within-person union; no unobserved synthetic channels')
    budget.tick()
    return a,src,out,selection_pin
