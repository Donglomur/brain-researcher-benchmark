"""Concrete five-phase scientific composition under separately issued gates."""
from pathlib import Path
import common as c
import authority,analysts,reference_study,native,legacy,grading,release,admission
from observation import observer

def object_body(descriptor,budget):return c.capture_json(descriptor,budget,[Path(descriptor['path']).parent])

def closure(bundle,phase,source,budget,protected_root):
    """Actual source-owned child+observer admission, not a completed flag."""
    c.exact(bundle,('spec','receipt','external','external_authority'))
    spec=object_body(bundle['spec'],budget);receipt=object_body(bundle['receipt'],budget);external=object_body(bundle['external'],budget)
    issuer=c.capture_json(bundle['external_authority'],budget,[c.absolute(protected_root)])
    c.need(spec['phase']==phase and c.typed_equal(spec['source'],source),'expected complete predecessor phase/source')
    proof=observer.admit_external_closure(receipt,external,expected_spec=spec,receipt_descriptor=bundle['receipt'],budget=budget,external_authority=issuer)
    return {'proof':proof,'spec':spec,'receipt':receipt,'external':external,'issuer':issuer,'artifacts':{r['kind']:{k:r[k]for k in('path','bytes','sha256')}for r in receipt['artifacts']}}

def public_sources(source_files):
    wanted=('public/event_protocol.py','public/io_contract.py')
    result=[d for name in wanted for d in source_files if d['path'].endswith('/'+name)]
    c.need(len(result)==2,'exact two public analyst method/schema files');return result

def reference_sources(source_files):
    rows=[d for d in source_files if '/references/'in d['path']]
    c.need(len(rows)==9 and {Path(d['path']).name for d in rows}=={'SOURCE_MANIFEST.json','reference_cli.py','common.py','contracts.py','features.py','learners.py','math_core.py','selection.py','event_protocol.py'},'complete exclusive reference source mounts')
    return rows

def analyst_config(value,selected,budget,source_files):
    c.need(type(value)is dict,'actual analyst configuration');config=dict(value);d=value['provider']
    c.need(c.typed_equal(d,selected['provider_config']),'actual provider descriptor bound to protected credential authority')
    provider=object_body(d,budget);c.need(selected['credential_names']==[provider['api_key_env']],'only selected credential name')
    protocol=[d for d in source_files if d['path'].endswith('/public/ANALYST_PROTOCOL.md')]
    documents=[d for d in source_files if '/public/protocol/'in d['path']]
    c.need(len(protocol)==1 and c.typed_equal(value['protocol'],protocol[0])and c.typed_equal(value['protocol_sources'],documents),'data-free prompts use only exact source-owned public protocol documents')
    config['provider']=provider;return config

def observation_authority(selected,spec):
    # The adapter's compact guard is derived only after authority.admit has
    # captured all exact independent protected issuer receipts. It is not a
    # replacement for those upstream concrete joins or a newly issued approval.
    return {'schema':'neural010-source-execution-authority-v1','execution_selected':True,'source':selected['source'],'qualification':{role:{'status':'qualified','source':selected['source'],'independent_issuer_selected':True,'original_receipt':selected['qualification_receipts'][role]}for role in authority.ROLES},'observation_spec':c.pin(c.encoded(spec))}

def observe(selected,source,source_files,requestpin,phase,budget,bodies):
    run=authority.admit(selected,source,phase,budget,source_files,observer=True)
    c.need(c.typed_equal(selected['request'],requestpin)and requestpin['bytes']<=run['request_caps'][phase],'exact independently selected bounded observer request')
    request=object_body(requestpin,budget);c.exact(request,('schema','phase','source','spec','output_root'))
    c.need(request['schema']=='neural010-observer-request-v1'and request['phase']==phase and c.typed_equal(request['source'],source),'source-owned observer request')
    spec=request['spec'];c.need(c.typed_equal(spec['source_files'],source_files)and c.typed_equal(spec['source'],source)and spec['phase']==phase,'actual complete worker source closure')
    c.need(spec['public_inputs']==[],'observer never recursively opens task data; phase-owned source admission controls those operands')
    c.need(c.typed_equal(spec['provider_config'],selected['provider_config'])and c.typed_equal(spec['credential_names'],selected['credential_names']),'same separately selected provider name/configuration')
    roots=sorted({str(Path(d['path']).parent)for d in observer.spec_document(spec,budget).values()})
    return observer.observe_phase(spec,budget=budget,authority=observation_authority(selected,spec),capture_roots=roots,output_root=request['output_root'])

def execute(request,requestpin,selected,run,budget,bodies,source_files):
    phase=request['phase'];payload=request['payload'];root=c.new_directory(request['output_root'],budget);old=legacy.load(bodies)
    result=None;artifacts=[]
    if phase=='fixed-authors':
        c.exact(payload,('analyst_config',));config=analyst_config(payload['analyst_config'],selected,budget,source_files)
        result=analysts.AnalystStudy(config,budget,root,public_sources(source_files)).fixed_authors()
        for replication,a in enumerate(result['authors']):
            artifacts.extend([('fixed_source_'+str(replication),a['source']),('fixed_author_'+str(replication),a['receipt'])])
    elif phase=='references':
        c.exact(payload,('reference_seal_settings','fixed_authors_closure','capture_roots'))
        settings=payload['reference_seal_settings'];c.exact(settings,('preparation','reference_source','reference_limits','native_config','native_phase_limits','native_source_files'))
        # Author source is closed before any authentic phase-one body is read.
        closed=closure(payload['fixed_authors_closure'],'fixed-authors',request['source'],budget,selected['root'])
        c.need('phase_result'in closed['artifacts'],'complete fixed-author predecessor result')
        authors=object_body(closed['artifacts']['phase_result'],budget);c.need(authors['schema']=='neural010-data-free-authors-v1'and len(authors['authors'])==3,'three previously closed data-free programs')
        prepared=reference_study.preparation(settings['preparation'],budget,old);refs=reference_sources(source_files);manifest=next(d for d in refs if d['path'].endswith('/SOURCE_MANIFEST.json'))
        c.need(c.typed_equal(manifest,settings['reference_source'])and c.typed_equal(refs,settings['native_source_files']),'reference source selected in exact original request')
        native_root=c.new_directory(root/'native',budget);request_root=c.new_directory(root/'study',budget)
        transport=native.Native(settings['native_config'],settings['native_phase_limits'],budget,native_root,refs)
        provisional=reference_study.ReferenceStudy(prepared,transport,manifest,settings['reference_limits'],request_root,budget,old).run()
        provisional_pin=c.publish_json(root/'REFERENCE_STUDY.json',provisional,budget)
        seal_request={'schema':'neural010-four-stream-seal-request-v1','source':request['source'],'reference_study':provisional_pin,'preparation':settings['preparation'],'reference_source':manifest,'reference_limits':settings['reference_limits'],'native_config':settings['native_config'],'native_phase_limits':settings['native_phase_limits'],'native_source_files':refs,'reference_phase_request':requestpin}
        seal_root=c.new_directory(root/'seal',budget)
        roots=[c.absolute(p)for p in payload['capture_roots']]
        result=release.seal_reference_study(seal_request,budget=budget,capture_roots=roots,output_root=seal_root,legacy=old)
        artifacts.append(('reference_study',provisional_pin))
        artifacts.extend([('master',result['master']),('admission',result['admission'])])
        artifacts.extend(('merged_'+arm,result['predictions'][arm])for arm in c.ARMS)
    elif phase=='release':
        c.exact(payload,('release_request','release_authority','capture_roots'))
        release_authority=c.capture_json(payload['release_authority'],budget,[c.absolute(selected['root'])])
        release_authority['execution_authority']=observation_authority(selected,{'release_request':payload['release_request']})
        # The release implementation deliberately does not touch its assessment
        # descriptor before the complete independent reference closure barrier.
        result=release.release_assessment(payload['release_request'],protected_authority=release_authority,budget=budget,capture_roots=[c.absolute(p)for p in payload['capture_roots']],output_root=root,legacy=old)
        artifacts.extend((kind,result[key])for kind,key in(('historical','historical'),('matched','matched'),('envelope','envelope'),('release_receipt','receipt')))
    elif phase=='analysts':
        c.exact(payload,('analyst_config','fixed_authors_closure','release_closure'))
        fixed=closure(payload['fixed_authors_closure'],'fixed-authors',request['source'],budget,selected['root']);released=closure(payload['release_closure'],'release',request['source'],budget,selected['root'])
        authors=object_body(fixed['artifacts']['phase_result'],budget);released_body=object_body(released['artifacts']['phase_result'],budget)
        original_author_request=object_body(fixed['spec']['request'],budget)
        c.need(c.typed_equal(original_author_request['payload']['analyst_config'],payload['analyst_config']),'same model/tool/method/author/execution ceilings in fixed and adaptive modes')
        config=analyst_config(payload['analyst_config'],selected,budget,source_files)
        result=analysts.AnalystStudy(config,budget,root,public_sources(source_files)).execute(authors,released_body)
        for index,ctx in enumerate(result['contexts']):
            artifacts.extend([('submission_'+str(index),ctx['output']),('context_'+str(index),ctx['receipt']),('view_'+str(index),ctx['view']),('request_'+str(index),ctx['request']),('native_'+str(index),ctx['native'])])
    else:
        c.exact(payload,('analysts_closure','release_closure'))
        analytical=closure(payload['analysts_closure'],'analysts',request['source'],budget,selected['root']);released=closure(payload['release_closure'],'release',request['source'],budget,selected['root'])
        analysis=object_body(analytical['artifacts']['phase_result'],budget);r=object_body(released['artifacts']['phase_result'],budget)
        c.need(analysis['schema']=='neural010-complete-analysts-v1'and type(analysis['count'])is int and analysis['count']==12,'complete12 outputs before protected computation')
        actual_request=object_body(analytical['spec']['request'],budget);cfg=dict(actual_request['payload']['analyst_config']);cfg['provider']=object_body(cfg['provider'],budget);sources=public_sources(source_files)
        fixed=closure(actual_request['payload']['fixed_authors_closure'],'fixed-authors',request['source'],budget,selected['root']);fixed_request=object_body(fixed['spec']['request'],budget)
        c.need(c.typed_equal(fixed_request['payload']['analyst_config'],actual_request['payload']['analyst_config']),'same full preselected analytical budget/configuration across modes')
        fixed_body=object_body(fixed['artifacts']['phase_result'],budget);fixed_inputs=[cfg['protocol'],*cfg['protocol_sources'],*sources]
        for replication,a in enumerate(fixed_body['authors']):
            admitted=admission.author_episode(a['receipt'],identity='fixed-author/'+str(replication),replication=replication,inputs=fixed_inputs,config=cfg,sources=sources,budget=budget)
            c.need(c.typed_equal(admitted['sealed_source'],a['source']),'exact fixed author response/source')
        h=object_body(r['historical'],budget);m=object_body(r['matched'],budget)
        submissions=[object_body(d,budget)for d in analysis['outputs']]
        # Final source/runtime observation joins are repeated below before any
        # expected reconstruction function can be called.
        for context,descriptor in zip(analysis['contexts'],analysis['outputs']):
            c.need(c.typed_equal(context['output'],descriptor),'exact closed context report')
            current=context['context'];view=object_body(context['view'],budget);candidate_request=object_body(context['request'],budget)
            admission.local_cost(context['budget'],cfg['execution_limits'],budget)
            c.need(c.typed_equal(context['permitted_author_limits'],cfg['author_limits'])and c.typed_equal(context['permitted_execution_limits'],cfg['execution_limits']),'equal preselected author/execution ceilings for every condition')
            c.need(c.typed_equal(view['context'],current)and c.typed_equal(view['historical'],r['historical'])and c.typed_equal(view['matched'],r['matched'])and c.typed_equal(view['envelope'],r['envelope']),'same released corpus in the exact current view')
            expected_waveforms=r['waveforms']if current['view']=='full_waveform'else[]
            c.need(c.typed_equal(view['waveforms'],expected_waveforms)and c.typed_equal(view['source'],sources),'complete actual full/withheld waveform access')
            c.need(c.typed_equal(candidate_request['context'],current)and c.typed_equal(candidate_request['source'],context['sealed_source'])and c.typed_equal(candidate_request['view_manifest'],context['view']),'same sealed actual candidate request')
            inputs=[r['historical'],r['matched'],r['envelope'],context['view'],*expected_waveforms,*sources]
            if current['mode']=='frozen_program':
                a=fixed_body['authors'][current['replication']];c.need(c.typed_equal(context['author'],a['receipt'])and c.typed_equal(context['sealed_source'],a['source']),'shared immutable source, fresh fixed worker')
            else:
                a=admission.author_episode(context['author'],identity=current['id'],replication=current['replication'],inputs=inputs,config=cfg,sources=sources,budget=budget)
                c.need(c.typed_equal(a['sealed_source'],context['sealed_source']),'adaptive final source exactly returned by its own author')
            admission.native_job(context['native'],job_id=current['id']+'/final',kind='fixed',script=context['sealed_source']['path'],args=['--request',context['request']['path'],'--output','{WORK}/SUBMISSION.json'],inputs=[context['sealed_source'],context['request'],*inputs],sources=sources,workspace=[],config=cfg['native'],phase_limits=cfg['native_phase_limits'],context_deadline=context['budget']['original_deadline'],budget=budget)
        result=grading.grade_all(h,m,r['historical'],r['matched'],r['master'],submissions,analysis['contexts'],r['envelope'],analysis['views'],old['analysis_core'],budget)
    budget.check_clock();resultpin=c.publish_json(root/'RESULT.json',result,budget);artifacts.append(('phase_result',resultpin))
    # The output roster is source-owned and emitted once. An independent parent
    # observes this process's subsequent natural exit before admitting it.
    output={'schema':'neural010-observed-phase-output-v1','phase':phase,'source':request['source'],'request':requestpin,'original_origin':float(budget.origin),'original_deadline':float(budget.end),'artifacts':[{'kind':kind,**descriptor}for kind,descriptor in artifacts]}
    manifest=c.publish_json(root/'OUTPUT_MANIFEST.json',output,budget);budget.check_clock()
    return {'schema':'neural010-provisional-phase-result-v1','phase':phase,'output_manifest':manifest,'result':resultpin,'budget':budget.snapshot(),'own_future_exit_established':False,'qualification_created':False}
