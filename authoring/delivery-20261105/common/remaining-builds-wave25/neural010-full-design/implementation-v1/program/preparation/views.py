"""Pure support/view construction. No access to scientific arrays or keys."""
import hashlib
from storage import ID, need, valid_pin, encoded

ROW_KEYS={'recording_id','patient_id','duration_seconds','montage_id','channel_count','channel_labels','source_edf','target_free_projection'}

def validate_rows(rows, expected_people=23, expected_records=686):
    need(type(rows)is list and len(rows)==expected_records,'complete selected recording roster')
    seen=set();people=set()
    for r in rows:
        need(type(r)is dict and set(r)==ROW_KEYS,'exact target-free metadata')
        for k in ('recording_id','patient_id'):
            need(type(r[k])is str and ID.fullmatch(r[k]),'opaque canonical ID')
        need(r['recording_id'] not in seen,'unique recording');seen.add(r['recording_id']);people.add(r['patient_id'])
        need(type(r['duration_seconds'])is int and 0<r['duration_seconds']<=86400,'whole observed seconds')
        need(type(r['channel_count'])is int and r['channel_count']>0 and type(r['channel_labels'])is list
             and len(r['channel_labels'])==r['channel_count'] and all(type(v)is str and v for v in r['channel_labels']),'complete channel multiset')
        expected=hashlib.sha256(encoded(sorted(r['channel_labels']),False)).hexdigest()
        need(r['montage_id']==expected,'exact montage multiset identity')
        valid_pin(r['source_edf']);valid_pin(r['target_free_projection'])
    need(sum(r['duration_seconds'] for r in rows)<=10000000,'accepted global observed-time ceiling')
    need(len(people)==expected_people,'complete biological cohort')
    return sorted(people)

def support_document(rows):
    need(type(rows)is list and rows,'training support nonempty')
    seen=set();clean=[]
    for r in rows:
        for k in ('patient_id','recording_id'):
            need(type(r[k])is str and ID.fullmatch(r[k]),'opaque support ID')
        need(r['recording_id'] not in seen,'support duplicate');seen.add(r['recording_id'])
        need(type(r['duration_seconds'])is int and r['duration_seconds']>0,'support exact seconds')
        clean.append({k:r[k] for k in ('patient_id','recording_id','duration_seconds','source_edf','target_free_projection')})
        valid_pin(r['source_edf']);valid_pin(r['target_free_projection'])
    document={'schema':'neural010-training-support-v1','dataset':'CHB-MIT','dataset_version':'1.0.0',
              'records':sorted(clean,key=lambda r:(r['patient_id'],r['recording_id']))}
    return encoded(document,False)

def validate_annotations(rows, annotations):
    need(type(annotations)is dict and set(annotations)=={r['recording_id'] for r in rows},'exact annotations support')
    for r in rows:
        last=-1;ev=annotations[r['recording_id']];need(type(ev)is list,'event list')
        for ab in ev:
            need(type(ab)is list and len(ab)==2 and all(type(x)in(int,float) for x in ab),'event pair')
            a,b=ab;need(a==int(a) and b==int(b) and 0<=a<b<=r['duration_seconds'] and a>=last,'ordered integral observed annotation');last=b
    for person in {r['patient_id'] for r in rows}:
        subset=[r for r in rows if r['patient_id']==person]
        positive=sum(b-a for r in subset for a,b in annotations[r['recording_id']])
        total=sum(r['duration_seconds'] for r in subset)
        need(0<positive<total,'each biological person has positive and nonictal support')

def make_views(rows, annotations, *, expected_people=23, expected_records=686):
    people=validate_rows(rows,expected_people,expected_records);validate_annotations(rows,annotations)
    rows=sorted(rows,key=lambda r:r['recording_id'])
    for outer in people:
        for inner in [None,*[p for p in people if p!=outer]]:
            held={outer} if inner is None else {outer,inner}
            train=[r for r in rows if r['patient_id'] not in held]
            query_person=outer if inner is None else inner
            query=[r for r in rows if r['patient_id']==query_person]
            need(len({r['patient_id'] for r in train})==expected_people-len(held),'exact complete training people')
            name=outer+'/final' if inner is None else outer+'/inner/'+inner
            common={'schema':'neural010-detector-view-v1','task_id':'NEURAL-010','outer_person':outer,'inner_person':inner}
            train_doc=dict(common,role='training',records=[dict(r,events=annotations[r['recording_id']]) for r in train])
            query_doc=dict(common,role='query',records=query)
            validation=None if inner is None else dict(common,role='validation_labels',records=[{'recording_id':r['recording_id'],'patient_id':r['patient_id'],'duration_seconds':r['duration_seconds'],'events':annotations[r['recording_id']]} for r in query])
            yield {'name':name,'TRAIN.json':encoded(train_doc),'QUERY.json':encoded(query_doc),
                   'SUPPORT.json':support_document(train),'VALIDATION.json':None if validation is None else encoded(validation)}
