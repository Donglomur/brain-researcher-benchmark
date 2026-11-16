"""One inherited protected producer; commit closure/output, never private grade."""
import argparse
from pathlib import Path
import sys
import time
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
import execution_support as S

def run_arm(run,end):
    lib=S.api();strict=S.recovery();budget=lib['HostBudget'](run,7500000,1800000)
    result={'candidate_id':S.ID,'status':'operator_error','handled_candidate_outcome':False,'all_workers_absent':False,'private_reference_reads':0,'private_grade_dispatched':False}
    try:
        manifest=S.runtime_manifest(run)
        S.need(time.monotonic()<end-150,'Full protected unit and recovery room')
        unit_end=min(end-10,time.monotonic()+140)
        value=lib['run_unit'](run/'program.py',manifest['program_sha256'],manifest['unit'],run/'unit',budget,unit_end,unit_end,None,S.ID,lambda *unused:None)
        S.need(value['all_owned_absent'] is True,'Protected producer/holder/volume closure')
        owned,errors=strict.inventory(run);S.need(not errors,'Exact owned resource inventory')
        absence=[strict.recover(run,folder,item,lib['BaseEngine'](end-1,folder,budget),budget) for folder,item in owned]
        S.save(run/'unit/independent_absence.json',{'resources':absence},budget)
        S.need(len(absence)==3 and all(r['absence_verified'] for r in absence),'Three exact owned resources absent')
        normal=('unit_committed','invalid_unit_submission','output_boundary_rejected','candidate_program_failed')
        timed=value['status']=='execution_failed_preserved' and value.get('candidate_wait_timed_out') is True
        S.need(value['status'] in normal or timed,'Infrastructure failure is not a candidate result')
        outcome={'candidate_id':S.ID,'condition':manifest['condition'],'program_sha256':manifest['program_sha256'],'unit_status':value['status'],'output':value.get('output'),'all_unit_resources_absent':True,'producer_output_commit_sha256':value.get('commit_sha256'),'before_any_private_grade':True}
        result['outcome_commit_sha256']=S.save(run/'unit/outcome_commit.json',outcome,budget)
        result.update(status=value['status'],handled_candidate_outcome=True,all_workers_absent=True,candidate_program_executed='producer' in value)
    except BaseException as error:result['error']=repr(error)[:2000]
    finally:S.save(run/'controller_result.json',result,budget,131072)
    return 0 if result['handled_candidate_outcome'] and result['all_workers_absent'] else 2

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--work-end',type=float,required=True);a=p.parse_args()
    raise SystemExit(run_arm(a.run.absolute(),a.work_end))
