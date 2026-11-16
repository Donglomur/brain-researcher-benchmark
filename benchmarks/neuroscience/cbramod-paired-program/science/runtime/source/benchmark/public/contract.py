"""Full primary CBraMod artifact panel with separate prospective conditions."""
import hashlib
import json
import re

TASK='PAPER-paper-method-024'
MAX_ARTIFACT_BYTES=8_000_000_000
PRIMARY=['EEGNet','EEGConformer','SPaRCNet','ContraWR','CNN-Transformer','FFCL','ST-Transformer','BIOT','LaBraM-Base','CBraMod']
PROSPECTIVE=['CBraMod','EEGNet','EEGConformer','BIOT','LaBraM-Base','EEGPT','REVE']
VARIANTS=['attention_full','attention_axial','attention_CCNet','position_none','position_absolute','position_conditional','pretraining_dirty','pretraining_none']


def need(v,message):
    if not v:raise ValueError(message)


def exact(v,keys):need(type(v) is dict and set(v)==set(keys),'exact object fields')
def ident(v):need(type(v) is str and re.fullmatch('[A-Za-z0-9_.-]{1,200}',v),'safe opaque identifier')
def sha(v):need(type(v) is str and re.fullmatch('[0-9a-f]{64}',v),'SHA256')
def encode(v):return (json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode('utf-8')
def digest(v):return hashlib.sha256(encode(v)).hexdigest()


def cases(panel,purpose,reference=False):
    need(purpose in ('reproduction','improvement'),'purpose fixed before predictions')
    result=[]
    for d in panel['primary_downstream_datasets']:
        if purpose=='improvement':methods=PROSPECTIVE if reference else ['proposed']
        else:
            methods=PRIMARY.copy()
            if d['id']=='ISRUC':methods+=['DeepSleepNet','USleep']
            if d['id'] in ('TUEV','TUAB'):methods+=['LaBraM-Large','LaBraM-Huge','CBraMod_excluding_'+d['id']]
            if d['id'] in panel['central_ablation_panel']:methods+=['CBraMod_'+v for v in VARIANTS]
        for method in methods:
            for slot in range(5):
                result.append({'id':d['id']+'__'+method+'__'+str(slot),'dataset':d['id'],'method':method,'seed_slot':slot,'columns':d['classes'] or 1})
    return result


def validate_query(q,panel):
    exact(q,('schema','task_id','purpose','condition','datasets','source_qualification_sha256','metric_abi'))
    need(q['schema']=='cbramod_query_v1' and q['task_id']==TASK,'task query identity');sha(q['source_qualification_sha256'])
    cases(panel,q['purpose'])
    expected='paper_original_splits' if q['purpose']=='reproduction' else 'person_heldout_low_label_30pct'
    need(q['condition']==expected,'separate original and prospective conditions')
    abi=q['metric_abi'];exact(abi,('pr_definition','seed_sd_ddof','class_decision','undefined_policy','native_source_sha256'))
    need(abi['pr_definition'] in ('unresolved','average_precision','trapezoidal_pr_auc'),'explicit PR definition')
    need(abi['seed_sd_ddof'] is None or type(abi['seed_sd_ddof']) is int and abi['seed_sd_ddof'] in (0,1),'explicit seed SD convention')
    need(abi['class_decision']=='argmax_lowest_index_tie' and abi['undefined_policy']=='explicit_null_no_support_drop','declared canonical artifact conventions')
    if abi['native_source_sha256'] is not None:sha(abi['native_source_sha256'])
    need(type(q['datasets']) is list and len(q['datasets'])==len(panel['primary_downstream_datasets']),'all12 primary datasets')
    for row,d in zip(q['datasets'],panel['primary_downstream_datasets']):
        exact(row,('id','class_labels','rows','training_groups','validation_groups','split_sha256','preprocessing_sha256','input_sha256','label_selection_sha256','sequence_assignment_sha256'))
        need(row['id']==d['id'],'fixed full dataset order')
        for key in ('split_sha256','preprocessing_sha256','input_sha256','label_selection_sha256'):sha(row[key])
        if d['id']=='ISRUC':sha(row['sequence_assignment_sha256'])
        else:need(row['sequence_assignment_sha256'] is None,'sequence context only for ISRUC')
        labels=row['class_labels']
        need(type(labels) is list and len(labels)==(d['classes'] or 0) and len(set(labels))==len(labels),'complete class order or empty regression ontology')
        for label in labels:ident(label)
        train=row['training_groups'];validation=row['validation_groups']
        for groups in (train,validation):
            need(type(groups) is list and 1<=len(groups)<=20000 and groups==sorted(set(groups)),'complete ordered biological groups')
            for group in groups:ident(group)
        need(type(row['rows']) is list and 2<=len(row['rows'])<=d['total_paper_samples'],'bounded complete frozen assessment support')
        ids=[];test=set()
        for sample in row['rows']:
            exact(sample,('id','group'));ident(sample['id']);ident(sample['group']);ids.append(sample['id']);test.add(sample['group'])
        need(len(ids)==len(set(ids)),'unique assessment identities, no duplicate windows')
        whole_person=q['purpose']=='improvement' or d['split_unit'] in ('whole_subject','whole_subject_sequence')
        if whole_person:need(not set(train)&set(validation) and not test&set(train) and not test&set(validation),'whole-person split; no train/validation/test identity overlap')
        # Unknown source exclusions, trial joins and authentic cohorts are not
        # certified by these structural checks or by self-declared hashes.
    return q


def submission(c,q,panel):
    validate_query(q,panel)
    exact(c,('schema','task_id','query_sha256','information_arm','files'))
    need(c['schema']=='cbramod_prediction_artifacts_v1' and c['task_id']==TASK and c['query_sha256']==digest(q),'exact submission identity')
    need(c['information_arm'] in ('paper_and_data','paper_data_official_code'),'declared access label, not attestation')
    spec=cases(panel,q['purpose']);need(type(c['files']) is list and len(c['files'])==len(spec),'full method/condition/five-seed panel')
    counts={d['id']:len(d['rows']) for d in q['datasets']};names=set();total=0
    for f,case in zip(c['files'],spec):
        exact(f,('case','path','shape','dtype','bytes','sha256'));need(f['case']==case['id'],'ordered case identity')
        need(type(f['path']) is str and re.fullmatch('predictions/[A-Za-z0-9_.-]{1,160}\\.npy',f['path']) and f['path'] not in names,'safe unique prediction path');names.add(f['path'])
        need(type(f['shape']) is list and all(type(v) is int for v in f['shape']) and f['shape']==[counts[case['dataset']],case['columns']],'exact full prediction rectangle')
        need(f['dtype'] in ('<f4','<f8'),'numeric float32/64 C-order artifact')
        need(type(f['bytes']) is int and 80<=f['bytes']<=MAX_ARTIFACT_BYTES,'bounded artifact bytes');sha(f['sha256']);total+=f['bytes']
    need(total<=MAX_ARTIFACT_BYTES,'complete candidate byte budget')
    return spec
