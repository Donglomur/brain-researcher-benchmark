"""Host-owned phase assembly, output/state seals and full-clock shift materialization.

No candidate can choose a source person, path, split, extra mount or model state.
All operations retain original enclosing clocks. APIs are future execution code;
source construction never calls them on authentic operands.
"""
from pathlib import Path
import os
import uuid
import time
import stat
from .common import capture, decode, encoded, need, pin, publish, stream_pin, npy_header, VIEWS, DecodingStream, npy_layout
from .packet import view_plan
from .transport import stage_view, file_mount, source_mounts
from .investigator import captured


def handles(fold, person):
    return {str(s):uuid.uuid4().hex for s in fold['final_training_people']+[person]}


def captured_tree(result, prefix, purpose='input'):
    receipt=result['receipt']; need(receipt['status']=='captured' and receipt['all_native_resources_closed'] is True,'Sealed model after producer retirement')
    root=Path(receipt['quarantine_root']);members=receipt['output_inventory']['files']
    files={k[len(prefix):]:v for k,v in members.items() if k.startswith(prefix)}
    need(files and all(k and not k.startswith('/') for k in files),'Nonempty complete subtree')
    # Output container UID must be able to read captured ordinary artifacts.
    # Chmod changes permission only, never content or declared membership.
    selected=root/prefix
    for path in selected.rglob('*'):
        need(not path.is_symlink(),'No model links')
        path.chmod(0o555 if path.is_dir() else 0o444)
    selected.chmod(0o555)
    return {'path':str(selected),'kind':'directory','purpose':purpose,'files':files},pin(encoded(files))


def view(rows,fold,person,name,role,binding,root,meter):
    return stage_view(view_plan(rows,fold,person,name,role,binding),root,meter)


def shift_plan(plan, root, meter, retained_limit):
    """Only current-person EEG arrays; clock/EOG and public IDs stay identical."""
    import numpy as np
    need(plan['role']=='infer' and plan['view'] in ('EC','EOC'),'Declared current-query inference shift')
    root=Path(root);need(not root.exists(),'Fresh shift realization');root.mkdir(mode=0o700)
    transformed=[]; retained=0; custody=[]
    epochs={n['directory']:n['epochs'] for n in plan['nights']}
    for i,item in enumerate(plan['members']):
        target=item['target'];artifact=item['artifact']
        if not target.endswith(('channel-0.npy','channel-1.npy')):
            transformed.append(item);continue
        e=epochs[str(Path(target).parent)];need(e>=2,'Full shift support')
        expected={k:artifact[k] for k in ('bytes','sha256')}
        header_bytes=expected['bytes']-e*3000*8
        need(10<=header_bytes<=4108,'Header offset derived from exact original extent and full sample support')
        size=e*3000*8+4096;need(retained+size<=retained_limit,'Prospective complete shifted-input retention');retained+=size
        meter.write(size); path=root/f'channel-{i}.npy'
        dest=np.lib.format.open_memmap(path,mode='w+',dtype='<f8',shape=(e*3000,));out=dest.reshape(e,3000);k=max(1,e//3)
        try:
            with DecodingStream(artifact['path'],expected,meter) as source:
                h=npy_layout(source.read(header_bytes),expected['bytes'])
                need(h['dtype']=='<f8' and h['shape']==[e*3000] and h['header_bytes']==header_bytes,'Exact authenticated consumed shift-header layout')
                for first in range(0,e,64):
                    stop=min(e,first+64);count=(stop-first)*3000
                    body=source.read(count*8);need(len(body)==count*8,'Complete consumed original shift input')
                    values=np.frombuffer(body,dtype='<f8').reshape(stop-first,3000)
                    need(np.isfinite(values).all(),'Finite authentic shift input')
                    indexes=(np.arange(first,stop)+k)%e;out[indexes]=values;meter.tick()
            dest.flush()
        finally:dest._mmap.close()
        with path.open('rb') as f:os.fsync(f.fileno())
        from .prepare import file_pin
        meter.read(path.stat().st_size+1);lock=file_pin(path,retained_limit);path.chmod(0o444)
        transformed.append({**item,'artifact':lock}); custody.append({'target':target,'original':expected,'transformed':{k:lock[k] for k in ('bytes','sha256')},'epochs':e,'offset_epochs':k})
    return {**plan,'members':transformed}, {'transform':'same_epoch_rotation_on_EEG_only_v1','members':custody,'retained_reserved_bytes':retained}


def admit_generated_state(seal, seal_pin, configuration, clock, required_after_seconds, meter):
    """Concrete bounded post-seal local operator intake, never a candidate tool.

    Precommitted reviewer policy and private filesystem custody identify the
    admitted input channel. They do not establish reviewer scientific competence.
    The request/response and receiver costs are retained; no deadline is renewed.
    """
    need(set(configuration)=={'policy_path','policy_pin','inbox','response_bytes','max_wait_seconds'},'Exact precommitted admission channel')
    policy=decode(capture(configuration['policy_path'],configuration['policy_pin'],meter=meter))
    need(policy['schema']=='neural007_generated_state_review_policy_v1' and policy['source']==seal['programme_source']
         and policy['reviewers'] and all(type(x) is str and x for x in policy['reviewers']), 'Pinned independent reviewer policy/source')
    inbox=Path(configuration['inbox']);need(inbox.is_absolute() and inbox.is_dir() and not any(p.is_symlink() for p in (inbox,*inbox.parents)), 'Ordinary operator-only inbox')
    st=inbox.stat();need(st.st_uid==os.getuid() and stat.S_IMODE(st.st_mode)==0o700,'Private inbox outside all candidate/provider mounts')
    need(type(configuration['response_bytes']) is int and 0<configuration['response_bytes']<=262144
         and type(configuration['max_wait_seconds']) is int and configuration['max_wait_seconds']>0,'Bounded selected response/wait allowance')
    started=meter.tick();end=min(started+configuration['max_wait_seconds'],clock['deadline']-required_after_seconds,clock['campaign_deadline'])
    need(started<end,'Full final fit/inference reserve remains; no scope reduction or deadline extension')
    directory=inbox/seal['context'];need(not directory.exists(),'One admission request, no implicit retry');directory.mkdir(mode=0o700)
    request={'schema':'neural007_generated_state_review_request_v1','context':seal['context'],'seal':seal_pin,'programme_source':seal['programme_source'],
             'source_bundle':seal['bundle'],'policy':configuration['policy_pin'],'clock':clock,'response_deadline':end}
    request_pin=publish(directory/'REQUEST.json',encoded(request),meter)
    response_path=directory/'RESPONSE.json'
    while not response_path.exists():
        need(time.monotonic()<end,'Post-seal review response deadline');meter.tick();time.sleep(min(.05,max(0,end-time.monotonic())))
    need(time.monotonic()<end,'Response admitted before original cutoff')
    body=capture(response_path,cap=configuration['response_bytes'],meter=meter);response=decode(body)
    expected={'schema','context','request','seal','programme_source','source_bundle','policy','reviewer','decision',
              'query_learned_state_excluded','fit_recomputes_from_training_only','reported_reviewer_cost'}
    need(set(response)==expected and response['schema']=='neural007_generated_state_review_response_v1','Exact bounded reviewer response')
    need(response['context']==seal['context'] and response['request']==request_pin and response['seal']==seal_pin
         and response['programme_source']==seal['programme_source'] and response['source_bundle']==seal['bundle']
         and response['policy']==configuration['policy_pin'] and response['reviewer'] in policy['reviewers'], 'Exact request/source/seal/reviewer-policy joins')
    captured=publish(directory/'CAPTURED_RESPONSE.json',body,meter)
    need(response['decision']=='approved' and response['query_learned_state_excluded'] is True
         and response['fit_recomputes_from_training_only'] is True,'Independent final-state content admission; refusal remains terminal')
    need(time.monotonic()<end,'Content capture inside original response deadline')
    result={'request':request_pin,'response':captured,'wait_and_capture_seconds':time.monotonic()-started,'clock':clock,
            'reported_reviewer_cost':response['reported_reviewer_cost'],'reviewer_competence_independently_qualified':False}
    publish(directory/'ADMISSION.json',encoded(result),meter);return result


def predictions(result, public_view, binding, person, meter, prefix='artifacts/'):
    value=decode(captured(result,prefix+'PREDICTIONS.json',meter))
    need(set(value)=={'schema','nights'} and value['schema']=='neural007_predictions_v1','Exact complete prediction declaration')
    wanted={(r['person'],r['night']):r for r in public_view['nights']}
    seen=set();rows=[];inventory=result['receipt']['output_inventory']['files'];root=Path(result['receipt']['quarantine_root'])
    for n in value['nights']:
        need(set(n)=={'person','night','epochs','path'},'Exact prediction member')
        key=(n['person'],n['night']);need(key in wanted and key not in seen,'No missing/foreign/duplicated current night');seen.add(key)
        need(n['epochs']==wanted[key]['epochs'],'All full-clock output rows')
        from .common import relative
        name=prefix+relative(n['path']);need(name in inventory,'Captured declared probabilities')
        rows.append({'night':int(n['night'].removeprefix('night-')),'epochs':n['epochs'],
                     'probabilities':{'path':str(root/name),**inventory[name]}})
    need(seen==set(wanted),'Every original current-person night predicted')
    return rows
