"""Isolated captured-source entry. No candidate import or operand before gates."""
import argparse,builtins,hashlib,json,os,stat,sys,time,types
from pathlib import Path

def bootstrap(size,digest):
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
    m=raw(manifest,size,digest);doc=json.loads(m)
    if set(doc)!={'schema','files','runtime_qualified'}or doc['schema']!='neural010-complete-runtime-source-v1'or doc['runtime_qualified']is not False:raise ValueError('source manifest')
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

def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--phase',required=True,choices=('fixed-authors','references','release','analysts','grade'));modes=parser.add_mutually_exclusive_group();modes.add_argument('--observe',action='store_true');modes.add_argument('--root-observe',action='store_true')
    for field in('source','request','authority'):
        if field!='source':parser.add_argument('--'+field,required=True)
        parser.add_argument('--'+field+'-bytes',type=int,required=True);parser.add_argument('--'+field+'-sha256',required=True)
    parser.add_argument('--origin',type=float,required=True);args=parser.parse_args(argv)
    root,bodies,source_files,load,bootstrap_bytes,source=bootstrap(args.source_bytes,args.source_sha256);c=load('common')
    # Only the separately protected metadata authority is opened to obtain the
    # preselected budget. It contains no candidate/data/credential body.
    descriptor={'path':args.authority,'bytes':args.authority_bytes,'sha256':args.authority_sha256};c.descriptor(descriptor)
    c.need(descriptor['bytes']<=1048576,'bounded protected authority metadata')
    p=c.absolute(descriptor['path']);c.need(not any(q.is_symlink()for q in(p,*p.parents)),'ordinary protected authority')
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        st=os.fstat(fd);c.need(stat.S_ISREG(st.st_mode)and st.st_nlink==1 and st.st_size==descriptor['bytes'],'bounded ordinary authority before read')
        with os.fdopen(fd,'rb',closefd=False)as stream:first=stream.read(descriptor['bytes']+1)
    finally:os.close(fd)
    c.need(c.pin(first)=={k:descriptor[k]for k in('bytes','sha256')},'exact protected authority bytes');authority=c.parse(first)
    budget=c.Budget(args.origin,authority['child_limits']);budget.charge('read_bytes',bootstrap_bytes+len(first)+1)
    reread=c.capture(descriptor,budget,[p.parent]);c.need(first==reread,'stable protected authority before operands')
    requestpin={'path':args.request,'bytes':args.request_bytes,'sha256':args.request_sha256};c.descriptor(requestpin)
    if args.root_observe:
        result=load('campaign').observe_selected(authority,source,source_files,requestpin,args.phase,budget)
    elif args.observe:
        result=load('phase_driver').observe(authority,source,source_files,requestpin,args.phase,budget,bodies)
    else:
        run=load('authority').admit(authority,source,args.phase,budget,source_files)
        c.need(c.typed_equal(authority['request'],requestpin),'request selected before capture')
        c.need(requestpin['bytes']<=run['request_caps'][args.phase],'preselected complete phase request extent')
        request=c.capture_json(requestpin,budget,[Path(requestpin['path']).parent]);load('authority').request_join(request,authority,requestpin,args.phase,budget)
        result=load('phase_driver').execute(request,requestpin,authority,run,budget,bodies,source_files)
    budget.check_clock();sys.stdout.buffer.write(c.encoded(result));sys.stdout.buffer.flush();budget.check_clock()

if __name__=='__main__':main()
