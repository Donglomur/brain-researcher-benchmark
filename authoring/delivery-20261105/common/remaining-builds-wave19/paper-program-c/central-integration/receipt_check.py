"""Pure metadata joins for the complete, source-bound OSL outer receipt.

No scientific operand, numerical library or process is accessed here. This
validates original source-produced records; it does not independently observe
the final adapter's exit or replace the original provider's phase evidence.
"""
import hashlib
import json
import math
from pathlib import Path
import re

TASK='PAPER-paper-signal-add-004'


def need(value,label):
    if not value:raise ValueError(label)


def encoded(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def same(left,right):
    """Exact typed JSON-tree equality without serializing entire ledger trees.

    Preserve bool/int distinctions and signed float zero. JSON inputs have
    string keys and finite scalar values; this admits no extra Python domain.
    """
    if type(left)is not type(right):return False
    if type(left)is dict:
        return (all(type(k)is str for k in left)and all(type(k)is str for k in right)
                and left.keys()==right.keys()and all(same(left[k],right[k])for k in left))
    if type(left)is list:return len(left)==len(right)and all(same(a,b)for a,b in zip(left,right))
    if type(left)is float:return math.isfinite(left)and math.isfinite(right)and left.hex()==right.hex()
    if type(left)in(str,int,bool,type(None)):return left==right
    return False


def pin(value):
    body=encoded(value);return {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}


def descriptor(value,empty=False):
    need(type(value)is dict and set(value)=={'bytes','sha256'},'exact receipt descriptor')
    need(type(value['bytes'])is int and value['bytes']>=(0 if empty else 1)
         and type(value['sha256'])is str and len(value['sha256'])==64
         and all(x in '0123456789abcdef' for x in value['sha256']),'typed receipt identity')


def number(value):return type(value)in(int,float)and math.isfinite(value)


def validate(outer,close,inner,logs,expected_jobs,operation,operation_pin,origin,attempt_path):
    end=origin+operation['limits']['wall_seconds'];work_end=end-operation['outer_cleanup_seconds']
    need(number(origin)and number(end)and origin<work_end<end,'original complete clocks')
    need(outer.get('schema')=='osl_complete_program_outer_receipt_v1' and outer.get('task_id')==TASK,'exact original outer schema')
    need(same(outer['operation'],operation_pin)and number(outer['origin'])and outer['origin']==origin
         and number(outer['deadline'])and outer['deadline']==end,'exact operation and inherited original clock')
    need(same(outer['global_limits'],operation['limits']),'no original resource partition rewriting')
    need(outer['publication_errors']==[] and outer['controller_natural_exit']is True
         and outer['independent_terminal_absence_complete']is True and outer['numerical_complete']is True,'original complete publication/custody/assessment')
    need(outer['runtime_qualified']is False and outer['scientific_qualification']is False
         and outer['whole_paper_reproduced']is False,'no runtime/scientific/wholepaper promotion')
    need(close.get('schema')=='osl_independent_controller_close_v1'and same(outer['controller_close'],pin(close))
         and same(outer['controller_close_independently_observed_in_memory'],close),'actual original controller receipt identity')
    need(type(close['exit_code'])is int and close['exit_code']==0 and close['natural_exit']is True
         and close['forced']is False and close['reaped']is True and close['process_group_absent']is True
         and close['error_type']is None and close['cleanup_errors']==[],'natural controller zero and independent cleanup')
    token=close['process_identity']
    need(type(token)is dict and set(token)=={'schema','pid','pgid','session_id','uid','start_time_ticks','boot_id'}
         and token['schema']=='osl_linux_process_identity_v1','original anchored controller identity')
    need(all(type(token[k])is int for k in ('pid','pgid','session_id','uid','start_time_ticks'))
         and token['pid']==token['pgid']==token['session_id']>1 and token['uid']>=0 and token['start_time_ticks']>0
         and type(token['boot_id'])is str and re.fullmatch('[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',token['boot_id']),
         'typed original Linux process ownership token')
    need(number(close['started'])and number(close['finished'])and origin<=close['started']<=close['finished']<end
         and number(close['work_deadline'])and close['work_deadline']==work_end
         and number(close['global_deadline'])and close['global_deadline']==end,'original controller cutoff without extension')
    root=Path(attempt_path)
    loader='import sys,runpy; p=sys.argv.pop(1); sys.path.insert(0,p); runpy.run_path(p+"/controller.py",run_name="__main__")'
    argv=[operation['host_python']['path'],'-I','-S','-B','-c',loader,str(root/'host_source'),
          '--operation',str(root/'OPERATION.json'),'--operation-sha256',operation_pin['sha256'],
          '--output',str(root/'work'),'--origin',repr(origin)]
    need(close['argv']==argv,'exact concrete original controller command')
    need(type(logs)is dict and set(logs)=={'stdout','stderr'} and same(logs,close['logs']),'captured complete controller log identities')
    for d in logs.values():descriptor(d,True)
    need(sum(d['bytes']for d in logs.values())<=operation['controller_log_bytes'],'original combined log bound')
    need(inner.get('schema')=='osl_complete_program_inner_return_v1'and inner.get('task_id')==TASK
         and same(inner['source'],operation['source_manifest']),'exact original full source in inner return')
    need(same(outer['inner_return'],{'pin':pin(inner),'value':inner}),'actual original inner receipt identity')
    need(inner['numerical_complete']is True and inner['outer_natural_exit_and_terminal_absence_required']is True,'original protected assessment complete')
    descriptor(inner['execution']);descriptor(inner['assessment'])
    need(all(inner[k]is False for k in ('runtime_qualified','scientific_qualification','whole_paper_reproduced')),'no inner promotion')
    for snapshot,limits in [(outer['outer_partition'],{k:operation['outer_'+k]for k in ('read_bytes','write_bytes','retained_bytes')}),
                            (inner['budget'],{k:operation['limits'][k]-operation['outer_'+k]for k in ('read_bytes','write_bytes','retained_bytes')})]:
        need(number(snapshot['origin'])and snapshot['origin']==origin and number(snapshot['deadline'])and snapshot['deadline']==end
             and number(snapshot['observed'])and origin<=snapshot['observed']<end,'original disjoint budget clocks')
        for key,limit in [('logical_read_charge',limits['read_bytes']),('logical_write_charge',limits['write_bytes']),('retained_charge',limits['retained_bytes'])]:
            need(type(snapshot[key])is int and 0<=snapshot[key]<=limit,'original budget partition '+key)
        need(snapshot['kernel_native_IO_or_RSS_certified']is False and snapshot['scientific_qualification']is False,'no exact kernel/resource qualification')
    ledger=outer['independent_attempt_ledger']
    need(ledger.get('schema')=='osl_independent_full_attempt_ledger_v1'
         and type(ledger['planned'])is int and ledger['planned']==5853
         and type(ledger['native'])is int and ledger['native']==453
         and type(ledger['held_hmm'])is int and ledger['held_hmm']==5400,'full original attempted scope')
    need(ledger['journal_error']is None and ledger['all_attempts_accounted_without_success_subsetting']is True
         and ledger['all_attempts_have_admitted_terminal_disposition']is True,'complete original attempt history')
    need(type(expected_jobs)is list and len(expected_jobs)==5853,'full source-generated expected jobs')
    expected={j['id']:j for j in expected_jobs};need(len(expected)==5853,'unique source job identities')
    rows=ledger['rows'];need(type(rows)is list and len(rows)==5853,'all original dispositions, no subset')
    seen=set();failed=0
    for row in rows:
        job=row['job'];key=job['id']
        need(key in expected and key not in seen and same(job,expected[key]),'every exact original job dictionary once')
        need(row['status']in('completed','failed'),'every job has an admitted terminal disposition')
        need(type(row['evidence'])is list and row['evidence'],'source journal evidence for every attempted job')
        for d in row['evidence']:descriptor(d)
        failed+=row['status']=='failed';seen.add(key)
    need(type(ledger['all_numerical_attempts_completed'])is bool
         and ledger['all_numerical_attempts_completed']==(failed==0),'failed attempts remain explicit')
    receipts=inner['phase_receipts'];recovery=outer['independent_recovery']
    need(type(receipts)is list and 5875<=len(receipts)<=11725 and type(recovery)is list
         and len(recovery)==len(receipts),'complete variable phase/recovery roster, not mandatory11725 successes')
    for d in receipts:descriptor(d)
    phases=set()
    for row in recovery:
        phase=row['phase_id'];need(type(phase)is str and len(phase)==64 and all(x in '0123456789abcdef' for x in phase)and phase not in phases,'unique original phase namespaces')
        phases.add(phase)
        if row.get('resource_creation_not_started')is True:continue
        rr=row.get('receipt',{});cli=row.get('prior_cli_custody',{})
        need(all(rr.get(k)is True for k in ('all_resource_custody_closed','all_namespaces_empty','cli_reaped'))
             and cli.get('all_recorded_cli_groups_absent')is True,'every original phase resource custody closed')
    return {'native_attempts':453,'held_attempts':5400,'all_terminal_dispositions':5853,'failed_attempts_retained':failed,
            'actual_phase_records':len(receipts),'maximum_phase_records':11725,'original_numerical_complete':True,
            'new_scientific_score_computed_by_adapter':False,'original_final_evaluation_reused':True,
            'external_adapter_natural_exit_still_required':True}
