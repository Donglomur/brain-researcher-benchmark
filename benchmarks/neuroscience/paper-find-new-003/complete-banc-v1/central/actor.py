"""Two-phase submitted programme with sealed clustering before label release."""
from pathlib import Path
from banc_runtime.codec import need,encode,pin,descriptor,relative,parse
from .authority import verify_envelope,LIMIT_FIELDS
from .io import exact_fields,read,read_json,write_json,fresh_directory,integer,metadata
from .storage import copy,census
from .reference import allocate,attempt_receipt,process_limits,persist_process
from .clustering import capture_prelabel,policy_identity
from .process import bounded_process,sandbox_argv

FORBIDDEN_CLUSTER={'fixed_an_dn_annotations','fixed_cns_annotations','fixed_effector_annotations',
 'transmitter_original_predictions','transmitter_checkpoint_selection_history','transmitter_selected_model_identity'}

def actor_plan(ctx,meter):
    method=ctx['method'];d=method['actor_plan'];root=ctx['roots']['input_root']
    p=read_json(root,d,meter)
    exact_fields(p,('schema','submission','official_code','cluster_view','downstream_view','cluster_argv','downstream_argv',
      'cluster_output','submission_bundle','limits','exposure_review'),'complete actor plan')
    need(p['schema']=='banc_complete_actor_v1','full actor schema')
    need(type(p['submission']) is list and p['submission'] and len({x['path'] for x in p['submission']})==len(p['submission']),'complete unique submitted code closure')
    for row in p['submission']:descriptor(row)
    for phase in ('cluster','downstream'):
        need(type(p[phase+'_view']) is list,'explicit visible view')
        argv=p[phase+'_argv'];need(type(argv) is list and argv and all(type(x) is str for x in argv),'fixed no-shell submitted argv')
        # Actor source executes only from its read-only input view. The rootfs
        # interpreter is selected by the deployment, not a submitted executable.
        need(argv[0].startswith('/input/submission/') and '..' not in Path(argv[0]).parts,'submitted script from sealed code view')
        l=p['limits'][phase];exact_fields(l,LIMIT_FIELDS,'whole actor phase allocation')
        for key,value in l.items():integer(value,key,1)
    need(type(p['official_code']) is list and len(set(p['official_code']))==len(p['official_code']),'explicit result-free official-code exposure')
    need(all(x in ctx['source']['runtime_captured'] and x.startswith('source/') and x.endswith(('.R','.py','.md','.toml')) for x in p['official_code']),'exact captured original source files only')
    if ctx['program'].arm=='paper_and_data':need(not p['official_code'],'paper/data arm excludes official code')
    else:need(p['official_code'],'code arm must expose audited official source')
    q=verify_envelope(parse(metadata(root/relative(p['exposure_review']),meter,1048576)),ctx['keys'],ctx['deployment']['issuers']['runtime'],'actor_exposure')
    exact_fields(q,('source_sha256','method_sha256','actor_plan_sha256','cluster_view_sha256','downstream_view_sha256','result_free_official_code_sha256','paired_budget_policy_sha256','clustering_policy_sha256'),'independent actor exposure')
    need(q['source_sha256']==ctx['source']['manifest_identity']['sha256'] and q['method_sha256']==ctx['authority'].method_identity and
      q['actor_plan_sha256']==d['sha256'] and q['cluster_view_sha256']==pin(encode(p['cluster_view']))['sha256'] and
      q['downstream_view_sha256']==pin(encode(p['downstream_view']))['sha256'] and q['result_free_official_code_sha256']==pin(encode(p['official_code']))['sha256'],'exact independent views/code audit')
    from .io import digest
    digest(q['paired_budget_policy_sha256'])
    need(q['clustering_policy_sha256']==policy_identity(),'independent audit binds source-owned fresh/fixed quantity map')
    for phase in ('cluster','downstream'):
        names=[]
        for row in p[phase+'_view']:
            exact_fields(row,('role','descriptor','destination','complete_view_provenance_sha256'),'qualified actor data view')
            need(row['role'] in method['data'],'source-specific data role')
            if phase=='cluster':need(row['role'] not in FORBIDDEN_CLUSTER,'fixed labels/selected test products withheld before clustering seal')
            descriptor(row['descriptor']);relative(row['destination']);digest(row['complete_view_provenance_sha256'])
            names.append(row['destination'])
        need(len(set(names))==len(names),'unique actor view destinations')
    relative(p['cluster_output']);relative(p['submission_bundle'])
    return p

def run_actor(ctx,root,meter):
    p=actor_plan(ctx,meter);input_root=ctx['roots']['input_root'];cap=ctx['deployment']['limits']['read_bytes']
    logs=fresh_directory(root,'logs');phases={};attempts=[]
    for phase in ('cluster','downstream'):
        view=fresh_directory(root,phase+'-input');out=fresh_directory(root,phase+'-output')
        copy(view,'paper.pdf',read(input_root,ctx['method']['paper'],meter,cap),meter)
        for d in p['submission']:copy(view,'submission/'+d['path'],read(input_root,d,meter,cap),meter)
        for row in p[phase+'_view']:copy(view,'data/'+row['destination'],read(input_root,row['descriptor'],meter,cap),meter)
        for member in p['official_code']:copy(view,'official/'+member,ctx['source']['runtime_captured'][member],meter)
        if phase=='downstream':
            first=phases['cluster'];d=first['files'][p['cluster_output']]
            # The first output was frozen and hashed before this label-bearing
            # view was created. New phase cannot mutate it or the trusted files.
            copy(view,'sealed-clusters/'+p['cluster_output'],read(first['root'],d,meter,cap),meter)
        l=p['limits'][phase];allocate(l,meter)
        command=[ctx['deployment']['sandbox']['python'],'-B']+p[phase+'_argv']
        argv=sandbox_argv(ctx['deployment']['sandbox'],role='actor_'+phase,input_root=view,output_root=out,
          source_root=ctx['source']['root'],command=command,meter=meter)
        meter.reserve_output(65536)
        receipt=bounded_process(argv,cwd=out,log_root=logs,name=phase,limits=process_limits(l,meter),meter=meter)
        persist_process(root,phase+'-process.json',receipt,meter)
        files,total=census(out,meter,cap=l['file_bytes'],total_cap=l['output_bytes'])
        meter.complete_output(total)
        receipt={**receipt,'process_log_bytes':receipt['output_bytes'],'output_bytes':receipt['output_bytes']+total}
        write_json(root,phase+'-complete-process.json',receipt,meter);attempts.append(attempt_receipt(receipt))
        phases[phase]={'root':str(out),'files':files,'receipt':receipt,'identity':pin(encode(files))['sha256']}
        write_json(root,phase+'-seal.json',phases[phase],meter)
        need(receipt['exit_code']==0,'submitted actor failed; costs and outputs retained')
        required=p['cluster_output'] if phase=='cluster' else p['submission_bundle']
        need(required in files,'complete actor phase output is missing')
        if phase=='cluster':
            phases[phase]['prelabel']=capture_prelabel(out,files[required],files,ctx['source']['contracts'],ctx['program'].selection_identity,meter,l['file_bytes'])
    prelabel={**phases['cluster']['prelabel'],'downstream_phase_inventory_identity':phases['downstream']['identity']}
    return {'phases':phases,'prelabel':prelabel,'bundle_root':phases['downstream']['root'],'bundle':phases['downstream']['files'][p['submission_bundle']],
      'attempts':attempts,'complete_submission_identity':pin(encode(p['submission']))['sha256'],
      'clustering_sealed_before_fixed_labels':True,'reference_or_key_mounts_exposed':False,'scientific_qualification':False}
