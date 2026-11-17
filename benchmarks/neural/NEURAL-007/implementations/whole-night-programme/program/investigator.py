"""Concrete current-person investigator/frozen-policy state machine.

Every tool executes through Native, every adaptive response through Session.
Only operator-owned metadata builds the conversation. File-returned candidate
claims are not scientific admission, and no outer target is a tool argument.
"""
from pathlib import Path
import time
from .common import capture, decode, descriptor, encoded, need, pin, publish, MODES
from .transport import file_mount

ACTION_SCHEMA = {'type':'object','properties':{'action':{'enum':['python_probe','finalize']},
    'source':{'type':'string'},'observation_role':{'type':'string'},'fit_source':{'type':'string'},
    'inference_source':{'type':'string'},'recipe':{'type':'object'},'scientific_claim':{'type':'object'}},'required':['action']}


def action(value):
    need(type(value) is dict and value.get('action') in ('python_probe','finalize'), 'Declared investigation action')
    fields = {'action','source','observation_role'} if value['action']=='python_probe' else {'action','fit_source','inference_source','recipe','scientific_claim'}
    need(set(value)==fields, 'No arbitrary tool route/arguments')
    code = ['source'] if value['action']=='python_probe' else ['fit_source','inference_source']
    for k in code:
        need(type(value[k]) is str and 0<len(value[k].encode())<=1048576 and '\0' not in value[k], 'Bounded whole UTF8 Python source')
        compile(value[k], '<captured-'+k+'>', 'exec')
    need(len(encoded(value))<=1048576, 'Whole generated bundle budget')
    if value['action']=='finalize':
        need(type(value['recipe']) is dict and type(value['scientific_claim']) is dict, 'Exact structured recipe/claim')
        claim=value['scientific_claim']
        need(set(claim)=={'question','method','claims','uncertainty','alternatives','limitations'}, 'Scientific claim support fields')
        need(type(claim['claims']) is list, 'Typed claim list')
        for c in claim['claims']:
            need(c['support'] in ('training','validation','unlabeled_current_query'), 'No preseal outer performance claim')
            need(c['kind'] in ('validation_metric','signal_summary','methodological'), 'Typed numeric/non-numeric evidence')
            if c['kind']!='methodological':
                for k in ('source','model','inputs','artifact','estimator'):
                    need(k in c, 'Executable numeric evidence provenance')
    return value


def captured(result, name, meter, cap=1048576):
    receipt=result['receipt']; need(receipt['status']=='captured' and receipt['all_native_resources_closed'] is True
       and receipt['producer_closed_before_capture'] is True, 'Naturally closed tool before observation')
    members=receipt['output_inventory']['files']; need(name in members, 'Complete captured artifact')
    return capture(Path(receipt['quarantine_root'])/name,members[name],cap,meter)


def investigate(context, native, session, phase_policy, root, public_manifest, probe_mounts, trusted_mounts, clock, meter, frozen=None):
    """phase_policy is captured operator configuration, never executable callback.

    Frozen policy and all emitted code are recorded with the globally committed
    source. Replay determinism must be separately qualified; no fresh author may
    edit its emitted action. Adaptive state is only this context's transcript.
    """
    root=Path(root); need(root.is_absolute() and not root.exists(), 'Fresh investigation record'); root.mkdir(mode=0o700)
    mode=context['mode']; need(mode in MODES, 'Exact canonical mode')
    need((mode==MODES[1]) == (session is not None), 'Actual provider only for investigator')
    need((mode==MODES[0]) == (frozen is not None), 'Globally committed frozen policy only')
    transcript=[{'role':'system','content':phase_policy['system_prompt']},
                {'role':'user','content':{'task':'Predict every full-clock30s epoch in every current-person night. Five classes W,N1,N2,N3,R.',
                 'view':public_manifest,'tool':'python_probe','max_probes':6,'max_decisions':8,
                 'final_output':'training-only fit source, immutable-model inference source, recipe, executable supported claims'}}]
    probes=0; decisions=[]; finalized=None; probe_results={}
    try:
        if session is not None: session.start()
        for turn in range(1,9):
            need(clock['origin']<=time.monotonic()<clock['deadline'], 'Original context clock')
            prompt=encoded(transcript); need(len(prompt)<=8388608, 'Whole context transcript ceiling')
            publish(root/f'prompt-{turn}.json',prompt,meter)
            if session is not None:
                value, receipt=session.generate(prompt.decode(),ACTION_SCHEMA)
            else:
                history= root/f'prompt-{turn}.json'
                mounts={**probe_mounts,**trusted_mounts,'/history':file_mount(history,pin(prompt),'contract'),
                        '/candidate/main.py':file_mount(frozen['path'],frozen['source'],'program')}
                config=phase_policy['phases'][f'policy-{turn}']
                result=native.run(context['id']+f'-policy-{turn}','policy','A',{'history':True},mounts,clock,config['limits'],config.get('exposure'))
                value=decode(captured(result,'artifacts/ACTION.json',meter)); receipt={'native':result['receipt_pin'],'global_policy':frozen['source']}
            value=action(value); publish(root/f'action-{turn}.json',encoded(value),meter)
            decisions.append({'turn':turn,'action':pin(encoded(value)),'receipt':receipt})
            transcript.append({'role':'assistant','content':value})
            if value['action']=='finalize': finalized=value; break
            need(probes<6,'No seventh numerical probe'); probes+=1
            source=value['source'].encode(); code=root/f'probe-{probes}.py'; source_pin=publish(code,source,meter)
            mounts={**probe_mounts,**trusted_mounts,'/candidate/main.py':file_mount(code,source_pin,'program')}
            config=phase_policy['phases'][f'probe-{probes}']
            result=native.run(context['id']+f'-probe-{probes}','probe','B' if session else 'A',{},mounts,clock,config['limits'],config.get('exposure'))
            result['probe_source']=source_pin; probe_results[probes]=result
            observed=decode(captured(result,'artifacts/OBSERVATION.json',meter,65536))
            # stdout is retained evidence but not silently substituted for the
            # typed observation. No grader or reference output is mounted.
            transcript.append({'role':'tool','content':{'probe':probes,'observation':observed,'source':source_pin,'receipt':result['receipt_pin']}})
        need(finalized is not None,'Explicit finalization within eight decisions')
        closure=session.close() if session is not None else {'provider_used':False,'global_policy':frozen['source']}
        # No provider may survive into fit/inference. Semantic content admission
        # is separate and is required by the subsequent final-fit coordinator.
        from .claims import verify
        claim_verification=verify(finalized['scientific_claim']['claims'],public_manifest,probe_mounts,probe_results,meter)
        bundle={}
        for key,name in (('fit_source','fit.py'),('inference_source','infer.py')):
            body=finalized[key].encode();bundle[key]={'path':str(root/name),**publish(root/name,body,meter)}
        recipe=encoded(finalized['recipe']);bundle['recipe']={'path':str(root/'RECIPE.json'),**publish(root/'RECIPE.json',recipe,meter)}
        result={'schema':'neural007_investigation_seal_v1','context':context['id'],'programme_source':phase_policy['source'],'mode':mode,'decisions':decisions,
            'probes':probes,'bundle':bundle,'scientific_claim':finalized['scientific_claim'],'provider_closure':closure,
            'clock':clock,'sealed_at':time.monotonic(),'numeric_claim_verification':claim_verification,'scientific_content_admitted':False}
        seal=publish(root/'SEAL.json',encoded(result),meter)
        return result,seal
    except BaseException:
        if session is not None and not session.closed:
            try:session.abort()
            except BaseException as cleanup:
                publish(root/'CLEANUP_UNCERTAINTY.json',encoded({'type':type(cleanup).__name__}),meter)
        raise
