"""Trusted method provenance derived from actually collected producer jobs."""
from .errors import require
from .objects import canonical,digest
from reference_runtime.lineage import validate_training_lineage,require_xft_parent

def provenance(record):
    if record.get('original_process') is None:
        return {'job':None,'stage':None,'source':record['product'].get('source'),'request':record['product'].get('request'),'kind':'operator_input'}
    return {'job':record['producer_job'],'stage':record['producer_stage'],'source':record['product']['source'],'request':record['product']['request']}

def envelope(record):
    return {'identity':record['identity'],'product':record['product'],'provenance':provenance(record),'method_lineage':record.get('method_lineage')}

def collect_method_lineage(job,request,item,expected,parents):
    config=request.get('payload',{}).get('reference',{}).get('configuration',{})
    method=config.get('recipe',{}).get('method')
    require(expected.get('method')!='REVE-Base-XFT' or method=='REVE-Base-XFT','XFT expected method must use a bound actual configuration')
    if method!='REVE-Base-XFT' or item['kind'] not in ('state','prediction'):return None
    require(job['stage']==request['stage'],'actual method producer stage')
    if item['kind']=='state':require(item['details']['configuration']==config,'actual XFT state configuration')
    if job['stage']=='S10':
        require(item['kind']=='state','S10 creates an XFT state')
        training=validate_training_lineage(item['details']['schedule'].get('xft'),request,config)
        return {'schema':'reve-XFT-controller-lineage-v1','fit_stage':'S10','fit_product':digest(canonical(item)),'fit_request':item['request'],'fit_source':item['source'],'fit_job':job['id'],'training':training,'current_product':digest(canonical(item)),'current_stage':'S10'}
    require(job['stage'] in ('S15','S17'),'ordinary fitted state cannot masquerade as XFT')
    parent=request['payload']['reference']['parent_state']
    require(parent in parents and parent in request['parent_products'],'actual collected XFT parent required')
    record=parents[parent]
    require(request['parent_products'][parent]==record['identity'] and record['identity'] in item['parent_states'],'XFT parent cannot change between input and product')
    proof=require_xft_parent(envelope(record),calibrated=job['stage']=='S17')
    if job['stage']=='S15':
        require(item['kind']=='state' and item['details']['initial_state']==parent and item['details']['schedule'].get('xft')==proof['training'],'calibration must retain actual S10 ancestry')
    else:
        require(item['kind']=='prediction' and item['details']['state']==record['identity'],'query must name its actual calibrated XFT state')
    return {**proof,'current_product':digest(canonical(item)),'current_stage':job['stage']}

