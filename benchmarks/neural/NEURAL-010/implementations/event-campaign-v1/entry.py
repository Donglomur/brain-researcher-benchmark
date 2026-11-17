"""Isolated captured-source entry. No candidate import or operand before gates."""
import argparse,builtins,hashlib,json,os,stat,sys,time,types
from pathlib import Path

def bootstrap(size,digest):
    if type(size)is not int or not 0<size<=1048576:raise ValueError('bounded source manifest extent before capture')
    root=Path(__file__).absolute().parent;manifest=root/'SOURCE_MANIFEST.json'
    def raw(path,n,h):
        if type(n)is not int or n<=0 or n>16777216:raise ValueError('bounded source extent')
        if path.is_symlink()or any(p.is_symlink()for p in path.parents):raise ValueError('ordinary source path')
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            before=os.fstat(fd)
            if not stat.S_ISREG(before.st_mode)or before.st_nlink!=1 or before.st_size!=n:raise ValueError('ordinary exact source extent')
            with os.fdopen(fd,'rb',closefd=False)as stream:b=stream.read(n+1)
            after=os.fstat(fd);named=path.lstat()
            if any(getattr(before,k)!=getattr(after,k)or getattr(before,k)!=getattr(named,k)for k in('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns'))or len(b)!=n or hashlib.sha256(b).hexdigest()!=h:raise ValueError('changed exact source')
            return b
        finally:os.close(fd)
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('duplicate source manifest key')
            result[key]=value
        return result
    m=raw(manifest,size,digest);doc=json.loads(m,object_pairs_hook=pairs)
    if set(doc)!={'schema','files','runtime_qualified'}or doc['schema']!='neural010-event-campaign-source-v1'or doc['runtime_qualified']is not False:raise ValueError('source manifest')
    if type(doc['files'])is not list or not 1<=len(doc['files'])<=100:raise ValueError('bounded source closure')
    declared=set();total=0
    for row in doc['files']:
        if type(row)is not dict or set(row)!={'name','bytes','sha256'}:raise ValueError('source row before body capture')
        name=row['name'];n=row['bytes'];h=row['sha256']
        if type(name)is not str or name.startswith('/')or any(v in ('','.','..')for v in name.split('/'))or name in declared:raise ValueError('unique confined source name before capture')
        if type(n)is not int or not 0<n<=2097152 or type(h)is not str or len(h)!=64 or any(x not in '0123456789abcdef'for x in h):raise ValueError('typed source pin before body capture')
        declared.add(name);total+=n
    if total>2097152:raise ValueError('complete source byte bound')
    bodies={};descriptors=[];read=size+1
    for row in doc['files']:
        if type(row)is not dict or set(row)!={'name','bytes','sha256'}:raise ValueError('source row')
        name=row['name']
        if type(name)is not str or name.startswith('/')or any(v in('','.','..')for v in name.split('/'))or name in bodies:raise ValueError('unique confined source name')
        b=raw(root/name,row['bytes'],row['sha256']);bodies[name]=b;descriptors.append({'path':str(root/name),'bytes':len(b),'sha256':row['sha256']});read+=len(b)+1
    if 'entry.py'not in bodies or bodies['entry.py']!=raw(Path(__file__).absolute(),len(bodies['entry.py']),hashlib.sha256(bodies['entry.py']).hexdigest()):raise ValueError('actual entry identity')
    read+=len(bodies['entry.py'])+1;modules={};original=builtins.__import__
    def load(name):
        if name in modules:return modules[name]
        path=name.replace('.','/')+'.py';package=path not in bodies
        if package:
            if not any(p.startswith(name.replace('.','/')+'/')for p in bodies):raise ImportError(name)
            module=types.ModuleType(name);module.__package__=name;module.__path__=[];modules[name]=module;return module
        module=types.ModuleType(name);module.__package__=name.rpartition('.')[0];module.__file__=str(root/path);modules[name]=module
        def importer(n,g=None,l=None,fromlist=(),level=0):
            if level:
                parts=(g or{}).get('__package__','').split('.');base='.'.join(parts[:len(parts)-level+1]);n=base+('.'+n if n else'')
            if n.replace('.','/')+'.py'in bodies or any(p.startswith(n.replace('.','/')+'/')for p in bodies):
                item=load(n)
                if fromlist:
                    for child in fromlist:
                        if child!='*'and not hasattr(item,child)and(n+'.'+child).replace('.','/')+'.py'in bodies:setattr(item,child,load(n+'.'+child))
                    return item
                top=n.split('.')[0];parent=load(top)
                if '.'in n:setattr(parent,n.split('.',1)[1],item)
                return parent
            return original(n,g,l,fromlist,0)
        module.__dict__['__builtins__']={**vars(builtins),'__import__':importer};exec(compile(bodies[path],str(root/path),'exec'),module.__dict__);return module
    return root,bodies,descriptors,load,read,{'path':str(manifest),'bytes':size,'sha256':digest}

def preflight_capture(path,size,digest):
    p=Path(path)
    if p.name.casefold() in ('assessment.json','train.json','validation.json')or not p.is_absolute()or '..'in p.parts:
        raise ValueError('metadata role/path required before capture')
    if type(size)is not int or not 0<size<=1048576:raise ValueError('bounded selected metadata')
    if any(q.is_symlink()for q in [p,*p.parents]):raise ValueError('ordinary selected metadata')
    fd=os.open(p,os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW)
    try:
        a=os.fstat(fd)
        if not stat.S_ISREG(a.st_mode)or a.st_nlink!=1 or a.st_size!=size:raise ValueError('exact selected metadata extent')
        raw=os.read(fd,size+1);z=os.fstat(fd);named=p.lstat()
        if len(raw)!=size or hashlib.sha256(raw).hexdigest()!=digest or any(getattr(a,k)!=getattr(z,k)or getattr(a,k)!=getattr(named,k)for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')):
            raise ValueError('stable selected metadata bytes')
        return raw
    finally:os.close(fd)


def reserve_invocation(root,request_sha,source_sha,command,output):
    # Small external operator ledger survives source/authentication failures.
    # This is a resource reservation, not an authority/qualification service.
    import re
    if not re.fullmatch('[0-9a-f]{64}',request_sha)or not re.fullmatch('[0-9a-f]{64}',source_sha):raise ValueError('selected digests')
    root=Path(root)
    if not root.is_absolute()or '..'in root.parts or not root.is_dir()or any(x.is_symlink()for x in [root,*root.parents]):raise ValueError('preexisting independent operator ledger')
    body=(json.dumps({'schema':'neural010-event-invocation-reservation-v1','command':command,'request_sha256':request_sha,
        'source_sha256':source_sha,'output':output,'preflight_read_reserved_bytes':12582912,'preflight_write_reserved_bytes':16384,
        'charge_retained_on_failure':True},sort_keys=True)+'\n').encode()
    if len(body)>16384:raise ValueError('bounded reservation metadata')
    fd=os.open(root/(request_sha+'.json'),os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
    try:
        todo=memoryview(body)
        while todo:
            n=os.write(fd,todo)
            if n<=0:raise OSError('incomplete reservation')
            todo=todo[n:]
        os.fsync(fd)
    finally:os.close(fd)
    fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)


def main(argv=None):
    origin=time.monotonic()
    parser=argparse.ArgumentParser(description='NEURAL-010 held-person event campaign; external custody/participant services required')
    parser.add_argument('command',choices=('run','score'))
    for field in ('source','request','authority'):
        if field!='source':parser.add_argument('--'+field,required=True)
        parser.add_argument('--'+field+'-bytes',type=int,required=True)
        parser.add_argument('--'+field+'-sha256',required=True)
    parser.add_argument('--output',required=True);parser.add_argument('--reservation-root',required=True)
    parser.add_argument('--read-root',action='append',required=True)
    args=parser.parse_args(argv)
    reserve_invocation(args.reservation_root,args.request_sha256,args.source_sha256,args.command,args.output)
    # No raw error/path/traceback is sent to a participant or exposed on stdout.
    # Detailed retained artifacts are operator-private; failure is never a score.
    root,bodies,source_files,load,source_reads,located_source=bootstrap(args.source_bytes,args.source_sha256)
    u=load('common');source={k:located_source[k]for k in ('bytes','sha256')}
    raw=preflight_capture(args.request,args.request_bytes,args.request_sha256)
    authority=preflight_capture(args.authority,args.authority_bytes,args.authority_sha256)
    request=u.parse(raw);budget=u.Budget(request['limits']);budget.origin=origin;budget.end=origin+request['limits']['seconds']
    budget.charge('read_bytes',source_reads+len(raw)+len(authority)+2)
    io=u.IO([*args.read_root,str(root),args.output,args.reservation_root],budget)
    io.create(Path(args.reservation_root)/(args.request_sha256+'.whole.json'),u.encoded({'schema':'neural010-event-whole-reservation-v1',
        'request':u.pin(raw),'source':source,'limits':request['limits'],'origin_monotonic':origin,'deadline_monotonic':budget.end,
        'entire_allowance_retained_on_failure':True}))
    campaign=load('campaign')
    operation=campaign.run if args.command=='run'else campaign.score
    result=operation(raw,authority,{'bytes':args.authority_bytes,'sha256':args.authority_sha256},source_pin=source,
        source_root=root,output_root=args.output,io=io)
    sys.stdout.buffer.write(u.encoded({'status':'complete_source_operation','result':result,
        'source_or_runtime_qualified':False,'scientific_result_established':False}));sys.stdout.buffer.flush()


if __name__=='__main__':
    try:main()
    except Exception as error:
        sys.stderr.write(json.dumps({'status':'incomplete','error_type':type(error).__name__,
            'assessment_or_score_must_not_be_inferred':True,'external_custody_must_retire_active_contexts':True})+'\n')
        raise SystemExit(2)
