"""Metadata/custody verification of all original phases; never decodes arrays."""
from common import need,parse,descriptor,pin,canonical,relative
from contract import SESSIONS,EPISODES,COVERAGE,WORK,contexts
from authoring import ARMS,PROGRAMS,authoring_files

def read(io,path,d,cap=1048576):return parse(io.capture(path,d,cap),cap)
def exactpin(d):return {k:d[k]for k in ('bytes','sha256')}

def journal(io,root,d,receipt=None,*,host=False):
    cap=65536 if host else 8*1024**2;events_cap=8 if host else 2753
    need(type(d['events'])is int and 0<d['events']<=events_cap and d['reserved_bytes']==cap,'exact original role journal cap')
    raw=io.capture(root/relative(d['path']),d,cap);events=[parse(r)for r in raw.splitlines()]
    need(len(events)==d['events'] and [r['sequence']for r in events]==list(range(len(events))) and len({r['name']for r in events})==len(events),'complete original ordered durable journal')
    if receipt is not None:need(events[-1]['name'].endswith('-PHASE') and events[-1]['event']==receipt,'original final phase receipt in journal')
    return events

def verify(io,root,selected,controller,engine,origin):
    raw=io.capture(root/'COLLECTION.json',{'bytes':(root/'COLLECTION.json').stat().st_size},owned_metadata_without_external_pin=True)
    r=parse(raw);need(r['schema']=='language_building_blocks_complete_paired_collection_v1' and r['task_id']==controller.TASK and r['source_manifest']==selected['source_manifest'] and r['contexts']==contexts() and r['coverage']==COVERAGE and r['original_origin']==origin and r['work_end']==origin+WORK,'complete selected source/scope/original clock')
    need(all(r[k]is False for k in ('private_grade_called','runtime_qualified','scientific_qualification','full_paper_reproduction','automatic_retry_authorized')) and r['forced_stop_independent_host_and_daemon_state']=='unknown','no qualification or forced-stop custody claim')
    need(r['phase_count']==213 and len(r['phase_receipts'])==213 and set(r['artifacts'])=={c['phase_id']for c in contexts()},'all213 original scientific contexts')
    need(r['full_admission']=={'native_candidate_panels':2,'candidate_prediction_files':140,'operator_native_panels':1,'operator_baseline_episodes':70,'operator_arrays':280,'target_arrays_opened':False,'scientific_grading_called':False},'actual complete admission attestation, not scientific grading')
    # Recheck all original closed input/source/CLI/native records and retained bytes.
    native={};pred={'A':{},'B':{}};refs={}
    for row,ctx in zip(r['phase_receipts'],contexts()):
        pid=ctx['phase_id'];base=root/'phases'/pid
        need(row['context']==ctx and row['input_retired_after_exact_closure']is True and row['original_output_bytes_retained']is True and row['receipt']['path']==f'phases/{pid}/ACCEPTED_PHASE.json','exact scientific phase and retained outputs')
        receipt=read(io,root/row['receipt']['path'],row['receipt']);files=controller.closure(receipt,engine,ctx,selected['source_manifest'],origin+WORK)
        req=read(io,base/'REQUEST.json',row['request']);engine.validate_request(ctx['role'],req)
        need(req['phase_id']==pid and req['source']==selected['source_manifest'] and req['image']==selected['images'][ctx['role']] and req['episode']==ctx['episode'],'same original request/image/source')
        need(row['journal']['path']==f'phases/{pid}/JOURNAL.jsonl','original phase journal location');journal(io,root,row['journal'],receipt)
        need(not(base/'input').exists(),'normal-success owned input retirement')
        expected={n:{'path':f'phases/{pid}/closed/artifacts/{n}',**d}for n,d in files.items()}
        need(r['artifacts'][pid]==expected,'no replacement of original output paths or identities')
        for n,d in expected.items():io.capture(root/d['path'],d,engine.expected_outputs(ctx['role'],ctx['episode'])[n],retain=False)
        if ctx['mode']=='native':native[ctx['arm']or'operator']={'root':f'phases/{pid}/closed/artifacts','files':files}
        elif ctx['arm']:pred[ctx['arm']][ctx['episode']]=expected['prediction.npz']
        else:refs[ctx['episode']]=expected
    need(r['native_panels']==native,'three exact original native panels')
    # Trusted preparation is a separate owned process, never a numerical target callback.
    hs=r['host_receipts'];need(len(hs)==71,'one full preparation and70 original episode producers')
    reports=[]
    for i,h in enumerate(hs):
        prefix='preparation' if i==0 else 'episodes/'+EPISODES[i-1]
        need(h['request_path']==prefix+'/HOST_REQUEST.json' and h['report']['path']==prefix+'/HOST_RESULT.json' and h['journal']['path']==prefix+'/HOST.jsonl','exact owned host recovery paths')
        q=read(io,root/h['request_path'],h['request']);v=read(io,root/h['report']['path'],h['report'])
        action='prepare'if i==0 else'episode';need(q['action']==action and q['source_manifest']==selected['source_manifest'] and q['environment']==selected['host_environment'] and q['original_end']==h['original_end']<=origin+WORK,'original host source/authority/deadline')
        need(v['schema']=='language_trusted_host_result_v1' and v['action']==action and v['source_manifest']==selected['source_manifest'] and v['request']==h['request'] and v['original_end']==h['original_end'] and v['scientific_fits_called']is False and v['qualified_by_this_process']is False,'same complete closed trusted report')
        if i:need(q['episode']==v['episode']==EPISODES[i-1] and q['prepared']==str(root/'preparation/prepared') and q['design']==str(root/'preparation/prepared/DESIGN.json') and q['output']==str(root/prefix/'staged'),'full original staged episode paths')
        else:need(q['archives']==selected['archives']['root'] and q['output']==str(root/'preparation'),'exact original archives/preparation root')
        engine.validate_cli_records(h['command_metadata']);need(len(h['command_metadata'])==1 and h['natural_closed']is True and h['forced_stop_custody']=='unknown','single naturally closed owned host child')
        ev=journal(io,root,h['journal'],host=True)
        need(len(ev)==3 and ev[-1]['name']=='HOST-CLOSED' and ev[-1]['event']==h['command_metadata'][0],'original host intent/result journal joins actual CLI closure')
        reports.append(v)
    prep=reports[0];pb=read(io,root/'PREPARATION_BINDING.json',r['preparation'])
    need(pb=={'prepared_files':prep['prepared'],'design':r['design'],'complete_originals':selected['archives'],'selected_retired_after_natural_close':True} and not(root/'preparation/selected').exists(),'complete original source/prepared join and selected retirement')
    b=read(io,root/'OPERATOR_BINDINGS.json',r['operator_bindings'],33554432)
    need(b['schema']=='language_episodes_v1' and b['design_sha256']==r['design']['sha256'] and list(b['episodes'])==list(EPISODES),'all70 original ordered binding identities')
    seen={s:set()for s in SESSIONS}
    for eid,hr in zip(EPISODES,reports[1:]):
        files=hr['files'];base=root/'episodes'/eid/'staged';binding=read(io,base/'operator/binding.json',files['operator/binding.json'],2000000)
        expected={'case':binding['case'],'source_rows':binding['source_rows'],'target':{'path':f'episodes/{eid}/staged/operator/target.npz',**files['operator/target.npz']},'baselines':refs[eid]['baselines.npz']}
        need(b['episodes'][eid]==expected and binding['target']['path']=='target.npz' and descriptor(binding['target'],33554432)==files['operator/target.npz'],'collection exactly follows original source-staged support/target rather than counts')
        c=binding['case'];need(c['id']==eid and c['design_sha256']==r['design']['sha256'] and pin(canonical(c))==files['candidate/case.json'],'original complete case identity')
        for key in ('training','query'):need(descriptor(c[key],268435456)==files['candidate/'+key+'.npz'],'same exact source public training/query packets')
        sr=binding['source_rows'];s=eid.rsplit('_f',1)[0];need(sr==sorted(set(sr)) and len(sr)==c['rows'] and not seen[s].intersection(sr),'same disjoint full source-staged query support');seen[s].update(sr)
        need(not(base/'candidate').exists(),'all original public episode packets retired only after three closed contexts')
        io.capture(base/'operator/target.npz',files['operator/target.npz'],33554432,retain=False)
        meta=read(io,root/refs[eid]['baselines.npz.metadata.json']['path'],refs[eid]['baselines.npz.metadata.json'],100000)
        need(meta['case_sha256']==pin(canonical(c))['sha256'] and meta['baselines']==descriptor(refs[eid]['baselines.npz'],33554432) and set(meta['selected'])=={'context','lexical','random_token','clock'},'independent source baseline identity, no candidate calibration surrogate')
        for arm in ARMS:pred[arm][eid]['case_sha256']=pin(canonical(c))['sha256']
    for arm in ARMS:
        panel=read(io,root/'panels'/(arm+'.json'),r['prediction_panels'][arm]);need(panel==controller.artifact_admission.prediction_panel(pred[arm],r['design']['sha256'],r['protocol_sha256']),'complete140 original predictions and exact public case joins')
    # The original preparations and source-derived design remain immutable too.
    for n,d in prep['prepared'].items():io.capture(root/'preparation/prepared'/relative(n),d,100000000,retain=False)
    commitment=read(io,root/'PAIR_COMMITMENT.json',r['commitment'])
    need(commitment['schema']=='language_building_blocks_global_four_program_commitment_v1' and commitment['data_or_native_phase_started']is False and commitment['attestation_is_independent_history_proof']is False,'global four-program commitment; author histories remain externally attested')
    for arm in ARMS:
        for purpose,cap in PROGRAMS.items():
            io.capture(root/'programs'/arm/(purpose+'.py'),commitment['programs'][arm][purpose],cap,retain=False)
            ar=read(io,root/'authorship'/arm/(purpose+'.json'),commitment['authorship'][arm][purpose])
            need(ar['program']==commitment['programs'][arm][purpose] and ar['arm']==arm and ar['purpose']==purpose,'all four original authoring records')
    return pin(raw)
