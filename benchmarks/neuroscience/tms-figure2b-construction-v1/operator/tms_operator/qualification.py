"""Binding of independently supplied qualification reports; never an issuer.

Reading matching JSON authenticates its bytes and scope, not the truth of external
native/provider evidence. That remains the trusted operator's responsibility.
This admission cannot replace the run's actual host/container/transport checks.
"""
from pathlib import Path
from .schema import *

KINDS={'host_containment','container_isolation','storage','model_transport'}

def admit_qualification(plan,runtime,budget):
    execution_plan(plan);exact_budget(budget)
    root=Path(runtime['stage_root']);selection={k:plan[k] for k in ('runtime','capsule','operator_lock','limits')}
    value=load(root/'QUALIFICATION.json',plan['qualification'],budget,65536)
    keys(value,{'schema','status','selection','evidence'})
    require(value['schema']=='tms_figure2b_runtime_qualification_v1' and value['status']=='qualified' and value['selection']==selection,'independent qualification for exact selected runtime/source/model policy')
    keys(value['evidence'],KINDS);reports={}
    forbidden=[]
    for paths in runtime['arm_paths'].values():forbidden.extend(Path(paths[k]).absolute() for k in ('view','task','work','output','logs'))
    for kind,row in value['evidence'].items():
        keys(row,{'path','pin'});pin(row['pin']);require(type(row['path']) is str and Path(row['path']).is_absolute(),'explicit qualification metadata path')
        path=Path(row['path']).absolute();require(not any(path.is_relative_to(p) for p in forbidden),'qualification evidence outside candidate-writable and view trees')
        report=load(path,row['pin'],budget,65536)
        keys(report,{'schema','kind','status','selection','assessor','observations'})
        require(report['schema']=='tms_figure2b_external_qualification_evidence_v1' and report['kind']==kind and report['status']=='passed' and report['selection']==selection,'scoped external qualification report')
        require(type(report['assessor']) is str and 0<len(report['assessor'])<=1024 and type(report['observations']) is dict and report['observations'],'identified external assessment with retained observations')
        reports[kind]=row
    return {'qualification':plan['qualification'],'selection':selection,'evidence':reports,
        'interpretation':'Caller-trusted external assessment; byte/scope joins alone do not establish empirical truth. Actual run observations remain mandatory.'}
