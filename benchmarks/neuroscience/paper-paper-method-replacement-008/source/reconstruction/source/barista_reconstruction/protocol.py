"""Source-derived full masked-channel roster; no real data or model execution."""
import hashlib
import json
import re

TASK_ID='PAPER-paper-method-replacement-008'
SCHEMA='barista_channel_reconstruction_v1'
PAPER_SHA='427c56188d6d0e2ef416a21fff14480fc1da84935118e567fecdeeac15253b07'
COMMIT='83b27375eba60e9eba9da4e7dd8fb283baace376'
PEOPLE=(1,2,3,4,6,7,10)
# Table6 training/validation/test segments, Table9 retained channel counts.
COUNTS={1:(2787,348,348,91),2:(3385,422,422,100),3:(1825,228,228,91),4:(1795,224,224,151),6:(1532,191,191,134),7:(1604,200,200,205),10:(1506,188,188,173)}
RECORDINGS={1:'sub_1_trial001',2:'sub_2_trial006',3:'sub_3_trial000',4:'sub_4_trial000',6:'sub_6_trial004',7:'sub_7_trial000',10:'sub_10_trial000'}
SCALES=('channels','parcels','lobes')
MODELS=tuple('barista_'+e+'_'+m for e in SCALES for m in SCALES)+tuple('random_'+e for e in SCALES)
ARMS=('paper_and_data','paper_data_official_code')
SAMPLES=6144
OUTPUTS=2*12*945
HEX=re.compile(r'[0-9a-f]{64}\Z')
FILENAME=re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,180}\.npy\Z')


def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(x):return hashlib.sha256(canonical(x)).hexdigest()
def _hash(x):return isinstance(x,str)and bool(HEX.fullmatch(x))


def validate_panel(panel):
    fields={'schema','task_id','paper_sha256','code_commit','generation_commitment','sessions','panel_id'}
    if not isinstance(panel,dict)or set(panel)!=fields or panel['schema']!=SCHEMA or panel['task_id']!=TASK_ID or panel['paper_sha256']!=PAPER_SHA or panel['code_commit']!=COMMIT:raise ValueError('Exact public source-panel contract')
    if not _hash(panel['generation_commitment'])or panel['panel_id']!=digest({k:v for k,v in panel.items()if k!='panel_id'}):raise ValueError('Public panel generation identity')
    sessions=panel['sessions']
    if not isinstance(sessions,list)or len(sessions)!=7:raise ValueError('All seven original sessions required')
    for row,person in zip(sessions,PEOPLE):
        expected={'person','recording','train_segments','validation_segments','test_segments','channel_ids'}
        train,val,test,channels=COUNTS[person]
        if not isinstance(row,dict)or set(row)!=expected or type(row['person'])is not int or row['person']!=person or row['recording']!=RECORDINGS[person]:raise ValueError('Exact held-session identity')
        if any(type(row[k])is not int or row[k]!=v for k,v in [('train_segments',train),('validation_segments',val),('test_segments',test)]):raise ValueError('Full Table6 segment support')
        ids=row['channel_ids']
        if not isinstance(ids,list)or len(ids)!=channels or any(not isinstance(x,str)or not x or len(x)>128 or any(ord(c)<32 for c in x)for x in ids)or len(set(ids))!=channels:raise ValueError('Authentic full native channel identity roster required')
    return panel


def requests(panel):
    validate_panel(panel)
    for arm in ARMS:
        for model in MODELS:
            for row in panel['sessions']:
                for i,channel in enumerate(row['channel_ids']):
                    yield {'id':f'{arm}__{model}__person{row["person"]}__channel{i:03d}','arm':arm,'model':model,'person':row['person'],'channel_id':channel,'shape':[row['test_segments'],SAMPLES]}


def validate_submission_metadata(value,panel,*,max_declared_bytes):
    """Metadata admission ONLY: caller must byte-authenticate ALL arrays before gold."""
    validate_panel(panel)
    if type(max_declared_bytes)is not int or max_declared_bytes<=0:raise ValueError('Future operator-owned byte allowance required')
    if not isinstance(value,dict)or set(value)!={'schema','task_id','panel_id','predictions'}or value['schema']!=SCHEMA or value['task_id']!=TASK_ID or value['panel_id']!=panel['panel_id']:raise ValueError('Exact candidate root identity')
    rows=value['predictions']
    if not isinstance(rows,list)or len(rows)!=OUTPUTS:raise ValueError('Complete22680 ordered masked-channel predictions required')
    total=0
    for row,expected in zip(rows,requests(panel)):
        if not isinstance(row,dict)or set(row)!={'id','values'}or row['id']!=expected['id']:raise ValueError('Complete ordered request identity')
        d=row['values']
        if not isinstance(d,dict)or set(d)!={'path','bytes','sha256','shape','dtype'}:raise ValueError('Exact primitive array descriptor')
        if not isinstance(d['path'],str)or not FILENAME.fullmatch(d['path'])or not _hash(d['sha256']):raise ValueError('Single safe NPY basename and exact SHA')
        if d['dtype']not in('<f4','<f8')or not isinstance(d['shape'],list)or any(type(x)is not int for x in d['shape'])or d['shape']!=expected['shape']:raise ValueError('Full test-segment ×6144 sample support')
        payload=expected['shape'][0]*SAMPLES*int(d['dtype'][-1])
        if type(d['bytes'])is not int or not payload<d['bytes']<=payload+4096:raise ValueError('Bounded NPY header and complete primitive payload')
        total+=d['bytes']
        if total>max_declared_bytes:raise ValueError('Operator candidate artifact allowance exceeded')
    return {'metadata_admitted':True,'array_bytes_admitted':False,'private_access_permitted':False,'requests':OUTPUTS,'declared_bytes':total}
