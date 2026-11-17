"""Pure metadata method provenance. No array, model, or fitting operations."""
from .catalog import need,identity
XFT_SOURCES=('Schirrmeister2017','Cho2017','PhysioNet-MI','Lee2019MI','Weibo2014')

def fit_stage(stage,c):
    method=c['recipe']['method']
    if stage in ('S09','S10','S11'):
        need(method!='REVE-Base-PT','PT cannot receive supervised adaptation')
        need((method=='REVE-Base-XFT')==(stage=='S10'),'XFT requires its actual five-source S10 producer')

def collection_lineage(collection,parts,role):
    need(role in ('train','dev'),'XFT collection role')
    need(set(collection)=={'schema','sources','overlap_qualification','class_mapping_qualification','target_people_exclusion_qualification'},'complete XFT collection')
    need(collection['schema']=='reve-XFT-five-source-view-v1' and set(collection['sources'])==set(XFT_SOURCES),'exact five XFT sources')
    need(set(parts)==set(XFT_SOURCES),'five actual opened source views')
    sources={}
    for source in XFT_SOURCES:
        m=parts[source]
        need(m['role']==role and m.get('source_dataset')==source and m['support'] and m['events'] and m['people'],'actual XFT source/role/support')
        sources[source]={'view':collection['sources'][source],'manifest_identity':identity(m),'support':m['support'],'events_identity':identity(m['events']),'people_identity':identity(m['people'])}
    quals={k:collection[k] for k in ('overlap_qualification','class_mapping_qualification','target_people_exclusion_qualification')}
    need(all(quals.values()),'qualified XFT ontology and source/target exclusions')
    return {'schema':'reve-XFT-actual-collection-v1','role':role,'collection_identity':identity(collection),'sources':sources,**quals}

def training_lineage(request,c,train,dev):
    fit_stage(request['stage'],c)
    need(request['stage']=='S10','actual XFT training stage')
    rows={'train':train['xft_collection'],'dev':dev['xft_collection']}
    for role,row in rows.items():
        need(row['role']==role and set(row['sources'])==set(XFT_SOURCES),'complete actual XFT training source union')
    need(rows['train']['class_mapping_qualification']==rows['dev']['class_mapping_qualification'],'same TRAIN/DEV class ontology')
    need(rows['train']['target_people_exclusion_qualification']==rows['dev']['target_people_exclusion_qualification'],'same TRAIN/DEV target exclusion')
    return {'schema':'reve-XFT-S10-lineage-v1','stage':'S10','request':identity(request),'source':request['source_id'],'configuration':identity(c),'views':dict(request['payload']['reference']['views']),'collections':rows}

def validate_training_lineage(value,request,c):
    need(type(value)is dict and set(value)=={'schema','stage','request','source','configuration','views','collections'},'closed XFT training lineage')
    need(value['schema']=='reve-XFT-S10-lineage-v1' and value['stage']==request['stage']=='S10','actual S10 lineage')
    need(value['request']==identity(request) and value['source']==request['source_id'] and value['configuration']==identity(c),'XFT actual source/request/configuration')
    need(value['views']==request['payload']['reference']['views'] and set(value['collections'])=={'train','dev'},'XFT actual opened views')
    for role,row in value['collections'].items():
        need(set(row)=={'schema','role','collection_identity','sources','overlap_qualification','class_mapping_qualification','target_people_exclusion_qualification'},'closed XFT collection lineage')
        need(row['schema']=='reve-XFT-actual-collection-v1' and row['role']==role and row['collection_identity'] and set(row['sources'])==set(XFT_SOURCES),'full XFT source union')
        need(all(row[k] for k in ('overlap_qualification','class_mapping_qualification','target_people_exclusion_qualification')),'XFT qualification lineage')
        for source,part in row['sources'].items():
            need(set(part)=={'view','manifest_identity','support','events_identity','people_identity'} and all(part.values()),'XFT actual source support')
    a,b=value['collections']['train'],value['collections']['dev']
    need(a['class_mapping_qualification']==b['class_mapping_qualification'] and a['target_people_exclusion_qualification']==b['target_people_exclusion_qualification'],'XFT common ontology/exclusions')
    return value

def require_xft_parent(envelope,calibrated):
    """Use controller-derived provenance, never a method label as ancestry."""
    p=envelope['product'];prov=envelope.get('provenance',{});proof=envelope.get('method_lineage')
    need(p['kind']=='state' and p['details']['configuration']['recipe']['method']=='REVE-Base-XFT','XFT parent configuration')
    need(type(proof)is dict and proof.get('schema')=='reve-XFT-controller-lineage-v1','controller-bound XFT ancestry required')
    expected='S15' if calibrated else 'S10'
    need(prov.get('stage')==expected and prov.get('source')==p['source'] and prov.get('request')==p['request'],'actual XFT parent producer')
    need(proof.get('current_product')==identity(p)==envelope['identity'] and proof.get('current_stage')==expected,'actual XFT parent product identity')
    need(proof.get('fit_stage')=='S10' and proof.get('fit_product') and proof.get('fit_request') and proof.get('fit_source'),'actual five-source fit ancestry')
    need(proof.get('training')==p['details']['schedule'].get('xft'),'XFT immutable fitted lineage')
    need(set(proof['training']['collections'])=={'train','dev'} and all(set(row['sources'])==set(XFT_SOURCES) for row in proof['training']['collections'].values()),'five actual sources survive ancestry')
    return proof

