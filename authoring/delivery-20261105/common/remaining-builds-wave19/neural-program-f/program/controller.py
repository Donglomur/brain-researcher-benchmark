"""Full150 one-case producers. This module never imports a scientific library."""
import os,shutil,time
from pathlib import Path

def write_json(p,value,budget,cap=2097152):
    return c.save(p,c.encoded(value),cap,budget.tick,budget.write)

def read_descriptor(row,budget,cap):
    policy.descriptor(row,cap)
    return c.capture(row['path'],cap,c.only_pin(row),budget.tick,budget.read)

def canonical(value):
    c.need(type(value)is dict and set(value)=={'schema','design','cases','preparation_receipt'},'exact complete canonical catalogue')
    c.need(value['schema']=='neural026_prepared_full50_v1','prepared catalogue schema')
    contracts.validate_design(value['design'])
    policy.descriptor(value['preparation_receipt'],2097152)
    c.need(type(value['cases'])is list and len(value['cases'])==50,'all50 prepared public packets')
    for row,cid in zip(value['cases'],contracts.case_ids()):
        c.need(type(row)is dict and set(row)=={'case_id','input','case'} and row['case_id']==cid,'complete canonical case order')
        policy.descriptor(row['input'],contracts.INPUT_CAP);policy.descriptor(row['case'],1048576)
    return value

def case_metadata(raw,row):
    value=c.parse(raw)
    expected=dict(schema='neural026_case_v1',**{k:row[k] for k in ('case_id','mouse','area','fold','train_id','query_id')},
                  output_file='predictions.npz',output_keys=['trial_id',*contracts.ARMS])
    c.need(type(value)is dict and value==expected and type(value.get('fold'))is int,'exact original one-case metadata')
    # Python numeric equality cannot turn boolean IDs into admitted integer IDs.
    for k in ('train_id','query_id'):
        c.need(all(type(x)is int for x in value[k]),'typed whole trial IDs')
    return value

def run(s,source,bodies,origin,end,source_reads):
    root=c.path(s['output']);c.need(not os.path.lexists(root),'fresh attempt root')
    budget=c.Budget(root,s['other_future_bytes'],end,s['limits']);budget.read(source_reads);budget.capacity(16384)
    root.mkdir(mode=0o700);c.sync_dir(root.parent,budget.tick)
    journals=[];completed=[];state='preflight';retired=0
    try:
        binding=c.parse(bodies['BINDING.json']);c.need(binding['schema']=='neural026_original_definitions_v1','original source binding')
        definition={}
        # Authenticate every exact source/doc dependency before any producer. No module execution here.
        for name,row in binding['sources'].items():definition[name]=read_descriptor(row,budget,1048576)
        cat_raw=read_descriptor(s['canonical'],budget,contracts.CATALOGUE_CAP);cat=canonical(c.parse(cat_raw))
        # Preventive complete-work reservations, not observed physical spending.
        # Both output copies may reach the unchanged original per-panel cap.
        inputs=sum(row['input']['bytes'] for row in cat['cases'])
        casebytes=sum(row['case']['bytes'] for row in cat['cases'])
        required=dict(reads=6*(inputs+casebytes)+150*s['limits']['native_response_bytes']+3*contracts.PANEL_CAP+134217728,
                      writes=3*(inputs+casebytes)+6*contracts.PANEL_CAP+134217728,
                      retained=6*contracts.PANEL_CAP+max(row['input']['bytes'] for row in cat['cases'])+134217728)
        for name,amount in required.items():c.need(s['limits'][name]>=amount,'preventive full150 '+name+' allowance')
        read_descriptor(cat['preparation_receipt'],budget,2097152)
        ref=c.pin(bodies['reference_program.py'])
        review=policy.reviews(c.parse(read_descriptor(s['reviews'],budget,2097152)),s,ref)
        programs={panel:read_descriptor(s['programs'][panel],budget,1048576) for panel in contracts.PANELS[:2]}
        programs['trusted_reference']=bodies['reference_program.py']
        contexts={};inventories={}
        for panel in contracts.PANELS:
            ctx=policy.context(c.parse(read_descriptor(s['contexts'][panel],budget,1048576)),panel,c.pin(programs[panel]),s)
            expected={name:c.pin(definition[name]) for name in contracts.visible(panel) if name not in ('input.npz','case.json')}
            c.need(ctx['documents']==expected,'exact access-condition document inventory')
            inventories[panel]=c.pin(read_descriptor(ctx['authoring_inventory'],budget,2097152));contexts[panel]=ctx
        c.need(len({x['context_id'] for x in contexts.values()})==3,'independent authoring/reference contexts')
        c.need(c.pin(definition['protocol.py'])==c.only_pin(binding['sources']['protocol.py']), 'fixed oracle source control')
        # Frozen captured source copies for native bind mounts, never the full repository.
        runtime=root/'trusted-runtime';runtime.mkdir()
        for name in ('holder.py','candidate_entry.py'):
            c.save(runtime/name,bodies[name],1048576,budget.tick,budget.write);c.readable(runtime/name,budget.tick)
        submitted=root/'programs';submitted.mkdir()
        for panel,raw in programs.items():
            c.save(submitted/(panel+'.py'),raw,1048576,budget.tick,budget.write);c.readable(submitted/(panel+'.py'),budget.tick)
        attemptroot=root/'attempts';attemptroot.mkdir();panelsroot=root/'panels';panelsroot.mkdir()
        for panel in contracts.PANELS:(panelsroot/panel).mkdir()
        manifest={p:[] for p in contracts.PANELS};totals={p:0 for p in contracts.PANELS}
        preflight=dict(schema='neural026_full150_preflight_v2',source=source,selection=c.pin(c.encoded(s)),canonical=s['canonical'],
                       reference=ref,programs={p:c.pin(x) for p,x in programs.items()},contexts=s['contexts'],
                       inventories=inventories,review=s['reviews'],origin_monotonic=origin,worker_deadline=end,
                       design=cat['design'],schedule=[list(x) for x in contracts.schedule()],required_worker_allowances=required)
        write_json(root/'PREFLIGHT.json',preflight,budget,contracts.CATALOGUE_CAP)
        for ordinal,(panel,cid) in enumerate(contracts.schedule()):
            journal=dict(ordinal=ordinal,panel=panel,case_id=cid,status='staging',staging='begun',native='not_started',view_retirement='not_started')
            journals.append(journal)
            state='stage';budget.tick();row=cat['cases'][ordinal%50];designrow=cat['design']['cases'][ordinal%50]
            attempt=attemptroot/f'{ordinal:03d}';budget.capacity(32768);attempt.mkdir();current=attempt/'view';current.mkdir()
            case_raw=read_descriptor(row['case'],budget,1048576);case_metadata(case_raw,designrow)
            input_raw=read_descriptor(row['input'],budget,contracts.INPUT_CAP)
            # The original source-preparation support review binds all numeric values. No original donor025 helper is substituted.
            viewpins={}
            for name,raw in [('input.npz',input_raw),('case.json',case_raw),*[(name,definition[name]) for name in contracts.visible(panel) if name not in ('input.npz','case.json')]]:
                viewpins[name]=c.save(current/name,raw,max(contracts.INPUT_CAP,1048576),budget.tick,budget.write);c.readable(current/name,budget.tick)
            del input_raw
            c.need(set(c.inventory(current,s['limits']['retained'])[0])==set(contracts.visible(panel)),'exact per-case view')
            intent=dict(schema='neural026_case_intent_v2',ordinal=ordinal,panel=panel,case_id=cid,source=source,
                        program=c.pin(programs[panel]),context=c.only_pin(s['contexts'][panel]),input=c.only_pin(row['input']),
                        case=c.only_pin(row['case']),view=viewpins,reference=ref,origin_monotonic=origin,worker_deadline=end)
            intentpin=write_json(attempt/'INTENT.json',intent,budget,contracts.CASE_RECEIPT_CAP)
            journal.update(status='native_preflight',staging='complete',intent=intentpin)
            state='native';budget.native('predict',ordinal)
            for name in ('holder.py','candidate_entry.py'):
                c.capture(runtime/name,1048576,c.pin(bodies[name]),budget.tick,budget.read)
            journal.update(status='native',native='attempted')
            result=native.phase(s,runtime,current,submitted/(panel+'.py'),attempt,ordinal,source,budget,end)
            journal['native']='closed'
            c.need(result['program']==c.pin(programs[panel]),'native exact selected program')
            for name,pin in viewpins.items():c.capture(current/name,contracts.INPUT_CAP,pin,budget.tick,budget.read)
            c.need(set(c.inventory(current,s['limits']['retained'])[0])==set(viewpins),'unchanged exact view membership')
            state='capture';raw=c.capture(attempt/'predictions.npz',contracts.FILE_CAP,result['output'],budget.tick,budget.read)
            totals[panel]+=len(raw);c.need(totals[panel]<=contracts.PANEL_CAP,'full panel encoded cap')
            outputpin=c.save(panelsroot/panel/(cid+'.npz'),raw,contracts.FILE_CAP,budget.tick,budget.write)
            record=dict(schema='neural026_case_closed_v2',intent=intentpin,native=c.pin(c.capture(attempt/'NATIVE.json',262144,None,budget.tick,budget.read)),
                        panel=panel,case_id=cid,ordinal=ordinal,output=outputpin,source=source,program=intent['program'],
                        reference=ref,context=intent['context'],input=intent['input'],case=intent['case'],view=viewpins)
            recordpin=write_json(attempt/'CLOSED.json',record,budget,contracts.CASE_RECEIPT_CAP)
            manifest[panel].append(dict(case_id=cid,file=cid+'.npz',**outputpin));completed.append(dict(ordinal=ordinal,closed=recordpin))
            journal['status']='retiring_view';journal['view_retirement']='attempted'
            selected_retirement=c.inventory(current,s['limits']['retained'])[2]
            journal['view_allocation_selected_for_retirement']=selected_retirement
            # Only this exact owned ordinary view is retired; costs stay cumulative. Other cases never mount it.
            shutil.rmtree(current);c.sync_dir(attempt,budget.tick);del raw
            retired+=selected_retirement
            journal.update(status='closed',view_retirement='closed')
        state='panel_publication';panelpins={}
        for panel in contracts.PANELS:
            panelpins[panel]=write_json(panelsroot/panel/'submission.json',dict(schema='neural026_submission_v1',cases=manifest[panel]),budget,contracts.CASE_RECEIPT_CAP)
        c.need(len(completed)==150,'all150 producers closed')
        pre_cost=budget.record()
        done=dict(schema='neural026_full150_complete_v2',source=source,selection=c.pin(c.encoded(s)),canonical=s['canonical'],reference=ref,
                  programs={p:c.pin(x) for p,x in programs.items()},contexts=s['contexts'],panels=panelpins,completed=completed,
                  origin_monotonic=origin,worker_deadline=end,costs_before_complete_publication=pre_cost,
                  retired_view_allocated_bytes=retired,case_history=journals,full50_cases_three_panels=True,scientific_qualified=False,grading_performed=False)
        raw=c.encoded(done);complete=c.save(root/'COMPLETE.json',raw,contracts.COMPLETE_CAP,budget.tick,budget.write)
        return dict(schema='neural026_full150_terminal_v2',source=source,selection=c.pin(c.encoded(s)),complete=complete,
                    final_costs=budget.record(),complete_publication_write_bytes=len(raw),status='complete_unqualified')
    except BaseException as error:
        if journals and journals[-1]['status']!='closed':
            initiating=journals[-1];initiating['status']='failed';initiating['error_type']=type(error).__name__
            if initiating['staging']=='begun':initiating['staging']='failed'
            if initiating['native']=='attempted':initiating['native']='failed_or_unclosed'
            if initiating['view_retirement']=='attempted':initiating['view_retirement']='failed_or_incomplete'
        failure=dict(schema='neural026_failed_v2',source=source,state=state,error_type=type(error).__name__,
                     attempted=journals,unattempted=[list(x) for x in contracts.schedule()[len(journals):]],
                     known_costs_before_failure_publication=budget.record(),retired_view_allocated_bytes=retired,
                     native_recovery_may_be_required=True,no_grade=True)
        try:write_json(root/'FAILURE.json',failure,budget)
        except BaseException:pass
        # The enclosing independent observer records unavailable failed-work counters as UNKNOWN, never zero.
        raise
