"""Concrete all37 native collection dispatch. No generic scientific executor.

The qualified external boundary stages exact source/views, executes the supplied
argv and observes processes. This module selects every job, capture builder,
source/helper mapping and output parser. It never implements ED or future fits.
"""
import types
from pathlib import Path
import time
from protocol import need,natural,sha,encode,decode,digest,descriptor,verify,qualify,bind,Budget,source_fingerprint
import capture

HERE=Path(__file__).resolve().parent

def load_builder(captured_body):
    """Execute only the source bytes included in the admitted fingerprint.

    No SourceFileLoader or bytecode cache is consulted. Standard imports and
    startup still belong to the independently qualified Python environment.
    """
    need(type(captured_body) is bytes and len(captured_body)<=262144,'captured builder source')
    filename=str(HERE/'native-capture/build_capture.py')
    module=types.ModuleType('ach_frozen_capture_builder');module.__file__=filename
    exec(compile(captured_body,filename,'exec',dont_inherit=True),module.__dict__)
    return module

def command(role,admission,program=None):
    if role=='operator_reference':
        # Exact fixed mount names, supplied by the qualified stage boundary.
        # Original helper selection is pinned; restoredefaultpath rejects ambient
        # user helper shadowing. Actual toolbox/startup path still needs review.
        expression=("restoredefaultpath; cd('/source/capture'); addpath('/source/capture','-begin'); "
          "addpath('/source/author/analysis','/source/author/utils','-end'); "
          "addpath('/source/selected-helpers','-begin'); "
          "achcap_limits=jsondecode(fileread('/request/limits.json')); "
          "ach_native_run('/data','/output',achcap_limits);")
        return admission['matlab_command']+['-batch',expression]
    key=('A' if role=='A_clarified' else 'B')+'/native'
    return [{'\u007bprogram\u007d':'/program/candidate','{request}':'/request/JOB.json','{output}':'/output'}.get(t,t)
            for t in admission['candidate_commands'][key]]

def source_packets(c,read,budget):
    bodies={}
    for d in c['original_source_members']:
        pin={k:d[k] for k in ('path','bytes','sha256')};budget.charge('read_bytes',pin['bytes']+1)
        bodies[d['author_relative_path']]=verify(read(pin),pin)
    helpers={}
    for h in c['selected_successor_helpers']:
        d=h['body'];budget.charge('read_bytes',d['bytes']+1);helpers[Path(h['target']).name]=verify(read(d),d)
    return bodies,helpers

def plans(c):
    return [dict(id=role+'/'+root['id'],role=role,root=root,mode=root['default_mode'])
            for role in c['roles'] for root in c['roots']]

def closure(r,job,binding,origin,end,now):
    need(type(r) is dict and r.get('job_id')==job['id'] and r.get('binding_digest')==binding
         and type(r.get('origin_ns')) is int and r['origin_ns']==origin,'independent job/source/origin binding')
    need(type(r.get('exit_code')) is int and r['exit_code']==0 and all(r.get(k) is True for k in
         ('natural_exit','all_descendants_closed','source_unchanged','view_isolation_verified','ordinary_files_only','parent_directories_fsynced','stream_eof','resources_complete')),'complete independent natural-zero custody')
    need(r.get('forced_stop') is False and r.get('unknown_foreign_custody') is False,'forced/unknown custody refuses')
    finish=r.get('finished_ns');need(type(finish) is int and origin<=finish<=now<end,'original strict phase clock')
    for k in ('stdout','stderr'):descriptor(r[k])
    need(type(r.get('inventory')) is list,'independent captured inventory')
    return r

def failure_detail(error,boundary):
    """Bounded operator-private diagnostic, never an execution authority.

    Exceptions originate in the independently qualified bridge/source, not
    deserialized candidate objects. Arbitrary candidate Python objects may not
    cross that boundary. Numerical logs stay in protected operator custody.
    """
    name=(type(error).__module__+'.'+type(error).__qualname__)[:192]
    try:
        message=str(error)
    except Exception:
        message='<exception string unavailable>'
    raw=message.encode('utf-8','replace')
    return dict(boundary=boundary,type=name,message=raw[:1024].decode('utf-8','replace'),
                message_truncated=len(raw)>1024)

def failure_descriptor(primary,secondary,budget):
    return dict(schema='ach_native_failure_v1',primary=failure_detail(primary,'primary'),
                secondary=secondary[:16],secondary_count=len(secondary),
                secondary_truncated=len(secondary)>16,measured_resources=budget.cost.copy(),
                unknown_accounting=list(budget.unknown),accepted_collection=False,
                durable_recording_established=False,outer_failure_capture_required=True)

def run(c,q,bundle_loader,admission_loader,source_reader,provider_factory,observer_factory,verify_authority,profile,*,origin_ns,clock=time.monotonic_ns):
    """Future selected native collection; installed q=false refuses before operands.

    Candidate/native subprocess execution and original MAT/input access exist only
    behind independently qualified external providers. No provider is installed.
    Original-input schemas and per-root projection coverage cannot be invented by
    either candidate. Success is a source/custody collection, never a paper score.
    """
    source_digest=qualify(q,c,verify_authority)
    need(q.get('origin_ns')==origin_ns and type(origin_ns) is int,'independently selected original origin')
    budget=Budget(profile,origin_ns,clock);capture.limits(profile['capture_limits'])
    actual_source,source_bodies=source_fingerprint(budget)
    need(actual_source==source_digest,'qualified exact installed production closure')
    bundle=bundle_loader();admission=admission_loader()
    binding=bind(c,bundle,admission,profile,source_digest,q)
    budget.charge('read_bytes',len(encode(bundle))+len(encode(admission)))
    observer=observer_factory(profile,source_digest)
    done=[];seen_contexts=set();failure=None;secondary=[]
    try:
        provider=provider_factory(profile,source_digest)
        need(provider is not observer,'independent physical observer')
        original,helpers=source_packets(c,source_reader,budget)
        # Capture-builder source is qualified as part of the exact installed package.
        builder=load_builder(source_bodies['native-capture/build_capture.py'])
        wire_contract=decode(source_bodies['native-capture/CAPTURE_SCHEMA.json'],16384)
        programs={}
        for key,d in bundle['programs'].items():
            budget.charge('read_bytes',d['bytes']+1);programs[key]=verify(provider.read_committed_program(d),d)
        freeze=dict(programs=bundle['programs'],contexts=bundle['authoring_contexts'],binding=binding,
                source_digest=source_digest,feedback_between_tracks_allowed=False,
                common_authoring_materials=admission['read_only_materials']['common'],
                author_code_by_context={k:(admission['read_only_materials']['B_author'] if k.startswith('B/') else []) for k in programs})
        seal=observer.commit_all_programs(freeze,origin_ns,budget.end)
        need(type(seal) is dict and seal.get('commitment_digest')==digest(freeze)
         and all(seal.get(k) is True for k in ('all_four_independently_authored','before_numeric_exposure','durable_source_seal','authoring_views_verified')),'global independent four-policy commitment')
        jobs=plans(c);need(len(jobs)==111,'complete original native programme')
        for ordinal,job in enumerate(jobs):
            budget.tick();root=job['root'];role=job['role'];context=f'ach-{ordinal:03d}-{root["id"]}'
            need(context not in seen_contexts,'fresh worker context');seen_contexts.add(context)
            source_map={name:original[name] for name in (root['original_path'],'utils/plotPretty.m','utils/plotDLCaligned.m')}
            generated=builder.build(root['id'],job['mode'],source_map,context)
            # Every generated source byte, including helper reads, is charged.
            source_extent=sum(len(b) for b in generated['sources'].values())+len(generated['capture_spec_bytes'])
            budget.charge('read_bytes',source_extent+builder.CONTRACT_BYTES)
            interface_items=[generated['capture_spec']['root_contract']]+generated['capture_spec']['external_helpers']
            public_anchors=[dict(anchor=item['source']['author_relative_path']+'::'+a['function']+'::L'+str(a['line']),kind=a['kind'])
                            for item in interface_items for a in item['capture_anchors']]
            request=dict(schema='ach_native_job_v1',job_id=job['id'],root_id=root['id'],role=role,mode=job['mode'],context_id=context,
                original_source_sha256=root['source']['sha256'],capture_spec_sha256=generated['capture_spec_sha256'],
                original_origin_ns=origin_ns,original_deadline_ns=budget.end,limits=profile['capture_limits'],
                expected_schema=admission['output_schemas'][root['id']],original_output_obligation=root['output_obligation'],
                classification=root['scientific_classification'],new_scientific_result_claim=False,
                capture_interface=dict(schema='ach_native_typed_capture_schema_v1',allowed_snapshot_anchors=public_anchors,
                  allowed_value_taps=[x['tag'] for x in interface_items[0]['transforms'] if x['kind']=='identity_value_tap'],
                  wire_contract=wire_contract,
                  original_code_or_reversal_edits_included=False))
            # All declared originals remain in the complete admission. Forced
            # recomputation exposes no saved/condition aggregate products to any
            # producer; authentic upstream epochs have their own exact mapping.
            rows={m['id']:m for m in c['original_input_members']}
            held_products={'saved_regression_product','saved_association_product','saved_auc_summary','saved_discrimination_product','condition_summary_neural','cellclass_or_derived_bundle_unresolved','condition_summary_behavior'}
            allowed={key:d for key,d in admission['original_inputs'].items()
                     if rows[key]['role']!='non_scientific_os_metadata' and
                        (job['mode']!='forced_recompute' or rows[key]['role'] not in held_products and rows[key]['role']!='condition_average_photometry')}
            view=dict(common=admission['read_only_materials']['common'],original_inputs=allowed,
                native_compatibility=admission['native_compatibility'][root['id']],
                original_native_target_names={k:rows[k]['member'] for k in allowed},
                processed_epochs=admission['processed_epoch_inputs'].get(root['id']),
                author_code=admission['read_only_materials']['B_author'] if role=='B_author_code' else [],
                oracle_capture_visible=False,other_context_history_visible=False,query_targets_visible=False)
            files={'/request/JOB.json':encode(request),'/request/limits.json':encode(profile['capture_limits']),
                   '/request/COMMON_CONVENTIONS.json':source_bodies['PUBLIC_CONVENTIONS.json']}
            if role=='operator_reference':
                files.update({'/source/capture/'+name:b for name,b in generated['sources'].items()})
                files.update({'/source/author/'+name:b for name,b in original.items()})
                files.update({'/source/selected-helpers/'+name:b for name,b in helpers.items()})
            else:
                key=('A' if role=='A_clarified' else 'B')+'/native';files['/program/candidate']=programs[key]
            argv=command(role,admission)
            job_binding=digest(dict(global_binding=binding,request=request,view=view,argv=argv,
                files={name:dict(bytes=len(b),sha256=__import__('hashlib').sha256(b).hexdigest()) for name,b in sorted(files.items())}))
            result=None;primary=None
            try:
                budget.tick()
                token=provider.stage_exact(context,files,view,job_binding,origin_ns,budget.end)
                budget.tick()
                result=provider.launch_exact(token,argv,job_binding,origin_ns,budget.end)
            except Exception as error:primary=error
            # Observation is attempted even if stage/launch failed. It owns
            # failure logs and independent process cleanup, not this self-report.
            try:
                observed=observer.close_job(context,job['id'],result,primary,job_binding,origin_ns,budget.end)
            except Exception as error:
                budget.unknown.append(job['id']+': independent observer failed; job costs/custody unknown')
                if primary is not None:
                    secondary.append(failure_detail(error,'job observation'))
                    if hasattr(primary,'add_note'):primary.add_note('Independent job observation also failed: '+type(error).__name__)
                    raise primary from error
                raise
            try:
                if not isinstance(observed,dict) or observed.get('resources_complete') is not True:
                    budget.unknown.append(job['id']+': resource measurement completeness not established')
                budget.receipt_cost(observed.get('resources') if isinstance(observed,dict) else None,job['id'])
            except Exception as error:
                if primary is not None:
                    secondary.append(failure_detail(error,'job cost admission'))
                    if hasattr(primary,'add_note'):primary.add_note('Independent job cost admission also failed: '+type(error).__name__)
                    raise primary from error
                raise
            if primary is not None:raise primary
            observed=closure(observed,job,job_binding,origin_ns,budget.end,budget.tick())
            need(type(result) is dict and set(result)=={'index'},'exact producer descriptor return')
            accepted=capture.admit(result['index'],lambda name,offset,n:provider.read_closed_output(context,name,offset,n),
                budget,request,generated,admission['output_schemas'][root['id']],observed['inventory'])
            record=dict(job_id=job['id'],mode=job['mode'],classification=root['scientific_classification'],
                        binding_digest=job_binding,output=accepted,closure_digest=digest(observed))
            done.append(record)
        need(len(done)==111 and [r['job_id'] for r in done]==[j['id'] for j in jobs],'no dropped roots/roles')
    except Exception as error:
        failure=error
    finally:
        try:
            overhead=observer.close_dispatch(binding,origin_ns,budget.end)
            need(type(overhead) is dict and overhead.get('binding_digest')==binding
                 and type(overhead.get('origin_ns')) is int and overhead['origin_ns']==origin_ns,
                 'independent operation-overhead identity')
            budget.receipt_cost(overhead.get('non_job_resources'),'operation overhead and cleanup')
            need(overhead.get('complete_non_job_accounting') is True
                 and overhead.get('all_owned_descendants_closed') is True,
                 'factory/commitment/failure/cleanup overhead and custody incomplete')
            now=budget.tick();finished=overhead.get('finished_ns')
            need(type(finished) is int and origin_ns<=finished<=now<budget.end,'overhead original clock')
        except Exception as error:
            budget.unknown.append('operation overhead/cleanup closure not admitted')
            if failure is None:failure=error
            else:
                secondary.append(failure_detail(error,'dispatch cleanup'))
                if hasattr(failure,'add_note'):failure.add_note('Dispatch cleanup also failed: '+type(error).__name__)
    if failure is None:
        try:
            need(not budget.unknown,'unresolved operation resource accounting')
            final=budget.tick()
        except Exception as error:failure=error
    if failure is not None:
        diagnostic=failure_descriptor(failure,secondary,budget)
        try:observer.record_failure(binding,diagnostic,done,origin_ns,budget.end)
        except Exception as error:
            secondary.append(failure_detail(error,'durable failure recording'))
            if hasattr(failure,'add_note'):failure.add_note('Independent final failure recording also failed: '+type(error).__name__)
        # If durable recording failed, the external entry observer must capture
        # this exact bounded descriptor from the raised trusted bridge error.
        try:failure.ach_failure_descriptor=failure_descriptor(failure,secondary,budget)
        except Exception as error:
            if hasattr(failure,'add_note'):failure.add_note('Structured failure attachment also failed: '+type(error).__name__)
        raise failure
    return dict(schema='ach_all37_native_collection_v1',status='complete_collection_provisional',origin_ns=origin_ns,
        finished_ns=final,deadline_ns=budget.end,commitment=seal,binding_digest=binding,records=done,
        resources=budget.cost,overhead_receipt=overhead,external_final_natural_zero_required=True,scientific_qualified=False,
        full_paper_complete=False,missing_obligations=c['mandatory_unresolved'],improvement_executed=False)
