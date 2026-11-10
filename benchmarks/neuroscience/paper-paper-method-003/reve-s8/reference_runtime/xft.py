"""The five required XFT sources, joined only after qualified common ontology/views."""
import numpy as np
from .catalog import need,identity
from .io import data_view
from .engine import project
from .lineage import XFT_SOURCES as SOURCES,collection_lineage

def xft_view(io,name,role,c):
    collection=io.json(name);need(set(collection)=={'schema','sources','overlap_qualification','class_mapping_qualification','target_people_exclusion_qualification'},'complete XFT collection')
    need(collection['schema']=='reve-XFT-five-source-view-v1' and set(collection['sources'])==set(SOURCES),'exact five XFT sources')
    need(all(collection[k] for k in ('overlap_qualification','class_mapping_qualification','target_people_exclusion_qualification')),'selected source/target exclusion and common ontology')
    parts=[]
    for source in SOURCES:
        part=data_view(io,collection['sources'][source],role,c);need(part[0].get('source_dataset')==source,'actual XFT source identity');parts.append(part)
    geometry=parts[0][2];signals=np.concatenate([project(x,p,geometry) for _,x,p,_ in parts]);labels=np.concatenate([y for _,_,_,y in parts]);events=[e for m,_,_,_ in parts for e in m['events']];people=[p for m,_,_,_ in parts for p in m['people']]
    need(len(events)==len(set(events)),'no repeated XFT observations');meta=dict(parts[0][0]);meta.update(events=events,people=people,support=identity([m['support'] for m,_,_,_ in parts]),source_dataset='five-source-XFT-union')
    meta['xft_collection']=collection_lineage(collection,{source:part[0] for source,part in zip(SOURCES,parts)},role)
    return meta,signals,geometry,labels
