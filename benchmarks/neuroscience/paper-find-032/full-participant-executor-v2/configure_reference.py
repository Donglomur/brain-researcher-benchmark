"""Create-only ordinary metadata configuration; never launches/imports the study."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import time


def need(value,why):
    if not value:raise ValueError(why)


def capture(p,cap,deadline):
    p=Path(p)
    need(p.is_absolute() and not any(x.is_symlink() for x in (p,*p.parents)),'unlinked absolute metadata')
    before=p.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and 0<before.st_size<=cap,'ordinary bounded metadata')
    fd=None;parts=[];first=None;secondaries=[]
    ident=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    try:
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
        need(ident(before)==ident(os.fstat(fd)),'same opened metadata identity')
        left=before.st_size
        while left:
            need(time.monotonic()<deadline,'bounded metadata capture deadline')
            block=os.read(fd,min(65536,left));need(bool(block),'complete metadata body')
            parts.append(block);left-=len(block)
        need(ident(before)==ident(os.fstat(fd))==ident(p.lstat()),'stable exact metadata')
    except BaseException as error:first=error
    finally:
        if fd is not None:
            try:os.close(fd)
            except BaseException as error:
                secondaries.append(error)
                if first is None:first=error
    if first is not None:
        ORIGINALS.append((first,tuple(secondaries),parts));raise first
    return b''.join(parts)


ORIGINALS=[]


def load(raw):
    def pairs(rows):
        out={}
        for k,v in rows:
            need(k not in out,'duplicate configuration key');out[k]=v
        return out
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda n:(_ for _ in ()).throw(ValueError('nonfinite JSON')))


def write(root,name,value):
    b=(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    need(len(b)<=1048576,'bounded emitted metadata')
    fd=os.open(root/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        done=0
        while done<len(b):
            n=os.write(fd,b[done:]);need(0<n<=len(b)-done,'complete metadata write');done+=n
        os.fsync(fd);os.fchmod(fd,0o400)
    finally:os.close(fd)
    return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'mode':0o400}


def main():
    ap=argparse.ArgumentParser(allow_abbrev=False)
    ap.add_argument('--template',required=True);ap.add_argument('--package',required=True)
    ap.add_argument('--output',required=True);args=ap.parse_args()
    need(os.geteuid()==0,'selected root metadata owner')
    started=time.monotonic();deadline=started+30;root=Path(args.package);destination=Path(args.output)
    need(root.is_absolute() and destination.is_absolute(),'absolute source/output roots')
    template=load(capture(Path(args.template),1048576,deadline))
    need(type(template)is dict and set(template)=={'schema','request','offset_seconds'} and
         template['schema']=='FIND032_REFERENCE_CONFIGURATION_TEMPLATE_V1','closed configuration template')
    request=template['request'];offsets=template['offset_seconds']
    names=('work_end','child_end','cleanup_end','owner_end','final_end')
    need(set(offsets)==set(names) and all(type(offsets[k]) in (int,float) and offsets[k]>0 for k in names)
         and all(offsets[a]<offsets[b] for a,b in zip(names,names[1:])),'explicit ascending original time offsets')
    graph_raw=capture(root/'REFERENCE_SOURCE_GRAPH.json',1048576,deadline);graph=load(graph_raw)
    need(set(graph)=={'schema','files'} and graph['schema']=='find032_reference_source_graph_v1','exact source graph')
    rows=graph['files'];need(0<len(rows)<=256 and sum(r['bytes'] for r in rows.values())<=4194304,'finite complete source graph')
    for name,pin in rows.items():
        need(name.startswith(('find032/','find032_runtime/','find032_reference/')) and name.endswith('.py') and
             all(p not in ('','.','..') for p in name.split('/')) and '\\' not in name,'source-only member')
        b=capture(root/'source'/name,1048576,deadline)
        need(len(b)==pin['bytes'] and hashlib.sha256(b).hexdigest()==pin['sha256'] and
             stat.S_IMODE((root/'source'/name).lstat().st_mode)==pin['mode'],'exact complete source pin')
    need(time.monotonic()-started<30,'finite ordinary configuration preparation')
    # Clock starts once, after finite source preparation; no run or retry here.
    origin=time.monotonic();request['times']={'origin':origin,**{k:origin+offsets[k] for k in names}}
    need(not any(p.is_symlink() for p in (destination,*destination.parents)),'unlinked create-only configuration root')
    os.mkdir(destination,0o700)
    cache=destination/'bytecode-cache';os.mkdir(cache,0o550);os.chmod(cache,0o550)
    request_pin=write(destination,'REQUEST.json',request)
    manifest_pin=write(destination,'SOURCES.json',{'schema':'find032_reference_captured_sources_v1',
                       'root':str(root/'source'),'files':rows})
    argv=[request['python'],'-I','-S','-B','-X','pycache_prefix='+str(cache),
          str(root/'source/find032_reference/entry.py'),'--mode','run',
          '--request',str(destination/'REQUEST.json'),'--request-bytes',str(request_pin['bytes']),
          '--request-sha256',request_pin['sha256'],'--request-mode',str(request_pin['mode']),
          '--source-manifest',str(destination/'SOURCES.json'),'--source-manifest-bytes',str(manifest_pin['bytes']),
          '--source-manifest-sha256',manifest_pin['sha256'],'--original-endpoint',str(request['times']['final_end'])]
    invocation={'schema':'FIND032_REFERENCE_INVOCATION_V1','argv':argv,'cwd':str(root),
                'selected_python_pin':request['python_pin'],'source_graph_pin':{'bytes':len(graph_raw),'sha256':hashlib.sha256(graph_raw).hexdigest()},
                'request_pin':request_pin,'source_manifest_pin':manifest_pin,'deadline':request['times']['final_end'],
                'execution_selected':False,'output_is_private':True,'natural_zero_and_stream_closure_required':True}
    write(destination,'INVOCATION.json',invocation)
    fd=os.open(destination,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
    print(json.dumps({'configuration':str(destination),'files':['REQUEST.json','SOURCES.json','INVOCATION.json'],
                      'executed':False,'original_deadline':request['times']['final_end']},sort_keys=True))


if __name__=='__main__':raise SystemExit(main())
