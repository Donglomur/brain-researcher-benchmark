"""Authenticate portable operative source without using historical host paths."""
from pathlib import Path
import time
from banc_runtime.codec import capture,parse,pin,need,encode
from banc_runtime.catalog import CONTRACT_NAMES,scope
from banc_runtime.construct import construct,manifest
from banc_runtime.producers import complete_pipeline
from banc_runtime.resources import Meter,Limits
from .io import metadata

ROOT=Path(__file__).resolve().parents[1]
PROFILE='complete_banc_programme_v1'
CONDITIONS={'R-A':('paper_and_data','reconstruction'),'R-B':('paper_data_official_code','reconstruction'),
 'I-A':('paper_and_data','fixed_quantity_improvement'),'I-B':('paper_data_official_code','fixed_quantity_improvement')}
SCOPE={'canonical_tasks':1,'panels':96,'families':18,'legacy_entries':24,'operator_branches':7,'open_scientific_gates':16,'accounting_jobs':139}
STAGES=('prepare','reference','actor','collect','grade','report')

def load_source():
    meter=Meter(Limits(8*1048576,1048576,100000,100000,1000,time.monotonic_ns()+30_000_000_000))
    path=ROOT/'SOURCE_MANIFEST.json'
    # Its hash is pinned by the registry/source freeze; its own fields pin every
    # operative member. This bootstrap does not authenticate arbitrary history.
    body=metadata(path,meter,1048576);doc=parse(body)
    need(doc['schema']=='banc_portable_complete_source_v1' and doc['scope']==SCOPE,'complete portable source identity')
    captured={}
    for d in doc['files']:
        need(d['path'] not in captured,'unique operative source member')
        captured[d['path']]=capture(ROOT,d,cap=1048576,meter=meter)
    need(len([x for x in captured if x.startswith('runtime/')])==100,'all100 accepted runtime members')
    catalog=parse(captured['runtime/SOURCE_CATALOG.json']);members={};runtime_bytes={}
    for row in catalog['files']:
        name=row['target'];raw=captured['runtime/'+name]
        need(pin(raw)=={k:row[k] for k in ('bytes','sha256')},'accepted catalogue member identity')
        members[name]={'path':name,**pin(raw)};runtime_bytes[name]=raw
    contracts={n:parse(runtime_bytes['contracts/'+n+'.json']) for n in CONTRACT_NAMES};scope(contracts)
    return {'root':ROOT,'manifest':doc,'manifest_identity':pin(body),'captured':captured,'runtime_captured':runtime_bytes,
      'members':members,'contracts':contracts,'catalogue_identity':{'path':'SOURCE_CATALOG.json',**pin(captured['runtime/SOURCE_CATALOG.json'])},
      'source_read_costs':meter.report()}

def programme(source,method):
    arm,objective=CONDITIONS[method['condition']]
    return construct(source['contracts'],source['members'],arm=arm,objective=objective,
      annotation_profile=method['annotation_profile'],operator_branch=method['operator_branch'],
      graph_variant=method['graph_variant'],data_descriptors=method['data'],source_catalogue_identity=source['catalogue_identity'])

def inspect_source():
    s=load_source();c=s['contracts']
    return {'schema':'banc_complete_portable_inspection_v1','task_id':'PAPER-FIND-NEW-003','profile':PROFILE,'scope':SCOPE,
      'conditions':list(CONDITIONS),'stages':list(STAGES),'panels':[x['id'] for x in c['OBLIGATIONS']['rows']],
      'families':c['WORKFLOW']['families'],'legacy':c['WORKFLOW']['legacy_entries'],'operator_branches':c['NATIVE_BRANCH_MAP']['rows'],
      'gates':c['GATES']['gates'],'source':s['manifest_identity'],'source_read_costs':s['source_read_costs'],
      'runtime_qualified':False,'scientific_qualification':False,'history_is_runtime_dependency':False}
