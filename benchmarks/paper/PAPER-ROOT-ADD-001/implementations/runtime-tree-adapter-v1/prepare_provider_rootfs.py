#!/usr/bin/env python3
"""One-image LANGUAGE provider rootfs projection. No extraction, install or execution.

The plan parser is bound to the retained host tarfile source. Linux apply reads
only authenticated byte ranges; it never invokes the tar parser. CLI execution
requires an externally selected finite profile; defaults are disabled.
"""
import argparse, hashlib, json, os, re, stat, sys, tarfile, time
from pathlib import Path

IMAGE = 'sha256:ab2bea4ced8dac37524a995444e928b80c4db04e9f5e7fddd26ea5dd3962781e'
INVENTORY = {'bytes':768588,'sha256':'ca8b7fc9d589fd3998fe81169d222597c73c3f2ba1addb4182b7763c4345f8b6'}
PYTHON = {'path':'usr/local/bin/python3.11','bytes':6168,'sha256':'9741b3a41b5a52cb1e3ef98902b8ed9fe4c8a608df791d965604394f646ccb15'}
TARFILE = {'bytes':106231,'sha256':'d6957647c11b6592e58e37d4e9f02f6cf9ee695cb0653b1072b542b8afac700d'}
LIMITS = {'archive_bytes':536870912,'member_bytes':134217728,'nodes':100000,
          'path_chars':1024,'alias_hops':64,'output_bytes':1073741824,
          'metadata_bytes':33554432,'audit_bytes':33554432,'plan_bytes':4194304,
          'manifest_bytes':4194304,'read_bytes':6442450944,
          'extension_each':65536,'extension_total':8388608}
SLOTS = ('input','candidate','artifacts','executor','tmp','proc','dev')
EMPTY = ('executor/entry.py','input/features.npy','input/request.json','input/responses.bin')
NORMAL = ('etc/hostname','etc/hosts','etc/resolv.conf','etc/mtab')
ZERO = hashlib.sha256(b'').hexdigest()
CHUNK = 65536

class Refusal(ValueError): pass

def need(ok, message):
    if not ok: raise Refusal(message)

def encoded(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()

def bounded_encoded(value,cap):
    result=bytearray()
    for piece in json.JSONEncoder(sort_keys=True,separators=(',',':'),allow_nan=False).iterencode(value):
        raw=piece.encode();need(len(result)+len(raw)+1<=cap,'serialized output cap before allocation')
        result.extend(raw)
    result.extend(b'\n');return bytes(result)

def pairs(items):
    result={}
    for key,value in items:
        need(key not in result,'duplicate JSON key');result[key]=value
    return result

def parse(raw):
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _: (_ for _ in ()).throw(Refusal('JSON constant')))

def digest(value): return type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None

def integer(value, minimum=0): return type(value) is int and value>=minimum

class Budget:
    def __init__(self, limits=None, seconds=540):
        self.limits=dict(LIMITS)
        if limits is not None:
            need(type(limits) is dict and set(limits)<=set(LIMITS),'known test limit keys')
            for key,value in limits.items():
                need(integer(value) and value<=LIMITS[key],'limits can only tighten');self.limits[key]=value
        self.deadline=time.monotonic()+seconds
        self.counters={'read_bytes':0,'written_bytes':0,'metadata_bytes':0,
                       'inner_tar_metadata_bytes_read':0,'inner_tar_boundary_probe_bytes_read':0}
    def check(self): need(time.monotonic()<self.deadline,'finite projection deadline')
    def read(self,n,metadata=False):
        self.check();need(integer(n) and self.counters['read_bytes']+n<=self.limits['read_bytes'],'explicit read stop before allocation')
        if metadata:need(self.counters['metadata_bytes']+n<=self.limits['metadata_bytes'],'metadata read stop before allocation')
        self.counters['read_bytes']+=n
        if metadata:self.counters['metadata_bytes']+=n
    def write(self,n):
        self.check();need(integer(n) and self.counters['written_bytes']+n<=1656750080,'aggregate projection write stop')
        self.counters['written_bytes']+=n

def stable(s): return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_nlink)

def parents(path):
    path=Path(path);need(path.is_absolute(),'absolute operation operand')
    for p in reversed(path.parents):need(stat.S_ISDIR(p.lstat().st_mode),'ordinary nonsymlink parent')
    return path

def open_regular(path, size=None):
    path=parents(path);fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    try:
        before=os.fstat(fd);need(stat.S_ISREG(before.st_mode) and before.st_nlink==1,'ordinary single-link input')
        if size is not None:need(before.st_size==size,'exact input size')
        return os.fdopen(fd,'rb',buffering=0),before
    except BaseException:os.close(fd);raise

def check_input(handle,path,before):
    need(stable(os.fstat(handle.fileno()))==stable(before)==stable(Path(path).lstat()),'stable input identity and extent')

def read_exact(handle,n,budget,metadata=False):
    need(integer(n) and n<=CHUNK,'bounded single input read');budget.read(n,metadata)
    raw=handle.read(n);need(len(raw)==n,'truncated input');return raw

def hash_range(handle,offset,size,budget):
    need(integer(offset) and integer(size),'range identity');handle.seek(offset);h=hashlib.sha256();left=size
    while left:
        raw=read_exact(handle,min(CHUNK,left),budget);h.update(raw);left-=len(raw)
    return h.hexdigest()

def bounded_json(path,pin,budget,cap):
    need(type(pin) is dict and integer(pin.get('bytes')) and pin['bytes']<=cap and digest(pin.get('sha256')),'bounded JSON descriptor')
    handle,before=open_regular(path,pin['bytes'])
    try:
        parts=[];left=pin['bytes']
        while left:
            raw=read_exact(handle,min(CHUNK,left),budget,True);parts.append(raw);left-=len(raw)
        data=b''.join(parts);need(hashlib.sha256(data).hexdigest()==pin['sha256'],'JSON digest');check_input(handle,path,before)
        return parse(data)
    finally:handle.close()

def canonical(name,limit=1024,root=False):
    need(type(name) is str and len(name)<=limit and not any(ord(c)<32 or ord(c)==127 for c in name),'bounded path characters')
    need('\\' not in name and not name.startswith('/'),'relative archive path')
    while name.startswith('./'):name=name[2:]
    name=name.rstrip('/')
    if name in ('','.'):need(root,'root only directory');return ''
    need(all(x not in ('','.','..') for x in name.split('/')),'canonical components')
    return name

def reserved(path): return path.split('/',1)[0] in SLOTS

def link_target(source,target,hard=False):
    need(type(target) is str and 0<len(target)<=1024 and '\\' not in target and not any(ord(c)<32 or ord(c)==127 for c in target),'bounded link target')
    # Keep '..' until traversal has resolved preceding symlinks. Lexically
    # collapsing it here would change a/../f when a itself is a directory link.
    pieces=[] if hard or target.startswith('/') else source.split('/')[:-1]
    pieces.extend(part for part in target.split('/') if part not in ('','.'))
    return '/'.join(pieces)

def qualify_tarfile(budget):
    need(sys.version_info[:3]==(3,11,6),'pinned host parser Python3.11.6')
    path=Path(tarfile.__file__);handle,before=open_regular(path,TARFILE['bytes'])
    try:
        need(hash_range(handle,0,TARFILE['bytes'],budget)==TARFILE['sha256'],'pinned tarfile source');check_input(handle,path,before)
    finally:handle.close()


class Census:
    def __init__(self, owner):
        self.owner = owner
        self.raw_headers = self.members = self.extension_bytes = self.regular_bytes = 0
        self.links = self.xattrs = self.whiteouts = self.directories = 0
        self.depth = 0
        self.pax_keys, self.pax_records = set(), 0
        self.type_counts = {}

    def raw(self, info, tf):
        self.owner.check()
        self.raw_headers += 1
        if self.raw_headers > self.owner.limits['nodes']:
            raise Refusal('inner_tar_raw_entry_cap')
        if type(info.size) is not int or info.size < 0:
            raise Refusal('inner_tar_negative_size')
        extensions = (tarfile.GNUTYPE_LONGNAME, tarfile.GNUTYPE_LONGLINK,
                      tarfile.XHDTYPE, tarfile.XGLTYPE, tarfile.SOLARIS_XHDTYPE)
        allowed = (tarfile.REGTYPE, tarfile.AREGTYPE, tarfile.DIRTYPE,
                   tarfile.SYMTYPE, tarfile.LNKTYPE)
        if info.type in extensions:
            if info.size > self.owner.limits['extension_each'] or self.extension_bytes + info.size > self.owner.limits['extension_total']:
                raise Refusal('inner_tar_extension_cap')
            self.extension_bytes += info.size
            if info.type in (tarfile.XHDTYPE, tarfile.XGLTYPE, tarfile.SOLARIS_XHDTYPE):
                start = tf.fileobj.tell()
                data = tf.fileobj.read((info.size + 511) // 512 * 512)
                if len(data) != (info.size + 511) // 512 * 512:
                    raise Refusal('inner_tar_extension_truncated')
                if any(data[info.size:]):
                    raise Refusal('inner_tar_nonzero_pax_padding')
                self.pax(data[:info.size])
                # Replay the same bounded inspected bytes to the stdlib hook;
                # no second physical metadata read and no reinterpretation.
                tf.fileobj.cache = (start, data)
                tf.fileobj.seek(start)
        elif info.type not in allowed:
            # Includes all sparse, device, FIFO and unknown raw type codes.
            raise Refusal('inner_tar_unsupported_or_sparse_type')
        elif info.type in (tarfile.REGTYPE, tarfile.AREGTYPE):
            if info.size > self.owner.limits['member_bytes'] or self.regular_bytes + info.size > self.owner.limits['output_bytes']:
                raise Refusal('inner_tar_regular_logical_size_cap')
            self.regular_bytes += info.size
        elif info.size != 0:
            raise Refusal('inner_tar_nonregular_data_size')

    def pax(self, body):
        offset, records = 0, 0
        while offset < len(body):
            self.owner.check()
            space = body.find(b' ', offset, min(len(body), offset + 8))
            if space < 0 or not re.fullmatch(rb'[1-9][0-9]{0,5}', body[offset:space]):
                raise Refusal('inner_tar_pax_record_length')
            count = int(body[offset:space])
            end = offset + count
            if end > len(body) or end <= space + 3 or body[end - 1:end] != b'\n':
                raise Refusal('inner_tar_pax_record_bounds')
            field = body[space + 1:end - 1]
            key, equals, value = field.partition(b'=')
            if not equals or not re.fullmatch(rb'[A-Za-z0-9_.-]{1,4096}', key):
                raise Refusal('inner_tar_pax_key')
            records += 1
            self.pax_records += 1
            self.pax_keys.add(key)
            # The stdlib's preliminary hdrcharset search may add this key
            # independently of the formal record loop; reserve its map slot.
            if records > 1024 or len(self.pax_keys | {b'hdrcharset'}) > 4096:
                raise Refusal('inner_tar_pax_record_or_key_cap')
            low = key.lower()
            if low == b'size' or b'sparse' in low or low.endswith(b'realsize') or low == b'schily.filetype':
                raise Refusal('inner_tar_size_changing_or_sparse_pax')
            if low in (b'path', b'linkpath') and len(value) > 4096:
                raise Refusal('inner_tar_pax_name_cap')
            if low.startswith((b'schily.xattr.', b'libarchive.xattr.')):
                self.xattrs += 1
            offset = end

    def member(self, item):
        self.owner.check()
        self.members += 1
        if self.members > self.owner.limits['nodes'] or item.sparse is not None:
            raise Refusal('inner_tar_member_or_sparse_cap')
        for value in (item.name, item.linkname):
            if len(value.encode('utf-8', 'surrogateescape')) > 4096:
                raise Refusal('inner_tar_name_or_link_cap')
        if item.type not in (tarfile.REGTYPE, tarfile.AREGTYPE, tarfile.DIRTYPE, tarfile.SYMTYPE, tarfile.LNKTYPE):
            raise Refusal('inner_tar_effective_type')
        if item.type in (tarfile.SYMTYPE, tarfile.LNKTYPE):
            self.links += 1
        if item.type == tarfile.DIRTYPE:
            self.directories += 1
        if item.name.rsplit('/', 1)[-1].startswith('.wh.'):
            self.whiteouts += 1
        key = item.type.hex()
        self.type_counts[key] = self.type_counts.get(key, 0) + 1

    def snapshot(self):
        return {'raw_headers_including_extensions': self.raw_headers, 'emitted_members': self.members,
                'metadata_extension_declared_bytes': self.extension_bytes,
                'declared_regular_logical_bytes': self.regular_bytes, 'links': self.links,
                'xattr_definitions': self.xattrs, 'whiteout_name_entries': self.whiteouts,
                'directories': self.directories, 'pax_records': self.pax_records,
                'distinct_pax_keys': len(self.pax_keys), 'raw_type_hex_counts': dict(self.type_counts)}

class GuardedTarInfo(tarfile.TarInfo):
    def _proc_member(self, tf):
        census = tf.fileobj.census
        census.raw(self, tf)
        census.depth += 1
        try:
            if census.depth > 64:
                raise Refusal('inner_tar_extension_recursion_cap')
            return super()._proc_member(tf)
        finally:
            census.depth -= 1


class ExportWindow:
    """Bounded metadata view with one validated PAX replay, no payload extraction."""
    def __init__(self,handle,size,budget,census):
        self.handle,self.size,self.budget,self.census=handle,size,budget,census
        self.position,self.cache=0,None
    def tell(self):return self.position
    def seek(self,offset,whence=os.SEEK_SET):
        self.budget.check();position=offset if whence==os.SEEK_SET else (self.position+offset if whence==os.SEEK_CUR else self.size+offset if whence==os.SEEK_END else -1)
        need(integer(position) and position<=self.size,'metadata seek within exact export');self.position=position;return position
    def read(self,n):
        need(integer(n) and n<=CHUNK,'bounded tar metadata read');n=min(n,self.size-self.position)
        if self.cache is not None:
            start,data=self.cache
            if start<=self.position and self.position+n<=start+len(data):
                raw=data[self.position-start:self.position-start+n];self.position+=len(raw)
                if self.position==start+len(data):self.cache=None
                return raw
            self.cache=None
        self.handle.seek(self.position);raw=read_exact(self.handle,n,self.budget,True);self.position+=n
        self.budget.counters['inner_tar_metadata_bytes_read']+=n
        if n==1:self.budget.counters['inner_tar_boundary_probe_bytes_read']+=1
        return raw

def scan_export(handle,archive_size,budget):
    need(integer(archive_size,1024) and archive_size%512==0 and archive_size<=budget.limits['archive_bytes'],'complete bounded tar extent')
    qualify_tarfile(budget);census=Census(budget);view=ExportWindow(handle,archive_size,budget,census)
    roster=[];names=set();folded=set();roster_bytes=0
    with tarfile.open(fileobj=view,mode='r:',tarinfo=GuardedTarInfo,encoding='utf-8',errors='strict',ignore_zeros=False) as tf:
        while True:
            budget.check();expected=tf.offset;item=tf.next()
            if item is None:
                need(expected%512==0 and archive_size-expected>=1024,'two zero end blocks')
                view.seek(expected)
                while view.tell()<archive_size:need(not any(view.read(min(CHUNK,archive_size-view.tell()))),'nonzero or malformed trailing tar')
                break
            census.member(item);tf.members.clear()
            kind='file' if item.isreg() else 'dir' if item.isdir() else 'symlink' if item.issym() else 'hardlink' if item.islnk() else None
            need(kind is not None,'supported effective tar type')
            name=canonical(item.name,budget.limits['path_chars'],kind=='dir')
            need(name not in names and name.casefold() not in folded,'duplicate or case-colliding archive path')
            need(not any(part.startswith('.wh.') for part in name.split('/')),'merged export cannot contain whiteouts')
            names.add(name);folded.add(name.casefold())
            need(integer(item.offset_data) and item.offset_data%512==0 and item.offset_data+item.size<=archive_size,'regular byte range inside export')
            sha=hash_range(handle,item.offset_data,item.size,budget) if kind=='file' else ''
            row={'path':name,'type':kind,'mode':item.mode,'bytes':item.size,'link':item.linkname,'offset':item.offset_data,'sha256':sha,'raw_name':item.name}
            size=len(encoded(row));need(roster_bytes+size<=budget.limits['audit_bytes'],'raw roster audit cap before retention');roster_bytes+=size;roster.append(row)
    return roster

def project_roster(roster,required_files,budget):
    need(type(roster) is list and len(roster)<=budget.limits['nodes'],'bounded complete raw roster')
    nodes={};folded={};audit=[];audit_size=0;plan_size=1024
    def note(row):
        nonlocal audit_size
        n=len(encoded(row));need(audit_size+n<=budget.limits['audit_bytes'],'projection audit cap before retention');audit_size+=n;audit.append(row)
    for row in roster:
        budget.check();need(type(row) is dict and set(row)=={'path','type','mode','bytes','link','offset','sha256','raw_name'},'exact roster schema')
        path=canonical(row['path'],budget.limits['path_chars'],row['type']=='dir');need(path==row['path'],'canonical roster identity')
        need(path not in nodes and path.casefold() not in folded,'duplicate/case-colliding roster')
        need(row['type'] in ('file','dir','symlink','hardlink') and integer(row['mode']) and integer(row['bytes']) and row['bytes']<=budget.limits['member_bytes'] and integer(row['offset']),'typed bounded roster member')
        need((row['type']=='file' and digest(row['sha256'])) or (row['type']!='file' and row['bytes']==0 and row['sha256']==''),'file hash or empty nonregular')
        need(type(row['link']) is str and len(row['link'])<=budget.limits['path_chars'] and type(row['raw_name']) is str and len(row['raw_name'])<=budget.limits['path_chars'],'bounded raw path/link metadata')
        need(not any(x.startswith('.wh.') for x in path.split('/')),'merged input whiteout refusal')
        nodes[path]=dict(row);folded[path.casefold()]=path
    if '' not in nodes:
        need(len(nodes)<budget.limits['nodes'],'implicit root node cap');nodes['']={'path':'','type':'dir','mode':0o755,'bytes':0,'link':'','offset':0,'sha256':'','raw_name':''}
    for path in list(nodes):
        parts=path.split('/')
        for i in range(1,len(parts)):
            parent='/'.join(parts[:i])
            if parent in nodes:need(nodes[parent]['type']=='dir','ordinary directory ancestor')
            else:
                need(len(nodes)<budget.limits['nodes'] and parent.casefold() not in folded,'implicit parent cap/collision')
                nodes[parent]={'path':parent,'type':'dir','mode':0o755,'bytes':0,'link':'','offset':0,'sha256':'','raw_name':''};folded[parent.casefold()]=parent
                note({'action':'implicit-directory','path':parent})
    children={p:[] for p,r in nodes.items() if r['type']=='dir'}
    for p in nodes:
        if p:children[p.rpartition('/')[0]].append(p)
    for values in children.values():values.sort()
    def resolve(path):
        chain=[];seen=set()
        def follow(components):
            stack=[];position=0
            while position<len(components):
                budget.check();part=components[position];position+=1
                if part in ('','.'):continue
                if part=='..':
                    need(bool(stack),'alias escapes virtual image');stack.pop();continue
                prefix='/'.join(stack+[part]);need(prefix in nodes,'dangling alias target');row=nodes[prefix]
                if chain:need(not reserved(prefix) and prefix not in NORMAL,'alias enters replaced/dynamic identity domain')
                if row['type'] in ('symlink','hardlink'):
                    state=(prefix,tuple(components[position:]));need(state not in seen,'alias cycle');seen.add(state)
                    need(len(chain)<budget.limits['alias_hops'],'finite alias hops');chain.append(prefix)
                    target=link_target(prefix,row['link'],row['type']=='hardlink')
                    rest=components[position:]
                    need(len(target)+sum(len(x)+1 for x in rest)<=budget.limits['path_chars'],'resolved alias path cap')
                    if row['type']=='hardlink':
                        terminal=follow(target.split('/'));need(nodes[terminal]['type']=='file' and not rest,'hardlink terminal is regular, never an ancestor');return terminal
                    return follow(target.split('/')+rest)
                need(position==len(components) or row['type']=='dir','non-directory alias ancestor')
                stack.append(part)
            terminal='/'.join(stack);need(terminal in nodes,'existing alias terminal');return terminal
        return follow(path.split('/')),chain
    dirs=set();files={};output_folded={};total=0
    def admit(path):
        nonlocal plan_size
        canonical(path,budget.limits['path_chars']);need(path not in dirs and path not in files and path.casefold() not in output_folded,'projection path collision')
        need(len(dirs)+len(files)<budget.limits['nodes'],'expanded node cap before insertion');output_folded[path.casefold()]=path
        plan_size+=len(path.encode())+8;need(plan_size<=budget.limits['plan_bytes'],'plan path budget')
    def adddir(path):
        if not path:return
        if path in dirs:return
        parent=path.rpartition('/')[0]
        if parent:adddir(parent)
        admit(path);dirs.add(path)
    def addfile(path,row,source,chain):
        nonlocal total,plan_size
        parent=path.rpartition('/')[0]
        if parent:adddir(parent)
        need(total+row['bytes']<=budget.limits['output_bytes'],'expanded content cap before insertion')
        out={'path':path,'bytes':row['bytes'],'sha256':row['sha256'],'mode':0o555 if row['mode']&0o111 else 0o444,'offset':row['offset'],'source':source,'hops':len(chain),'chain_sha256':hashlib.sha256(encoded(chain)).hexdigest()}
        n=len(encoded(out));need(plan_size+n<=budget.limits['plan_bytes'],'plan row budget before insertion');admit(path);plan_size+=n;total+=row['bytes'];files[path]=out
    def walk(source,dest,ancestry,inherited=()):
        budget.check()
        if reserved(dest):note({'action':'reserved-omit','source':source,'path':dest});return
        if dest in NORMAL:note({'action':'host-normalize','source':source,'path':dest,'prior':nodes[source]});return
        terminal,local_chain=resolve(source);chain=list(inherited)+local_chain
        need(len(chain)<=budget.limits['alias_hops'],'expanded alias ancestry hop cap');row=nodes[terminal]
        need(terminal not in ancestry,'directory alias includes ancestor or itself')
        if row['type']=='dir':
            adddir(dest)
            for child in children[terminal]:walk(child,(dest+'/' if dest else '')+child.rsplit('/',1)[-1],ancestry+(terminal,),tuple(chain))
        else:addfile(dest,row,terminal,chain)
        if chain:note({'action':'alias-copy','source':source,'path':dest,'terminal':terminal,'hops':len(chain),'chain_sha256':hashlib.sha256(encoded(chain)).hexdigest()})
        if row['type']=='file' and (row['mode']&0o7777)!=files[dest]['mode']:note({'action':'mode-normalize','source':terminal,'path':dest,'from':row['mode'],'to':files[dest]['mode']})
    for child in children['']:walk(child,child,('',))
    for slot in SLOTS:adddir(slot)
    zero={'bytes':0,'sha256':ZERO,'mode':0o444,'offset':0}
    for path in (*EMPTY,*NORMAL):
        need(path not in dirs and path not in files,'normalization collision');addfile(path,zero,'<normalized>',[])
    required_seen=set()
    for row in required_files:
        need(type(row) is dict and set(row)=={'path','bytes','sha256'} and row['path'] not in required_seen,'exact unique required file')
        required_seen.add(row['path']);got=files.get(row['path']);need(got is not None and got['bytes']==row['bytes'] and got['sha256']==row['sha256'],'all required scientific bytes survive unchanged')
    manifest={'schema':'language-frozen-public-tree/v1','kind':'runtime','condition':'generic','directories':sorted(dirs),'files':[{k:row[k] for k in ('path','bytes','sha256','mode')} for _,row in sorted(files.items())]}
    m=bounded_encoded(manifest,budget.limits['manifest_bytes'])
    largest=max((row['bytes'] for row in files.values()),default=0)
    need(4*largest+8*len(m)+2048*(len(dirs)+len(files))+4194304<=1073741824,'unchanged provider working formula')
    return {'directories':manifest['directories'],'files':[row for _,row in sorted(files.items())],'audit':audit}

def verify_projection(plan,budget):
    need(type(plan) is dict and set(plan)=={'schema','image','archive','required','projection'},'exact plan schema')
    need(plan['schema']=='language-provider-rootfs-plan/v1' and plan['image']==IMAGE,'one frozen scientific image')
    archive=plan['archive'];need(type(archive) is dict and set(archive)=={'bytes','sha256'} and integer(archive['bytes'],1024) and archive['bytes']<=budget.limits['archive_bytes'] and digest(archive['sha256']),'archive plan pin')
    projection=plan['projection'];need(type(projection) is dict and set(projection)=={'directories','files','audit'},'exact projection schema')
    dirs=projection['directories'];rows=projection['files'];need(type(dirs) is list and type(rows) is list and len(dirs)+len(rows)<=budget.limits['nodes'],'bounded plan roster')
    need(dirs==sorted(set(dirs)) and all(canonical(x,budget.limits['path_chars'])==x for x in dirs),'canonical sorted directories')
    seen=set(dirs);folded={x.casefold() for x in dirs};need(len(folded)==len(dirs),'directory case collision');total=0;files={}
    for row in rows:
        budget.check();need(type(row) is dict and set(row)=={'path','bytes','sha256','mode','offset','source','hops','chain_sha256'},'exact planned file')
        name=canonical(row['path'],budget.limits['path_chars']);need(name==row['path'] and name not in seen and name.casefold() not in folded,'unique planned path');seen.add(name);folded.add(name.casefold())
        need(integer(row['bytes']) and row['bytes']<=budget.limits['member_bytes'] and digest(row['sha256']) and row['mode'] in (0o444,0o555) and integer(row['offset']) and row['offset']+row['bytes']<=archive['bytes'],'planned bounded range/mode')
        need(integer(row['hops']) and row['hops']<=budget.limits['alias_hops'] and digest(row['chain_sha256']) and type(row['source']) is str and len(row['source'])<=budget.limits['path_chars'],'bounded alias provenance')
        total+=row['bytes'];need(total<=budget.limits['output_bytes'],'planned byte stop');files[name]=row
    need(list(files)==sorted(files),'sorted planned files')
    for name in seen:
        parent=name.rpartition('/')[0];need(not parent or parent in dirs,'complete parent directories')
    need(set(SLOTS)<=set(dirs),'all provider directory slots')
    need({x for x in dirs if reserved(x)}==set(SLOTS),'no nested reserved dirs')
    need({x for x in files if reserved(x)}==set(EMPTY),'only exact reserved files')
    for path in (*EMPTY,*NORMAL):need(path in files and files[path]['bytes']==0 and files[path]['sha256']==ZERO and files[path]['mode']==0o444,'exact empty normalized file')
    need(type(plan['required']) is list and len(plan['required'])<=3043,'bounded required roster');rs=set()
    for row in plan['required']:
        need(type(row) is dict and set(row)=={'path','bytes','sha256'} and row['path'] not in rs,'unique required descriptor');rs.add(row['path']);got=files.get(row['path']);need(got is not None and got['bytes']==row['bytes'] and got['sha256']==row['sha256'],'required scientific bytes bound')
    manifest={'schema':'language-frozen-public-tree/v1','kind':'runtime','condition':'generic','directories':dirs,'files':[{k:r[k] for k in ('path','bytes','sha256','mode')} for r in rows]}
    raw=bounded_encoded(manifest,budget.limits['manifest_bytes']);largest=max((r['bytes'] for r in rows),default=0);need(4*largest+8*len(raw)+2048*len(seen)+4194304<=1073741824,'provider working cap')
    return manifest

def publish(path,body,budget,mode=0o444):
    path=parents(path);need(not os.path.lexists(path),'fresh publication only')
    pending=path.with_name('.'+path.name+'.pending');fd=os.open(pending,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    try:
        budget.write(len(body))
        stream=os.fdopen(fd,'wb');fd=None
        with stream:stream.write(body);stream.flush();os.fchmod(stream.fileno(),mode);os.fsync(stream.fileno())
        os.link(pending,path,follow_symlinks=False);os.unlink(pending)
        d=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);os.fsync(d);os.close(d)
    finally:
        if fd is not None:
            try:os.close(fd)
            except OSError:pass
    return {'path':str(path),'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}

def apply_plan(plan,archive_path,output_root,manifest_path,budget):
    manifest=verify_projection(plan,budget);root=parents(output_root);mp=parents(manifest_path)
    need(root!=mp and root not in mp.parents and mp not in root.parents,'manifest strictly outside runtime tree')
    need(not os.path.lexists(root) and not os.path.lexists(mp) and not os.path.lexists(mp.with_name('.'+mp.name+'.pending')),'fresh output tree and publication')
    archive=plan['archive'];handle,before=open_regular(archive_path,archive['bytes']);created=False
    try:
        need(hash_range(handle,0,archive['bytes'],budget)==archive['sha256'],'whole export identity before apply');check_input(handle,archive_path,before)
        root.mkdir(mode=0o700);created=True;device=root.lstat().st_dev
        for name in sorted(manifest['directories'],key=lambda n:(n.count('/'),n)):
            budget.check();path=root/name;need(stat.S_ISDIR(path.parent.lstat().st_mode) and path.parent.lstat().st_dev==device,'owned ordinary directory parent');path.mkdir(mode=0o700)
        for row in plan['projection']['files']:
            budget.check();path=root/row['path'];fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
            try:
                st=os.fstat(fd);need(stat.S_ISREG(st.st_mode) and st.st_nlink==1 and st.st_dev==device,'new ordinary single-link output')
                handle.seek(row['offset']);left=row['bytes'];h=hashlib.sha256()
                while left:
                    raw=read_exact(handle,min(CHUNK,left),budget);budget.write(len(raw));need(os.write(fd,raw)==len(raw),'complete output write');h.update(raw);left-=len(raw)
                need(h.hexdigest()==row['sha256'],'copied range digest');os.fchmod(fd,row['mode']);os.fsync(fd)
            finally:os.close(fd)
        for name in sorted(manifest['directories'],key=lambda n:(-n.count('/'),n)):
            p=root/name;os.chmod(p,0o555,follow_symlinks=False);fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);os.fsync(fd);os.close(fd)
        os.chmod(root,0o555,follow_symlinks=False);fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);os.fsync(fd);os.close(fd)
        check_input(handle,archive_path,before)
        expected_dirs=set(manifest['directories']);expected_files={r['path']:r for r in manifest['files']};found_dirs=set();found_files=set();pending=['']
        while pending:
            parent=pending.pop()
            with os.scandir(root/parent) as entries:
                for entry in entries:
                    budget.check();name=(parent+'/' if parent else '')+entry.name;st=entry.stat(follow_symlinks=False)
                    need(st.st_dev==device,'same output filesystem')
                    if name in expected_dirs:need(stat.S_ISDIR(st.st_mode) and stat.S_IMODE(st.st_mode)==0o555,'final directory identity/mode');found_dirs.add(name);pending.append(name)
                    else:
                        need(name in expected_files and stat.S_ISREG(st.st_mode) and st.st_nlink==1,'no hidden or linked output');row=expected_files[name];fh,fs=open_regular(root/name,row['bytes'])
                        try:need(stat.S_IMODE(fs.st_mode)==row['mode'] and hash_range(fh,0,row['bytes'],budget)==row['sha256'],'final tree file digest/mode');check_input(fh,root/name,fs)
                        finally:fh.close()
                        found_files.add(name)
        need(found_dirs==expected_dirs and found_files==set(expected_files),'complete final tree roster')
        publication=publish(mp,bounded_encoded(manifest,budget.limits['manifest_bytes']),budget)
        return {'status':'ordinary_runtime_projection_created','manifest':publication,'files':len(found_files),'directories':len(found_dirs),'content_bytes':sum(r['bytes'] for r in manifest['files']),'counters':dict(budget.counters),'provider_qualified':False,'scientific_qualified':False}
    finally:
        handle.close()
        # Failed partial output is retained and charged; never recursively delete.

def required_inventory(path,budget):
    handle,before=open_regular(path,INVENTORY['bytes']);rows=[];h=hashlib.sha256();used=0;names=set()
    try:
        while used<INVENTORY['bytes']:
            reservation=min(8193,INVENTORY['bytes']-used);budget.read(reservation,True)
            line=handle.readline(reservation);budget.counters['read_bytes']-=reservation-len(line);budget.counters['metadata_bytes']-=reservation-len(line)
            need(line and len(line)<=8192 and line.endswith(b'\n'),'bounded inventory line before parse');used+=len(line);h.update(line)
            row=parse(line);need(type(row) is dict and {'distribution','path','bytes','sha256','mode','elf_magic','elf_machine'}==set(row),'exact retained numeric inventory schema')
            need(type(row['path']) is str and row['path'].startswith('/'),'numeric absolute image path');name=canonical(row['path'][1:]);need(name not in names and integer(row['bytes']) and digest(row['sha256']),'unique numeric descriptor');names.add(name)
            need(len(rows)<3042,'exact numeric roster cap before append');rows.append({'path':name,'bytes':row['bytes'],'sha256':row['sha256']})
        need(used==INVENTORY['bytes'] and h.hexdigest()==INVENTORY['sha256'] and len(rows)==3042,'complete original3042 numeric file inventory');check_input(handle,path,before)
    finally:handle.close()
    need(PYTHON['path'] not in names,'separate Python identity');return sorted(rows+[dict(PYTHON)],key=lambda x:x['path'])

def main():
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=('plan','apply'));ap.add_argument('--profile',required=True);ap.add_argument('--profile-sha256',required=True);args=ap.parse_args()
    budget=Budget();path=parents(args.profile);size=path.lstat().st_size;profile=bounded_json(path,{'bytes':size,'sha256':args.profile_sha256},budget,65536)
    need(type(profile) is dict and set(profile)=={'schema','selected_for_execution','expires_unix','operation','image','archive','inventory','plan','audit','output_root','manifest','limits','prior_read_charge'},'exact task-local profile')
    need(profile['schema']=='language-provider-rootfs-operation/v1' and profile['selected_for_execution'] is True and profile['operation']==args.mode and profile['image']==IMAGE,'operation disabled until exact external selection')
    need(integer(profile['expires_unix']) and time.time()<profile['expires_unix']<=time.time()+540 and profile['limits']==LIMITS,'finite selected unchanged profile')
    budget.deadline=min(budget.deadline,time.monotonic()+max(0,profile['expires_unix']-time.time()))
    need(integer(profile['prior_read_charge']) and profile['prior_read_charge']<=LIMITS['read_bytes'],'bounded preceding phase charge');budget.read(profile['prior_read_charge'])
    archive=profile['archive'];need(type(archive) is dict and set(archive)=={'path','bytes','sha256'} and integer(archive['bytes'],1024) and archive['bytes']<=LIMITS['archive_bytes'] and digest(archive['sha256']),'selected completed merged export')
    need(profile['inventory']=={'path':profile['inventory']['path'],**INVENTORY},'fixed retained installed inventory')
    required=required_inventory(profile['inventory']['path'],budget)
    if args.mode=='plan':
        handle,before=open_regular(archive['path'],archive['bytes'])
        try:
            need(hash_range(handle,0,archive['bytes'],budget)==archive['sha256'],'whole completed export hash');roster=scan_export(handle,archive['bytes'],budget);check_input(handle,archive['path'],before)
        finally:handle.close()
        projection=project_roster(roster,required,budget);plan={'schema':'language-provider-rootfs-plan/v1','image':IMAGE,'archive':{k:archive[k] for k in ('bytes','sha256')},'required':required,'projection':projection};verify_projection(plan,budget)
        raw=bounded_encoded(plan,LIMITS['plan_bytes'])
        tool_names=re.compile(r'^(?:cc|gcc(?:-[0-9]+)?|clang(?:-[0-9]+)?|ld(?:\..+)?|as|ar|make|meson|ninja|pkg-config|capability\.h|libcap\.so(?:\..+)?|libcap\.pc)$')
        tools=[row for row in projection['files'] if tool_names.fullmatch(row['path'].rsplit('/',1)[-1])]
        audit=bounded_encoded({'schema':'language-rootfs-projection-audit/v1','raw_roster':roster,'normalizations':projection['audit'],'tool_path_candidates':tools,'tool_version_execution_performed':False,'scope':'Projection, not full OCI equivalence','counters':budget.counters},LIMITS['audit_bytes'])
        apin=publish(profile['audit'],audit,budget);ppin=publish(profile['plan']['path'],raw,budget)
        result={'plan':ppin,'audit':apin,'counters':dict(budget.counters),'selected_image':IMAGE,'provider_qualified':False,'scientific_qualified':False}
    else:
        plan=bounded_json(profile['plan']['path'],profile['plan'],budget,LIMITS['plan_bytes']);need(plan['archive']=={k:archive[k] for k in ('bytes','sha256')} and plan['required']==required,'selected plan/archive/full scientific roster join')
        result=apply_plan(plan,archive['path'],profile['output_root'],profile['manifest'],budget)
    raw=encoded(result);need(len(raw)<=65536,'bounded result receipt');sys.stdout.buffer.write(raw);return 0

if __name__=='__main__':raise SystemExit(main())
