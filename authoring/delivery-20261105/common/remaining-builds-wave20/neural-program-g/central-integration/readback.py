"""Complete collection metadata admission, separate from protected numerical grading."""
from pathlib import Path
import re
from .core import need, encode, decode, pin, capture, read_json, inventory, number
from . import journals, panel, daemon, auxiliary
from _sleep_parent.packet import roster, admit_index
from _sleep_parent.schedule import graph


def immediate(tree, prefix=''):
    prefix=prefix+'/' if prefix else ''
    return {name[len(prefix):] for name in tree if name.startswith(prefix) and '/' not in name[len(prefix):]}


def file_names(tree, prefix):
    names=immediate(tree,prefix)
    need(all(tree[prefix+'/'+n]['kind']=='file' for n in names),'Ordinary flat source-owned journal')
    return names


def campaign_subtrees(root,tree,configuration,schedule,seals,providers,contexts,meter):
    """Exact source-owned support trees; shifted arrays are stat-only here."""
    need(not immediate(tree,'cache'),'Parent cache directory remains empty; caches live in quarantine')
    names=immediate(tree,'fixed')
    need(len(names)==1 and all(re.fullmatch('[0-9a-f]{32}',n) for n in names),'One opaque committed-source stage')
    name=next(iter(names)); fixed=configuration['fixed_submission']
    if configuration['frozen_profile']=='generic_current_person':
        wanted={'policy.py':fixed['policy']['source']}
    else:
        wanted={n:{k:fixed['bundle_members'][v][k] for k in ('bytes','sha256')}
            for n,v in [('fit.py','fit_source'),('infer.py','inference_source'),('RECIPE.json','recipe')]}
    need(file_names(tree,'fixed/'+name)==set(wanted),'Exact committed fixed source staging membership')
    for n,p in wanted.items():capture(root/'fixed'/name/n,p,meter,1048576)
    for wire in contexts.values():
        need(file_names(tree,'models/'+wire)==({'LIFECYCLE.json','PROVIDER_ADMISSION.json'} if wire in providers else set()),
             'Only adaptive provider admission files in every complete model namespace')
    for wire,seal in seals.items():
        wanted={'SEAL.json','fit.py','infer.py','RECIPE.json'}
        wanted|={f'prompt-{d["turn"]}.json' for d in seal['decisions']}
        wanted|={f'action-{d["turn"]}.json' for d in seal['decisions']}
        wanted|={f'probe-{n}.py' for n in range(1,seal['probes']+1)}
        need(file_names(tree,'investigations/'+wire)==wanted,'Exact whole investigation artifacts, no cleanup uncertainty')
    shifted={contexts[c['id']]:c for c in schedule['candidate_contexts'] if 'shifted' in c['inferences']}
    need(immediate(tree,'shifts')==set(shifted),'Every and only declared current-person EEG shift')
    for wire,context in shifted.items():
        # Candidate presentation sorts each night's channel names before clock;
        # derive names without reopening transform or numerical payload.
        stride=3 if context['view']=='EC' else 4
        wanted={'TRANSFORM.json'}|{f'channel-{i*stride+j}.npy' for i in range(len(context['nights'])) for j in (0,1)}
        need(file_names(tree,'shifts/'+wire)==wanted,'Complete full-night shifted EEG arrays, no extra artifact')


def chronology(schedule,seals,contexts,times,grant):
    """Actual source execution order, not numerical grid-choice verification."""
    ordered=[r['id'] for r in schedule['reference_caches']+schedule['references']+schedule['shared_candidate_fits']]
    previous=grant['clock']['origin']
    for identity in ordered:
        t=times[identity]
        need(previous<=t['origin']<=t['started'],'Reference/cache/shared-fit source order and original clock')
        previous=t['finished']
    for c in schedule['candidate_contexts']:
        wire=contexts[c['id']]; inferences=[times[c['id']+'-'+control] for control in c['inferences']]
        first=inferences[0]
        if wire in seals:
            seal=seals[wire]; clock=seal['clock']; fitted=times[c['id']+'-fit']
            need(previous<=clock['origin'] and seal['sealed_at']<fitted['started'],'Context begins after prior operation and final fit follows seal')
            relevant=[fitted]+inferences
            for t in relevant:
                need(t['origin']==clock['origin'] and t['original_deadline']==clock['deadline'],
                     'Fit and all inference phases retain the original investigation clock')
            for name,t in times.items():
                if name.startswith(wire+'-policy-') or name.startswith(wire+'-probe-'):
                    need(t['finished']<seal['sealed_at'],'Investigation producer closes before final seal')
            previous=fitted['finished']
        else:
            need(previous<=first['origin'],'Restricted reuse query wave begins after prior context')
        for t in inferences:
            need(previous<t['started'] and t['origin']==first['origin'] and t['original_deadline']==first['original_deadline'],
                 'All current-person inference controls preserve one enclosure and source order')
            previous=t['finished']


def full_expected(schedule, contexts, root, meter, source, frozen_policy):
    expected={}; seals={}; provider_contexts={}; fixed_wire={}
    def add(logical,action,role,spec,**extra):
        need(logical not in expected,'Unique complete logical phase')
        expected[logical]={'logical':logical,'action':action,'role':role,'spec':spec,**extra}
    for spec in schedule['reference_caches']:
        add(spec['id'],'reference_cache','reference',spec)
    for spec in schedule['references']:
        add(spec['id'],'reference_fit' if spec['kind']=='reference_fit' else 'reference_infer','reference',spec)
    for spec in schedule['shared_candidate_fits']:
        add(spec['id'],'fit','A',spec)
    need(set(contexts)=={c['id'] for c in schedule['candidate_contexts']},'All624 actual current-person context mappings')
    need(len(set(contexts.values()))==len(contexts) and all(type(v) is str and re.fullmatch('[0-9a-f]{32}',v) for v in contexts.values()),
         'Unique private opaque contexts')
    for context in schedule['candidate_contexts']:
        logical=context['id']; wire=contexts[logical]
        role='A' if context['mode']=='frozen_program' else 'B'
        fixed_wire[logical]=wire
        wire_record=read_json(root/'records'/(logical+'-wire.json'),meter)
        need(wire_record['logical_context']==logical and wire_record['wire_context']==wire,'Recorded private logical context binding')
        if context['final_fit']=='fresh_current_context':
            seal=read_json(root/'investigations'/wire/'SEAL.json',meter)
            need(seal['schema']=='neural007_investigation_seal_v1' and seal['context']==wire
                 and seal['programme_source']==source and seal['mode']==context['mode'], 'Exact complete investigation seal')
            decisions=seal['decisions']; need(type(decisions) is list and 1<=len(decisions)<=8,'All bounded decisions')
            need([x['turn'] for x in decisions]==list(range(1,len(decisions)+1)),'Complete ordered decisions')
            probes=0
            for d in decisions:
                action=read_json(root/'investigations'/wire/f"action-{d['turn']}.json",meter,d['action'])
                if role=='A':
                    prompt=capture(root/'investigations'/wire/f"prompt-{d['turn']}.json",meter=meter)
                    add(wire+f"-policy-{d['turn']}",'policy',role,context,wire_context=wire,turn=d['turn'],prompt_pin=pin(prompt))
                    need(d['receipt']['global_policy']==frozen_policy,'Globally committed policy in every fixed decision')
                if action['action']=='python_probe':
                    probes+=1; need(probes<=6 and d['turn']<len(decisions),'No final unresolved probe')
                    add(wire+f'-probe-{probes}','probe',role,context,wire_context=wire,probe=probes,probe_source=pin(action['source'].encode('utf-8')))
                else:
                    need(action['action']=='finalize' and d['turn']==len(decisions),'Exactly one final decision at end')
            need(seal['probes']==probes and type(seal['probes']) is int,'Complete actual probe count')
            need(number(seal['sealed_at']) and seal['clock']['origin']<=seal['sealed_at']<seal['clock']['deadline'], 'Original investigation seal chronology')
            seal={k:seal[k] for k in ('schema','context','programme_source','mode','decisions','probes','clock','sealed_at','provider_closure','bundle')}
            seals[wire]=seal
            if role=='B':
                provider_contexts[wire]=seal
            else:
                need(seal['provider_closure']=={'provider_used':False,'global_policy':frozen_policy}, 'No hidden provider in frozen workflow')
            add(logical+'-fit','fit',role,context)
        for control in context['inferences']:
            add(logical+'-'+control,'infer',role,{**context,'control':control})
    need(len(provider_contexts)==312, 'All312 independent adaptive providers')
    return expected,seals,provider_contexts,fixed_wire


def collect(configuration, grant, source, source_bodies, index_body, stdout, profile, endpoints, meter, native_policy):
    root=Path(configuration['root']); native={**configuration['native'],'_captured_mechanical_policy':native_policy}
    need(native_policy['source']==source and native_policy['image']==native['image']
         and native_policy['approved_rule']=='source_derived_exact_sleep_phase_mounts_v1','Exact prelaunch captured mechanical exposure rule')
    roots={'campaign':root,'control':Path(native['control_root']),'jobs':Path(native['job_root']),
           'quarantine':Path(native['quarantine_root'])}
    meter.owned_roots=list(roots.values())
    trees={k:inventory(p,meter,profile['tree_members']) for k,p in roots.items()}
    need(sum(len(t) for t in trees.values())<=profile['tree_members'],'Whole operation tree ceiling')
    rows,folds=roster(source_bodies['design/ROSTER.json'],source_bodies['design/FOLDS.json'])
    prepared=admit_index(decode(index_body),rows,pin(source_bodies['design/ROSTER.json']),False,meter)
    schedule=graph(folds,rows,configuration['frozen_profile'])
    completion=read_json(root/'COMPLETION.json',meter)
    need(decode(stdout,profile['json_depth'],profile['json_nodes'])==completion,'Complete actual child stdout equals durable completion')
    need(completion['schema']=='neural007_campaign_source_completion_v1' and completion['source']==source
         and completion['counts']==schedule['counts'] and completion['graph']==pin(encode(schedule))
         and completion['outer_scores_loaded'] is False and completion['scientific_content_admitted'] is False
         and completion['runtime_qualification_inherited'] is False,'Complete source-only collection declaration')
    need(completion['tracked_io_envelopes']==grant['tracked_io_envelopes'],'Same complete parent resource scope')
    need(read_json(root/'GRAPH.json',meter,completion['graph'])==schedule,'Exact unchanged whole graph')
    values={}
    for key,name in [('predictions','PREDICTIONS.json'),('receipts','RECEIPTS.json'),('operands','OPERANDS.json'),
                     ('private_presentations','PRIVATE_PRESENTATIONS.json'),('private_contexts','PRIVATE_CONTEXTS.json')]:
        values[key]=read_json(root/name,meter,completion[key])
    from .panel_primitives import admit_panel
    admitted=admit_panel(values['predictions'],schedule,prepared,values['receipts'])
    fixed_policy=configuration['fixed_submission'].get('policy',{}).get('source')
    expected,seals,providers,context_map=full_expected(schedule,values['private_contexts'],root,meter,source,fixed_policy)
    maximum=9405 if configuration['frozen_profile']=='generic_current_person' else 4749
    need(len(expected)<=maximum,'Whole permitted actual phase count')
    required_top={'stages','records','shifts','investigations','models','provider','cache','fixed',
        'PRIVATE_PRESENTATIONS.json','GRAPH.json','PREDICTIONS.json','RECEIPTS.json','PRIVATE_CONTEXTS.json','OPERANDS.json','COMPLETION.json'}
    need(immediate(trees['campaign'])==required_top,'No failed or unexpected campaign root artifacts')
    need(immediate(trees['campaign'],'investigations')==set(seals)
         and immediate(trees['campaign'],'provider')==set(providers)
         and immediate(trees['campaign'],'models')==set(context_map.values()),'Complete investigation/provider/model namespace')
    campaign_subtrees(root,trees['campaign'],configuration,schedule,seals,providers,context_map,meter)
    for k in ('control','jobs','quarantine'):
        names=immediate(trees[k]); need(names and all(re.fullmatch('[0-9a-f]{32}',n) for n in names),'Only opaque native phase roots')
        need(all(trees[k][n]['kind']=='directory' for n in names),'Only native phase directories')
    need(immediate(trees['control'])==immediate(trees['jobs'])==immediate(trees['quarantine']), 'All native creation/control/capture namespaces intersect exactly')
    wire_for={}
    for wire in sorted(immediate(trees['jobs'])):
        join=read_json(roots['jobs']/wire/'JOIN.json',meter)
        logical=join['logical_phase']
        need(logical in expected and logical not in wire_for and join['wire_phase']==wire,'All actual native jobs derive from complete source graph/seals')
        wire_for[logical]=wire
    need(set(wire_for)==set(expected),'No omitted actual phase, including all probes/policies')
    views=auxiliary.Views(root,trees['campaign'],meter,profile['view_cache_bytes'])
    need(views.stage_count==len(schedule['reference_caches'])+len(schedule['references'])+
         len(schedule['shared_candidate_fits'])+sum(1+len(c['inferences']) for c in schedule['candidate_contexts']
            if c['final_fit']=='fresh_current_context')+
         sum(len(c['inferences']) for c in schedule['candidate_contexts'] if c['final_fit']!='fresh_current_context')+len(seals),
         'Complete main-phase plus investigation stage count')
    for logical,operand in values['operands'].items():
        need(logical in wire_for,'Only complete known phase operands')
        wire=wire_for[logical]
        need(operand['request']['path']==str(roots['control']/wire/'REQUEST.json')
             and operand['job']['path']==str(roots['jobs']/wire/'JOB.json'),
             'Exact source-owned request and JOB paths before any panel locator read')
        vp=Path(operand['view']['path']); bp=Path(operand['binding']['path'])
        need(vp.parent.parent==root/'stages' and vp.name=='VIEW.json' and bp==vp.parent/'BINDING.json'
             and str(vp.relative_to(root)) in trees['campaign'] and str(bp.relative_to(root)) in trees['campaign'],
             'Only enumerated stage VIEW/BINDING metadata before opening')
        if 'transform' in operand:
            context=logical.rsplit('-',1)[0]
            need(context in context_map and operand['transform']['path']==str(root/'shifts'/context_map[context]/'TRANSFORM.json'),
                 'Exact current-context shift metadata path before opening')
    need(all(type(path) is str and Path(path).parent.parent==roots['control']
             and Path(path).name=='RECEIPT.json' and Path(path).parent.name in set(wire_for.values())
             for path in values['receipts'].values()), 'Only captured native receipt locators before panel reads')
    admitted=panel.admit(values['predictions'],schedule,prepared,values['receipts'],source,meter,
        values['operands'],values['private_presentations'],folds)
    cache_files={}; reference_models={}
    for spec in schedule['reference_caches']:
        wire=wire_for[spec['id']]
        r=read_json(roots['control']/wire/'RECEIPT.json',meter)
        files=r['output_inventory']['files']
        cache_files[(spec['subject'],spec['night'])]={name:files['cache/'+name]
            for name in ('context-0.npy','context-1.npy','context-2.npy','context-clock.npy')}
    for spec in schedule['references']:
        if spec['kind']=='reference_fit':
            r=read_json(roots['control']/wire_for[spec['id']]/'RECEIPT.json',meter)
            reference_models[spec['id']]={'model':r['output_inventory']['files']['MODEL.pkl'],'timing':r['timing']}

    owned={endpoint['path']:[] for endpoint in endpoints}; receipt_pins={}; phase_times={}; phase_evidence={}
    main={k for k,v in expected.items() if v['action'] not in ('policy','probe')}
    need(native['docker_socket'] in owned and configuration['model']['docker_socket'] in owned,'Exact daemon domains')
    for logical in sorted(expected):
        wire=wire_for[logical]
        names=file_names(trees['control'],wire)
        need(file_names(trees['jobs'],wire)=={'JOB.json','JOIN.json','EXPOSURE.json'},'Exact complete source-owned JOB root')
        result=journals.native(roots['control']/wire,roots['jobs']/wire,roots['quarantine']/wire,
            names,expected[logical],native,source,meter)
        auxiliary.exposure(expected[logical],result,views,prepared,folds,values['private_presentations'],
            source_bodies,cache_files,reference_models,seals,context_map,configuration,admitted)
        receipt_pins[logical]=result['receipt_pin']
        if expected[logical]['action'] in ('policy','probe'):
            e={'receipt_pin':result['receipt_pin'],'output_root':result['receipt']['quarantine_root'],
               'files':{k:v for k,v in result['receipt']['output_inventory']['files'].items()
                        if k in ('artifacts/ACTION.json','artifacts/OBSERVATION.json')},
               'clock':result['join']['clock']}
            if expected[logical]['action']=='policy':
                e['history_pin']=expected[logical]['prompt_pin']
            else:e['probe_source']=expected[logical]['probe_source']
            phase_evidence[logical]=e
        timing=result['receipt']['timing']; phase_times[logical]=timing
        need(grant['clock']['origin']<=timing['origin']<=timing['started']<timing['finished']<grant['clock']['deadline'],
             'All actual phases inside original whole campaign clock')
        need(result['join']['clock']=={'origin':timing['origin'],'deadline':timing['original_deadline'],
             'campaign_origin':grant['clock']['origin'],'campaign_deadline':grant['clock']['deadline']},
             'Whole original clock retained in every native JOIN')
        need(result['request']['resources']==configuration['phase_limits'][expected[logical]['action']]
             and result['receipt']['enforced_resource_limits']==result['request']['resources'],
             'Exact action-specific matched compute/resource limits')
        if logical in main:
            record=read_json(root/'records'/(logical+'.json'),meter)
            need(record['receipt_pin']==result['receipt_pin'] and record['receipt']==result['receipt']
                 and record['logical_phase']==logical and record['wire_phase']==wire,
                 'Captured main record equals independently observed producer')
        owned[native['docker_socket']].extend(result['resources'])
        # Metadata inventory authenticates complete membership/extents only.
        actual={name[len(wire)+1:]:v for name,v in trees['quarantine'].items()
                if name.startswith(wire+'/') and v['kind']=='file'}
        declared=result['receipt']['output_inventory']['files']
        need(set(actual)==set(declared) and all(actual[n]['bytes']==d['bytes'] for n,d in declared.items()),
             'Whole captured output tree matches all declarations; numerical hashes not replayed')
        if logical in values['operands']:
            operand=values['operands'][logical]
            need(operand['wire_phase']==wire and operand['request']['path']==str(roots['control']/wire/'REQUEST.json')
                 and operand['job']['path']==str(roots['jobs']/wire/'JOB.json'), 'Graded operands join independently enumerated physical phase')
    expected_receipts={receipt_pins[k]['sha256']:str(roots['control']/wire_for[k]/'RECEIPT.json') for k in main}
    need(values['receipts']==expected_receipts,'Complete exact main producer receipt registry')
    chronology(schedule,seals,context_map,phase_times,grant)
    record_names={k+'.json' for k in main}|{k+'-wire.json' for k in context_map}
    need(immediate(trees['campaign'],'records')==record_names,'Complete source-owned main records and private context joins')
    for wire,seal in seals.items():
        for d in seal['decisions']:
            if seal['mode']=='frozen_program':
                need(d['receipt']['native']==receipt_pins[wire+f"-policy-{d['turn']}"], 'Every policy decision derives from captured native phase')
    if configuration['frozen_profile']=='training_only_reuse':
        shared={r['id'] for r in schedule['shared_candidate_fits']}
        candidate={k for k,v in expected.items() if v['role'] in ('A','B') and k not in shared}
        need(max(phase_times[k]['finished'] for k in shared)<min(phase_times[k]['origin'] for k in candidate),
             'Every restricted shared training fit sealed before any candidate query context')
    model_closures=[]
    for wire,seal in sorted(providers.items()):
        lifecycle=read_json(root/'models'/wire/'LIFECYCLE.json',meter)
        admission=read_json(root/'models'/wire/'PROVIDER_ADMISSION.json',meter)
        need(lifecycle=={'context':wire,'deadline':seal['clock']['deadline']}
             and admission['context']==wire and admission['source']==source
             and admission['image']==configuration['model']['image']
             and admission['boundary_policy']==configuration['model']['boundary_policy']
             and admission['mailbox_policy']=='fresh_readonly_append_only_current_context',
             'Exact actual persistent-provider source/image/lifecycle admission')
        mounts={}
        for name in ('__init__.py','entry.py','common.py','provider_worker.py'):
            mounts['/library/program/'+name]={'kind':'file','purpose':'program','files':{name:pin(source_bodies['program/'+name])}}
        model_config=configuration['model']; a=model_config['profile']
        mounts['/profile.json']={'kind':'file','purpose':'contract','files':{Path(a['path']).name:{k:a[k] for k in ('bytes','sha256')}}}
        mounts['/models']={k:v for k,v in model_config['models'].items() if k!='path'}
        mounts['/lifecycle.json']={'kind':'file','purpose':'contract','files':{'LIFECYCLE.json':pin(encode(lifecycle))}}
        need(admission['immutable_mounts']==mounts,'All actual immutable provider source/model/profile mounts, no extra channel')
        observed=journals.model(root/'provider'/wire,immediate(trees['campaign'],'provider/'+wire),seal,configuration['model'],source,meter)
        need(immediate(trees['campaign'],'provider/'+wire+'/requests')==observed['request_names'],'No missing/extra provider mailbox action')
        owned[configuration['model']['docker_socket']].extend(observed['resources'])
        model_closures.append(seal['provider_closure'])
    need(sorted(completion['provider_context_costs'],key=lambda x:x['context'])==sorted(model_closures,key=lambda x:x['context']),
         'Every provider cost/closure belongs to complete current-context set')
    transcript_observation=auxiliary.transcripts(root,seals,context_map,schedule,phase_evidence,views,prepared,folds,
        values['private_presentations'],configuration,meter)
    # No remaining operation-owned creator has an unresolved intent. Only now
    # can sequential daemon inventories support operation-relative absence.
    daemon_observations=[]
    for endpoint in endpoints:
        containers=daemon.request(endpoint,'container',meter.end,profile['http'],meter)
        volumes=daemon.request(endpoint,'volume',meter.end,profile['http'],meter)
        absence=daemon.absent(owned[endpoint['path']],containers['rows'],volumes['rows'],True)
        daemon_observations.append({'container_query':containers,'volume_query':volumes,'absence':absence,
            'owned_resources':len(owned[endpoint['path']])})
    for name,p in roots.items():
        need(inventory(p,meter,profile['tree_members'])==trees[name],'Whole source-owned output tree unchanged during admission')
    return {'schema':'sleep_full153_collection_observation_v1','source':source,'complete_collection_metadata':True,
        'people':78,'nights':153,'original_objects':306,'modes':2,'views':4,'candidate_inferences':936,
        'reference_inferences':1170,'profile':configuration['frozen_profile'],'observed_native_phases':len(expected),
        'provider_contexts':312,'metadata_panel_records':len(admitted),'transcript_observation':transcript_observation,'private_targets_authenticated_by_parent_collection':True,
        'central_readback_opened_numerical_bodies':False,'protected_grading_invoked':False,
        'numerical_probabilities_validated':False,'scientific_content_admitted':False,
        'runtime_qualification_inherited':False,'research_qualified':False,'submission_ready':False,
        'daemon_observations':daemon_observations,'source_bound_model_terminal_flow_not_individual_terminal_records':True,
        'parent_birth_acquisition_qualified_by_this_observation':False}
