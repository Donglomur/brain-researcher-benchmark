"""One-shot independent host closure. Captures source before controller execution."""
import time
BOOT=time.monotonic()
import argparse,hashlib,json,os,selectors,signal,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

def observe(selection_path,expected_hash):
    raw,v,budget=authority(selection_path,expected_hash,BOOT,'outer_limits');work_end=BOOT+v['limits']['wall_seconds'];control=ordinary(v['outer_control']);need(not control.exists() and control.parent.is_dir(),'one-shot fresh independentoutercontrol');control.mkdir(mode=0o700)
    mraw=read(v['source_manifest']['path'],v['source_manifest'],budget,1048576);m=parse(mraw);need(m['schema']=='critical_init_program_source_v1' and m['task_id']==TASK and len(m['files'])<=128,'exact complete runtimecapture');snap=control/'source'
    for n,d in m['files'].items():
        need(not Path(n).is_absolute() and '..'not in Path(n).parts,'relative immutable source');body=read(ordinary(v['root_source'])/n,d,budget,16777216);write(snap/n,body,budget)
    write(snap/'SOURCE_MANIFEST.json',mraw,budget)
    for q in sorted(snap.rglob('*'),key=lambda q:len(q.parts),reverse=True):
        if q.is_dir():os.chmod(q,0o555)
    os.chmod(snap,0o555)
    derived={**v,'root_source':str(snap),'source_manifest':{'path':str(snap/'SOURCE_MANIFEST.json'),**descriptor(v['source_manifest'])}}
    dbody=encode(derived);dp=write(control/'DERIVED_SELECTION.json',dbody,budget);write(control/'DISPATCH.json',encode({'root_authority':{'path':str(selection_path),**pin(raw)},'derived_authority':dp,'only_delta':['root_source','source_manifest.path'],'original_origin':BOOT,'original_deadline':work_end,'outer_deadline':budget.end,'no_retry':True}),budget)
    command=[sys.executable,'-I','-B',str(snap/'controller.py'),'--selection',str(control/'DERIVED_SELECTION.json'),'--selection-sha256',dp['sha256'],'--origin',str(BOOT)];p=sel=None;buf={'out':bytearray(),'err':bytearray()};eof={'out':False,'err':False};natural=False;absent=False;code=None;error=None;collection=None;post=None
    try:
        p=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True,bufsize=0);write(control/'CHILD.json',encode({'pid':p.pid,'pgid':p.pid,'original_origin':BOOT,'spawn_to_persistence_gap_possible':True}),budget);sel=selectors.DefaultSelector()
        for k,f in [('out',p.stdout),('err',p.stderr)]:os.set_blocking(f.fileno(),False);sel.register(f,selectors.EVENT_READ,k)
        while sel.get_map():
            budget.tick()
            for key,_ in sel.select(min(.1,max(0,budget.end-time.monotonic()))):
                b=os.read(key.fileobj.fileno(),min(65536,1048577-len(buf[key.data])))
                if not b:eof[key.data]=True;sel.unregister(key.fileobj);continue
                budget.reading(len(b));buf[key.data].extend(b);need(len(buf[key.data])<=1048576,'bounded controllerterminal')
        code=p.wait(timeout=max(0,budget.end-time.monotonic()));need(code==0,'natural controllerexit0');natural=True
        try:os.killpg(p.pid,0)
        except ProcessLookupError:absent=True
        need(absent and not buf['err'],'closedownedcontrollergroup, silentstderr');returned=parse(bytes(buf['out']));collection=returned['collection'];post=returned['post_durability'];need(returned['original_deadline']==work_end and BOOT<post<work_end,'same originalcollection clock');body=read(ordinary(v['output'])/'COLLECTION.json',collection,budget,67108864);doc=parse(body);need(doc['source']==descriptor(v['source_manifest']) and doc['original_origin']==BOOT and doc['original_deadline']==work_end and doc['all261closed']is True,'bound complete source/clockcollection')
    except BaseException as exc:error={'type':type(exc).__name__,'message':str(exc)[:512]}
    finally:
        if p is not None and not absent:
            try:os.killpg(p.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            try:code=p.wait(timeout=max(0,min(1,budget.end-time.monotonic())))
            except BaseException:pass
        if sel is not None:sel.close()
        if p is not None:
            for f in (p.stdout,p.stderr):
                if f is not None:f.close()
    # A forced interruption cannot certify daemon-resource cleanup; preserve uncertainty.
    value={'schema':'critical_init_outer_observation_v1','source':descriptor(v['source_manifest']),'root_authority':pin(raw),'derived_authority':dp,'collection':collection,'natural_exit':natural and error is None,'exit_code':code,'owned_group_absent':absent,'streams_eof':all(eof.values()),'original_origin':BOOT,'original_deadline':work_end,'outer_deadline':budget.end,'collection_durable_before_deadline':post is not None and post<work_end,'collection_post_durability':post,'outer_before_final_persistence':time.monotonic(),'error':error,'forced_stop_daemon_resource_custody':'unknown' if error else 'all261recordedclosures','runtime_qualified':False,'scientific_qualified':False}
    # Final persistence after a late failure is retained as a failure record, not admitted success.
    if time.monotonic()<budget.end:rp=write(control/'OUTER.json',encode(value),budget)
    else:
        value['natural_exit']=False;value['collection_durable_before_deadline']=False;rp=None
    return {'observation':rp,'post_durability':time.monotonic(),'original_deadline':budget.end,'success':error is None and rp is not None,'independent_root_terminal_admission_still_required':True}

def main():
    p=argparse.ArgumentParser();p.add_argument('--selection',required=True);p.add_argument('--selection-sha256',required=True);a=p.parse_args();r=observe(a.selection,a.selection_sha256);print(json.dumps(r,sort_keys=True));raise SystemExit(0 if r['success'] else 2)
if __name__=='__main__':main()
