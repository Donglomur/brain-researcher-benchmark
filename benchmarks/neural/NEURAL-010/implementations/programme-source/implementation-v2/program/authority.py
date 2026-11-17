"""Exact protected issuer-channel joins, separate from candidate operands.

Hashes establish content identity. Physical custody of the selected operator
channel and its independent issuers is a mandatory deployment qualification;
this module does not claim that a self-written JSON file grants permission.
"""
from pathlib import Path
import common as c

ROLES=('input','method','native','physical_custody','provider','resources','observer')
PHASES=('fixed-authors','references','release','analysts','grade')

def admit(selected,source,phase,budget,source_files,observer=False,root_observer=False):
    c.exact(selected,('schema','source','phase','execution_role','request','root','issuer_registry','qualification_receipts','run','child_limits','initial_counters','source_files','selected_for_actual_execution','credential_names','provider_config'))
    c.need(selected['schema']=='neural010-protected-phase-authority-v1'and selected['selected_for_actual_execution']is True,'separate protected operator execution selection')
    c.need(not(observer and root_observer),'one exact execution role')
    role_name='root_observer'if root_observer else('observer'if observer else'worker')
    c.need(selected['execution_role']==role_name and phase in PHASES and selected['phase']==phase and c.typed_equal(selected['source'],source)and c.typed_equal(selected['source_files'],source_files),'exact role/phase and complete source identity')
    root=c.absolute(selected['root']);c.need(not root.is_symlink(),'ordinary protected issuer root')
    registry=c.capture_json(selected['issuer_registry'],budget,[root])
    c.exact(registry,('schema','source','run','role_templates','independent_issuers','selected_for_actual_execution'))
    c.need(registry['schema']=='neural010-protected-issuer-registry-v1'and registry['selected_for_actual_execution']is True and c.typed_equal(registry['source'],source)and c.typed_equal(registry['run'],selected['run']),'separately selected protected approval registry')
    c.exact(selected['qualification_receipts'],ROLES);c.exact(registry['role_templates'],ROLES);c.exact(registry['independent_issuers'],ROLES)
    # Stable registry/templates never contain current or future request,
    # authority or issued-receipt hashes. Exact per-invocation receipt pins are
    # selected through the separate protected authority. This graph is acyclic:
    # source/run -> templates -> registry -> request -> receipts -> authority.
    for role in ROLES:
        template_pin=registry['role_templates'][role];template=c.capture_json(template_pin,budget,[root])
        c.exact(template,('schema','role','source','run','issuer','status','allowed_phases','allowed_execution_roles','request_binding_rule','approved_conditions'))
        c.need(template['schema']=='neural010-independent-qualification-template-v1'and template['role']==role and template['status']=='qualified','separately qualified stable role template')
        c.need(c.typed_equal(template['source'],source)and c.typed_equal(template['run'],selected['run']),'template exact source and complete run')
        c.need(type(template['allowed_phases'])is list and len(template['allowed_phases'])==len(set(template['allowed_phases']))and set(template['allowed_phases'])<=set(PHASES)and phase in template['allowed_phases'],'template admits current complete phase')
        c.need(type(template['allowed_execution_roles'])is list and len(template['allowed_execution_roles'])==len(set(template['allowed_execution_roles']))and set(template['allowed_execution_roles'])<={'worker','observer','root_observer'}and role_name in template['allowed_execution_roles'],'template admits current actual process role')
        c.need(template['request_binding_rule']=='later-independent-operator-exact-request-v1','later request selection is independent, never self-issued by this worker')
        c.need(type(template['approved_conditions'])is dict and template['approved_conditions'],'explicit reviewed source/runtime conditions')
        c.need(type(registry['independent_issuers'][role])is list and type(template['issuer'])is str and template['issuer']in registry['independent_issuers'][role],'stable selected independent template issuer')
        descriptor=selected['qualification_receipts'][role];body=c.capture_json(descriptor,budget,[root])
        c.exact(body,('schema','role','execution_role','source','phase','run','request','issuer_registry','template','issuer','status','approved_conditions'))
        c.need(body['schema']=='neural010-independent-qualification-v1'and body['role']==role and body['execution_role']==role_name and body['phase']==phase and body['status']=='qualified','independent exact role qualification required')
        c.need(c.typed_equal(body['source'],source)and c.typed_equal(body['run'],selected['run'])and c.typed_equal(body['request'],selected['request']),'source/run/request-bound qualification')
        c.need(body['issuer']==template['issuer']and c.typed_equal(body['issuer_registry'],selected['issuer_registry'])and c.typed_equal(body['template'],template_pin),'exact current independently issued registry/template/issuer chain')
        c.need(c.typed_equal(body['approved_conditions'],template['approved_conditions']),'current receipt cannot silently broaden independently reviewed conditions')
    run=c.capture_json(selected['run'],budget,[root]);admit_run(run,budget)
    group='root_observer_limits'if root_observer else('observer_limits'if observer else'phase_limits')
    c.need(c.typed_equal(run[group][phase],selected['child_limits']),'exact preselected phase share')
    c.need(c.typed_equal(selected['initial_counters'],{k:0 for k in budget.used}),'fresh phase ledger, no invented prior consumption')
    if phase in('fixed-authors','analysts'):
        c.descriptor(selected['provider_config']);c.need(type(selected['credential_names'])is list and len(selected['credential_names'])==1 and type(selected['credential_names'][0])is str,'one explicit credential environment name, never its value')
    else:c.need(selected['provider_config']is None and selected['credential_names']==[],'no credentials in non-provider phase')
    budget.check_clock();return run

def admit_run(run,budget):
    c.exact(run,('schema','original_origin','original_deadline','whole_limits','phase_limits','observer_limits','root_observer_limits','request_caps','artifact_caps','status'))
    c.need(run['schema']=='neural010-complete-run-allocation-v1'and run['status']=='selected_not_qualified_by_this_record','complete preselected allocation')
    c.need(type(run['original_origin'])is float and run['original_origin']==budget.origin and type(run['original_deadline'])is float and run['original_deadline']==budget.end,'unchanged whole-study clock')
    c.exact(run['phase_limits'],PHASES);c.exact(run['observer_limits'],PHASES);c.exact(run['root_observer_limits'],PHASES);c.exact(run['request_caps'],PHASES);c.exact(run['artifact_caps'],PHASES)
    keys=tuple(budget.limits)
    for phase in PHASES:
        for row in(run['phase_limits'][phase],run['observer_limits'][phase],run['root_observer_limits'][phase]):
            c.exact(row,('seconds',*keys));c.need(c.finite(row['seconds'],0)==budget.end-budget.origin,'phase shares retain original complete deadline')
            for key in keys:c.integer(row[key],0)
        c.integer(run['request_caps'][phase],1);c.integer(run['artifact_caps'][phase],1)
    c.exact(run['whole_limits'],('seconds',*keys))
    c.need(c.finite(run['whole_limits']['seconds'],0)==budget.end-budget.origin,'whole selected wall envelope equals the original clock')
    for key in keys:
        c.need(sum(run[group][phase][key]for group in('phase_limits','observer_limits','root_observer_limits')for phase in PHASES)<=c.integer(run['whole_limits'][key]),'all complete prospective phase reservations fit whole envelope')
    return run

def request_join(request,authority,descriptor,phase,budget):
    c.need(c.typed_equal(authority['request'],descriptor),'exact request selected before reading its operands')
    c.exact(request,('schema','phase','source','run','output_root','payload'))
    c.need(request['schema']=='neural010-phase-request-v1'and request['phase']==phase and c.typed_equal(request['source'],authority['source'])and c.typed_equal(request['run'],authority['run']),'complete source/phase/run request join')
    c.absolute(request['output_root']);c.need(type(request['payload'])is dict,'source-owned complete phase payload');budget.check_clock();return request
