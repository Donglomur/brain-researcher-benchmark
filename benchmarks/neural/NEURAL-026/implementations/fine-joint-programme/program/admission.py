"""Independent full-output closure checks; no labels, fitting or grading."""
import math
import os
import re


def native(c, directory, expected, source, kind, ordinal, read, tick, selection, program, origin, worker_end):
    value = c.parse(c.capture(directory / 'NATIVE.json', 262144, expected, tick, read))
    c.need(value['schema'] == 'neural026-sequential-native-phase-v2' and value['source'] == source and
           value['kind'] == kind and type(value['ordinal']) is int and value['ordinal'] == ordinal and
           value['status'] == 'captured', 'Exact native phase identity')
    for key in ('all_native_resources_closed', 'cli_reaped', 'producer_closed_before_capture'):
        c.need(value[key] is True, 'Complete native lifecycle')
    c.need(value['private_scoring_called'] is False and value['error_type'] is None and
           len(value['closures']) == 3 and all(row['closed'] is True for row in value['closures']) and
           sorted(row['kind'] for row in value['closures']) == ['container', 'container', 'volume'],
           'Every native resource closed')
    prefixes = set()
    roles = set()
    for row in value['closures']:
        match = re.fullmatch(r'neural026-([a-f0-9]{24})-(candidate|holder|volume)', row.get('name', ''))
        c.need(match is not None, 'Exact named native resource')
        prefix, role = match.groups()
        c.need(role not in roles and row['kind'] == ('volume' if role == 'volume' else 'container'),
               'Distinct native resource roles')
        prefixes.add(prefix)
        roles.add(role)
        c.need(row.get('absence_observed') is True and row.get('creation_outcome_unknown') is False and
               row.get('removed') is True and row.get('closed') is True, 'Known creation, actual removal and observed absence')
    c.need(len(prefixes) == 1 and roles == {'candidate', 'holder', 'volume'}, 'One complete owned resource family')
    c.validate_natural_exit(value['natural_exit'])
    c.validate_cli_commands(value['command_metadata'], selection['native_reply_bytes'])
    c.need(value['image'] == selection['image'] and type(value['producer_memory_bytes']) is int and
           value['producer_memory_bytes'] == selection['memory_bytes'] and
           type(value['producer_seconds']) in (int, float) and
           value['producer_seconds'] == selection['producer_seconds'] and value['program'] == program,
           'Exact selected producer/image/program and resource receipt')
    for key in ('phase_started_monotonic', 'phase_deadline', 'worker_deadline'):
        c.need(type(value[key]) in (int, float) and math.isfinite(value[key]), 'Finite original phase clock')
    c.need(origin <= value['phase_started_monotonic'] < value['phase_deadline'] <= value['worker_deadline'] == worker_end,
           'Original worker deadline bounds phase')
    return value

def admit(c,contracts,expected_reference,expected_documents,root,terminal,source,selection,deadline,read):
    tick=lambda:c.before(deadline)
    def get(p,expected=None,cap=2097152):return c.parse(c.capture(p,cap,expected,tick,read))
    c.need(type(terminal)is dict and terminal.get('schema')=='neural026_full150_terminal_v2'
           and terminal.get('source')==source and terminal.get('selection')==c.pin(c.encoded(selection))
           and terminal.get('status')=='complete_unqualified','exact complete terminal')
    c.need(not os.path.lexists(root/'FAILURE.json'),'no failure marker')
    done=get(root/'COMPLETE.json',terminal['complete'],contracts.COMPLETE_CAP);pre=get(root/'PREFLIGHT.json',cap=contracts.CATALOGUE_CAP)
    programs={p:c.only_pin(selection['programs'][p]) for p in contracts.PANELS[:2]};programs['trusted_reference']=expected_reference
    for obj,schema in ((done,'neural026_full150_complete_v2'),(pre,'neural026_full150_preflight_v2')):
        c.need(obj['schema']==schema and obj['source']==source and obj['selection']==terminal['selection']
               and obj['canonical']==selection['canonical'] and obj['reference']==expected_reference
               and obj['programs']==programs and obj['contexts']==selection['contexts'],'exact independent source/configuration joins')
    origin=pre['origin_monotonic'];worker_end=deadline-selection['limits']['observer_seconds']
    c.need(type(origin)in(int,float) and math.isfinite(origin) and origin+selection['limits']['whole_seconds']==deadline
           and pre['worker_deadline']==done['worker_deadline']==worker_end and done['origin_monotonic']==origin,'one original clock')
    cat=get(selection['canonical']['path'],c.only_pin(selection['canonical']),contracts.CATALOGUE_CAP)
    contracts.validate_design(cat['design']);c.need(pre['design']==cat['design'],'full original design identity')
    inputs=sum(row['input']['bytes'] for row in cat['cases']);casebytes=sum(row['case']['bytes'] for row in cat['cases'])
    required=dict(reads=6*(inputs+casebytes)+150*selection['limits']['native_response_bytes']+3*contracts.PANEL_CAP+134217728,
                  writes=3*(inputs+casebytes)+6*contracts.PANEL_CAP+134217728,
                  retained=6*contracts.PANEL_CAP+max(row['input']['bytes'] for row in cat['cases'])+134217728)
    c.need(pre['required_worker_allowances']==required and all(selection['limits'][k]>=v for k,v in required.items()),'full duplicated-output/input preventive allowance')
    c.need(pre['schedule']==[list(x) for x in contracts.schedule()],'full150 schedule')
    c.need(done['full50_cases_three_panels'] is True and done['scientific_qualified'] is False
           and done['grading_performed'] is False,'full ungraded comparison scope')
    before=done['costs_before_complete_publication'];after=terminal['final_costs']
    c.need(after['read_reservations']==before['read_reservations']
           and after['write_reservations']==before['write_reservations']+terminal['complete']['bytes']
           and terminal['complete_publication_write_bytes']==terminal['complete']['bytes'],'complete publication debit')
    expected_phases=[dict(kind='predict',ordinal=i,reserved=selection['limits']['native_response_bytes']) for i in range(150)]
    c.need(before['native_phases']==after['native_phases']==expected_phases,'all150 full native reservations')
    for record in (before,after):
        for key,limit in (('read_reservations','reads'),('write_reservations','writes')):
            c.need(type(record[key])is int and 0<record[key]<=selection['limits'][limit],'bounded typed whole accounting')
        c.need(record['physical_IO_measured'] is False and record['failed_and_retired_costs_retained'] is True,'no false physical measurement')
    c.need(type(done['completed'])is list and len(done['completed'])==150,'all150 closure entries')
    c.need(type(done['case_history'])is list and len(done['case_history'])==150,'every attempted case disposition')
    panelrows={};c.need(set(done['panels'])==set(contracts.PANELS),'all3 panel identities')
    for panel in contracts.PANELS:
        folder=root/'panels'/panel;manifest=get(folder/'submission.json',done['panels'][panel],contracts.CASE_RECEIPT_CAP)
        c.need(type(manifest)is dict and set(manifest)=={'schema','cases'} and manifest['schema']=='neural026_submission_v1'
               and type(manifest['cases'])is list and len(manifest['cases'])==50,'exact complete original panel manifest')
        c.need(set(p.name for p in folder.iterdir())=={'submission.json',*(cid+'.npz' for cid in contracts.case_ids())},'no panel extras/omissions')
        total=0
        for row,cid in zip(manifest['cases'],contracts.case_ids()):
            c.need(type(row)is dict and set(row)=={'case_id','file','bytes','sha256'} and row['case_id']==cid
                   and row['file']==cid+'.npz','exact output descriptor order')
            pin=c.only_pin(row);c.need(pin['bytes']<=contracts.FILE_CAP,'output extent')
            total+=pin['bytes'];c.need(total<=contracts.PANEL_CAP,'panel format bound')
        panelrows[panel]=manifest['cases']
    for ordinal,(panel,cid) in enumerate(contracts.schedule()):
        tick();entry=done['completed'][ordinal]
        c.need(type(entry)is dict and set(entry)=={'ordinal','closed'} and type(entry['ordinal'])is int and entry['ordinal']==ordinal,'exact closure ordinal')
        folder=root/'attempts'/f'{ordinal:03d}';c.need(not os.path.lexists(folder/'view'),'case view retired')
        closed=get(folder/'CLOSED.json',entry['closed'],contracts.CASE_RECEIPT_CAP);intent=get(folder/'INTENT.json',closed['intent'],contracts.CASE_RECEIPT_CAP)
        history=done['case_history'][ordinal]
        c.need(type(history)is dict and history.get('ordinal')==ordinal and history.get('panel')==panel and history.get('case_id')==cid
               and history.get('status')=='closed' and history.get('staging')=='complete' and history.get('native')=='closed'
               and history.get('view_retirement')=='closed' and history.get('intent')==closed['intent'],'complete staging/native/view history')
        row=cat['cases'][ordinal%50];expected_output=c.only_pin(panelrows[panel][ordinal%50])
        for obj in (closed,intent):
            c.need(obj['panel']==panel and obj['case_id']==cid and type(obj['ordinal'])is int and obj['ordinal']==ordinal
                   and obj['source']==source and obj['program']==programs[panel] and obj['reference']==expected_reference
                   and obj['context']==c.only_pin(selection['contexts'][panel])
                   and obj['input']==c.only_pin(row['input']) and obj['case']==c.only_pin(row['case']),'case/source/input/context/program joins')
        c.need(closed['schema']=='neural026_case_closed_v2' and intent['schema']=='neural026_case_intent_v2'
               and intent['origin_monotonic']==origin and intent['worker_deadline']==worker_end,'case original clock')
        c.need(type(intent['view'])is dict and closed['view']==intent['view'] and set(intent['view'])==set(contracts.visible(panel))
               and intent['view']['input.npz']==c.only_pin(row['input']) and intent['view']['case.json']==c.only_pin(row['case']),'exact case view and no oracle in specification-only')
        for name in contracts.visible(panel):
            if name not in ('input.npz','case.json'):c.need(intent['view'][name]==expected_documents[name],'source-authenticated access-condition document')
        n=native(c,folder,closed['native'],source,'predict',ordinal,read,tick,selection,programs[panel],origin,worker_end)
        c.need(n['output']==closed['output']==expected_output,'same independently closed output')
        c.capture(folder/'predictions.npz',contracts.FILE_CAP,expected_output,tick,read)
        c.capture(root/'panels'/panel/(cid+'.npz'),contracts.FILE_CAP,expected_output,tick,read)
    c.need(set(p.name for p in (root/'attempts').iterdir())=={f'{i:03d}' for i in range(150)},'exact full attempt namespace')
    c.need(c.inventory(root,selection['limits']['retained'],500000)[2]<=selection['limits']['retained'],'retained attempt outputs; external slot separately reserved')
    tick();return done['panels'],terminal['complete']

