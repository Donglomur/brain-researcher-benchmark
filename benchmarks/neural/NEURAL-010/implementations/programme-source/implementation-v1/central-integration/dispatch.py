"""Real qualification/default route, full original phases, provisional closeout."""
import os
from pathlib import Path
import uuid

def source_recheck(env,reader,rows=None):
    for name,pin in (env['source_rows']if rows is None else rows).items():
        reader.opaque({'path':str(env['repo']/name),**pin},16777216)
    reader.tick()

def execute(args,env,startup):
    # Fixed actual registered runtime admission precedes even review/program
    # reads. Absence currently refuses here, with no candidate operand touched.
    registered=env['registration'].qualify(env,startup)
    document,review_pin=startup.json(args['review'],2097152)
    review=p.review(document,args);c=env['c']
    u.need(p.same(review['source_manifest'],{'path':str(env['here']/'SOURCE_MANIFEST.json'),**env['source_pin']}),'exact central manifest selected by review')
    u.need(review['original_origin']<=env['entry_start']<review['scientific_deadline'],'literal inherited origin, no entry reset')
    startup.tick(review['scientific_deadline'])
    programme=p.programme(p.read_pin(startup,review['program'],2097152),review,env)
    cl=programme['central_limits']
    reader=u.Reader(read_limit=cl['metadata_read_bytes'],write_limit=cl['metadata_write_bytes'],deadline=review['final_deadline'],clock=startup.clock)
    # Explicit adoption of the preselected original-clock final interval; every
    # bootstrap/qualification/operand read remains charged. Scientific code and
    # authority waits retain the distinct original scientific deadline below.
    for key in ('read_reserved','read_observed','write_reserved','write_observed','hash_bytes','decode_bytes','failures'):setattr(reader,key,getattr(startup,key))
    u.need(reader.read_reserved<=reader.read_limit and reader.write_reserved<=reader.write_limit,'all startup costs fit selected metadata partition')
    env['execution_reader']=reader;env['select_outer_timer'](review['final_deadline'])
    run=p.read_pin(reader,programme['run'],2097152)
    trial=p.allocation(programme,run,review,c);env['parent_authority'].admit_run(run,trial)
    first,command=env['registration'].campaign(env,reader,registered,review,args['actual_argv'],args['actual_cwd'])
    u.need(command==args['actual_argv'],'actual complete central command')
    # Metadata custody is selected through the registered independent policy.
    # No mere ordinary-file ownership claim establishes candidate isolation.
    protected=u.absolute(programme['protected_root'])
    for path in [programme['run']['path'],*programme['capture_roots']]:u.absolute(path)
    policy=registered['policy'];writable=[u.absolute(args['output'])]
    writable.extend(u.absolute(root)for roots in programme['phase_roots'].values()for root in roots.values())
    for out in writable:
        u.need(not out.exists()and not out.is_symlink(),'every complete selected output is fresh')
        u.need(any(out.is_relative_to(u.absolute(root))for root in policy['operand_roots']),'output inside independently admitted namespace')
        for channel_root in (policy['request_root'],policy['response_root']):
            q=u.absolute(channel_root);u.need(out!=q and not out.is_relative_to(q)and not q.is_relative_to(out),'channel namespaces separate from all outputs')
    u.need(u.absolute(programme['run']['path']).is_relative_to(protected),'original run metadata protected')
    binding={'task_id':p.TASK,'source_manifest':review['source_manifest'],'parent_source':env['parent_pin'],
        'program':review['program'],'review':{'path':args['review'],**review_pin},
        'original_origin':review['original_origin'],'original_deadline':review['scientific_deadline'],
        'final_deadline':review['final_deadline'],'outer_deadline':review['outer_deadline'],'scope':p.SCOPE}
    channel=env['authority'].FileAuthority(policy,registered['policy_pin'],reader,uuid.uuid4().hex,binding)
    channel.request('central_admission',binding)
    env['registration'].repeat_before_launch(env,reader,registered,review,first,args['actual_argv'],args['actual_cwd'])
    source_recheck(env,reader);trial.check_clock()
    output=c.new_directory(args['output'],trial)
    reader.write_new(output/'CENTRAL_INTENT.json',u.bounded_canonical({**binding,'argv':args['actual_argv'],
        'working_directory':args['actual_cwd'],'source_rows':env['source_rows'],'qualified_source_rows':registered['qualified_source_rows'],
        'policy':registered['policy_pin'],'run':programme['run'],'reserved_central_limits':cl,
        'original_parent_whole_limits':run['whole_limits'],'no_qualification_conferred':True},16777216),16777216)
    closed=env['driver'].execute(env,reader,channel,programme,run,review,output)
    u.need(list(closed)==list(p.PHASES)and all(row['scientific_deadline_admission_complete']is True for row in closed.values()),'all5 complete scientific closures')
    # Only final source/receipt readback remains. No additional scientific phase,
    # target release, report generation or grader can run after this transition.
    source_recheck(env,reader,registered['qualified_source_rows'])
    for desc in (review['program'],{'path':args['review'],**review_pin},programme['run']):reader.opaque(desc,2097152)
    final={'schema':'neural010-central-provisional-completion-v1','task_id':p.TASK,'scope':p.SCOPE,
        'program':review['program'],'review':{'path':args['review'],**review_pin},'source_manifest':review['source_manifest'],
        'parent_source':env['parent_pin'],'source_rows':env['source_rows'],'qualified_source_rows':registered['qualified_source_rows'],
        'registry':{'path':env['registration'].REGISTRY,**registered['registry_pin']},
        'actual_argv':args['actual_argv'],'working_directory':args['actual_cwd'],
        'phases':[{k:v for k,v in closed[ph].items()if k!='admitted'}|{'phase':ph}for ph in p.PHASES],
        'grade':closed['grade']['admitted']['artifacts']['phase_result'],
        'channel_records':channel.records,'channel_count':channel.sequence,'original_origin':review['original_origin'],
        'scientific_deadline':review['scientific_deadline'],'final_deadline':review['final_deadline'],
        'outer_deadline_monotonic':review['outer_deadline'],'reserved_partitions':env['reserved_partitions'],
        'metadata_cost_snapshot_before_receipt':reader.report(),'own_future_exit_established':False,
        'runtime_or_scientific_qualification_conferred':False,'new_score_computation':False}
    receipt=reader.write_new(output/'CENTRAL_COMPLETION.json',u.bounded_canonical(final,16777216),16777216)
    reader.tick()
    return {'status':'provisional_full_parent_completed_outer_exit_required','task_id':p.TASK,'receipt':receipt,
        'outer_deadline_monotonic':review['outer_deadline'],'source_manifest':review['source_manifest'],
        'runtime_or_scientific_qualification_conferred':False,'own_future_exit_established':False}
