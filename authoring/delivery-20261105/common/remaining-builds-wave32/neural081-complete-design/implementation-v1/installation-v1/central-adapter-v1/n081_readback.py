"""Actual complete parent graph replay; no protected target or new scorer."""
from pathlib import Path
import common as c
import closure,grading,protocol
from host_observation import admit
from n081_host import parent_argv
from n081_selection import parent_authority
import n081_shared_gate as gate

def owned_json(ctx,path,cap):
    budget=ctx['budget'];path=c.absolute(str(path));size=path.lstat().st_size;c.integer(size,1,cap)
    ctx['guard'].admit({'path':str(path),'bytes':size,'sha256':'0'*64})
    budget.charge('read_bytes',size+1);raw=gate.capture(path,size);budget.check_clock()
    return c.parse(raw),{'path':str(path),**c.pin(raw)}

def replay(ctx,outer_observation):
    budget=ctx['budget'];review=ctx['review'];config=ctx['envelope']['controller'];source=ctx['parent_source'];files=ctx['parent_files'];cap=review['memory']['metadata_cap_bytes']
    parent_authority(ctx)
    report,report_desc=owned_json(ctx,Path(ctx['envelope']['outer_output'])/'ADMISSION.json',min(cap,16*2**20))
    c.exact(report,('schema','source','intent','launch_request','original_observation','streams','controller_result','study','grade','all_original_counts','original_origin','normal_endpoint','completed_monotonic','status','budget','scientific_performance_not_established_by_source_build'))
    c.need(report['schema']=='neural081_independent_outer_admission_v1'and report['status']=='admitted_after_actual_natural_controller_and_complete_source_graph'and c.typed_equal(report['source'],source),'actual original whole outer admission')
    c.need(c.typed_equal(report['launch_request'],ctx['envelope']['launch_request'])and report['original_origin']==budget.origin and report['normal_endpoint']==budget.end,'same acyclic request and original clock')
    completed=c.finite(report['completed_monotonic']);c.need(budget.origin<=completed<=outer_observation['ended_monotonic']<=budget.end,'original outer closes after its report within original endpoint')
    def read(desc):return c.capture(desc,budget,[Path(desc['path']).parent],empty=desc['bytes']==0)
    def document(desc):return c.parse(read(desc))
    intent=document(report['intent']);c.exact(intent,('schema','source','envelope','launch_request','argv','origin','normal_endpoint','credential_names','credential_values_recorded'))
    controller_argv=parent_argv(ctx,'controller')
    for key,value in [('source',source),('envelope',review['program']),('launch_request',ctx['envelope']['launch_request']),('argv',controller_argv)]:c.need(c.typed_equal(intent[key],value),'actual controller intent '+key)
    c.need(intent['schema']=='neural081_outer_controller_intent_v1'and intent['origin']==budget.origin and intent['normal_endpoint']==budget.end and intent['credential_names']==[review['launch']['credential_name']]and intent['credential_values_recorded']is False,'actual protected original launch intent')
    c.exact(report['streams'],('stdout','stderr'));streams={name:read(desc)for name,desc in report['streams'].items()}
    original=document(report['original_observation']);admit(original,controller_argv,budget.origin,budget.end,report['streams']['stdout'],report['streams']['stderr'])
    c.need(original['ended_monotonic']<=completed,'controller completion precedes outer admission')
    for name,body in streams.items():c.need(c.pin(body)=={k:report['streams'][name][k]for k in('bytes','sha256')},'complete original controller stream')
    c.need(report['controller_result']['path']==str(Path(config['output_root'])/'RESULT.json'),'source-owned complete controller output path')
    result=document(report['controller_result'])
    c.need(result['schema']=='neural081_provisional_complete_controller_v1'and c.typed_equal(result['source'],source)and result['status']=='provisional_until_independent_whole_controller_natural_exit','actual original controller source/result')
    c.need(c.typed_equal(result['study'],report['study'])and c.typed_equal(result['grade'],report['grade']),'actual outer/controller artifact joins')
    index=protocol.validate_index(document(result['index']));protected=[index[k]for k in('protected_support_descriptor','protected_assessment_descriptor')]
    ctx['guard'].protect(protected)
    c.need(protocol.counts(index)['N']==ctx['run']['N']and c.typed_equal(protocol.counts(index),report['all_original_counts']),'complete original census and counts')
    roots=[Path(config['output_root']),config['channel']['request_root'],config['channel']['response_root'],*[r['authority']['channel_root']for r in result['channel_records']],*[Path(d['path']).parent for d in files]]
    audit=closure.AuditAccess(roots,protected,[],budget)
    study=audit.json(result['study']);c.need(c.typed_equal(study['source_files'],files)and c.typed_equal(study['index'],result['index'])and study['normal_endpoint']==budget.end,'complete original execution-source/index/clock closure')
    graph=closure.admit(result['study'],index,audit,source)
    grading.admit_panels(index,graph['panels'],audit,source)
    actual_run=closure.qualifications(result['channel_records'],source,files,audit,phases=('G0','G1','G2','G3','G5'))
    c.need(c.typed_equal(actual_run,ctx['run']),'same full original run through final protected grading')
    native=closure.native(result['grade']['closure'],audit,files,expected_job='G5/complete',expected_kind='grader')
    c.need(result['grade']['result']in native['artifacts'],'actual protected grader produced this report')
    score=audit.json(result['grade']['result'])
    c.need(c.typed_equal(score['study'],result['study'])and score['protected_reads_after_full_barrier']is True and score['provider_or_candidate_resume_allowed']is False,'actual target-last report, no resumed candidate/provider')
    budget.check_clock()
    return {'outer_admission':report_desc,'controller_result':report['controller_result'],'study':result['study'],'grade':result['grade'],'counts':protocol.counts(index),'protected_bodies_read_by_central':False,'new_score_computed':False,'complete_original_graph_replayed':True,'original_source_files':files}
