"""One-process generated construction controls; never provider or original-data qualification."""
from __future__ import annotations
import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import traceback

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import raw_contract as C
import raw_programme as P
import raw_admission as A
import raw_compare as R


def expect(message,call):
    try: call()
    except (ValueError,KeyError) as exc:
        C.need(message in str(exc), 'Unexpected refusal: '+str(exc));return str(exc)
    raise AssertionError('Expected refusal: '+message)


class GeneratedPerson:
    case='development-001'
    epochs=2780
    clock=((0.0,0.0,1.0),)
    def samples(self,start,stop,channels):
        C.need(start==0 and stop==3000,'Generated first-epoch fixture only')
        return [[float((i%100)-50)*(index+1)*1e-6 for i in range(3000)] for index,name in enumerate(channels)]


def run(root,source,dependency_root):
    import numpy as np
    root=C.ordinary_path(root);root.mkdir(mode=0o700)
    results=[]; observations={'target_canary_open_events':0,'process_events':0,'network_events':0}
    canary=root/'PRIVATE_TARGET_CANARY';C.write_new(canary,b'generated private canary\n')
    def guard(event,args):
        if event=='open' and args and isinstance(args[0],(str,bytes,os.PathLike)):
            candidate=os.path.abspath(os.fsdecode(args[0]))
            if candidate==str(canary) or candidate.startswith(str(canary)+os.sep):
                observations['target_canary_open_events']+=1;raise AssertionError('Private target touched')
        if event in ('subprocess.Popen','os.system','os.posix_spawn','os.fork','pty.spawn'):
            observations['process_events']+=1;raise AssertionError('No child/native workload selected')
        if event in ('socket.connect','socket.bind','socket.getaddrinfo'):
            observations['network_events']+=1;raise AssertionError('No network selected')
    sys.addaudithook(guard)
    try:
        knowledge=C.write_new(root/'knowledge.json',C.encode({'schema':'sleep007_epoch_shared_knowledge_v1',
            'provider':'GENERATED_CONTROL','model':'generated','revision':'fixture-v1',
            'policy':C.KNOWLEDGE_POLICY,'external_assets':[]}))
        candidate=C.write_new(root/'candidate.py',b'# Generated fixed candidate source; never executed in these controls.\n')
        prepared=P.prepare(candidate['path'],knowledge,source,root/'prepared',image='sha256:'+'1'*64,dependency_root=dependency_root)
        rt=P.load_runtime(source,dependency_root); value,definition,prior=P.checked_prepared(prepared,rt)
        packets={m:C.project_epoch(GeneratedPerson(),0,m) for m in C.MODALITIES}
        shared=C.check_shared_epoch(packets[C.EEG],packets[C.EEG_EOG])
        projections={m:C.write_projection(packets[m],root/m) for m in C.MODALITIES}
        mounts={m:P.make_mounts(value,rt,projections[m])[0] for m in C.MODALITIES}
        C.need(mounts[C.EEG]['/program/program.py']==mounts[C.EEG_EOG]['/program/program.py']
               and mounts[C.EEG]['/trusted/PROGRAMME.json']==mounts[C.EEG_EOG]['/trusted/PROGRAMME.json'],
               'Same actual frozen programme and definition across modalities')
        C.need(projections[C.EEG]['signals']['bytes']==48128 and projections[C.EEG_EOG]['signals']['bytes']==72128,
               'Physical complete two versus three channels')
        resources={'setup_seconds':30,'producer_seconds':20,'capture_seconds':30,'cleanup_seconds':20,
            'memory_bytes':3*2**30,'cpu_nanos':1750000000,'pids':64,'scratch_bytes':64*2**20,
            'max_files':3,'max_directories':1,'max_file_bytes':400000,'max_output_bytes':8*2**20,
            'manifest_bytes':4096,'max_cli_calls':100,'max_cli_bytes':2*2**20,'inventory_bytes':32768,
            'source_read_bytes':32*2**20,'host_write_bytes':8*2**20}
        module=P.provider_module(rt); contract=sys.modules[module.__package__+'.contract']
        requests={m:P.phase_request(packets[m],definition,value['definition'],C.pin(b'UNADMITTED_EXPOSURE'),resources,0.0,1000.0)
                  for m in C.MODALITIES}
        for m in C.MODALITIES: contract.validate_request(requests[m],mounts[m],2000.0)
        C.need(requests[C.EEG]['phase_id']!=requests[C.EEG_EOG]['phase_id'],'Distinct fresh modality phases')
        extra=dict(mounts[C.EEG]);extra['/input/labels.json']=dict(next(iter(extra.values())))
        expect('Exactly six',lambda:P.checked_mounts(extra))
        wrong={k:dict(v) for k,v in mounts[C.EEG].items()};wrong['/input/signals.npy']['kind']='directory'
        expect('No directory',lambda:P.checked_mounts(wrong))
        expect('Exact modality-specific',lambda:P.checked_prediction({'condition':C.PROGRAMME_CONDITIONS[C.EEG_EOG],
            'epoch_id':packets[C.EEG].epoch_id,'probabilities':[.2]*5},packets[C.EEG]))
        changed=C.decode(C.encode(value));changed['definition']={**changed['definition'],'sha256':'0'*64}
        altered=C.write_new(root/'altered-prepared.json',C.encode(changed))
        expect('Retained bytes changed',lambda:P.checked_prepared(altered,rt))
        results.append({'name':'real_preparation_two_physical_modalities_six_mounts_canonical_request',
                        'status':'passed','shared':shared,'definition':P.plain(value['definition']),
                        'provider_execute_calls':0,'qualification':False})

        answers=C.FirstAnswers();evidence=C.pin(b'GENERATED_FIRST_FINAL')
        for epoch_id in C.required_targets(): answers.accept(epoch_id,[.2]*5,evidence)
        C.need(len(answers.complete())==5450,'Complete first-final denominator')
        expect('irreversible',lambda:answers.accept(C.required_targets()[0],[1.,0.,0.,0.,0.],evidence))
        incomplete=C.FirstAnswers();incomplete.accept(C.required_targets()[0],[.2]*5,evidence)
        expect('All5450',incomplete.complete)
        rows=answers.complete();rows[1]['epoch_id']=rows[0]['epoch_id']
        expect('ordered complete roster',lambda:C.checked_complete_rows(rows))
        results.append({'name':'full_5450_first_final_and_duplicate_partial_rejection','status':'passed','people':2})

        panels={}
        for ordinal,key in enumerate(A.PANELS):
            rows=[{'epoch_id':epoch_id,'probabilities':[float(k==(index+ordinal)%5) for k in range(5)]}
                  for index,epoch_id in enumerate(C.required_targets())]
            panels[A.CONDITIONS[key]]=C.write_new(root/('panel-'+str(ordinal)+'.npz'),C.submission_bytes(rows))
        scoring=R.scorer(source,dependency_root);calls=[]
        targets={case:{'epoch_id':scoring.adapter.expected_ids(scoring.adapter.Case(case,count)),
                       'stage':np.arange(count,dtype=np.int64)%5,'score_mask':np.ones(count,dtype=bool)} for case,count in C.CASES}
        def loader(): calls.append('generated_targets');return targets
        arithmetic=R._arithmetic_after_public(scoring,panels,loader)
        C.need(calls==['generated_targets'] and arithmetic['actual_target_loader_calls']==1
               and arithmetic['core_target_callback_calls']==2 and arithmetic['arithmetic_only_no_access_admission'] is True,
               'One generated target load reused by unchanged paired arithmetic')
        for arm in A.ARMS:
            perf=arithmetic['within_arm_eog_contrasts'][arm]
            C.need(perf['n_development_people']==2 and perf['class_order']==list(C.CLASSES)
                   and all(r['full_epochs']==dict(C.CASES)[r['person_id']] for r in perf['absolute_performance']['EEG_clock']['per_person']),
                   'Original full two-person scoring denominator')
        viewer_scores=arithmetic['within_arm_eog_contrasts']['viewer']
        programme_scores=arithmetic['within_arm_eog_contrasts']['programme']
        C.need(viewer_scores['absolute_performance']['EEG_clock']['person_mean_macro_f1']==1.0
               and viewer_scores['absolute_performance']['EEG_EOG_clock']['person_mean_macro_f1']==0.0
               and viewer_scores['paired_contrast']['person_mean_macro_f1_delta']==-1.0
               and programme_scores['paired_contrast']['person_mean_macro_f1_delta']==0.0
               and arithmetic['programme_minus_viewer'][C.EEG]['person_mean_macro_f1_delta']==-1.0
               and arithmetic['programme_minus_viewer'][C.EEG_EOG]['person_mean_macro_f1_delta']==0.0,
               'Known generated four-panel mapping and signed contrasts')
        missing=dict(panels);missing.pop(next(iter(missing)))
        expect('Four complete',lambda:R._arithmetic_after_public(scoring,missing,loader))
        altered=dict(panels);first=next(iter(altered));altered[first]={**altered[first],'sha256':'0'*64}
        expect('digest differs',lambda:R._arithmetic_after_public(scoring,altered,loader))
        C.need(len(calls)==1,'Malformed four-panel inputs rejected before target callback')
        C.write_new(root/'ARITHMETIC_CONTROL.json',C.encode(arithmetic))
        results.append({'name':'four_full_numeric_panels_unchanged_arithmetic_one_generated_target_load','status':'passed',
                        'panels':{k:P.plain(v) for k,v in panels.items()},'qualification':False})

        public={'source':source,'dependency_root':str(dependency_root),'original_inputs':{case:str(root/('NO_ORIGINAL_'+case)) for case,_ in C.CASES},
                'knowledge':knowledge,'collections':{}}
        coordinate={'public':public,'target_root':str(canary),'output_root':str(root/'NOT_CREATED')}
        worker={'schema':'neural008_raw_worker_request_v1','public':public,
                'public_freeze':{'path':str(root/'NO_FREEZE'),'bytes':1,'sha256':'0'*64},
                'target_root':str(canary),'output_path':str(root/'NO_GRADE.json')}
        actual=[]
        for operation,config in (('coordinate',coordinate),('worker',worker)):
            operand=C.write_new(root/(operation+'-missing.json'),C.encode(config))
            argv=['--operation',operation,'--config',operand['path'],'--bytes',str(operand['bytes']),'--sha256',operand['sha256']]
            with contextlib.redirect_stdout(io.StringIO()):
                refusal=expect('All four complete',lambda:R.main(argv))
            actual.append({'operation':operation,'refusal':refusal})
        # Finished probability arrays cannot masquerade as custody collections in either real entry.
        public_finished={**public,'collections':panels}
        for operation,config in (('coordinate',{**coordinate,'public':public_finished}),('worker',{**worker,'public':public_finished})):
            operand=C.write_new(root/(operation+'-finished-arrays.json'),C.encode(config))
            argv=['--operation',operation,'--config',operand['path'],'--bytes',str(operand['bytes']),'--sha256',operand['sha256']]
            try:
                with contextlib.redirect_stdout(io.StringIO()):R.main(argv)
            except (ValueError,UnicodeDecodeError) as exc:
                actual.append({'operation':operation,'finished_arrays_refused':type(exc).__name__,'message':str(exc)[:256]})
            else:raise AssertionError('Finished arrays passed access custody')
        C.need(not (root/'NO_GRADE.json').exists() and not (root/'NOT_CREATED').exists(),'No target or grade on invalid public input')
        results.append({'name':'actual_coordinator_and_worker_cli_gates_before_targets','status':'passed','entries':actual,
                        'separate_process_or_os_isolation_tested':False})
        C.need(not any(observations.values()),'No canary/native/network event')
        status='passed'
    except BaseException as exc:
        status='failed';results.append({'failure':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc(limit=12)})
    files=[]
    for path in sorted(root.rglob('*')):
        if path.is_file():
            if path==canary:raw=b'generated private canary\n'
            else:raw=path.read_bytes()
            files.append({'path':str(path.relative_to(root)),**C.pin(raw)})
    report={'schema':'neural008_raw_pair_generated_controls_v1','status':status,'tests':results,'observations':observations,
            'generated_files':files,'retained_before_result_bytes':sum(x['bytes'] for x in files),
            'original_material_reads':0,'provider_calls':0,'participant_execution':False,
            'provider_qualification':False,'scientific_qualification':False,'scope':'generated one-process source/contract/arithmetic controls'}
    result=C.write_new(root/'PAIR_RESULT.json',C.encode(report));print(json.dumps({'status':status,'result':result},sort_keys=True))
    if status!='passed':raise SystemExit(1)
    return report


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True);parser.add_argument('--bindings',required=True)
    parser.add_argument('--bytes',type=int,required=True);parser.add_argument('--sha256',required=True);parser.add_argument('--dependency-root',required=True)
    a=parser.parse_args(argv)
    source={'path':a.bindings,'bytes':a.bytes,'sha256':a.sha256}
    root=C.ordinary_path(a.root);root.mkdir(mode=0o700)
    report={'schema':'neural008_raw_companion_generated_campaign_v1','status':'failed',
            'processes':1,'original_material_reads':0,'provider_qualification':False,'scientific_qualification':False}
    try:
        pair=run(root/'pair',source,a.dependency_root)
        import tests_viewer
        viewer=tests_viewer.run_controls(source,a.dependency_root,root/'viewer')
        C.need(pair['status']=='passed' and viewer['status']=='pass','Both generated control components passed')
        report.update(status='passed',pair_status=pair['status'],viewer=viewer)
    except BaseException as exc:
        report.update(error=type(exc).__name__,message=str(exc),traceback=traceback.format_exc(limit=12))
    report['retained_before_combined_result_bytes']=sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
    result=C.write_new(root/'RESULT.json',C.encode(report))
    print(json.dumps({'status':report['status'],'result':result},sort_keys=True))
    if report['status']!='passed':raise SystemExit(1)
    return report


if __name__=='__main__':main()
