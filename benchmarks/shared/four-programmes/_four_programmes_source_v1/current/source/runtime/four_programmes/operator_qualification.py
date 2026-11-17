"""Fixed six-domain semantic consumer of genuine earlier operator evidence."""
import errno
import hashlib
from .operator_intake import require,canonical,DIMENSIONS
from .operator_records import validate_operator_record
from .operator_schema_data import DATA

def body_identity(body):
    raw=canonical(body)
    return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def same_body(descriptor,body):
    require({k:descriptor[k]for k in ('bytes','sha256')}==body_identity(body),'exact earlier complete body')

def _distinct(rows):
    require(len({canonical(x)for x in rows})==len(rows),'no repeated original semantic occurrence')

def _original_artifacts(selection):
    indexes={};used={}
    for plural,name,count in (
            ('invocations','OriginalOperatorQualificationInvocationV1',12),
            ('observations','OriginalOperatorQualificationObservationV1',12),
            ('completions','OriginalOperatorQualificationCompletionV1',6)):
        rows=selection['qualification_evidence'][plural]
        require(len(rows)==count,'complete original artifact roster')
        index={}
        for row in rows:
            validate_operator_record(name,row['body']);same_body(row['descriptor'],row['body'])
            key=canonical(row['descriptor']);require(key not in index,'unique original artifact identity')
            index[key]=row['body']
        indexes[plural]=index;used[plural]=set()
    def take(plural,pin):
        key=canonical(pin)
        require(key in indexes[plural] and key not in used[plural],'one selected complete original artifact')
        used[plural].add(key)
        return indexes[plural][key]
    return indexes,used,take

def _join_original_report(report,take):
    domain=report['domain'];invocations=[];observations=[]
    for case in report['cases']:
        original=take('invocations',case['original_invocation'])
        observed=take('observations',case['original_observation'])
        require(original['domain']==domain and original['case']==case['case'] and
                original['attempt']==report['original_attempt'] and
                original['qualifier_source']==original['fixed_procedure_source']==report['qualifier_source'] and
                original['environment']==report['qualifier_environment'] and
                original['subject']==report['subject'] and original['process']==report['original_process'],
                'actual original invocation source/domain/process/subject')
        require(observed['domain']==domain and observed['case']==case['case'] and
                observed['invocation']==case['original_invocation'] and
                observed['observer_source']==case['observer_source']==report['qualifier_source'] and
                observed['process']==report['original_process'] and
                original['started_ns']==observed['started_ns']==case['started_ns'] and
                observed['completed_ns']==case['completed_ns'] and
                observed['observation']==case['observation'],'exact original raw observation projection')
        invocations.append(case['original_invocation']);observations.append(case['original_observation'])
    completed=take('completions',report['original_completion'])
    require(completed['domain']==domain and completed['attempt']==report['original_attempt'] and
            completed['qualifier_source']==report['qualifier_source'] and
            completed['environment']==report['qualifier_environment'] and
            completed['subject']==report['subject'] and completed['process']==report['original_process'] and
            completed['waited_pid']==report['original_process']['pid'] and
            completed['started_ns']==report['started_ns'] and completed['completed_ns']==report['completed_ns'] and
            completed['invocations']==invocations and completed['observations']==observations and
            completed['cost']==report['original_cost'],'actual complete original terminal and ordered case inverse')
    cost=completed['cost']
    require(cost['original_attempt']==report['original_attempt'] and
            cost['process']==report['original_process'] and not cost['unknown_dimensions'] and
            cost['observed_through_ns']<=completed['completed_ns'],'same original completed qualifier cost')

def _join_original_tools(selection,invocation):
    pairs=selection['static_values']['qualified_command_pairs'];evidence=selection['tool_evidence']
    require(len(pairs)==len(evidence),'one complete original tool evidence triple per selected role')
    all_pins=[]
    for pair,record in zip(pairs,evidence):
        for key,typ in [('invocation','OriginalOperatorToolInvocationV1'),
                        ('completion','OriginalOperatorToolCompletionV1'),
                        ('qualification','OriginalOperatorToolQualificationV1')]:
            row=record[key];validate_operator_record(typ,row['body']);same_body(row['descriptor'],row['body'])
            all_pins.append(row['descriptor'])
        start=record['invocation']['body'];end=record['completion']['body'];qualified=record['qualification']['body']
        require(record['invocation']['descriptor']==pair['original_invocation'] and
                record['completion']['descriptor']==pair['original_completion'] and
                record['qualification']['descriptor']==pair['qualification_report'],
                'exact original per-tool artifacts, not uninspected references')
        require(start['tool']==pair['tool']==qualified['tool'] and
                start['argv'][0]==pair['original_argv0']==pair['command']==qualified['command'] and
                start['qualifier_source']==pair['qualifier_source']==qualified['qualifier_source'] and
                start['environment']==pair['environment']==qualified['environment'] and
                start['executable']==pair['qualified_executable']==qualified['qualified_executable'],
                'same original qualified command element/source/environment/executable')
        require(start['process']==pair['original_process']==end['process'] and
                end['waited_pid']==start['process']['pid'] and end['attempt']==start['attempt'] and
                end['invocation']==pair['original_invocation'] and
                qualified['original_invocation']==pair['original_invocation'] and
                qualified['original_completion']==pair['original_completion'] and
                start['started_ns']==end['started_ns']<=end['completed_ns']<=qualified['completed_ns']<=invocation.intake.first_wall,
                'actual original per-tool wait/terminal/qualification precedes intake')
        cost=end['cost']
        require(cost['original_attempt']==start['attempt'] and cost['process']==start['process'] and
                cost['observed_through_ns']<=end['completed_ns'] and not cost['unknown_dimensions'],
                'actual earlier per-tool original costs')
    _distinct(all_pins)

def _prefix(prefix,invocation):
    validate_operator_record('NativePreEntryPrefixV1',prefix)
    a=invocation.launch_anchor;r=a['original_reservation']
    same_body(prefix['reservation'],r)
    require(prefix['original_attempt']==a['original_attempt'] and prefix['process']==invocation.intake.body['entry_identity'],
            'original pre-entry process/attempt')
    require(prefix['clock']==invocation.intake.body['clock'] and
            prefix['original_counter_identity']==r['original_counter_identity'] and
            prefix['original_terminal_reserve']==r['terminal_reserve'] and
            prefix['observer_source']==r['pre_entry_observer_source'] and
            prefix['observed_through_ns']<=invocation.intake.first_wall,'same earlier native accounting origin')
    require(not prefix['unknown_dimensions'],'missing actual pre-entry accounting cannot be zero-filled')
    for dim in DIMENSIONS:
        require(prefix['completed'][dim]<=prefix['conservative_allocated'][dim]<=a['native_preentry_reserved'][dim],
                'actual earlier prefix inside same original retained reservation')

def _cases(report,invocation,selection):
    domain=report['domain'];cases=report['cases']
    require([c['case']for c in cases]==DATA['cases'][domain],'whole exact original qualification case roster')
    for case in cases:
        validate_operator_record('OperatorQualificationCaseV1',case)
        require(case['observer_source']==report['qualifier_source'] and
                report['started_ns']<=case['started_ns']<=case['completed_ns']<=report['completed_ns'],
                'original case source and time interval')
        require(case['original_invocation']!=case['original_observation'],'actual distinct invocation and observation')
        o=case['observation'];kind=case['case']
        if kind=='source_closure_complete':
            require(o['selected_closure']==invocation.profile['installed_closure'] and
                    o['observed_members']==selection['installed_closure']['members'] and
                    not o['missing'] and not o['extra'],'full selected original source closure')
        elif kind=='source_loaded_identity':
            expected=[{'role':x['role'],'module':x['loaded_module'],'descriptor':x['descriptor'],
                       'code_sha256':x['loaded_code_sha256']}for x in selection['installed_closure']['members']]
            require(o['module_code_identities']==expected and not o['mutable_or_unselected_modules'],
                    'complete qualifier source/code identities')
            require(o['namespace_origin']==selection['installed_closure']['qualification_subject'],
                    'same earlier source qualification subject')
        elif kind=='dependency_complete':
            require(o['selected_dependencies']==invocation.profile['dependency_closure'] and
                    o['observed_dependencies']==selection['dependencies']['members'] and
                    not o['missing'] and not o['extra'],'full selected dependency closure')
        elif kind=='environment_exact':
            require(o['selection']==invocation.profile['environment'] and
                    o['observed_environment']==selection['environment'],'same exact qualification environment')
        elif kind=='entry_fd_readonly_sealed':
            require(o['fd']==197 and o['access_mode']==0 and o['seals']==15 and o['offset']==0 and
                    o['write_attempt_errno']in (errno.EPERM,errno.EBADF) and
                    o['truncate_attempt_errno']in (errno.EPERM,errno.EBADF),
                    'actual qualified immutable readonly transport and original negative outcomes')
        elif kind=='entry_not_participant_accessible':
            require(o['probe_source']==report['qualifier_source'] and o['source_isolation_subject']==report['subject'] and
                    all(x in (errno.EACCES,errno.EPERM,errno.EBADF)for x in o['observed_errno']) and
                    o['descendant_fd197_occurrences']==0,'complete original exclusion probe outcomes')
        elif kind=='original_process_anchor':
            require(o['launcher']==selection['launcher_identity'] and o['entry']==selection['entry_identity'] and
                    o['boot_id']==selection['entry_identity']['boot_id'] and
                    o['parent_pid']==selection['launcher_identity']['pid'],'original launcher/entry identity')
            require(o['launcher_start_ticks']==invocation.observed['launcher_start_ticks'] and
                    o['entry_start_ticks']==invocation.observed['entry_start_ticks'],
                    'actual current anchored original starts, not PID equality alone')
        elif kind=='monotonic_clock_mapping':
            require(o['clock']==selection['clock'] and o['mapping']==selection['clock_mapping'] and
                    o['clock_source']==selection['clock_mapping']['source'],'same actual qualified monotonic mapping')
        elif kind=='seven_dim_original_prefix':
            require(o['prefix']==selection['pre_entry_prefix'],'complete actual original prefix')
            _prefix(o['prefix'],invocation)
        elif kind=='reservation_transfer_continuity':
            r=invocation.launch_anchor['original_reservation']
            require(o['reservation']==r and o['counter_identity']==r['original_counter_identity'] and
                    o['original_terminal_reserve']==r['terminal_reserve'] and o['observed_start']==selection['clock'],
                    'same original reservation, clocks and counter identity before transfer')
        elif kind=='tool_complete_roster':
            require(o['tools']==selection['static_values']['original_tool_roster'] and
                    o['qualified_pairs']==selection['static_values']['qualified_command_pairs'],
                    'complete original tool roster and actual qualifier pairs')
        elif kind=='tool_original_invocation':
            require(o['invocations']==selection['static_values']['qualified_command_pairs'] and
                    o['environment']==invocation.profile['environment'],'exact original complete tool invocations')
            for pair in o['invocations']:
                validate_operator_record('OperatorQualifiedCommandV1',pair)
                require(pair['command']==pair['original_argv0'] and pair['qualifier_source']==report['qualifier_source'] and
                        pair['environment']==o['environment'],'actual qualified single argv element/source/environment')
                require(pair['original_invocation']!=pair['original_completion'],'earlier original tool invocation and terminal')
        else:raise ValueError('unselected qualification case')

def verify_operator_evidence_v1(invocation):
    from .operator_entry import InstalledOperatorInvocation
    require(type(invocation)is InstalledOperatorInvocation,'actual fixed installed entry')
    invocation.require_observed_entry()
    s=invocation.intake.body;a=invocation.launch_anchor;p=invocation.profile
    invocation.intake.reserve('work_units',len(invocation.intake.raw)*512+4096)
    invocation.intake.reserve('retained_bytes',len(invocation.intake.raw)*32+4096)
    validate_operator_record('OperatorEntrySelectionV3',s)
    require(s['profile']==a['installed_profile'] and s['deployment_id']==p['deployment_id'] and
            s['original_launch']==a['original_launch'] and s['original_reservation']==a['original_reservation'] and
            s['attempt_id']==a['original_attempt'] and s['nonce']==a['launch_nonce'],
            'same protected original operator launch and installed selection')
    require(s['launcher_identity']==a['original_launcher'] and
            s['entry_identity']==invocation.observed['entry_identity'] and
            s['launcher_identity']['source']==p['launcher_source'] and
            s['entry_identity']['source']==p['entry_source']==a['entry_source'] and
            s['entry_identity']['launch_nonce']==a['launch_nonce'] and
            s['entry_identity']['parent_launch']==a['original_launch'],
            'actual original process/source/nonce/launch, not declared PID')
    same_body(p['installed_closure'],s['installed_closure']);same_body(p['dependency_closure'],s['dependencies'])
    same_body(p['environment'],s['environment'])
    require(s['installed_closure']['source_environment']==p['environment'] and
            s['dependencies']['source_environment']==p['environment'],
            'same installed closure/dependency and selected original environment')
    require(invocation.observed['environment']==s['environment'] and
            invocation.observed['source_members']==s['installed_closure']['members'] and
            invocation.observed['dependency_members']==s['dependencies']['members'],
            'actual current installed source/environment equals qualified original subject')
    report_rows=s['qualification_reports'];reports=[row['body']for row in report_rows]
    for row in report_rows:same_body(row['descriptor'],row['body'])
    _distinct([row['descriptor']for row in report_rows])
    qualification=s['qualification_set'];same_body(qualification['descriptor'],qualification['body'])
    complete=qualification['body'];validate_operator_record('OperatorQualificationSetV1',complete)
    require(complete['reports']==[row['descriptor']for row in report_rows] and
            complete['deployment']==p['deployment_id'] and complete['qualification_policy']==p['qualification_policy'] and
            complete['installed_closure']==p['installed_closure'] and complete['dependency_closure']==p['dependency_closure'] and
            complete['environment']==p['environment'],'complete earlier source-selected qualification set')
    indexes,used,take=_original_artifacts(s)
    require([r['domain']for r in reports]==DATA['domains'],'all six complete qualification domains')
    require([r['domain']for r in p['qualification_issuers']]==DATA['domains'],'source-selected fixed qualifier roster')
    subjects={'installed_source':p['installed_closure'],'dependency_environment':p['dependency_closure'],
              'protected_operator_entry':a['installed_profile'],'original_parent_identity':a['original_launch'],
              'original_resource_accounting':a['original_reservation']['original_envelope'],
              'programme_tool_commands':s['static_values']['base_agent_policy']['descriptor']}
    for report,issuer in zip(reports,p['qualification_issuers']):
        validate_operator_record('OperatorQualificationReportV1',report)
        require(report['qualifier_source']==issuer['source'] and report['qualifier_environment']==issuer['environment'] and
                report['original_process']['source']==issuer['source'] and
                report['policy']==p['qualification_policy'] and report['deployment']==p['deployment_id'] and
                report['subject']==subjects[report['domain']],'exact original qualifier/domain/source/subject')
        require(report['started_ns']<=report['completed_ns']<=invocation.intake.first_wall,
                'qualification completed before original intake, never a future proof')
        _join_original_report(report,take)
        _cases(report,invocation,s)
    require(all(used[k]==set(indexes[k])for k in indexes),'no unused qualification artifact or alias')
    require(max(r['completed_ns']for r in reports)<=complete['completed_ns']<=invocation.intake.first_wall,
            'complete qualification set exists before original intake')
    require(s['intake_occurrence']['protected_channel_qualification']==report_rows[DATA['domains'].index('protected_operator_entry')]['descriptor'],
            'actual inherited occurrence binds the exact earlier protected-channel qualification')
    source_report=report_rows[DATA['domains'].index('installed_source')]['descriptor']
    static=s['static_values']
    require(static['plan_constants']['source_admission']==source_report and
            static['native_root_configuration']['source_admission']==source_report and
            static['native_root_configuration']['source_qualification']==source_report and
            static['entry_configuration']['source_qualification']==source_report and
            static['policy_constants']['source_qualification']==source_report and
            static['policy_constants']['native_qualification']==qualification['descriptor'],
            'actual earlier Q1 source/report and complete native-entry set, never a future capture')
    require(static['native_root_configuration']['native_qualification']!=qualification['descriptor'] and
            static['entry_configuration']['native_qualification']!=qualification['descriptor'],
            'operator FD197 evidence does not qualify native roots or worker FD199/198')
    tools=s['static_values']['original_tool_roster'];_distinct(tools)
    for k in ('base_agent_policy','base_development_profile','base_local_backend_profile','base_artifact_selection'):
        same_body(s['static_values'][k]['descriptor'],s['static_values'][k]['body'])
    policy=static['base_agent_policy'];profile=static['base_development_profile'];backend=static['base_local_backend_profile'];artifacts=static['base_artifact_selection']
    input_selection=static['agent_input_selection']
    same_body(input_selection['descriptor'],input_selection['body'])
    from .backend_native_v3_codec import validate_native_type
    selected_input=input_selection['body'];validate_native_type('AgentInputSelectionV1',selected_input)
    installed=[x['descriptor']for x in s['installed_closure']['members']]
    source_roles=('input_ABI','producer_source','protocol_source','renderer_source','renderer_bound_source')
    require(all(selected_input[k]in policy['body']['source_closure'] and selected_input[k]in installed
                for k in source_roles),'entire selected agent input/renderer implementation in original qualified source closure')
    require(selected_input['template']==artifacts['body']['template_file'] and
            selected_input['renderer_source']==artifacts['body']['template_renderer'],
            'same exact selected literal template and renderer, no new artifact identity')
    # The bound qualification is an independently selected reference only.
    # This original operator/source qualification does not fabricate its body
    # or supply the still-required real input producer/renderer enforcement.
    require(policy['body']['local_backend']==backend['descriptor'] and
            profile['body']['agent_policy']==policy['descriptor'] and
            backend['body']['artifact_selection']==artifacts['descriptor'] and
            backend['body']['worker_entry_source']==static['entry_configuration']['entry_script'],
            'exact earlier current backend/artifact/worker and original policy/profile joins')
    configuration=static['artifact_configuration']
    expected=[('server_executable',backend['body']['server_executable']),('model_gguf',artifacts['body']['model_gguf']),
              ('template',artifacts['body']['template_file']),('tokenizer_source',artifacts['body']['tokenizer_source']),
              ('renderer_source',artifacts['body']['template_renderer'])]
    require(configuration['backend_profile']==backend['descriptor'] and configuration['artifact_selection']==artifacts['descriptor'] and
            [(x['role'],x['selected'])for x in configuration['roles']]==expected,
            'whole five-role exact selected artifact mapping; bodies remain unopened at Q1')
    require([x['tool']for x in s['static_values']['qualified_command_pairs']]==tools,
            'all tools once in original first-occurrence order')
    original_tools=s['static_values']['base_agent_policy']['body']['tool_closure']
    ordered=[]
    for tool in original_tools:
        if tool not in ordered:ordered.append(tool)
    require(tools==ordered,'full original tool_closure, never a filtered subprogram')
    _join_original_tools(s,invocation)
    _prefix(s['pre_entry_prefix'],invocation)
    invocation.intake.native_prefix=s['pre_entry_prefix']
    invocation.verified_reports=tuple(reports)
    invocation.evidence_verified=True
    return invocation
