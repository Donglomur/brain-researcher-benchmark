"""Exactly ten source-owned trusted G0 workers; ordinary host sees descriptors."""
from pathlib import Path
import common as c
import protocol as p
from reference_driver import unique_descriptors,artifact

NAMES=frozenset(('common','protocol','arrays','custody','outputs','preparation','preparation_worker'))

def source_members(manifest):
    c.exact(manifest,('schema','entry','bootstrap','modules','dependency_qualification','installed_versions'))
    c.need(manifest['schema']=='neural081_preparation_source_manifest_v1','source-owned G0 entry closure')
    c.need(manifest['entry']['path'].endswith('/preparation_entry.py')and manifest['bootstrap']['path'].endswith('/worker_bootstrap.py'),'literal isolated G0 bootstrap')
    names=[]
    for row in manifest['modules']:c.exact(row,('name','source'));names.append(row['name']);c.descriptor(row['source'])
    c.need(len(names)==len(NAMES)and set(names)==NAMES,'all seven fixed preparation modules')
    sources=[manifest['entry'],manifest['bootstrap'],*[r['source']for r in manifest['modules']]]
    c.need(len(unique_descriptors(sources))==len(sources),'unique exact source bodies');c.descriptor(manifest['dependency_qualification'])
    c.exact(manifest['installed_versions'],('numpy','mne'));return sources

def run(selected,runtime,source,manifest,budget,output_root):
    from runtime import Runtime,admit_closure
    c.need(type(runtime)is Runtime,'actual source-owned runtime, no completed-output callback')
    c.exact(selected,('inventory','release_root','raw_files','key','protocol_source','annotation_authority','worker_io','protected_roots'))
    c.need(type(selected['worker_io'])is list and len(selected['worker_io'])==10,'ten separately selected complete IO envelopes')
    c.need(type(selected['raw_files'])is list and len(selected['raw_files'])==11,'all original ten FIF and README descriptors')
    for d in [selected['inventory'],selected['key'],selected['protocol_source'],selected['annotation_authority'],*selected['raw_files']]:c.descriptor(d)
    c.need(selected['key']['bytes']==32,'descriptor-only exact private key extent')
    sources=source_members(manifest);out=c.new_directory(output_root,budget)
    manifest_desc=c.publish_json(out/'SOURCE.json',manifest,budget)
    generation=c.pin(c.encoded({'schema':'neural081_generation_v1','raw_files':selected['raw_files'],'inventory':selected['inventory'],'key_descriptor':selected['key'],'protocol_source':selected['protocol_source'],'annotation_authority':selected['annotation_authority']}))['sha256']
    jobs=[];people=[];release=None;final=None
    for ordinal,person in enumerate(c.PEOPLE):
        started=budget.clock();deadline=min(budget.end,started+3600.)
        job='G0/'+person;work=runtime.allocate(job)
        io=selected['worker_io'][ordinal];c.exact(io,('read_bytes','write_bytes'))
        for value in io.values():c.integer(value,1)
        # These are lower bounds, not a claim that native/package IO fits them.
        minimum_read=sum(d['bytes']+1 for d in(selected['raw_files']if ordinal==0 else[selected['raw_files'][ordinal]]))
        minimum_read+=sum(d['protected']['bytes']+1 for d in people)if ordinal==9 else 0
        minimum_read+=3*sum(d['bytes']+1 for d in sources)+selected['inventory']['bytes']+selected['key']['bytes']+1
        c.need(io['read_bytes']>=minimum_read and io['write_bytes']>=65536,'complete source/release/prior metadata floor before operation')
        payload={'schema':'neural081_G0_request_v1','task_id':c.TASK,'ordinal':ordinal,'person':person,'source':source,'generation':generation,'inventory':selected['inventory'],'release_root':selected['release_root'],'raw_files':selected['raw_files'],'key':selected['key'],'protocol_source':selected['protocol_source'],'annotation_authority':selected['annotation_authority'],'environment':{**manifest['installed_versions'],'source_qualified':True,'annotation_qualified':True},'release_receipt':release,'earlier_people':people if ordinal==9 else[],'output_root':str(work)}
        allowed=[selected['inventory'],selected['key'],selected['protocol_source'],selected['annotation_authority'],*(selected['raw_files']if ordinal==0 else[selected['raw_files'][ordinal]])]
        if release is not None:allowed.append(release)
        if ordinal==9:allowed.extend(row['protected']for row in people)
        allowed=unique_descriptors(allowed)
        request={'schema':'neural081_preparation_worker_request_v1','job':job,'source':source,'payload':payload,'output_root':str(work),'allowed':allowed,'protected':[],'source_manifest':manifest_desc,'clock':{'origin':budget.origin,'deadline':deadline},'worker_io':io}
        request_desc=c.publish_json(out/(person+'-REQUEST.json'),request,budget)
        all_mounts=unique_descriptors([*allowed,*sources,manifest_desc,manifest['dependency_qualification'],request_desc])
        opaque={d['path']for d in selected['raw_files']}|{selected['key']['path']}|{r['protected']['path']for r in people}
        mounts=[{'source':d,'target':d['path'],'opaque_host':d['path']in opaque}for d in all_mounts]
        entry=manifest['entry'];bootstrap=manifest['bootstrap']
        argv=['--request',request_desc['path'],'--request-bytes',str(request_desc['bytes']),'--request-sha256',request_desc['sha256'],'--bootstrap',bootstrap['path'],'--bootstrap-bytes',str(bootstrap['bytes']),'--bootstrap-sha256',bootstrap['sha256'],'--read-cap',str(io['read_bytes']),'--write-cap',str(io['write_bytes']),'--origin',str(budget.origin),'--deadline',str(deadline),'--entry-bytes',str(entry['bytes'])]
        closed=runtime.run(job,entry['path'],mounts,argv,seconds=3600,memory_bytes=16*2**30,kind='preparation',worker_io=io,workspace=work,original_deadline=deadline)
        admit_closure(closed)
        result_desc=artifact(closed,'RESULT.json');body=c.capture_json(result_desc,budget,[Path(result_desc['path']).parent])
        c.exact(body,('schema','ordinal','person','source','generation','release_receipt','person_protected','complete_preparation'))
        c.need(body['schema']=='neural081_G0_result_v1'and type(body['ordinal'])is int and body['ordinal']==ordinal and body['person']==person and body['generation']==generation and c.typed_equal(body['source'],source),'actual exact G0 worker identity')
        supplied={d['path']:d for d in closed['artifacts']}
        d=body['person_protected'];c.need(c.typed_equal(supplied.get(d['path']),d),'closed trusted person body descriptor, never opened by controller')
        people.append({'person':person,'protected':d})
        if ordinal==0:
            release=body['release_receipt'];c.need(c.typed_equal(supplied.get(release['path']),release),'first trusted release artifact')
        else:c.need(c.typed_equal(body['release_receipt'],release),'unchanged first verification lineage')
        if ordinal==9:
            final=body['complete_preparation'];c.exact(final,('index','closure','protected_support','protected_assessment'))
            for d in final.values():c.need(c.typed_equal(supplied.get(d['path']),d),'all protected/public final outputs produced by actual tenth worker')
        else:c.need(body['complete_preparation']is None,'no hidden earlier complete preparer')
        jobs.append({'person':person,'ordinal':ordinal,'request':request_desc,'result':result_desc,'closure':closed['receipt'],'worker_io':io,'original_deadline':deadline})
    index=p.validate_index(c.capture_json(final['index'],budget,[Path(final['index']['path']).parent]))
    c.need(index['preparation_generation']==generation and c.typed_equal(index['protected_support_descriptor'],final['protected_support'])and c.typed_equal(index['protected_assessment_descriptor'],final['protected_assessment']),'last-worker label-free/protected descriptor joins')
    closure=c.capture_json(final['closure'],budget,[Path(final['closure']['path']).parent])
    c.need(closure['generation']==generation and c.typed_equal(closure['person_results'],[r['protected']for r in people]),'all ten original closed person operands assembled')
    report={'schema':'neural081_complete_G0_driver_v1','source':source,'generation':generation,'jobs':jobs,'outputs':final,'ten_trusted_workers':True,'ordinary_controller_numeric_or_label_body_reads':0}
    descriptor=c.publish_json(out/'RESULT.json',report,budget);budget.check_clock()
    return {'descriptor':descriptor,'index':index,'index_descriptor':final['index'],'preparation':closure,'protected':[final['protected_support'],final['protected_assessment']],'jobs':jobs}
