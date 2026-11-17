"""All54 × four modes structural admission after natural worker closure; no gold."""
import os
MODES=('candidate','cca','constant','frequency-permuted')
def admitted_native(c,root,expected,source,kind,ordinal,read,tick):
    record=c.parse(c.capture(root/'NATIVE.json',262144,expected,tick,read))
    c.need(record['schema']=='neural084-native-phase-v1' and record['kind']==kind and type(record['ordinal'])is int and record['ordinal']==ordinal and record['source']==source and record['status']=='captured','exact native phase')
    for key in ('all_native_resources_closed','cli_reaped','producer_closed_before_capture'):c.need(record[key]is True,'complete native custody')
    c.need(record['private_scoring_called']is False and record['error_type']is None,'unscored phase')
    c.need(len(record['closures'])==3 and all(r['closed']is True for r in record['closures']) and sorted(r['kind'] for r in record['closures'])==['container','container','volume'],'exact owned resources closed')
    c.validate_natural_exit(record['natural_exit']);c.validate_cli_commands(record['command_metadata'],400000)
    return record

def admit(c,packet,unused,root,terminal,source,s,deadline,read):
    tick=lambda:c.before(deadline)
    c.need(type(terminal)is dict and terminal.get('schema')=='neural084-worker-result-v1' and terminal.get('status')=='complete_unqualified' and terminal.get('source')==source and type(terminal.get('query_count'))is int and terminal['query_count']==21600,'complete candidate21600 queries')
    c.need(not os.path.lexists(root/'FAILURE.json') and not os.path.lexists(root/'current'),'no failure or current view')
    done=c.parse(c.capture(root/'COMPLETE.json',packet.JSON_CAP,terminal['complete'],tick,read))
    c.need(done['schema']=='neural084-full54-complete-v1' and done['status']=='complete_unqualified' and done['source']==source and done['program']==c.only_pin(s['program']) and done['plan']==s['plan'] and done['public_manifest']==c.only_pin(s['public_manifest']) and done['preparation']==s['preparation'],'same complete source/program/input')
    for key in ('all_views_retired','source_packet_unchanged','all54_policy_fixed_before_exposure'):c.need(done[key]is True,'all54 custody')
    for key in ('private_targets_or_keys_opened','private_scoring_performed','scientific_qualified','runtime_qualified'):c.need(done[key]is False,'unscored unqualified')
    index=c.parse(c.capture(s['public_manifest']['path'],131072,c.only_pin(s['public_manifest']),tick,read))
    entries=index['folds'];c.need(index['schema']=='neural084-full54-input-index-v1' and len(entries)==54 and [x['person'] for x in entries]==list(range(1,55)),'all54 exact index')
    rows=done['folds'];c.need(type(rows)is list and len(rows)==54 and [r['person'] for r in rows]==list(range(1,55)),'all54 closures')
    submitted=c.parse(c.capture(root/'submission.json',262144,done['submission'],tick,read))
    c.need(type(submitted)is dict and set(submitted)=={'schema','input_index','modes','folds'} and submitted['schema']=='neural084-complete-prediction-files-v1' and submitted['input_index']==c.only_pin(s['public_manifest']) and submitted['modes']==list(MODES) and submitted['folds']==rows and done['submission']==terminal['submission'],'exact final four-mode index')
    expected_names={f'fold{p:03d}.json' for p in range(1,55)}
    for i,(entry,row) in enumerate(zip(entries,rows)):
        fold=c.parse(c.capture(c.path(entry['public_root'])/'fold.json',262144,entry['fold.json'],tick,read));ident=f'fold{i+1:03d}'
        c.need(fold['schema']=='neural084_fold_v1' and fold['generation']==index['generation'] and fold['fold']==ident and fold['classes']==[1,2,3,4] and len(fold['ids'])==400 and len(set(fold['ids']))==400,'original exact public fold')
        c.need(type(row['ordinal'])is int and row['ordinal']==i and row['fold']==ident and row['person']==i+1 and row['view_retired']is True and set(row['outputs'])==set(row['native'])==set(MODES),'complete case/mode closure')
        folder=root/'phases'/ident;c.need(c.parse(c.capture(folder/'CLOSED.json',32768,None,tick,read))==row,'durable exact fold closure')
        for kind in MODES:
            native=admitted_native(c,folder/kind,row['native'][kind],source,kind,i,read,tick);c.need(native['output']==row['outputs'][kind],'same raw output pin')
            raw=c.capture(folder/kind/'predictions.json',262144,row['outputs'][kind],tick,read);packet.prediction(raw,fold)
            c.need(c.capture(root/'predictions'/kind/(ident+'.json'),262144,row['outputs'][kind],tick,read)==raw,'same final raw bytes')
    for kind in MODES:
        files,dirs,_=c.inventory(root/'predictions'/kind,54*262144+1048576,60);c.need(set(files)==expected_names and len(dirs)==1,'exact all54 predictions for each scorer invocation')
    handoff=c.parse(c.capture(root/'GRADE_HANDOFF.json',32768,None,tick,read));c.need(handoff['execution_authorized']is False and handoff['private_gold_or_pool_opened']is False and handoff['all54_required_per_mode']is True,'separate grade only')
    tick();c.need(c.inventory(root,s['limits']['retained'],400200)[2]<=s['limits']['retained']-16384,'retained capacity plus outer slot')
    return done['submission'],terminal['complete']
