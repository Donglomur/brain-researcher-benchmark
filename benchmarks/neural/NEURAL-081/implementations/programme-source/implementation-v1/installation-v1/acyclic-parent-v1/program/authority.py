"""Protected acyclic independent qualification channel, before authentic operands.

This validates exact operator-issued source/run/request/role joins. It cannot
make an unqualified filesystem, provider, image, input or runtime qualified.
"""
from pathlib import Path
import common as c
import schedule
from custody import disjoint_roots

ROLES=('input','access','native','physical_custody','provider','resources','observer')
PHASES=('G0','G1','G2','G3','G5')
ACTORS=('controller','outer','preparer','reference','author','issuer','candidate','grader')

def run_allocation(run,budget,index=None):
    c.exact(run,('schema','origin','normal_endpoint','whole_limits','phase_limits','outer_limits','issuer_limits','N','request_caps','artifact_caps','status'))
    c.need(run['schema']=='neural081_complete_run_v1'and run['status']=='selected_not_qualified_by_this_record','complete separately selected run')
    c.need(type(run['origin'])is float and run['origin']==budget.origin and type(run['normal_endpoint'])is float and run['normal_endpoint']==budget.end,'original exact whole clock')
    n=c.integer(run['N'],120,100000)
    expected=10*3600+3680*7200+3680*900+20*300+12*n*480+3600+120*(54*n+27)+24*60+86400+60*(7391+54*n+24)
    c.need(run['normal_endpoint']==run['origin']+expected,'source-owned complete original normal bound, no reviewer reallocation')
    if index is not None:c.need(schedule.p.counts(index)['N']==n,'actual complete census equals selected run before downstream exposure')
    c.exact(run['phase_limits'],PHASES);c.exact(run['request_caps'],PHASES);c.exact(run['artifact_caps'],PHASES)
    shares=[*run['phase_limits'].values(),run['outer_limits'],run['issuer_limits']]
    for row in [run['whole_limits'],*shares]:
        c.exact(row,('seconds',*budget.limits));c.need(type(row['seconds'])in(int,float)and not isinstance(row['seconds'],bool)and row['seconds']==expected,'all shares inherit original origin/end')
        for key in budget.limits:c.integer(row[key])
    for key in budget.limits:c.need(sum(s[key]for s in shares)<=run['whole_limits'][key],'all phase/outer/persistent issuer reservations fit whole ledger')
    c.need(run['whole_limits']['host_processes']>=3 and run['issuer_limits']['host_processes']>=1,'one controller/outer/persistent issuer plus any explicitly counted qualification operations')
    for phase in PHASES:c.integer(run['request_caps'][phase],1);c.integer(run['artifact_caps'][phase],1)
    return run

def admit(authority,source,request_pin,phase,actor,budget,source_files,*,protected_roots):
    c.exact(authority,('schema','source','source_files','run','request','phase','actor','channel_root','registry','receipts','selected_actual','provider_config','credential_names'))
    c.need(authority['schema']=='neural081_execution_authority_v1'and authority['selected_actual']is True,'separate exact actual execution selection, not build/install acceptance')
    c.need(phase in PHASES and actor in ACTORS and authority['phase']==phase and authority['actor']==actor and c.typed_equal(authority['source'],source)and c.typed_equal(authority['source_files'],source_files)and c.typed_equal(authority['request'],request_pin),'exact current phase/actor/source/request before operands')
    roots=disjoint_roots([authority['channel_root'],*protected_roots]);channel=roots[0]
    def metadata(desc):
        c.descriptor(desc);c.need(c.absolute(desc['path']).is_relative_to(channel),'selected protected issuer metadata only');return c.capture_json(desc,budget,[channel])
    registry=metadata(authority['registry']);c.exact(registry,('schema','source','run','templates','issuers','selected_actual'))
    c.need(registry['schema']=='neural081_qualification_registry_v1'and registry['selected_actual']is True and c.typed_equal(registry['source'],source)and c.typed_equal(registry['run'],authority['run']),'stable independently protected registry')
    c.exact(registry['templates'],ROLES);c.exact(registry['issuers'],ROLES);c.exact(authority['receipts'],ROLES)
    conditions={}
    for role in ROLES:
        template=metadata(registry['templates'][role]);c.exact(template,('schema','role','source','run','issuer','status','phases','actors','request_binding','conditions'))
        c.need(template['schema']=='neural081_qualification_template_v1'and template['role']==role and template['status']=='qualified'and c.typed_equal(template['source'],source)and c.typed_equal(template['run'],authority['run']),'qualified exact stable source/run role')
        c.need(type(template['phases'])is list and len(set(template['phases']))==len(template['phases'])and set(template['phases'])<=set(PHASES)and phase in template['phases'],'selected allowed phase')
        c.need(type(template['actors'])is list and len(set(template['actors']))==len(template['actors'])and set(template['actors'])<=set(ACTORS)and actor in template['actors'],'selected physical actor role')
        c.need(type(registry['issuers'][role])is list and template['issuer']in registry['issuers'][role]and template['request_binding']=='later-independent-exact-request-v1'and type(template['conditions'])is dict and template['conditions'],'acyclic independent issuer/conditions')
        receipt=metadata(authority['receipts'][role]);c.exact(receipt,('schema','role','source','run','request','phase','actor','registry','template','issuer','status','conditions'))
        c.need(receipt['schema']=='neural081_qualification_receipt_v1'and receipt['role']==role and receipt['phase']==phase and receipt['actor']==actor and receipt['status']=='qualified','exact independently issued current role receipt')
        for k,v in [('source',source),('run',authority['run']),('request',request_pin),('registry',authority['registry']),('template',registry['templates'][role]),('conditions',template['conditions'])]:c.need(c.typed_equal(receipt[k],v),'exact current '+k+' join')
        c.need(receipt['issuer']==template['issuer'],'same independently admitted issuer');conditions[role]=receipt['conditions']
    run=run_allocation(metadata(authority['run']),budget)
    c.need(conditions['access'].get('policy')=='single_query_transductive_v4'and conditions['access'].get('statistical_semantic_reviewer')is None,'V4 matched query adaptation, no hidden reviewer')
    if phase in ('G2','G3')and actor in ('controller','author'):
        c.descriptor(authority['provider_config']);c.need(type(authority['credential_names'])is list and len(authority['credential_names'])==1 and type(authority['credential_names'][0])is str,'single admitted provider name, no value')
    else:c.need(authority['provider_config']is None and authority['credential_names']==[],'no credential capability in numeric/preparer/issuer/grader')
    budget.check_clock();return run,conditions

def request(request,authority,pin,phase):
    c.exact(request,('schema','task_id','phase','source','run','output_root','payload'))
    c.need(request['schema']=='neural081_phase_request_v1'and request['task_id']==c.TASK and request['phase']==phase and c.typed_equal(authority['request'],pin)and c.typed_equal(request['source'],authority['source'])and c.typed_equal(request['run'],authority['run']),'exact source-owned phase request')
    c.absolute(request['output_root']);c.need(type(request['payload'])is dict,'typed phase payload');return request
