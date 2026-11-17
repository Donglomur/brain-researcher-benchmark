"""Concrete independent parent observation of each selected complete phase.

The five phase authorities are issued through the protected operator channel as
their exact predecessor artifacts become available. This source performs the
actual outer launch and closure; a JSON success flag is never a substitute.
Its own subsequent exit remains a separate final external publication gate.
"""
from pathlib import Path
import common as c
import authority
from native import Bridge
from transport.process import ProcessObserver
from observation import observer

def observe_selected(selected,source,source_files,requestpin,phase,budget):
    run=authority.admit(selected,source,phase,budget,source_files,root_observer=True)
    c.need(c.typed_equal(selected['request'],requestpin)and requestpin['bytes']<=run['request_caps'][phase],'independently selected complete root observer request')
    request=c.capture_json(requestpin,budget,[Path(requestpin['path']).parent]);c.exact(request,('schema','phase','source','observer_request','observer_authority','output_root','seconds','cleanup_seconds','stream_cap'))
    c.need(request['schema']=='neural010-root-observation-request-v1'and request['phase']==phase and c.typed_equal(request['source'],source),'exact root observer task/source')
    inner=c.capture_json(request['observer_request'],budget,[Path(request['observer_request']['path']).parent]);spec=inner['spec']
    c.need(inner['schema']=='neural010-observer-request-v1'and inner['phase']==phase and c.typed_equal(inner['source'],source)and spec['phase']==phase and c.typed_equal(spec['source'],source)and c.typed_equal(spec['source_files'],source_files)and spec['public_inputs']==[],'whole exact source-only observed phase')
    observer.spec_document(spec,budget)
    target=c.capture_json(request['observer_authority'],budget,[c.absolute(selected['root'])])
    c.need(target['execution_role']=='observer'and target['phase']==phase and c.typed_equal(target['request'],request['observer_request'])and c.typed_equal(target['source'],source),'actual protected observer authority')
    for k in('provider_config','credential_names'):c.need(c.typed_equal(spec[k],selected[k])and c.typed_equal(target[k],selected[k]),'same selected credential names/configuration across both observers')
    for d in [source,*source_files,spec['python'],request['observer_request'],request['observer_authority']]:c.authenticate_stream(d,budget,[Path(d['path']).parent])
    child_authority=c.capture(spec['child_authority'],budget,[c.absolute(selected['root'])]);child_request=c.capture(spec['request'],budget,[Path(spec['request']['path']).parent])
    provider=None if spec['provider_config']is None else c.capture(spec['provider_config'],budget,[Path(spec['provider_config']['path']).parent])
    observer.environment_binding(spec,child_request,child_authority,provider)
    argv=[spec['python']['path'],'-I','-B',spec['entry']['path'],'--observe','--phase',phase,'--source-bytes',str(source['bytes']),'--source-sha256',source['sha256'],'--request',request['observer_request']['path'],'--request-bytes',str(request['observer_request']['bytes']),'--request-sha256',request['observer_request']['sha256'],'--authority',request['observer_authority']['path'],'--authority-bytes',str(request['observer_authority']['bytes']),'--authority-sha256',request['observer_authority']['sha256'],'--origin',repr(float(budget.origin))]
    c.need(c.absolute(request['output_root']).is_relative_to(c.absolute(selected['root'])),'externally trusted observation bindings remain inside protected operator custody')
    directory=c.new_directory(request['output_root'],budget);intent=c.publish_json(directory/'ROOT_INTENT.json',{'schema':'neural010-original-root-phase-intent-v1','phase':phase,'source':source,'request':requestpin,'argv':argv,'original_origin':float(budget.origin),'original_deadline':float(budget.end),'credential_names':spec['credential_names'],'provider_config':spec['provider_config']},budget)
    result=None
    try:
        env=observer.child_environment(spec);budget.charge('host_processes',1)
        result=ProcessObserver().run(argv,cwd=spec['cwd'],env=env,budget=Bridge(budget),seconds=request['seconds'],cleanup_seconds=request['cleanup_seconds'],stream_cap=request['stream_cap'])
        stdout=c.publish(directory/'stdout.bin',result['stdout'],budget);stderr=c.publish(directory/'stderr.bin',result['stderr'],budget)
        observer.natural(result['observation'],argv,budget)
        for d in [source,*source_files,spec['python'],request['observer_request'],request['observer_authority']]:c.authenticate_stream(d,budget,[Path(d['path']).parent])
        returned=c.parse(result['stdout']);c.need(returned['complete_release_or_grade_authorized']is False,'inner observer remains provisional before original outer exit')
        receipt=returned['receipt'];c.need(receipt['path']==str(Path(inner['output_root'])/'OBSERVATION.json'),'literal closed observer receipt')
        observed_body=c.capture_json(receipt,budget,[Path(receipt['path']).parent]);c.need(c.typed_equal(observed_body,returned['body']),'original observer return and captured artifact agree')
        external={'schema':'neural010-root-observer-exit-v1','observer_source':source,'observer_request':request['observer_request'],'receipt':receipt,'stdout':stdout,'stderr':stderr,'observation':result['observation']}
        external_pin=c.publish_json(directory/'EXTERNAL_OBSERVATION.json',external,budget)
        derived={'schema':'neural010-root-external-observer-authority-v1','external_body':{k:external_pin[k]for k in('bytes','sha256')},'observer_argv':argv,'observer_source':source,'observer_request':request['observer_request'],'receipt':receipt,'original_origin':float(budget.origin),'original_deadline':float(budget.end),'phase':phase}
        # The current root source is separately selected through original issuer
        # receipts above. This binding describes the actual observed child; it
        # cannot self-authorize a different source, request or future root exit.
        proof=observer.admit_external_closure(observed_body,external,expected_spec=spec,receipt_descriptor=receipt,budget=budget,external_authority=derived)
        authority_pin=c.publish_json(directory/'EXTERNAL_AUTHORITY.json',derived,budget)
        result_body={'schema':'neural010-root-observed-phase-v1','phase':phase,'intent':intent,'source':source,'request':requestpin,'observer_receipt':receipt,'external':external_pin,'external_authority':authority_pin,'admission':proof,'original_origin':float(budget.origin),'original_deadline':float(budget.end),'root_caller_own_future_exit_established':False,'budget':budget.snapshot()}
        pin=c.publish_json(directory/'ROOT_RESULT.json',result_body,budget);budget.check_clock();return {'result':pin,'body':result_body}
    except BaseException as error:
        # No retry or cleanup-to-success. Original in-memory returned streams
        # remain available to the outer operator even if publication fails.
        evidence={'intent':intent,'failure_type':type(error).__name__,'original_failure':getattr(error,'evidence',None),'returned_stdout_hex':None if result is None else result['stdout'].hex(),'returned_stderr_hex':None if result is None else result['stderr'].hex(),'publication_or_survivor_state':'unknown; inspect before any retry','budget':budget.snapshot()}
        try:c.publish_json(directory/'ROOT_FAILURE.json',evidence,budget)
        except BaseException:pass
        try:error.evidence=evidence
        except BaseException:pass
        raise
