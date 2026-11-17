#!/usr/bin/env python3
"""Reviewed source commits on private refs; root-only, worktree-free integration.

There is deliberately no push command. Ref/index crash consistency uses a
journal; it is not a claim of an atomic multi-file filesystem transaction.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import selectors
import signal
import stat
import subprocess
import sys
import tempfile
import time
import uuid

MEMBER_KEYS=('files','members','author_files','owned_files','review_members','exact_files','paths','proposal_files','proposed_members','include','path_allowlist')
TEXT_SUFFIXES={'.py','.pyi','.r','.m','.sh','.bash','.zsh','.js','.mjs','.cjs','.ts','.tsx','.jsx','.c','.h','.cc','.cpp','.hpp','.rs','.go','.java','.jl','.sql','.md','.rst','.txt','.json','.jsonl','.ndjson','.yaml','.yml','.toml','.ini','.cfg','.conf','.in','.patch','.diff','.html','.css','.xml'}
DENIED_SUFFIXES={'.key','.pem','.p12','.pfx','.crt','.der','.npy','.npz','.nwb','.mat','.h5','.hdf5','.hdf','.bin','.raw','.dat','.pickle','.pkl','.pt','.pth','.ckpt','.safetensors','.fdt','.set','.edf','.bdf','.csv','.tsv','.parquet','.arrow','.feather','.db','.sqlite','.sqlite3','.mdb','.rds','.rdata','.zip','.tar','.gz','.bz2','.xz','.7z','.rar','.zst','.pdf','.png','.jpg','.jpeg','.gif','.tif','.tiff','.mp4','.wav','.flac','.dmg','.iso','.so','.dylib','.dll','.exe'}
DENIED_PARTS={'.git','.ssh','.aws','.azure','.gnupg','artifacts-build','private','secrets','credentials','raw','arrays','answers'}
DENIED_NAMES={'.env','.gitmodules','.gitattributes','id_rsa','id_ed25519','id_dsa','credentials','credentials.json','token.json','tokens.json','paper.txt','paper.pdf'}
STAMP=('st_dev','st_ino','st_mode','st_size','st_mtime_ns','st_ctime_ns')
ACTIVE=('MERGE_HEAD','CHERRY_PICK_HEAD','REVERT_HEAD','REBASE_HEAD','AUTO_MERGE','BISECT_LOG','rebase-merge','rebase-apply','sequencer')
JOURNAL='neuro-source-queue.transaction.json'

class Refusal(RuntimeError):pass
class RecoveryRequired(Refusal):pass

def need(ok,reason):
    if not ok:raise Refusal(reason)

def sha(raw):return hashlib.sha256(raw).hexdigest()
def canonical(value):return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def strict(raw):
    def pairs(items):
        out={}
        for key,value in items:
            need(key not in out,'duplicate_json_key');out[key]=value
        return out
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'nonfinite_json'))
def stamp(s):return tuple(getattr(s,k)for k in STAMP)
def owner(s):return (s.st_dev,s.st_ino)

def relative(value):
    need(type(value)is str and value and len(value)<=1024 and '\\'not in value and '\x00'not in value and
         all(ord(c)>=32 and ord(c)!=127 for c in value),'plain_relative_path')
    p=PurePosixPath(value)
    need(not p.is_absolute()and value==p.as_posix()and all(x not in ('','.','..')for x in value.split('/')),'canonical_relative_path')
    return p

def source_path(value):
    p=relative(value);parts=tuple(x.lower()for x in p.parts)
    need(not any(x in DENIED_PARTS or x.startswith('.env')for x in parts),'forbidden_source_directory_or_secret_name')
    need(p.name.lower()not in DENIED_NAMES,'forbidden_payload_name')
    suffixes={x.lower()for x in p.suffixes}
    need(not suffixes&DENIED_SUFFIXES,'forbidden_payload_extension_before_read')
    need(p.suffix.lower()in TEXT_SUFFIXES or p.name in ('LICENSE','NOTICE','LICENSE.author','NOTICE.author','Makefile','Dockerfile'),'unsupported_source_format_before_read')
    return p

def beneath(path,prefixes):
    return any(path==p or path.startswith(p+'/')for p in prefixes)

def no_links(root,path):
    current=root
    for item in relative(path).parts:
        current=current/item
        need(not current.is_symlink(),'symlink_path_refused')
    return current

def capture(root,path,expected,max_bytes):
    """After all metadata gates, exact stable ordinary-file capture."""
    p=no_links(root,path);fd=None
    try:
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
        before=os.fstat(fd)
        need(stat.S_ISREG(before.st_mode)and before.st_nlink==1 and 0<=before.st_size<=max_bytes,'ordinary_bounded_source_file')
        need(before.st_size==expected['bytes'],'source_extent_changed')
        out=bytearray()
        while len(out)<=before.st_size:
            block=os.read(fd,min(65536,before.st_size+1-len(out)))
            if not block:break
            out.extend(block)
        need(len(out)==before.st_size and stamp(before)==stamp(os.fstat(fd))==stamp(p.lstat()),'source_identity_changed')
    finally:
        if fd is not None:os.close(fd)
    raw=bytes(out);need(sha(raw)==expected['sha256'],'source_sha256_changed')
    return raw

def pin_record(row):
    need(type(row)is dict,'member_record')
    path=row.get('path',row.get('source'))
    need(not('path'in row and'source'in row and row['path']!=row['source']),'ambiguous_member_path')
    source_path(path)
    size=row.get('bytes');digest=row.get('sha256');mode=row.get('git_mode','100644')
    need(type(size)is int and size>=0 and type(digest)is str and re.fullmatch('[0-9a-f]{64}',digest),'typed_exact_source_pin')
    need(mode in ('100644','100755'),'regular_source_git_mode')
    return {'path':path,'bytes':size,'sha256':digest,'git_mode':mode}

def reviewed_manifest(repo,path,size,digest,prefixes,member_key=None,include_manifest=False,max_file=1048576,max_total=16777216):
    prefixes=tuple(str(relative(p))for p in prefixes)
    need(prefixes and all(p not in ('.git','.')for p in prefixes),'explicit_owned_prefix')
    source_path(path);need(Path(path).suffix.lower()=='.json','JSON_allowlist_required')
    expected=pin_record({'path':path,'bytes':size,'sha256':digest})
    raw=capture(repo.root,path,expected,2097152);doc=strict(raw)
    need(type(doc)is dict,'allowlist_object')
    candidates=[k for k in MEMBER_KEYS if k in doc and isinstance(doc[k],(list,dict))]
    if member_key is None:
        need(len(candidates)==1,'ambiguous_member_key_use_explicit_member_key');member_key=candidates[0]
    need(member_key in MEMBER_KEYS and member_key in doc,'supported_explicit_member_key')
    rows=doc[member_key]
    if type(rows)is dict:
        need(all(type(v)is dict and'path'not in v and'source'not in v for v in rows.values()),'mapping_member_schema')
        rows=[dict(v,path=k)for k,v in rows.items()]
    need(type(rows)is list and 0<len(rows)<=2048,'bounded_nonempty_member_list')
    records=[pin_record(row)for row in rows]
    if include_manifest:records.append(expected)
    by={}
    # Validate EVERY path/type/prefix/extent before opening ANY member body.
    for row in records:
        need(beneath(row['path'],prefixes),'member_outside_owned_prefix')
        need(row['bytes']<=max_file,'member_file_cap')
        if row['path']in by:need(by[row['path']]==row,'conflicting_duplicate_member')
        by[row['path']]=row
    need(sum(x['bytes']for x in by.values())<=max_total,'whole_source_payload_cap')
    return tuple(by[p]for p in sorted(by)),{'path':path,'bytes':size,'sha256':digest,'member_key':member_key},prefixes

class GitProcess:
    """Bounded pipe I/O, owned process session, finite cleanup for Git only."""
    def __init__(self,repo,args,index=None,cap=8388608,seconds=30):
        self.end=time.monotonic()+seconds;self.cap=cap;self.out=bytearray();self.err=bytearray();self.pending=memoryview(b'');self.close_input=False
        self.p=subprocess.Popen(repo.command(args),cwd=repo.root,env=repo.environment(index),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True,bufsize=0)
        self.sel=None
        try:
            self.sel=selectors.DefaultSelector()
            for stream,key in ((self.p.stdout,'out'),(self.p.stderr,'err')):
                os.set_blocking(stream.fileno(),False);self.sel.register(stream,selectors.EVENT_READ,key)
            os.set_blocking(self.p.stdin.fileno(),False)
        except BaseException as error:
            try:self.close()
            except BaseException as cleanup:error.add_note('owned Git setup cleanup: '+repr(cleanup))
            raise
    def send(self,data,close=False):
        need(not self.pending,'git_pending_input');self.pending=memoryview(data);self.close_input=close
        if data:self.sel.register(self.p.stdin,selectors.EVENT_WRITE,'in')
        elif close:self.p.stdin.close()
    def step(self):
        need(time.monotonic()<self.end,'git_deadline')
        for key,_ in self.sel.select(min(.05,max(0,self.end-time.monotonic()))):
            if key.data=='in':
                try:n=os.write(key.fileobj.fileno(),self.pending[:65536])
                except BlockingIOError:continue
                need(n>0,'git_short_pipe_write');self.pending=self.pending[n:]
                if not self.pending:
                    self.sel.unregister(key.fileobj)
                    if self.close_input:key.fileobj.close()
            else:
                try:raw=os.read(key.fileobj.fileno(),min(65536,self.cap+1-len(self.out)-len(self.err)))
                except BlockingIOError:continue
                if not raw:self.sel.unregister(key.fileobj);key.fileobj.close();continue
                getattr(self,key.data).extend(raw)
                need(len(self.out)+len(self.err)<=self.cap,'git_output_cap')
        if not self.sel.get_map()and self.p.poll()is None:time.sleep(.005)
    def line(self,expected):
        while b'\n'not in self.out:
            if self.p.poll()is not None and not self.sel.get_map():raise Refusal('git_transaction_refused')
            self.step()
        line,_,tail=self.out.partition(b'\n');self.out=bytearray(tail)
        need(line==expected,'git_transaction_acknowledgement')
    def finish(self):
        while self.sel.get_map()or self.p.poll()is None:self.step()
        rc=self.p.wait(timeout=max(.001,self.end-time.monotonic()))
        return rc,bytes(self.out),bytes(self.err)
    def close(self):
        errors=[]
        try:
            if self.p.poll()is None:
                try:os.killpg(self.p.pid,signal.SIGTERM)
                except ProcessLookupError:pass
                try:self.p.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    try:os.killpg(self.p.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    self.p.wait(timeout=1)
        except BaseException as error:errors.append(error)
        for resource in(self.sel,self.p.stdin,self.p.stdout,self.p.stderr):
            if resource is not None:
                try:resource.close()
                except BaseException as error:errors.append(error)
        if errors:
            for error in errors[1:]:errors[0].add_note('additional Git cleanup: '+repr(error))
            raise errors[0]

class Repo:
    def __init__(self,path):
        self.root=Path(path).absolute();need(self.root.is_dir(),'repository_directory')
        top=self.git(['rev-parse','--show-toplevel'],cap=8192).decode().strip()
        need(Path(top)==self.root,'exact_repository_root')
        self.gitdir=Path(self.git(['rev-parse','--absolute-git-dir'],cap=8192).decode().strip())
        self.index=Path(self.git(['rev-parse','--path-format=absolute','--git-path','index'],cap=8192).decode().strip())
        self.common=Path(self.git(['rev-parse','--path-format=absolute','--git-common-dir'],cap=8192).decode().strip())
        need(not self.gitdir.is_symlink()and self.index.parent==self.gitdir,'ordinary_worktree_gitdir')
        self.journal=self.gitdir/JOURNAL
    def environment(self,index=None):
        env={k:v for k,v in os.environ.items()if not k.startswith('GIT_')}
        env.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_SYSTEM=os.devnull,GIT_TERMINAL_PROMPT='0',GIT_OPTIONAL_LOCKS='0',GIT_NO_REPLACE_OBJECTS='1',GIT_LITERAL_PATHSPECS='1',LC_ALL='C')
        if index is not None:env['GIT_INDEX_FILE']=str(index)
        return env
    def command(self,args):
        return ['git','--no-pager','-c','core.hooksPath='+os.devnull,'-c','core.fsmonitor=false','-c','core.splitIndex=false','-c','core.untrackedCache=false','-c','commit.gpgsign=false','-c','core.autocrlf=false','-c','gc.auto=0','-c','maintenance.auto=false','-C',str(self.root),*args]
    def git(self,args,data=b'',index=None,cap=8388608,accepted=(0,)):
        p=GitProcess(self,args,index,cap)
        try:p.send(data,close=True);rc,out,err=p.finish()
        finally:p.close()
        need(rc in accepted,'git_'+args[0].replace('-','_')+'_refused_'+str(rc))
        return out
    def oid(self,value):
        need(type(value)is str and re.fullmatch('[0-9a-f]{40}|[0-9a-f]{64}',value),'full_object_id')
        return value
    def commit_oid(self,ref):
        need(type(ref)is str and ref and not ref.startswith('-')and '\x00'not in ref,'plain_revision')
        return self.oid(self.git(['rev-parse','--verify',ref+'^{commit}'],cap=256).decode().strip())
    def head_ref(self):return self.git(['symbolic-ref','--quiet','HEAD'],cap=1024).decode().strip()
    def tree(self,commit):return self.oid(self.git(['rev-parse',commit+'^{tree}'],cap=256).decode().strip())
    def entry(self,commit,path):
        raw=self.git(['ls-tree','-z',commit,'--',path],cap=2048)
        if not raw:return None
        fields=raw.rstrip(b'\0').split(b'\t');need(len(fields)==2 and fields[1].decode()==path,'exact_tree_path')
        mode,kind,oid=fields[0].decode().split();need(kind=='blob'and mode in('100644','100755'),'regular_source_blob_only')
        return mode,self.oid(oid)
    def blob(self,oid,size=None,cap=1048576):
        n=int(self.git(['cat-file','-s',oid],cap=128))
        need(0<=n<=cap and(size is None or n==size),'git_blob_extent_before_body_read')
        raw=self.git(['cat-file','blob',oid],cap=n+1);need(len(raw)==n,'exact_git_blob_length');return raw

def queue_ref(repo,value):
    need(re.fullmatch(r'refs/heads/agents/neuro/[A-Za-z0-9][A-Za-z0-9._/-]*',value or''),'scoped_agent_ref')
    repo.git(['check-ref-format',value],cap=1024);return value

def source_bytes(raw):
    need(b'\x00'not in raw,'binary_payload_refused')
    try:raw.decode('utf-8')
    except UnicodeDecodeError:raise Refusal('non_UTF8_source_refused')
    need(not re.search(rb'-----BEGIN (?:[A-Z ]*PRIVATE KEY|OPENSSH PRIVATE KEY)-----',raw),'private_key_content_refused')

def make_commit(repo,records,manifest,prefixes,ref,message,base=None):
    ref=queue_ref(repo,ref);base=repo.commit_oid(base or'HEAD')
    captured=[]
    for row in records:
        raw=capture(repo.root,row['path'],row,row['bytes']);source_bytes(raw);captured.append((row,raw))
    with tempfile.TemporaryDirectory(prefix='neuro-source-index-',dir=repo.gitdir)as temp:
        idx=Path(temp)/'index';repo.git(['read-tree',base],index=idx)
        lines=[]
        for row,raw in captured:
            oid=repo.oid(repo.git(['hash-object','-w','--stdin'],data=raw,cap=256).decode().strip())
            lines.append((row['git_mode']+' '+oid+'\t'+row['path']).encode()+b'\0')
        repo.git(['update-index','-z','--index-info'],data=b''.join(lines),index=idx,cap=1024)
        tree=repo.oid(repo.git(['write-tree'],index=idx,cap=256).decode().strip())
        need(tree!=repo.tree(base),'no_source_changes')
        oid=repo.oid(repo.git(['commit-tree',tree,'-p',base],data=(message+'\n').encode(),cap=256).decode().strip())
        repo.git(['update-ref','--create-reflog',ref,oid,'0'*len(oid)],cap=2048)
    return {'status':'queued','ref':ref,'commit':oid,'base':base,'tree':tree,'reviewed_manifest':manifest,'prefixes':prefixes,'members':len(records),'shared_HEAD_or_index_modified':False,'worktree_written':False,'pushed':False}

def verify_agent(repo,records,ref,expected,prefixes):
    ref=queue_ref(repo,ref);expected=repo.oid(expected)
    need(repo.commit_oid(ref)==expected,'reviewed_agent_tip_changed')
    parts=repo.git(['rev-list','--parents','-n','1',expected],cap=512).decode().split()
    need(len(parts)==2,'single_parent_source_commit_required');base=repo.oid(parts[1])
    raw=repo.git(['diff-tree','--no-commit-id','--name-status','-r','-z','--no-renames',base,expected],cap=4194304)
    parts=raw.split(b'\0');need(parts[-1]==b'','terminated_diff_records');parts.pop()
    need(len(parts)%2==0,'diff_record_pairs');allowed={r['path']:r for r in records};changed=[]
    # Reject all unreviewed/type/prefix changes before reading any Git blob body.
    for status,name in zip(parts[::2],parts[1::2]):
        path=name.decode('utf-8');source_path(path)
        need(status in(b'A',b'M')and path in allowed and beneath(path,prefixes),'agent_diff_outside_reviewed_source')
        changed.append(path)
    need(changed,'empty_agent_diff')
    for row in records:
        entry=repo.entry(expected,row['path']);need(entry is not None and entry[0]==row['git_mode'],'reviewed_blob_mode')
        raw=repo.blob(entry[1],row['bytes'],max(row['bytes'],1));need(sha(raw)==row['sha256'],'agent_blob_sha256_changed');source_bytes(raw)
    return base,tuple(changed)

def fsync_dir(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)

def atomic_file(path,raw,mode=0o600):
    tmp=path.with_name(path.name+'.queue-'+uuid.uuid4().hex)
    fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode)
    try:
        with os.fdopen(fd,'wb')as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        os.replace(tmp,path);fsync_dir(path.parent)
    finally:
        if tmp.exists():tmp.unlink()

def regular_bytes(path,cap=33554432,links=(1,)):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    try:
        before=os.fstat(fd)
        need(stat.S_ISREG(before.st_mode)and before.st_nlink in links and 0<=before.st_size<=cap,'bounded_regular_metadata')
        raw=bytearray()
        while len(raw)<=before.st_size:
            block=os.read(fd,min(65536,before.st_size+1-len(raw)))
            if not block:break
            raw.extend(block)
        need(len(raw)==before.st_size and stamp(before)==stamp(os.fstat(fd))==stamp(path.lstat()),'stable_metadata_file')
        return bytes(raw),stat.S_IMODE(before.st_mode)
    finally:os.close(fd)

def safe_index(repo):
    raw,mode=regular_bytes(repo.index)
    need(raw,'nonempty_shared_index')
    return raw,mode

def active_operations(repo,own_index=False):
    for name in ACTIVE:need(not(repo.gitdir/name).exists(),'active_git_operation')
    for p in(repo.gitdir/'HEAD.lock',repo.common/'packed-refs.lock'):
        need(not p.exists(),'active_git_lock')
    if not own_index:need(not repo.index.with_name('index.lock').exists(),'active_git_index_lock')

def file_owner(path):
    st=path.lstat();need(stat.S_ISREG(st.st_mode)and not stat.S_ISLNK(st.st_mode),'ordinary_owned_lock');return list(owner(st))

def owned_unlink(path,identity):
    if path.exists():need(file_owner(path)==identity,'lock_ownership_changed');path.unlink()

class RefTransaction:
    def __init__(self,repo,branch,old,new):
        self.repo=repo;self.p=GitProcess(repo,['update-ref','--stdin'],cap=8192);self.prepared=False;self.committed=False
        self.p.send(('start\nupdate '+branch+' '+new+' '+old+'\nprepare\n').encode())
        try:
            self.p.line(b'start: ok');self.p.line(b'prepare: ok');self.prepared=True
            # Current Git includes current-branch HEAD protection automatically.
            need((repo.gitdir/'HEAD.lock').is_file(),'Git_transaction_must_lock_current_HEAD')
        except BaseException:self.p.close();raise
    def commit(self):
        self.p.send(b'commit\n',close=True);self.p.line(b'commit: ok');self.committed=True
        rc,out,err=self.p.finish();need(rc==0 and not out,'git_commit_transaction_completion')
    def abort(self):
        if self.prepared and not self.committed and self.p.p.poll()is None:
            self.p.send(b'abort\n',close=True);self.p.line(b'abort: ok');self.p.finish()
    def close(self):self.p.close()

def journal_write(repo,state):atomic_file(repo.journal,canonical(state))

def publish_index(repo,new_index,index_lock,expected_owner,mode):
    """Replace index atomically WITHOUT releasing the Git index lock."""
    raw,_=regular_bytes(new_index)
    fd=os.open(index_lock,os.O_WRONLY|os.O_NOFOLLOW)
    try:
        need(list(owner(os.fstat(fd)))==expected_owner,'index_lock_ownership_changed_before_write')
        os.ftruncate(fd,0);os.fchmod(fd,mode)
        view=memoryview(raw)
        while view:
            n=os.write(fd,view);need(n>0,'short_index_write');view=view[n:]
        os.fsync(fd)
    finally:os.close(fd)
    link=repo.gitdir/('neuro-index-publish-'+uuid.uuid4().hex)
    try:os.link(index_lock,link);os.replace(link,repo.index);fsync_dir(repo.gitdir)
    finally:
        if link.exists():link.unlink()

def clean_temp(temp):
    if not temp.exists():return
    need(not temp.is_symlink(),'recovery_temp_not_linked')
    for p in temp.iterdir():
        need(p.name in('original-index','new-index','new-index.lock')and not p.is_dir(),'unexpected_transaction_temp_member')
        p.unlink()
    temp.rmdir()

def integrate(repo,records,manifest,prefixes,ref,expected,message,branch,root_integrator=False):
    need(root_integrator,'root_integrator_acknowledgement_required')
    need(re.fullmatch(r'refs/heads/build/[A-Za-z0-9._/-]+',branch or''),'explicit_build_branch')
    need(repo.head_ref()==branch,'current_build_branch_required');head=repo.commit_oid(branch)
    need(not repo.journal.exists(),'unfinished_queue_transaction_requires_recovery');active_operations(repo)
    base,changed=verify_agent(repo,records,ref,expected,prefixes)
    repo.git(['merge-base','--is-ancestor',base,head],cap=1024)
    for p in changed:
        for commit in(base,head):
            entry=repo.entry(commit,p)
            if entry is not None:need(int(repo.git(['cat-file','-s',entry[1]],cap=128))<=1048576,'merge_base_source_blob_cap')
    index_lock=repo.index.with_name('index.lock');lock_id=None;tx=None;state=None;temp=None;committed=False
    # Exclusive journal is the queue integrator lock; Git's own locks protect Git users.
    fd=os.open(repo.journal,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    os.close(fd)
    try:
        fd=os.open(index_lock,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600);os.close(fd);lock_id=file_owner(index_lock)
        active_operations(repo,own_index=True);need(repo.head_ref()==branch and repo.commit_oid(branch)==head,'build_HEAD_changed_before_index_snapshot')
        original,mode=safe_index(repo)
        temp=Path(tempfile.mkdtemp(prefix='neuro-source-integrate-',dir=repo.gitdir));saved=temp/'original-index';saved.write_bytes(original);os.chmod(saved,mode)
        idx=temp/'new-index';idx.write_bytes(original)
        need(repo.oid(repo.git(['write-tree'],index=idx,cap=256).decode().strip())==repo.tree(head),'staged_user_work_refused')
        patch=repo.git(['diff','--binary','--full-index','--no-ext-diff','--no-textconv','--no-renames',base,expected,'--'],cap=67108864)
        repo.git(['apply','--cached','--3way','--whitespace=nowarn','-'],data=patch,index=idx,cap=1048576)
        tree=repo.oid(repo.git(['write-tree'],index=idx,cap=256).decode().strip())
        new=repo.oid(repo.git(['commit-tree',tree,'-p',head,'-p',expected],data=(message+'\n').encode(),cap=256).decode().strip())
        state={'schema':'neuro_source_queue_transaction_v1','pid':os.getpid(),'branch':branch,'old':head,'new':new,'agent':expected,'temp':str(temp),'original_index_sha256':sha(original),'new_index_sha256':sha(idx.read_bytes()),'index_mode':mode,'index_lock_owner':lock_id,'phase':'prepared_files','git_pid':None,'git_lock_owners':{},'manifest':manifest}
        journal_write(repo,state)
        tx=RefTransaction(repo,branch,head,new)
        state['git_pid']=tx.p.p.pid
        for p in(repo.gitdir/'HEAD.lock',repo.common/(branch+'.lock')):
            if p.exists():state['git_lock_owners'][str(p)]=file_owner(p)
        state['phase']='ref_prepared';journal_write(repo,state)
        need(sha(repo.index.read_bytes())==state['original_index_sha256'],'shared_index_changed_despite_lock')
        state['phase']='publishing_index';journal_write(repo,state)
        publish_index(repo,idx,index_lock,lock_id,mode)
        state['phase']='index_published';journal_write(repo,state)
        tx.commit();committed=True
        state['phase']='committed';journal_write(repo,state)
    except BaseException:
        if tx is not None:
            try:tx.abort()
            except BaseException:pass
            finally:tx.close()
        current=repo.commit_oid(branch)
        # A lost post-commit acknowledgement is reconciled, never called rolled back.
        if state is not None and current==state['new']:
            committed=True
        elif state is not None and current==state['old']:
            try:atomic_file(repo.index,(temp/'original-index').read_bytes(),state['index_mode'])
            except BaseException:raise RecoveryRequired('index_restore_failed_journal_retained')
        elif state is not None and state['phase']not in('prepared_files','ref_prepared'):
            raise RecoveryRequired('branch_changed_after_publication_journal_retained')
        if not committed:
            if temp is not None:clean_temp(temp)
            if lock_id is not None:owned_unlink(index_lock,lock_id)
            repo.journal.unlink();fsync_dir(repo.gitdir)
            raise
    finally:
        if tx is not None:tx.close()
    need(committed,'integration_not_committed')
    # Once both ref and index are committed, cleanup failure is recoverable,
    # not a false claim that the merge failed atomically.
    try:
        clean_temp(temp)
        owned_unlink(index_lock,lock_id)
        repo.journal.unlink();fsync_dir(repo.gitdir)
        cleanup='complete'
    except BaseException:cleanup='journal_recovery_required'
    return {'status':'integrated','commit':state['new'],'parents':[head,expected],'branch':branch,'reviewed_manifest':manifest,'members':len(records),'worktree_written':False,'pushed':False,'cleanup':cleanup}

def recover(repo,root_integrator=False):
    need(root_integrator,'root_integrator_acknowledgement_required')
    raw,_=regular_bytes(repo.journal,65536);state=strict(raw)
    need(state.get('schema')=='neuro_source_queue_transaction_v1','complete_owned_journal_required')
    need(re.fullmatch(r'refs/heads/build/[A-Za-z0-9._/-]+',state['branch']),'owned_recovery_branch')
    repo.oid(state['old']);repo.oid(state['new'])
    for pid in(state['pid'],state['git_pid']):
        if pid is None:continue
        need(type(pid)is int and pid>1,'recorded_owner_pid')
        try:os.kill(pid,0)
        except ProcessLookupError:pass
        else:raise Refusal('journal_owner_process_still_exists')
    need(repo.head_ref()==state['branch'],'recovery_HEAD_changed')
    current=repo.commit_oid(state['branch']);need(current in(state['old'],state['new']),'recovery_ref_not_owned_old_or_new')
    temp=Path(state['temp']);need(temp.parent==repo.gitdir and temp.name.startswith('neuro-source-integrate-')and not temp.is_symlink(),'owned_recovery_directory')
    for name in ACTIVE:need(not(repo.gitdir/name).exists(),'active_git_operation_during_recovery')
    need(not(repo.common/'packed-refs.lock').exists(),'active_packed_refs_during_recovery')
    # Validate every still-present Git lock BEFORE any index restoration.
    expected_locks=state['git_lock_owners']
    for p in(repo.gitdir/'HEAD.lock',repo.common/(state['branch']+'.lock')):
        if p.exists():need(str(p)in expected_locks and file_owner(p)==expected_locks[str(p)],'unowned_Git_lock_during_recovery')
    index_lock=repo.index.with_name('index.lock');held=index_lock.exists();created=False
    if held:need(file_owner(index_lock)==state['index_lock_owner'],'recovery_owned_index_lock')
    else:
        fd=os.open(index_lock,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600);os.close(fd)
        state['index_lock_owner']=file_owner(index_lock);created=True
    try:
        index,_=regular_bytes(repo.index,links=(1,2));actual=sha(index)
        if current==state['old']:
            if actual!=state['original_index_sha256']:
                need(held and actual==state['new_index_sha256'],'recovery_will_not_overwrite_unowned_staged_work')
                original,_=regular_bytes(temp/'original-index')
                need(sha(original)==state['original_index_sha256'],'recovery_original_index_pin')
                atomic_file(repo.index,original,state['index_mode'])
        elif held:
            need(actual==state['new_index_sha256'],'committed_owned_index_changed')
        # With committed ref and already-released lock, later user staging is
        # left untouched; recovery only removes this transaction's metadata.
        for path,identity in expected_locks.items():
            p=Path(path);need(p in(repo.gitdir/'HEAD.lock',repo.common/(state['branch']+'.lock')),'owned_git_recovery_lock_path');owned_unlink(p,identity)
        clean_temp(temp);owned_unlink(index_lock,state['index_lock_owner']);repo.journal.unlink();fsync_dir(repo.gitdir)
    except BaseException:
        if created:owned_unlink(index_lock,state['index_lock_owner'])
        raise
    return {'status':'recovered_committed'if current==state['new']else'recovered_rolled_back','commit':current,'worktree_written':False,'pushed':False}

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--repo',required=True)
    sub=parser.add_subparsers(dest='action',required=True)
    for name in('commit','integrate'):
        p=sub.add_parser(name);p.add_argument('--allowlist',required=True);p.add_argument('--allowlist-bytes',required=True,type=int);p.add_argument('--allowlist-sha256',required=True);p.add_argument('--member-key');p.add_argument('--prefix',action='append',required=True);p.add_argument('--include-allowlist',action='store_true');p.add_argument('--ref',required=True);p.add_argument('--message',required=True)
        if name=='commit':p.add_argument('--base')
        else:p.add_argument('--expected-commit',required=True);p.add_argument('--branch',default='refs/heads/build/neuroscience-200');p.add_argument('--root-integrator',action='store_true')
    p=sub.add_parser('recover');p.add_argument('--root-integrator',action='store_true')
    args=parser.parse_args(argv);repo=Repo(args.repo)
    if args.action=='recover':result=recover(repo,args.root_integrator)
    else:
        records,manifest,prefixes=reviewed_manifest(repo,args.allowlist,args.allowlist_bytes,args.allowlist_sha256,args.prefix,args.member_key,args.include_allowlist)
        need(args.message and len(args.message.encode())<=8192 and '\x00'not in args.message,'bounded_commit_message')
        if args.action=='commit':result=make_commit(repo,records,manifest,prefixes,args.ref,args.message,args.base)
        else:result=integrate(repo,records,manifest,prefixes,args.ref,args.expected_commit,args.message,args.branch,args.root_integrator)
    print(json.dumps(result,sort_keys=True));return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'status':'refused','reason':str(error)if isinstance(error,Refusal)else type(error).__name__,'pushed':False}),file=sys.stderr)
        raise SystemExit(2)
