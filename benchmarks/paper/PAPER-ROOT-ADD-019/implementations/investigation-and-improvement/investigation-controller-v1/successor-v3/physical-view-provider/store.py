"""Exact ordinary-file staging; read-only modes do not constitute a sandbox."""
import os
import stat
from pathlib import Path
from wire import need, token, relative, integer, body_pin, check_pin, encode, Cleanup

NOFOLLOW=getattr(os,'O_NOFOLLOW',0)
DIRECTORY=getattr(os,'O_DIRECTORY',0)

def _ordinary(fd):
    s=os.fstat(fd);need(stat.S_ISREG(s.st_mode) and s.st_nlink==1,'single-link ordinary file');return s

def read_exact(path, expected, ledger, cap, *, dir_fd=None, cutoff='scientific'):
    check_pin(expected);need(expected['bytes']<=integer(cap,1),'declared read cap')
    ledger.reserve({'read_bytes':expected['bytes']+1},'exact file read',cutoff=cutoff)
    live=ledger.acquire_live(2*(expected['bytes']+1),'exact read internal copies',cutoff=cutoff)
    with Cleanup(ledger) as cleanup:
        cleanup.defer('release exact-read live reservation',lambda:ledger.release_live(live))
        fd=os.open(path,os.O_RDONLY|NOFOLLOW,dir_fd=dir_fd)
        cleanup.defer('close exact-read file',lambda:os.close(fd))
        before=_ordinary(fd);need(before.st_size==expected['bytes'],'declared exact extent')
        parts=[];left=expected['bytes']+1
        while left:
            block=os.read(fd,min(left,65536))
            if not block:break
            parts.append(block);left-=len(block)
        raw=b''.join(parts);after=_ordinary(fd)
        need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==
             (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),'source stable during read')
        need(body_pin(raw)==expected,'exact source pin');ledger.tick(cutoff);return raw

class FileStore:
    def __init__(self, root, ledger):
        self.root=Path(root);self.ledger=ledger;self.contexts={};self.stage_states={};self.closed=set()
        ledger.reserve({'write_bytes':4096,'retained_bytes':4096},'exclusive root metadata')
        self.root.mkdir(mode=0o700,parents=False,exist_ok=False)
        self.fd=os.open(self.root,os.O_RDONLY|DIRECTORY|NOFOLLOW)
        self.identity=os.fstat(self.fd)

    def _root_identity(self):
        current=os.stat(self.root,follow_symlinks=False)
        need(stat.S_ISDIR(current.st_mode) and (current.st_dev,current.st_ino)==
             (self.identity.st_dev,self.identity.st_ino),'owned root identity')

    def context_path(self, context):
        token(context);need(context in self.contexts,'owned staged context');self._root_identity()
        return self.root/context

    def stage(self, context, files):
        token(context);need(context not in self.contexts,'fresh context')
        need(type(files) is dict and files,'nonempty complete files')
        for name,raw in files.items():relative(name);need(type(raw) is bytes,'exact staged bytes')
        dirs={tuple(name.split('/')[:i]) for name in files for i in range(1,len(name.split('/')))}
        size=sum(len(b) for b in files.values());self.ledger.reserve(
            {'write_bytes':size+4096*(len(files)+len(dirs)+1),'retained_bytes':size+4096*(len(files)+len(dirs)+1),
             'read_bytes':size},'complete staging extent')
        self._root_identity();os.mkdir(context,0o700,dir_fd=self.fd)
        manifest={name:body_pin(raw) for name,raw in sorted(files.items())}
        self.contexts[context]=manifest;self.stage_states[context]={'status':'staging','completed_files':[]}
        state=self.stage_states[context]
        try:
            with Cleanup(self.ledger,state) as closing:
                directory=os.open(context,os.O_RDONLY|DIRECTORY|NOFOLLOW,dir_fd=self.fd)
                closing.defer('close staging context',lambda:os.close(directory))
                for name,raw in sorted(files.items()):
                    with Cleanup(self.ledger,state) as parents:
                        parts=name.split('/');parent=os.dup(directory)
                        owner=parents.defer('close staging parent',lambda fd=parent:os.close(fd))
                        for part in parts[:-1]:
                            try:os.mkdir(part,0o700,dir_fd=parent)
                            except FileExistsError:pass
                            child=os.open(part,os.O_RDONLY|DIRECTORY|NOFOLLOW,dir_fd=parent)
                            child_owner=parents.defer('close staging child',lambda fd=child:os.close(fd))
                            parents.close_now(owner);parent=child;owner=child_owner
                        with Cleanup(self.ledger,state) as writing:
                            fd=os.open(parts[-1],os.O_WRONLY|os.O_CREAT|os.O_EXCL|NOFOLLOW,0o400,dir_fd=parent)
                            writing.defer('close staged source',lambda:os.close(fd))
                            view=memoryview(raw)
                            while view:
                                n=os.write(fd,view);need(n>0,'complete write');view=view[n:]
                            os.fsync(fd)
                        os.fsync(parent)
                        state['completed_files'].append(name)
                os.fsync(directory);os.fsync(self.fd)
        except BaseException as error:
            state['status']='failed';state['failure_type']=type(error).__name__
            self.ledger.fail('partial source staging',error);raise
        state['status']='complete'
        self.ledger.tick();return manifest

    def seal(self, context, *, cutoff='scientific'):
        base=self.context_path(context);manifest=self.contexts[context]
        need(self.stage_states[context]['status']=='complete','all staged source writes complete')
        for name,expected in manifest.items():self._read_file(context,name,expected,cutoff=cutoff)
        self.closed.add(context)
        return {'context':context,'files':manifest,'readonly_source_modes':True,'physical_isolation_qualified':False}

    def read(self, context, name, offset, count, expected=None):
        relative(name);integer(offset);integer(count);need(context in self.closed,'closed immutable store context')
        manifest=self.contexts[context];need(name in manifest,'exact context file inventory')
        observed=manifest[name];need(expected is None or observed==expected,'selected exact file')
        need(offset<=observed['bytes'] and count<=observed['bytes']-offset+1,'bounded interval with one EOF sentinel')
        raw=self._read_file(context,name,observed)
        return raw[offset:offset+count]

    def _read_file(self, context, name, expected, *, cutoff='scientific'):
        self.context_path(context);relative(name)
        with Cleanup(self.ledger) as cleanup:
            parent=os.open(context,os.O_RDONLY|DIRECTORY|NOFOLLOW,dir_fd=self.fd)
            owner=cleanup.defer('close source parent',lambda fd=parent:os.close(fd))
            parts=name.split('/')
            for component in parts[:-1]:
                child=os.open(component,os.O_RDONLY|DIRECTORY|NOFOLLOW,dir_fd=parent)
                child_owner=cleanup.defer('close source child',lambda fd=child:os.close(fd))
                cleanup.close_now(owner);parent=child;owner=child_owner
            return read_exact(parts[-1],expected,self.ledger,max(expected['bytes'],1),dir_fd=parent,cutoff=cutoff)

    def close(self):os.close(self.fd)
