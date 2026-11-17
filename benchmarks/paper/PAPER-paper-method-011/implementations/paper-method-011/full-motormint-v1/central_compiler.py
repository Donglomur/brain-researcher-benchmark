"""Concrete complete-request construction; no scientific execution here."""
import copy,os
from central_common import need,keys,pin,encode,exact_json,capture,absolute,relative,check_pin

FILLED_ADMISSION=('plan_sha256','runtime_source_sha256','execution_selection_sha256')
FILLED_CAMPAIGN=('admission_sha256','metadata_root','output_root','runtime_root','runtime_manifest','cgroup_path','ownership_token')

def materialize_metadata(template,admission,campaigns,publisher,maximum):
    """Copy every selected metadata input through exact bounded custody.

    Raw neural files remain in their independently admitted input roots. This
    function is an actual future authorized metadata copier, not a source-build
    claim that those data, gates, methods or targets are available.
    """
    root=absolute(template['metadata_root']);seen={};mapping=[]
    def copied(desc):
        keys(desc,('path','bytes','sha256'));relative(desc['path']);check_pin({k:desc[k] for k in ('bytes','sha256')})
        key=desc['path']
        if key in seen:
            need(seen[key]['original']==desc,'one immutable source pin per metadata path')
            return dict(seen[key]['destination'])
        raw,observed=capture(root+'/'+key,{k:desc[k] for k in ('bytes','sha256')},publisher.meter,maximum=maximum)
        name='metadata-'+str(len(seen)).zfill(6)+'.blob'
        out=publisher.put_bytes(name,raw,maximum=maximum)
        destination={'path':name,**out['pin']}
        seen[key]={'original':dict(desc),'destination':destination}
        mapping.append({'original':observed,'destination':out})
        return dict(destination)
    admission['bindings']=[copied(x) for x in admission['bindings']]
    admission['gate_evidence']={k:copied(v) for k,v in admission['gate_evidence'].items()}
    for campaign in campaigns:
        for field in ('indices','configs','recipes','trusted_payloads'):
            campaign[field]={k:copied(v) for k,v in campaign[field].items()}
        campaign['external_authoring_attempts']=copied(campaign['external_authoring_attempts'])
    return mapping

def assemble_request(template,admission,campaigns,sources,deployment,review_pin,publisher):
    """Actual acyclic producer shared by prepare and run, after full validation."""
    raw=sources.files['RUNTIME_MANIFEST.json']
    record=publisher.put_bytes('RUNTIME_MANIFEST.json',raw,maximum=1048576)
    runtime_digest=sources.runtime_pin['sha256']
    # Canonical runtime encoding is the original runtime digest algorithm's bytes.
    admission['plan_sha256']=__import__('hashlib').sha256(
        __import__('json').dumps(template['plan'],sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
    admission['runtime_source_sha256']=runtime_digest
    admission['execution_selection_sha256']=review_pin['sha256']
    runtime_digest_api=__import__('hashlib').sha256(
        __import__('json').dumps(admission,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
    for number,campaign in enumerate(campaigns):
        campaign.update(admission_sha256=runtime_digest_api,metadata_root=publisher.path,
            output_root=publisher.path+'/runtime-output/pair-'+str(number).zfill(4),
            runtime_root=sources.root+'/runtime',runtime_manifest={'path':'RUNTIME_MANIFEST.json',**record['pin']},
            cgroup_path=deployment['child_cgroup_path'],ownership_token=deployment['ownership_token'])
    hashes=[__import__('hashlib').sha256(
        __import__('json').dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest() for x in campaigns]
    return {'admission_value':admission,'selected_admission_sha256':runtime_digest_api,
            'plan':template['plan'],'campaigns':campaigns,'campaign_sha256':hashes}

def prepare(sources,runtime,template,deployment,review,review_pin,publisher):
    """Validate all17 modules, full typed support and balanced A/B before copies."""
    keys(template,('schema','task','metadata_root','plan','admission_template','campaign_templates'))
    need(template['schema']=='motormint_complete_program_template_v1' and template['task']=='PAPER-paper-method-011','whole programme template')
    plan=template['plan'];admission=copy.deepcopy(template['admission_template'])
    campaigns=copy.deepcopy(template['campaign_templates'])
    module=runtime.load('mintbench.admission');validation=runtime.load('mintbench.validation')
    publisher.meter.tick();module.validate_plan(plan);publisher.meter.tick()
    need(type(campaigns) is list and 2<=len(campaigns)<=128,'complete balanced block, not one adaptive case')
    runtime.load('mintbench.schedule').validate_block(campaigns)
    need(all(admission.get(k) is None for k in FILLED_ADMISSION),'constructor-only admission fields must be empty')
    need(admission['mode']=='authentic','invented controls cannot construct authentic run authority')
    need(set(admission['gate_evidence'])=={g['id'] for g in runtime.load('mintbench.catalog').gaps()['gaps']},
         'every original gate required before input capture')
    for pin_ in list(admission['gate_evidence'].values())+admission['bindings']:validation.descriptor(pin_)
    module.context_pair(admission['context_pair'])
    ids={c['id'] for c in plan['cases']}
    reference_sha=sources.manifest['runtime_files']['reference_sources/worker_program.py']['sha256']
    need(all(c['reference_source_sha256']==reference_sha for c in plan['cases']),
         'one real complete reference dispatcher across the full plan')
    loss_sources={}
    for case in plan['cases']:
        if case['module']=='neuron_loss':
            old=loss_sources.setdefault(case['method'],case['source_recipe_sha256'])
            need(old==case['source_recipe_sha256'],'loss method source is invariant across hidden masks/counts/regimes')
    for campaign in campaigns:
        need(all(campaign.get(k) is None for k in FILLED_CAMPAIGN),'constructor-only campaign fields must be empty')
        for field in ('indices','configs','recipes','trusted_payloads'):
            need(type(campaign[field]) is dict and set(campaign[field])==ids,'all-case source metadata, no reduced prefix')
        need(campaign['schema']=='motormint_full_campaign_v2','actual accepted campaign schema')
        need(set(campaign['programs'])=={'reference','candidate_A','candidate_B'},'whole reference and paired code conditions')
        need(campaign['docker']==deployment['docker'] and campaign['python']==deployment['python']
             and campaign['gpu_devices']==deployment['gpu_devices'],'deployment-bound actual runtime executables/devices')
        worker=sources.manifest['runtime_files']['mintbench/worker.py']['sha256']
        for program in campaign['programs'].values():need(program['worker_sha256']==worker,'all roles use exact accepted worker')
        need(campaign['programs']['reference']['source_sha256']==sources.manifest['runtime_files']['reference_sources/worker_program.py']['sha256'],
             'actual original reference dispatcher source, not a callback')
    limits=admission['limits']
    need(limits['normal_seconds']==deployment['normal_seconds'] and limits['cleanup_seconds']==deployment['cleanup_seconds'],
         'same original source/normal/cleanup clock')
    need(len(campaigns)*3*len(plan['cases'])<=limits['attempts'],'whole block includes every attempted case')
    role_seconds=admission['context_pair']['A']['resources']['role_seconds']
    need(len(campaigns)*3*(role_seconds+limits['cleanup_seconds'])<limits['normal_seconds'],'room for actual preparation, scoring and paired roles')
    mapping=materialize_metadata(template,admission,campaigns,publisher,deployment['maximum_metadata_bytes'])
    request=assemble_request(template,admission,campaigns,sources,deployment,review_pin,publisher)
    admitted=module.Admission(request['admission_value'],request['selected_admission_sha256'],plan);admitted.require_authentic()
    publisher.meter.tick()
    # Reopen every copied constructor input before serializing the actual caller.
    for campaign in request['campaigns']:
        for case in plan['cases']:
            values={}
            for name in ('indices','configs','recipes'):
                d=campaign[name][case['id']];raw,_=capture(publisher.path+'/'+d['path'],
                    {k:d[k] for k in ('bytes','sha256')},publisher.meter,maximum=deployment['maximum_metadata_bytes'])
                values[name]=exact_json(raw,deployment['maximum_metadata_bytes'])
            runtime.load('mintbench.bindings').validate_bundle(case,values['indices'],values['configs'],values['recipes'])
            need(validation.digest(values['indices'])==case['input_index_sha256']
                 and validation.digest(values['configs'])==case['config_sha256']
                 and validation.digest(values['recipes'])==case['metric_recipe_sha256'],'exact prepared case commitments')
            publisher.meter.tick()
    # Runtime digest uses UTF8 canonical form, identical to original validation.
    raw=validation.encoded(request);need(len(raw)<=33554432,'complete caller request fits original child contract')
    produced=publisher.put_bytes('COMPLETE_REQUEST.json',raw,maximum=33554432)
    publisher.put('METADATA_COPY_INDEX.json',mapping,maximum=deployment['maximum_metadata_bytes'])
    clock=review['clock'];origin=clock['origin_ns']/1e9
    need(clock['scientific_ns']==clock['origin_ns']+deployment['normal_seconds']*1000000000
         and clock['closure_ns']==clock['scientific_ns']+deployment['cleanup_seconds']*1000000000,
         'exact original central/runtime deadline correspondence')
    spec={'request_root':publisher.path,'request':{'path':'COMPLETE_REQUEST.json',**produced['pin']},
        'output_root':publisher.path+'/runtime-output','output_bytes':deployment['runtime_output_bytes'],
        'final_reserve_bytes':deployment['runtime_final_reserve_bytes'],'python':deployment['python'],
        'child_source':sources.root+'/runtime/mintbench/campaign_child.py',
        'child_source_sha256':sources.manifest['runtime_files']['mintbench/campaign_child.py']['sha256'],
        'cgroup_path':deployment['cgroup_path'],'child_cgroup_path':deployment['child_cgroup_path'],
        'gpu_devices':deployment['gpu_devices'],'normal_seconds':deployment['normal_seconds'],
        'cleanup_seconds':deployment['cleanup_seconds'],'docker':deployment['docker'],'ownership_token':deployment['ownership_token']}
    spec_body=publisher.put('OUTER_SPECIFICATION.json',spec,maximum=65536)
    return {'request':request,'request_descriptor':produced,'specification':spec,
        'specification_descriptor':spec_body,'specification_sha256':validation.digest(spec),
        'selected_clock':{'origin':origin,'end':clock['scientific_ns']/1e9,'cleanup_end':clock['closure_ns']/1e9},
        'case_count':len(plan['cases']),'pair_count':len(campaigns),'all17_modules_validated':True,
        'metadata_copies':len(mapping),'qualified':False}

