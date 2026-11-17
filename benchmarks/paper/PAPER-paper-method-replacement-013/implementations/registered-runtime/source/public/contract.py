"""Full candidate and qualified support metadata contracts; no data at import."""
from io_contract import *
from array_io import descriptor
from panel import PANEL,COHORTS,definition,visible_modalities
from bisect import bisect_left

KINDS={'regression':1,'joint':3,'classification':25}

def support(row):
    exact(row,('id','recording','animal','start_tick','stop_tick','context_start_tick','split'))
    for k in ('id','recording','animal'):identifier(row[k])
    require(row['split'] in ('train','validation','test'),'support split')
    for k in ('start_tick','stop_tick','context_start_tick'):require(type(row[k]) is int and row[k]>=0,'integer source ticks')
    require(row['context_start_tick']<=row['start_tick']<row['stop_tick'],'ordered support extent')
    return row

def validate_support(rows,policy):
    require(type(rows) is list and 0<len(rows)<=1000000,'bounded complete support')
    for r in rows:support(r)
    require(len({r['id'] for r in rows})==len(rows),'unique windows')
    require(len({(r['recording'],r['start_tick'],r['stop_tick']) for r in rows})==len(rows),'unique original temporal windows')
    groups={s:[r for r in rows if r['split']==s] for s in ('train','validation','test')}
    require(all(groups.values()),'all three partitions required')
    # Compare complete receptive-field intervals, not just center timestamps.
    if policy in ('blocked_time','held_session'):
        by={}
        for r in rows:by.setdefault(r['recording'],[]).append(r)
        for rec,vals in by.items():
            vals=sorted(vals,key=lambda r:r['context_start_tick']);ends={s:-1 for s in groups}
            for r in vals:
                require(all(ends[s]<=r['context_start_tick'] for s in ends if s!=r['split']), 'cross-partition context overlap')
                ends[r['split']]=max(ends[r['split']],r['stop_tick'])
    if policy=='held_session':
        ids={s:{r['recording'] for r in v} for s,v in groups.items()}
        require(all(not ids[a]&ids[b] for a,b in (('train','validation'),('train','test'),('validation','test'))),'held-session partition')
    return groups

def query(q,production=True):
    exact(q,('schema','task_id','source_revision','cohorts','supports','cases','qualification'))
    require(q['schema']=='neuroformer_query_v1' and q['task_id']==TASK and q['source_revision']==REVISION,'query identity')
    exact(q['cohorts'],COHORTS)
    for name,n in COHORTS.items():
        r=q['cohorts'][name];exact(r,('neurons','source_recording','animal','source_manifest_sha256'))
        require(type(r['neurons']) is int and r['neurons']==(n if production else 2),'complete native neuron roster')
        identifier(r['source_recording']);identifier(r['animal']);sha256(r['source_manifest_sha256'])
    exact(q['qualification'],('source_manifest_sha256','split_plan_sha256','normalization_sha256','bridge_sha256','metric_profile','native_runtime_qualified'))
    for k in ('source_manifest_sha256','split_plan_sha256','normalization_sha256','bridge_sha256'):sha256(q['qualification'][k])
    require(q['qualification']['metric_profile'] in ('prospective_finite_artifact_v1','qualified_source_v1'),'explicit metric profile')
    require(type(q['qualification']['native_runtime_qualified']) is bool,'qualification boolean')
    require(type(q['supports']) is dict and 0<len(q['supports'])<=32,'bounded shared support plans')
    support_groups={}
    for key,sp in q['supports'].items():
        identifier(key);exact(sp,('cohort','policy','rows'));require(sp['cohort'] in COHORTS and sp['policy'] in ('source_split','blocked_time','held_session'),'support plan identity')
        support_groups[key]=validate_support(sp['rows'],sp['policy'])
    require(type(q['cases']) is list and len(q['cases'])==len(PANEL),'full case panel')
    for c,p in zip(q['cases'],PANEL):
        exact(c,('definition','policy','support_id','output_shape','class_centers','bindings'))
        require(c['definition']==p,'exact declared panel order')
        expected='held_session' if p['family']=='held_session_speed' else 'blocked_time' if p['family'].startswith('blocked_') else 'source_split'
        require(c['policy']==expected,'separate original/prospective split')
        require(c['support_id'] in q['supports'],'known complete support')
        sp=q['supports'][c['support_id']];require(sp['cohort']==p['cohort'] and sp['policy']==c['policy'],'case/support identity join')
        g=support_groups[c['support_id']]
        if p['kind']=='counts' and 'neural_history' in visible_modalities(p):
            test=g['test']
            by_record={}
            for r in test:by_record.setdefault(r['recording'],[]).append((r['start_tick'],r['stop_tick']))
            by_record={k:sorted(v) for k,v in by_record.items()};starts={k:[a for a,b in v] for k,v in by_record.items()}
            require(all(all(a[1]<=b[0] for a,b in zip(v,v[1:])) for v in by_record.values()),'nonoverlapping rollout output blocks')
            for i,r in enumerate(test):
                if i==0 or r['recording']!=test[i-1]['recording'] or r['start_tick']!=test[i-1]['stop_tick']:
                    lo,hi=r['start_tick']-30,r['start_tick']
                    intervals=by_record[r['recording']];j=bisect_left(starts[r['recording']],hi)-1
                    require(j<0 or intervals[j][1]<=lo,'initial history intersects an assessed query block')
        n=len(g['test']);neurons=q['cohorts'][p['cohort']]['neurons']
        shape=[n,10,neurons] if p['kind']=='counts' else [n,KINDS[p['kind']]]
        require(c['output_shape']==shape,'complete output geometry')
        if p['kind']=='classification':
            require(type(c['class_centers']) is list and len(c['class_centers'])==25,'25 source-bound class centers')
            for x in c['class_centers']:number(x)
            require(all(a<b for a,b in zip(c['class_centers'],c['class_centers'][1:])),'strict ordered class centers')
        else:require(c['class_centers'] is None,'no invented classification map')
        exact(c['bindings'],('preprocessing_sha256','source_metric_qualification_sha256','reference_training_sha256'))
        for v in c['bindings'].values():sha256(v)
    # Matched few-shot arms share the exact observation/label budget.
    rows={c['definition']['id']:c for c in q['cases']}
    for cohort in COHORTS:
        for family in ('speed_regression','speed_classification','neural_ablation'):
            family_rows=[c for c in q['cases'] if c['definition']['cohort']==cohort and c['definition']['family']==family]
            require(all(rows_for(q,c)==rows_for(q,family_rows[0]) for c in family_rows),'identical family assessment/training support')
        full=rows[f'{cohort}--speed_regression--neuroformer--100']
        for pct in (1,10):
            a=rows[f'{cohort}--fewshot_speed--pretrained--{pct}'];b=rows[f'{cohort}--fewshot_speed--scratch--{pct}']
            require(a['support_id']==b['support_id'],'matched pretrained/scratch support')
            ag=support_groups[a['support_id']];fg=support_groups[full['support_id']]
            ai={r['id'] for r in ag['train']};fi={r['id'] for r in fg['train']}
            require(ai<=fi and len(ai)==(len(fi)*pct+99)//100,'declared training-window label budget')
            require(ag['validation']==fg['validation'] and ag['test']==fg['test'],'few-shot fixed validation/test support')
            require(all(r in fg['train'] for r in ag['train']),'exact same training observations')
        lo=support_groups[rows[f'{cohort}--fewshot_speed--pretrained--1']['support_id']]['train'];hi=support_groups[rows[f'{cohort}--fewshot_speed--pretrained--10']['support_id']]['train']
        require(all(r in hi for r in lo),'prospective nested label budget')
    return q

def rows_for(q,c):return q['supports'][c['support_id']]['rows']

def target_binding(q,t):
    exact(t,('schema','query_sha256','bridge','bridge_sha256','external_source_qualification_required'))
    require(t['schema']=='neuroformer_private_binding_v1' and t['query_sha256']==digest(q),'private query identity')
    require(t['bridge_sha256']==digest(t['bridge'])==q['qualification']['bridge_sha256'],'externally selected query binds exact bridge/array pins')
    require(t['external_source_qualification_required'] is True,'source qualification boundary')
    return t

def output_index(q):
    return {'schema':'neuroformer_output_index_v1','task_id':TASK,'query_sha256':digest(q),
       'cases':[{'case_id':c['definition']['id'],'shape':c['output_shape'],'kind':c['definition']['kind']} for c in q['cases']]}

def submission(v,q):
    exact(v,('schema','task_id','query_sha256','arm','predictions'))
    require(v['schema']=='neuroformer_submission_v1' and v['task_id']==TASK and v['query_sha256']==digest(q),'submission identity')
    require(v['arm'] in ARMS,'access condition')
    require(type(v['predictions']) is list and len(v['predictions'])==len(q['cases']),'complete predictions')
    names=[]
    for i,(r,c) in enumerate(zip(v['predictions'],q['cases'])):
        exact(r,('case_id','array'));require(r['case_id']==c['definition']['id'],'complete ordered cases');d=descriptor(r['array'])
        require(d['path']==f'predictions/{i:04d}.npy' and d['shape']==c['output_shape'],'fixed output path and full support')
        require(d['dtype']==('<i4' if c['definition']['kind']=='counts' else '<f8'),'output dtype');names.append(d['path'])
    require(len(names)==len(set(names)),'unique output paths');return v
