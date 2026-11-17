"""One protected source-owned G5 worker after complete controller G4 admission."""
from pathlib import Path
import common as c
from runtime import Runtime,admit_closure
from reference_driver import unique_descriptors,artifact

NAMES=frozenset(('common','protocol','arrays','custody','outputs','metrics','grading','closure','schedule','runtime','host_observation','candidate_runner','transport','transport.common','transport.provider','transport.process','authority'))

def run(index,index_desc,study,barrier,metadata_readset,protected,source,manifest,worker_io,runtime,budget,output_root):
    c.need(type(runtime)is Runtime,'actual source-owned native G5')
    c.exact(manifest,('schema','entry','bootstrap','modules','dependency_qualification','installed_versions'))
    c.need(manifest['schema']=='neural081_grader_source_manifest_v1'and manifest['entry']['path'].endswith('/grade_entry.py')and manifest['bootstrap']['path'].endswith('/worker_bootstrap.py'),'literal isolated protected grader')
    names=[r['name']for r in manifest['modules']];c.need(len(names)==len(NAMES)and set(names)==NAMES,'complete fixed protected grader module roster')
    sources=[manifest['entry'],manifest['bootstrap'],*[r['source']for r in manifest['modules']]]
    for d in sources:c.descriptor(d)
    c.need(c.typed_equal(protected,[index['protected_support_descriptor'],index['protected_assessment_descriptor']]),'only exact complete two protected target operands')
    before=c.capture_json(barrier,budget,[Path(barrier['path']).parent])
    c.need(before['schema']=='neural081_complete_pretarget_barrier_v1'and before['protected_body_reads']==0 and type(before['protected_body_reads'])is int and c.typed_equal(before['metadata_reads'],metadata_readset)and c.typed_equal(before['study'],study),'all-source complete G4 barrier and exact observed readset')
    allowed=unique_descriptors([*metadata_readset,*protected,index_desc,study,barrier])
    c.exact(worker_io,('read_bytes','write_bytes'))
    floor=2*sum(d['bytes']+1 for d in allowed)+3*sum(d['bytes']+1 for d in sources)+32*2**20
    c.need(c.integer(worker_io['read_bytes'],1)>=floor and c.integer(worker_io['write_bytes'],1)>=2**20,'complete repeated admission and targets in original G5 IO envelope')
    root=c.new_directory(output_root,budget);job='G5/complete';deadline=min(budget.end,budget.clock()+3600.)
    work=runtime.allocate(job);md=c.publish_json(root/'SOURCE.json',manifest,budget)
    payload={'schema':'neural081_protected_grade_request_v1','source':source,'index':index_desc,'study':study,'output_root':str(work)}
    request={'schema':'neural081_grader_worker_request_v1','job':job,'source':source,'payload':payload,'output_root':str(work),'allowed':allowed,'protected':protected,'source_manifest':md,'clock':{'origin':budget.origin,'deadline':deadline},'worker_io':worker_io}
    rd=c.publish_json(root/'REQUEST.json',request,budget)
    mounted=unique_descriptors([*allowed,*sources,manifest['dependency_qualification'],md,rd]);opaque={d['path']for d in protected}
    mounts=[{'source':d,'target':d['path'],'opaque_host':d['path']in opaque}for d in mounted]
    entry,boot=manifest['entry'],manifest['bootstrap']
    argv=['--request',rd['path'],'--request-bytes',str(rd['bytes']),'--request-sha256',rd['sha256'],'--bootstrap',boot['path'],'--bootstrap-bytes',str(boot['bytes']),'--bootstrap-sha256',boot['sha256'],'--read-cap',str(worker_io['read_bytes']),'--write-cap',str(worker_io['write_bytes']),'--origin',str(budget.origin),'--deadline',str(deadline),'--entry-bytes',str(entry['bytes'])]
    observed=runtime.run(job,entry['path'],mounts,argv,seconds=3600,memory_bytes=8*2**30,kind='grader',worker_io=worker_io,workspace=work,original_deadline=deadline)
    admit_closure(observed);result=artifact(observed,'RESULT.json');body=c.capture_json(result,budget,[Path(result['path']).parent])
    c.need(body['schema']=='neural081_complete_assessment_v4'and c.typed_equal(body['source'],source)and c.typed_equal(body['study'],study)and body['protected_reads_after_full_barrier']is True and body['provider_or_candidate_resume_allowed']is False,'actual original protected assessment only after full barrier')
    budget.check_clock();return {'result':result,'closure':observed['receipt'],'request':rd,'barrier':barrier,'original_deadline':deadline,'worker_io':worker_io}
