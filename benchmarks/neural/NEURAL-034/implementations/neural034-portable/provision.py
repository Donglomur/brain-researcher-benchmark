"""Create one operator-only NEURAL-034 workspace; no Docker, imports or execution."""
from pathlib import Path
import argparse,hashlib,json,os,stat,time

ROOT=Path(__file__).resolve().parent
MAX_SOURCE=1048576
MAX_INPUT=4371604
CURRENT_CHANGES={'check_result.py','provision.py','tests/test_relocation.py'}

def need(ok,message):
    if not ok:raise ValueError(message)

def decode(body):
    def unique(rows):
        result={}
        for k,v in rows:
            need(k not in result,'duplicate JSON key');result[k]=v
        return result
    return json.loads(body,object_pairs_hook=unique,parse_constant=lambda _:need(False,'nonfinite JSON'))

def plain(path):
    path=Path(path).absolute()
    need(Path(path).as_posix()==str(path)and '..'not in path.parts and not any(c in str(path)for c in ('\0','\r','\n',',')),'literal path')
    need(not any(p.is_symlink()for p in(path,*path.parents)),'no linked path or ancestor')
    return path

def relative(name):
    need(type(name)is str and name and not Path(name).is_absolute()and Path(name).as_posix()==name and '..'not in Path(name).parts,'canonical relative member')
    return name

def stable(path,expected,cap,destination=None,deadline=None):
    """One exact stream, hash and stable ordinary-file identity; partial stays on error."""
    path=plain(path);need(type(expected['bytes'])is int and 0<expected['bytes']<=cap,'admitted extent')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);out=None
    stamp=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_size,s.st_nlink,s.st_mtime_ns,s.st_ctime_ns)
    try:
        before=os.fstat(fd)
        need(stat.S_ISREG(before.st_mode)and before.st_nlink==1 and before.st_size==expected['bytes'],'exact ordinary input')
        if destination is not None:
            destination=plain(destination);destination.parent.mkdir(parents=True,exist_ok=True)
            out=os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o444)
        h=hashlib.sha256();remaining=expected['bytes']
        while remaining:
            need(deadline is None or time.monotonic()<deadline,'stream deadline')
            b=os.read(fd,min(65536,remaining));need(b,'truncated input');h.update(b);remaining-=len(b)
            if out is not None:
                view=memoryview(b)
                while view:
                    written=os.write(out,view);need(written>0,'short destination write');view=view[written:]
        need(not os.read(fd,1)and stamp(before)==stamp(os.fstat(fd))==stamp(path.lstat()),'input changed')
        need(h.hexdigest()==expected['sha256'],'input checksum')
        if out is not None:os.fsync(out)
    finally:
        if out is not None:os.close(out)
        os.close(fd)

def bounded_bytes(path,cap):
    path=plain(path);fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd);need(stat.S_ISREG(before.st_mode)and before.st_nlink==1 and 0<before.st_size<=cap,'bounded ordinary metadata')
        with os.fdopen(fd,'rb',closefd=False)as f:b=f.read(cap+1)
        after=os.fstat(fd);linked=path.lstat();keys=('st_dev','st_ino','st_mode','st_size','st_nlink','st_mtime_ns','st_ctime_ns')
        need(len(b)==before.st_size and all(getattr(before,k)==getattr(after,k)==getattr(linked,k)for k in keys),'stable metadata extent');return b
    finally:os.close(fd)

def bounded_json(path,cap):return decode(bounded_bytes(path,cap))

def selected_source(manifest,manifest_bytes,current_source_manifest,current_source_manifest_sha256):
    """Select an explicitly pinned successor without rewriting its predecessor."""
    need((current_source_manifest is None)==(current_source_manifest_sha256 is None),'current source descriptor and independent hash must be paired')
    if current_source_manifest is None:return manifest['files'],None
    body=bounded_bytes(current_source_manifest,65536)
    need(hashlib.sha256(body).hexdigest()==current_source_manifest_sha256,'explicit current source identity')
    current=decode(body)
    need(set(current)=={'schema','task_id','execution_authority','native_qualification','historical_manifest','changed_members','files'},'exact current source descriptor')
    need(current['schema']=='neural034-current-source/v1'and current['task_id']=='NEURAL-034'and current['execution_authority']is False and current['native_qualification']is False,'source-only current descriptor')
    need(current['historical_manifest']=={'path':'SOURCE_MANIFEST.json','bytes':len(manifest_bytes),'sha256':hashlib.sha256(manifest_bytes).hexdigest()},'current source binds historical manifest')
    files=current['files'];need(type(files)is dict and set(files)==set(manifest['files']),'same complete source member set')
    changed=sorted(name for name in files if files[name]!=manifest['files'][name])
    need(current['changed_members']==changed and changed and set(changed)<=CURRENT_CHANGES,'only reviewed inspection and provisioning changes')
    return files,body

def provision(source,workspace,inputs,deadline,manifest_sha256,current_source_manifest=None,current_source_manifest_sha256=None):
    source=plain(source);workspace=plain(workspace)
    need(not workspace.exists()and workspace.parent.is_dir()and source!=workspace and source not in workspace.parents and workspace not in source.parents,'fresh separate workspace')
    manifest_bytes=bounded_bytes(source/'SOURCE_MANIFEST.json',65536)
    need(hashlib.sha256(manifest_bytes).hexdigest()==manifest_sha256,'explicit release manifest identity')
    manifest=decode(manifest_bytes)
    need(manifest['task_id']=='NEURAL-034'and manifest['execution_authority']is False,'source-only task manifest')
    files=manifest['files'];need(type(files)is dict and 1<=len(files)<=64,'bounded complete source inventory')
    need('SOURCE_MANIFEST.json'not in files and 'INPUTS.json'in files,'nonrecursive complete source manifest')
    need('CURRENT_SOURCE_MANIFEST.json'not in files,'reserved current documentary copy')
    files,current_bytes=selected_source(manifest,manifest_bytes,current_source_manifest,current_source_manifest_sha256)
    for name,pin in files.items():
        relative(name);stable(source/name,pin,MAX_SOURCE,deadline=deadline)
    input_body=bounded_bytes(source/'INPUTS.json',16384)
    need(len(input_body)<=16384 and {'bytes':len(input_body),'sha256':hashlib.sha256(input_body).hexdigest()}==files['INPUTS.json'],'captured exact input descriptor')
    data=decode(input_body);rows=data['files']
    need(len(rows)==10 and [r['role']for r in rows]==[f'fold-{i:02d}'for i in range(7)]+['public_panel','private_targets','private_references'],'full external population')
    need(type(inputs)is dict and set(inputs)=={r['role']for r in rows},'exact ten input locators')
    # No original body was opened before complete source/descriptor admission.
    workspace.mkdir(mode=0o700)
    receipt={'task_id':'NEURAL-034','status':'partial','execution_authority':False,'runtime_qualified':False,'source':[],'inputs':[],'candidate_must_not_receive_workspace':True,
             'historical_manifest_sha256':manifest_sha256,'current_source_manifest_sha256':current_source_manifest_sha256}
    try:
        for name,pin in sorted(files.items()):
            need(time.monotonic()<deadline,'whole provisioning deadline')
            stable(source/name,pin,MAX_SOURCE,workspace/name,deadline);receipt['source'].append(name)
        # The manifest is a small documentary copy; its own external release pin
        # must be authenticated by the invoking operator before this tool.
        (workspace/'SOURCE_MANIFEST.json').write_bytes(manifest_bytes)
        if current_bytes is not None:(workspace/'CURRENT_SOURCE_MANIFEST.json').write_bytes(current_bytes)
        for row in rows:
            need(time.monotonic()<deadline,'whole provisioning deadline')
            relative(row['path']);stable(inputs[row['role']],row,MAX_INPUT,workspace/row['path'],deadline)
            receipt['inputs'].append({'role':row['role'],'path':row['path'],'bytes':row['bytes'],'sha256':row['sha256']})
        (workspace/'artifacts-build').mkdir(exist_ok=True)
        (workspace/'operator').mkdir(mode=0o700,exist_ok=True)
        (workspace/'candidates').mkdir(mode=0o700,exist_ok=True)
        (workspace/'.cache-build/docker-config').mkdir(mode=0o700,parents=True)
        (workspace/'.cache-build/docker-config/config.json').write_text('{}\n')
        need(time.monotonic()<deadline,'complete copies and setup before deadline')
        receipt['status']='inputs_copied_pending_receipt_and_terminal'
    except BaseException as exc:
        receipt['failure']=type(exc).__name__+': '+str(exc)[:300];raise
    finally:
        body=(json.dumps(receipt,indent=2,sort_keys=True)+'\n').encode()
        need(len(body)<=32768,'receipt cap')
        with (workspace/'PROVISION_RECEIPT.json').open('xb')as f:f.write(body)
    need(time.monotonic()<deadline,'receipt publication before terminal success')
    receipt['status']='complete_inputs_and_source_only'
    return receipt

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',required=True);p.add_argument('--inputs',required=True);p.add_argument('--manifest-sha256',required=True)
    p.add_argument('--current-source-manifest');p.add_argument('--current-source-manifest-sha256');a=p.parse_args()
    deadline=time.monotonic()+120
    result=provision(ROOT,a.workspace,bounded_json(a.inputs,16384),deadline,a.manifest_sha256,a.current_source_manifest,a.current_source_manifest_sha256)
    print(json.dumps({'status':result['status'],'files':len(result['inputs']),'execution_authority':False,'terminal_exit_still_required':True}),flush=True)
    need(time.monotonic()<deadline,'terminal acknowledgment before deadline')
if __name__=='__main__':main()
