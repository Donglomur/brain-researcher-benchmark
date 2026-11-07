"""Protected future evaluator composition; only invented correctness checks run.

No CLI bypass exists. Numeric science is paused. A future root-selected grader
must authenticate external closure, this exact complete source, both programs,
full private target identity and separate scientific authority before calling.
"""

def grade(s,source,bodies,external,external_pin,root,read,load_gold,authority):
    c.need(type(authority)is dict and set(authority)=={'schema','task_id','source','external','scientific_grading_authorized','private_gold','query_generation'} and authority['schema']=='neural014-protected-grading-authority-v1' and authority['task_id']=='NEURAL-014' and authority['scientific_grading_authorized']is True and authority['source']==source and authority['external']==external_pin,'separate actual grading authorization and closure pin')
    c.exact_pin(authority['private_gold'])
    c.need(c.pin(external)==external_pin,'exact captured external closure bytes')
    outer=c.parse(external)
    c.need(outer.get('schema')=='neural014_complete_external_v1' and outer.get('status')=='complete_unqualified' and outer.get('source')==source and outer.get('attempt')==str(root) and outer.get('grading_performed')is False and outer.get('scientific_qualified')is False,'exact unscored source producer closure')
    c.need(outer.get('executing_outer_source')==c.pin(bodies['transport/run.py']) and outer.get('executing_worker_source')==c.pin(bodies['transport/worker.py']),'protected grade executing outer/worker source join')
    child=outer['child'];c.need(child.get('natural_exit')is True and type(child.get('exit_code'))is int and child['exit_code']==0 and child.get('process_reaped')is True and child.get('process_group_absent')is True and child.get('streams_closed')is True,'independent natural outer-child closure evidence')
    # Re-read every source-bound model/request/native/raw output through the
    # same independent admission; candidate cannot choose comparator artifacts.
    complete_raw=read(root/'COMPLETE.json',packet.JSON_CAP)
    complete=c.parse(complete_raw)
    result=dict(schema='neural014-worker-result-v1',status='complete_unqualified',source=source,complete=c.pin(complete_raw),phase_count=complete['phase_count'])
    join=outputs.admit_collection(s,source,bodies,result,root,read)
    c.need(c.encoded(join)==c.encoded(outer['joined_collection']),'protected grade joins independent outer collection')
    public=c.parse(read(s['public_manifest']['path'],packet.JSON_CAP,c.only_pin(s['public_manifest'])))
    c.need(public['generation']==authority['query_generation'],'separate exact gold generation')
    candidate=outputs.candidate_parse(read(root/'candidate.json',packet.JSON_CAP,join['panels']['candidate']))
    reference=outputs.candidate_parse(read(root/'independent_reference.json',packet.JSON_CAP,join['panels']['independent_reference']))
    def protected_gold():
        raw=load_gold();c.need(type(raw)is bytes and c.pin(raw)==authority['private_gold'],'exact independently selected private target bytes')
        return outputs.candidate_parse(raw)
    return outputs.compare(packet.suite(public),candidate,reference,protected_gold)
