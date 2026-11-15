"""Trusted local owner comparison of a frozen JSON submission; no program execution.

Reuses the accepted strict validator and complete reporting/continuous-error API.
The owner supplies the pinned lock and arm; neither comes from candidate content.
All reports remain private. Exit0 means comparison completed, not scientific pass.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys

LIMIT=65536
MODULES=('custody','reporting_core','extended_score','reporting_resolution')


def need(ok,code):
    if not ok:raise ValueError(code)


def bootstrap(path,sha,account):
    path=Path(path)
    need(path.is_absolute() and '..' not in path.parts and
         not any(p.is_symlink() for p in (path,*path.parents)), 'owner_lock_path')
    account['conservative_requested_bytes']+=LIMIT+1
    with path.open('rb') as stream:
        need(stat.S_ISREG(os.fstat(stream.fileno()).st_mode),'owner_lock_regular')
        raw=stream.read(LIMIT+1)
    need(len(raw)<=LIMIT and hashlib.sha256(raw).hexdigest()==sha,'owner_lock_identity')
    return json.loads(raw)


def load_owner(path,sha,accounting):
    need(type(accounting) is dict and set(accounting)=={'conservative_requested_bytes','authenticated_body_bytes'}
         and all(type(v) is int and v>=0 for v in accounting.values()),'caller_owned_read_ledger')
    lock=bootstrap(path,sha,accounting)
    need(lock['schema']=='nider_full120_local_owner_lock_v1' and
         lock['task']=='PAPER-EXP-20261113-003' and set(lock['modules'])==set(MODULES), 'owner_lock_schema')
    need(not any(name in sys.modules for name in MODULES),'fresh_owner_module_namespace')
    modules={}
    for name in MODULES:
        e=lock['modules'][name];p=Path(e['path'])
        need(p==Path(__file__).with_name(name+'.py') and not p.is_symlink(),'owner_source_location')
        accounting['conservative_requested_bytes']+=1048577
        with p.open('rb') as stream:body=stream.read(1048577)
        need(len(body)==e['bytes']<=1048576 and hashlib.sha256(body).hexdigest()==e['sha256'],'owner_source_identity')
        accounting['authenticated_body_bytes']+=len(body)
        spec=importlib.util.spec_from_file_location(name,p);module=importlib.util.module_from_spec(spec)
        sys.modules[name]=module;exec(compile(body,str(p),'exec'),module.__dict__);modules[name]=module
    c=modules['custody'];accounting['conservative_requested_bytes']+=LIMIT+1
    ref=c.read_pin(lock['reference'],LIMIT);accounting['authenticated_body_bytes']+=len(ref)
    doc=modules['reporting_core'].decode_numeric_json(ref)
    validated=modules['extended_score'].validate(doc,'A',lock['workbook_sha256'])
    need(lock['reference_arm']=='A' and lock['expected_fields']==120,'qualified_reference_scope')
    return {'lock':lock,'lock_pin':{'path':str(path),'sha256':sha},'modules':modules,
            'reference_bytes':ref,'reference_document':doc,'reference_validated':validated,
            'accounting':accounting}


def compare_file(owner,candidate_path,candidate_sha,arm,output):
    c=owner['modules']['custody'];reporting=owner['modules']['reporting_core']
    validator=owner['modules']['extended_score'];criterion=owner['modules']['reporting_resolution']
    need(arm in ('A','B'),'owner_selected_arm')
    candidate=c.plain(candidate_path);out=c.plain(output)
    need(out.parent.is_dir() and not out.exists(),'fresh_private_report_directory')
    entry={'path':str(candidate),'bytes':candidate.stat().st_size,'sha256':candidate_sha}
    owner['accounting']['conservative_requested_bytes']+=LIMIT+1
    raw=c.read_pin(entry,LIMIT)
    owner['accounting']['authenticated_body_bytes']+=len(raw)
    validated=validator.validate(reporting.decode_numeric_json(raw),arm,owner['lock']['workbook_sha256'])
    result=criterion.compare_validated(validated,owner['reference_validated'])
    need(len(result['cells'])==120 and result['continuous_total_fields']==120 and
         result['continuous_fields_excluded']==0 and result['held_binary_real_cells']==72 and
         result['aggregate_binary_pass_defined'] is False,'complete_comparison_scope')
    counts={};finite=0;undefined=0;nonzero=0;metadata_bad=0
    for row in result['cells']:
        counts[row['status']]=counts.get(row['status'],0)+1
        error=row['continuous_error'];metadata_bad+=not row['exact_metadata_agreement']
        if error['state']=='FINITE':
            finite+=1;nonzero+=int(error['absolute_error']['numerator'])!=0
        else:undefined+=1
    summary={'schema':'nider_full120_private_comparison_summary_v1','arm':arm,'fields':120,
             'reported_real_fields':27,'exact_integer_fields':21,'continuous_only_real_fields':72,
             'status_counts':counts,'finite_errors':finite,'undefined_errors':undefined,
             'nonzero_errors':nonzero,'metadata_mismatching_cells':metadata_bad,
             'aggregate_scientific_pass_defined':False,'comparison_completed':True,
             'reference_copy_is_only_grader_sanity':True,'new_benchmarks':0}
    binding={'schema':'nider_full120_owner_input_binding_v1','owner_lock':owner['lock_pin'],
             'reference':owner['lock']['reference'],'candidate':entry,'owner_selected_arm':arm,
             'workbook_sha256':owner['lock']['workbook_sha256'],'owner_only_reports':True}
    bodies={'OWNER_REPORT.json':c.encoded(result),'SUMMARY.json':c.encoded(summary),
            'INPUT_BINDING.json':c.encoded(binding)}
    need(sum(map(len,bodies.values()))<=262144,'private_comparison_output_extent')
    out.mkdir(mode=0o700)
    for name,body in bodies.items():c.write_new(out/name,body)
    return result,summary


def main(argv,accounting):
    os.umask(0o077)
    need(len(argv)==7,'usage_lock_locksha_arm_candidate_candidatesha_new_output')
    owner=load_owner(argv[1],argv[2],accounting);_,summary=compare_file(owner,argv[4],argv[5],argv[3],argv[6])
    print(json.dumps({'comparison_completed':True,'fields':120,'private_report_directory':argv[6],
                      'aggregate_scientific_pass_defined':False}))
    return 0


if __name__=='__main__':
    accounting={'conservative_requested_bytes':0,'authenticated_body_bytes':0}
    try:raise SystemExit(main(sys.argv,accounting))
    except Exception as error:
        print(json.dumps({'comparison_completed':False,'error_class':type(error).__name__,
                          'error':str(error),'retry':False,'body_accounting':accounting}),file=sys.stderr)
        raise SystemExit(2)
