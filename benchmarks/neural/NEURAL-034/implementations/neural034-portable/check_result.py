"""Read only a finished NEURAL-034 output tree; never open labels or execute code.

Consistency inspection of trusted-owner receipts, not an independent sandbox or
proof that untrusted forged receipts describe a real execution.
"""
from pathlib import Path
import argparse,hashlib,json,math,os,stat
COMPARATORS={'constant','amplitude','glial','behavior','combined','time_scrambled'}

def need(ok,message):
    if not ok:raise ValueError(message)

def read(path,cap=300000):
    path=Path(path).absolute()
    need(not any(p.is_symlink()for p in(path,*path.parents)),'unlinked output')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        s=os.fstat(fd);need(stat.S_ISREG(s.st_mode)and s.st_nlink==1 and 0<s.st_size<=cap,'bounded ordinary output')
        with os.fdopen(fd,'rb',closefd=False)as f:b=f.read(cap+1)
        t=os.fstat(fd);u=path.lstat();keys=('st_dev','st_ino','st_mode','st_size','st_nlink','st_mtime_ns','st_ctime_ns')
        need(len(b)==s.st_size and all(getattr(s,k)==getattr(t,k)==getattr(u,k)for k in keys),'stable extent');return b
    finally:os.close(fd)

def decode(b):
    def pairs(rows):
        d={}
        for k,v in rows:need(k not in d,'duplicate JSON field');d[k]=v
        return d
    return json.loads(b,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'nonfinite JSON'))

def sha(b):return hashlib.sha256(b).hexdigest()

def check(root):
    root=Path(root).absolute()
    outer=decode(read(root/'outer_execution.json'))
    need(outer.get('candidate_id')=='NEURAL-034'and outer.get('status')=='program_scored','completed whole task')
    for k in ('all_owned_absent','all_process_groups_absent_and_reaped','all_owned_cli_processes_absent','controller_direct_handle_reaped'):
        need(outer.get(k)is True,'closed '+k)
    inner_b=read(root/'attempt/execution.json');inner=decode(inner_b)
    need(sha(inner_b)==outer['inner_execution_sha256']and inner.get('status')=='program_scored'and inner.get('all_owned_absent')is True,'exact closed inner execution')
    need(inner.get('private_grade_dispatched')is True and len(inner['units'])==7,'all seven before grading')
    for i,u in enumerate(inner['units']):
        need(u.get('unit_id')==f'fold-{i:02d}'and u.get('status')=='unit_committed'and u.get('all_owned_absent')is True,'complete ordered units')
        execution=read(root/f'attempt/fold-{i:02d}/execution.json')
        need(sha(execution)==u['execution_sha256'],'unit execution identity')
        state=decode(execution)
        need(state.get('candidate_id')=='NEURAL-034'and state.get('unit_id')==u['unit_id']and state.get('status')=='unit_committed'and state.get('all_owned_absent')is True,'complete consistent unit execution')
        need(state.get('program_sha256')==inner['program_sha256'],'same executed programme')
    agg=decode(read(root/'attempt/aggregate_commit.json'))
    need(agg.get('status')=='all_seven_removed_producers_committed'and agg.get('all_units_absent_before_private_grade')is True,'full closure barrier')
    need(sha(read(root/'attempt/program.py',65536))==agg['program_sha256']==inner['program_sha256'],'same committed arbitrary program')
    probabilities=read(root/'attempt/probabilities.json',100000)
    need(sha(probabilities)==agg['submission_sha256'],'aggregate output identity')
    result=decode(probabilities);need(type(result['schema_version'])is int and result['schema_version']==1 and len(result['probabilities'])==140,'complete 140 rows')
    ids=set();counts=[0]*7
    for row in result['probabilities']:
        need(set(row)=={'fold','query_id','probability'}and type(row['fold'])is int and 0<=row['fold']<7 and type(row['query_id'])is str and len(row['query_id'])==24,'output fields')
        key=(row['fold'],row['query_id']);need(key not in ids,'no duplicate ID');ids.add(key);counts[row['fold']]+=1
        p=row['probability'];need(type(p)in(int,float)and math.isfinite(p)and 0<=p<=1,'finite probability')
    need(counts==[20]*7,'all seven complete folds')
    previous=None
    for i,want in enumerate(agg['unit_commit_sha256']):
        need(i<7,'no extra fold')
        b=read(root/f'attempt/fold-{i:02d}/commit.json',100000);v=decode(b)
        need(sha(b)==want and v.get('status')=='removed_producer_output_committed'and v['program_sha256']==agg['program_sha256']and v['previous_commit_sha256']==previous and v.get('producer_removed_before_capture')is True and v.get('all_candidate_holder_volume_absent')is True,'exact commitment chain')
        output=read(root/f'attempt/fold-{i:02d}/probabilities.json',100000)
        need(v['output']=={'bytes':len(output),'sha256':sha(output)},'captured unit output')
        execution=decode(read(root/f'attempt/fold-{i:02d}/execution.json'))
        need(execution.get('commit_sha256')==want and execution.get('output')==v['output'],'unit execution joins its output/commit')
        unit=decode(output)
        need(set(unit)=={'schema_version','probabilities'}and type(unit['schema_version'])is int and unit['schema_version']==1 and len(unit['probabilities'])==20,'unit output schema')
        expected=[{'query_id':r['query_id'],'probability':r['probability']}for r in result['probabilities']if r['fold']==i]
        need(sorted(unit['probabilities'],key=lambda r:r['query_id'])==sorted(expected,key=lambda r:r['query_id']),'unit outputs equal committed aggregate')
        previous=want
    need(len(agg['unit_commit_sha256'])==7 and agg['last_commit_sha256']==previous,'complete final commit')
    grade_b=read(root/'attempt/grade/score.json',150000);grade=decode(grade_b)
    need(sha(grade_b)==inner['grade']['score_sha256']and inner['grade'].get('absence_verified')is True,'closed exact grade')
    need(inner['grade'].get('submission_sha256')==agg['submission_sha256'],'grade binds committed aggregate')
    need(grade.get('status')=='scored'and len(grade['per_mouse'])==7 and {r['fold']for r in grade['per_mouse']}==set(range(7)),'complete per-mouse scoring')
    for row in grade['per_mouse']:
        need(set(row)=={'fold','balanced_accuracy','log_loss'}and type(row['fold'])is int,'complete typed per-mouse fields')
        need(all(type(row[k])in(int,float)and math.isfinite(row[k])for k in ('balanced_accuracy','log_loss'))and 0<=row['balanced_accuracy']<=1 and row['log_loss']>=0,'finite per-mouse metrics')
    need(set(grade['co_primary_metrics'])=={'balanced_accuracy','log_loss'}and set(grade['signed_candidate_minus_reference'])==COMPARATORS,'both metrics and all six comparisons')
    for metrics in [grade['co_primary_metrics'],*grade['signed_candidate_minus_reference'].values()]:
        need(set(metrics)=={'balanced_accuracy','log_loss'}and all(type(v)in(int,float)and math.isfinite(v)for v in metrics.values()),'finite complete metrics')
    primary=grade['co_primary_metrics']
    need(0<=primary['balanced_accuracy']<=1 and primary['log_loss']>=0,'co-primary metric domains')
    try:
        expected={k:math.fsum(r[k]for r in grade['per_mouse'])/7 for k in ('balanced_accuracy','log_loss')}
    except OverflowError as error:
        raise ValueError('representable equal-mouse metrics')from error
    # Recompute the exact reduction used by the frozen grader, without an
    # arbitrary tolerance that could admit a different reported result.
    need(primary==expected,'co-primary metrics equal the seven-mouse means')
    return {'status':'consistent_closed_seven_fold_result','cases':140,'mice':7,'score':grade['co_primary_metrics'],'actual_runtime_independently_attested_by_this_checker':False}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);a=p.parse_args();print(json.dumps(check(a.output),allow_nan=False))
