"""Qualified THINGSplus mapping admission; no invented semantic labels."""
from collections import Counter
from .domain import fields,need,text,digest,sha,encoded,uint,CATEGORIES

def category_schema(value, expected_sha):
    fields(value,('schema','source_doi','source_file_sha256','categories'))
    need(value['schema']=='thingsplus-53-original-roster-v1' and value['source_doi']=='10.3758/s13428-023-02110-8','selected published taxonomy')
    digest(value['source_file_sha256']);need(sha(encoded(value))==digest(expected_sha),'externally selected exact original category roster')
    c=value['categories'];need(type(c) is list and len(c)==CATEGORIES and all(type(x) is str for x in c),'53 original category names')
    for x in c: text(x)
    need(len(set(c))==CATEGORIES,'distinct categories, original order preserved')
    return tuple(c)

def mapping(value, categories, concept_roster):
    fields(value,('schema','category_schema_sha256','source_file_sha256','rows'))
    need(value['schema']=='thingsplus-concept-membership-v1','fixed mapping schema');digest(value['category_schema_sha256']);digest(value['source_file_sha256'])
    need(type(concept_roster) is list and len(concept_roster)==1854 and len(set(concept_roster))==1854,'all original 1854 concept IDs')
    rows=value['rows'];need(type(rows) is list and len(rows)==1854,'no dropped unsupported concepts')
    out={};counts=Counter();members=0
    for expected,row in zip(concept_roster,rows):
        fields(row,('concept_id','status','memberships'));need(row['concept_id']==expected,'exact source concept alignment, no name guessing')
        m=row['memberships'];need(type(m) is list and all(type(x) is str and x in categories for x in m) and len(set(m))==len(m),'original unique memberships')
        need(m==[x for x in categories if x in m],'fixed category order')
        if m:
            need(row['status']=='assigned','assigned original membership');out[expected]=tuple(int(x in m) for x in categories);counts['assigned']+=1
            counts['multiple']+=int(len(m)>1);members+=len(m)
        else:
            need(row['status']=='unsupported_unassigned','unassigned is not all-negative truth');out[expected]=None;counts['unassigned']+=1
    need(dict(counts)=={'assigned':1448,'multiple':664,'unassigned':406} and members==2355,'published complete taxonomy census')
    return out

def source_metadata(value):
    fields(value,('schema','training','test'))
    need(value['schema']=='things-eeg2-concept-image-alignment-v1','versioned exact source alignment')
    all_ids=set();out={}
    for kind,n,concepts,repeats in [('training',16540,1654,10),('test',200,200,1)]:
        rows=value[kind];need(type(rows) is list and len(rows)==n,'full source image rows')
        counts=Counter()
        for row in rows:
            fields(row,('row','image_id','concept_id'));uint(row['row']);text(row['image_id']);text(row['concept_id'])
            need(row['image_id'] not in all_ids,'distinct original image identity');all_ids.add(row['image_id']);counts[row['concept_id']]+=1
        need([r['row'] for r in rows]==list(range(n)) and len(counts)==concepts and set(counts.values())=={repeats},'source row order and concept exemplars')
        out[kind]=rows
    need(not set(r['concept_id'] for r in out['training']) & set(r['concept_id'] for r in out['test']),'unseen-concept held test')
    return out

def project_original_image_metadata(value):
    # These exact four names are selected by S8's original metadata_core validator.
    # The qualified source conversion supplies this plain JSON representation;
    # no concept is inferred from a filename or display label.
    fields(value,('train_img_files','test_img_files','train_img_concepts_THINGS','test_img_concepts_THINGS'))
    out={'schema':'things-eeg2-concept-image-alignment-v1'}
    for old,new in (('train','training'),('test','test')):
        names=value[old+'_img_files'];concepts=value[old+'_img_concepts_THINGS']
        need(type(names) is list and type(concepts) is list and len(names)==len(concepts),'original complete ordered parallel columns')
        out[new]=[{'row':i,'image_id':name,'concept_id':concept} for i,(name,concept) in enumerate(zip(names,concepts))]
    return source_metadata(out)
