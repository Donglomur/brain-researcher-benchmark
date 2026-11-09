"""Full unchanged programme composition through actual protected source gates."""
from pathlib import Path
import common as c
import n081_routing as routing
import n081_selection as selection
import n081_host as host
import n081_readback as readback

def execute(args,ctx):
    # No review/program/output or credential operand is touched before this real
    # fixed-registry qualification. Missing/current unqualified routes refuse.
    registry=routing.qualify(ctx,args.condition,ctx['bootstrap'])
    review,budget=selection.review_document(args,ctx,registry)
    central_argv=routing.actual_argv(ctx,args)
    first=routing.campaign_admit(ctx,args,review,registry,budget)
    selection.bind_envelope(ctx,args,review,budget)
    selection.parent_authority(ctx)
    routing.recheck_sources(ctx,budget)
    current=routing.qualify(ctx,args.condition,budget)
    c.need(c.typed_equal(current['descriptor'],registry['descriptor'])and c.typed_equal(current['document'],registry['document']),'same actual current registry')
    second=routing.campaign_admit(ctx,args,review,current,budget)
    campaign=routing.gate.finish(first,second,central_argv,str(ctx['repo']))
    credential_name=selection.recheck_selection(ctx)
    argv=host.parent_argv(ctx,'outer');budget.check_clock()
    root=c.new_directory(args.output,budget);intent=None;original=None
    try:
        intent=c.publish_json(root/'INTENT.json',{'schema':'neural081_central_parent_intent_v1','central_source':ctx['source'],'parent_source':ctx['parent_source'],'parent_files':ctx['parent_files'],'review':ctx['review_desc'],'approval_registry':ctx['approval_desc'],'envelope':review['program'],'launch_request':ctx['envelope']['launch_request'],'run':review['run'],'argv':argv,'cwd':'/','central_argv':central_argv,'campaign':campaign,'origin':budget.origin,'normal_endpoint':budget.end,'credential_names':[credential_name],'credential_values_recorded':False,'additional_task_host_processes':1},budget)
        original=host.launch(ctx,argv,credential_name)
        retained=host.retain_original(root,original,budget)
        host.natural(original,argv,ctx,retained)
        complete=readback.replay(ctx,original['observation'])
        routing.recheck_sources(ctx,budget);selection.recheck_selection(ctx)
        latest=routing.qualify(ctx,args.condition,budget)
        c.need(c.typed_equal(latest['descriptor'],registry['descriptor']),'same registered source at final admission')
        budget.check_clock()
        result={'schema':'neural081_provisional_central_result_v1','status':'requires_independent_original_central_natural_exit','task_id':c.TASK,'condition':args.condition,'central_source':ctx['source'],'parent_source':ctx['parent_source'],'intent':intent,'original_outer_observation':retained,'complete_parent_result':complete,'central_argv':central_argv,'original_origin':budget.origin,'normal_endpoint':budget.end,'completed_monotonic':budget.clock(),'source_only_installation_does_not_qualify_runtime':True,'scientific_performance_not_inferred':True,'automatic_retry':False}
        return host.final_result(root,result,budget)
    except BaseException as error:
        host.retain_failure(root,error,ctx,intent,original)
        raise
