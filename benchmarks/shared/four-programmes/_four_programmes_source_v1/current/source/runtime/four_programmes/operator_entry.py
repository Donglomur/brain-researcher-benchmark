"""Inactive fixed installed entry. Runtime leaves are never run by BUILD controls.

The external qualified harness and its isolated installed configuration are the
trust anchor. No public caller parameter can replace that configuration.
"""
import hashlib
import os
import stat
import sys
import time
import types
from .operator_intake import require,canonical,parse_canonical,begin_operator_intake,DIMENSIONS
from .operator_records import validate_operator_record

_ENTRY=object()
_CURRENT=None

def _code_identity(module):
    # Use explicit value fields rather than interpreter marshal reference
    # flags. This is code provenance, not a claim to hash mutable module heap.
    def project(value,depth=0):
        require(depth<=64,'fixed loaded code projection depth')
        typ=type(value)
        if typ is types.CodeType:
            return ['code',value.co_argcount,value.co_posonlyargcount,value.co_kwonlyargcount,
                value.co_nlocals,value.co_stacksize,value.co_flags,value.co_code.hex(),
                project(value.co_consts,depth+1),list(value.co_names),list(value.co_varnames),
                value.co_filename,value.co_name,value.co_qualname,value.co_firstlineno,
                value.co_linetable.hex(),value.co_exceptiontable.hex(),
                list(value.co_freevars),list(value.co_cellvars)]
        if value is None:return ['none']
        if value is Ellipsis:return ['ellipsis']
        if typ is bool:return ['bool',value]
        if typ is int:return ['int',str(value)]
        if typ is float:return ['float',value.hex()]
        if typ is complex:return ['complex',value.real.hex(),value.imag.hex()]
        if typ is str:return ['text',value]
        if typ is bytes:return ['bytes',value.hex()]
        if typ is tuple:return ['tuple',[project(x,depth+1)for x in value]]
        if typ is frozenset:return ['frozenset',sorted((project(x,depth+1)for x in value),key=canonical)]
        raise ValueError('unselected loaded code constant kind')
    entries=[]
    for name,value in sorted(vars(module).items()):
        if type(value)is types.FunctionType and value.__module__==module.__name__:
            entries.append([name,project(value.__code__)])
        elif type(value)is type and value.__module__==module.__name__:
            for member,item in sorted(vars(value).items()):
                if type(item)in (staticmethod,classmethod):item=item.__func__
                if type(item)is types.FunctionType:
                    entries.append([name+'.'+member,project(item.__code__)])
                elif type(item)is property:
                    for suffix,accessor in [('get',item.fget),('set',item.fset),('del',item.fdel)]:
                        if accessor is not None:entries.append([name+'.'+member+'.'+suffix,project(accessor.__code__)])
    require(entries,'complete selected module has source-owned executable definitions')
    return hashlib.sha256(canonical(entries)).hexdigest()

class InstalledOperatorInvocation:
    def __init__(self,token):
        require(token is _ENTRY,'only the fixed installed entry')
        self.pending_fd=197;self.raw_first=None;self.secondaries=[]
        self.launch_anchor=None;self.profile={};self.intake=None
        self.observed=None;self.evidence_verified=False;self.verified_reports=()
        self.prior_static=None;self.root_admission=None;self.transfer=None
        self.loaded_source_map={};self.file_occurrences=[];self.started_wall=None;self.started_cpu=None
        self.source_schedule_reserved=False;self.observe_attempted=False
    def retain(self,error,site):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append((error,site))
        if self.intake is not None:self.intake.retain(error,site)
    def require_observed_entry(self):
        require(self is _CURRENT and self.raw_first is None and self.observed is not None and
                self.intake is not None and self.intake.invocation is self and
                self.intake.close_known and self.pending_fd is None,
                'actual registered original installed entry with closed protected occurrence')
        return self
    def close_unadopted_fd_once(self):
        closing,self.pending_fd=self.pending_fd,None
        if closing is not None:
            try:os.close(closing)
            except BaseException as e:self.retain(e,'pre-anchor close')

def _read_selected(invocation,path,extent,*,exact=True,source=False):
    """One nofollow file occurrence after FD197 closes; bounded current source only."""
    c=invocation.intake
    require(c.close_known and c.fd is None,'one descriptor slot: close intake before any source/proc open')
    require(type(path)is str and path.startswith('/')and type(extent)is int and 0<extent<c.limits['read_bytes'],
            'fixed selected absolute source or kernel metadata extent')
    body_attempts=(extent+65535)//65536 if exact else 1
    request_cap=min(extent,65536) if exact else extent
    attempts=body_attempts+1
    c.reserve('read_bytes',body_attempts*request_cap+1)
    c.reserve('work_units',(extent+1)*32+attempts*4096)
    c.reserve('retained_bytes',(extent+1)*3+4096)
    occurrence={'path':path,'entered':False,'fd':None,'prefixes':[],'stat':None,'closed':False}
    invocation.file_occurrences.append(occurrence)
    try:
        occurrence['entered']=True
        occurrence['fd']=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
        before=os.fstat(occurrence['fd']);occurrence['stat']=before
        require(stat.S_ISREG(before.st_mode)and before.st_nlink==1,'one selected regular source/kernel member')
        if source:
            require(before.st_uid==0 and before.st_mode&0o222==0 and before.st_size==extent,
                    'installed selected source is root-owned immutable with exact extent')
        count=0;ended=False
        occurrence['requested_bytes']=0;occurrence['read_entries']=0
        for _ in range(body_attempts):
            if count==extent:break
            request=min(request_cap,extent-count)
            occurrence['requested_bytes']+=request;occurrence['read_entries']+=1
            chunk=os.read(occurrence['fd'],request)
            occurrence['prefixes'].append(chunk)
            if type(chunk)is bytes:c.completed['read_bytes']+=len(chunk)
            require(type(chunk)is bytes and len(chunk)<=request,'original bounded bytes')
            if not chunk:ended=True;break
            count+=len(chunk)
            c.observe_clock()
        # A short body read does not acquire another productive attempt. The
        # sole remaining operation is the independently reserved one-byte EOF
        # check. Retain its actual byte before refusing unexpected continuation.
        if not ended:
            occurrence['requested_bytes']+=1;occurrence['read_entries']+=1
            tail=os.read(occurrence['fd'],1);occurrence['prefixes'].append(tail)
            if type(tail)is bytes:c.completed['read_bytes']+=len(tail)
            require(type(tail)is bytes and tail==b'','complete original EOF within fixed attempts')
        raw=b''.join(occurrence['prefixes'])
        require(not exact or len(raw)==extent,'exact whole selected body')
        after=os.fstat(occurrence['fd'])
        require((before.st_dev,before.st_ino,before.st_mode,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==
                (after.st_dev,after.st_ino,after.st_mode,after.st_size,after.st_mtime_ns,after.st_ctime_ns),
                'same opened original source/kernel object')
        occurrence['raw']=raw
    except BaseException as e:
        invocation.retain(e,'installed source/identity read');c.unknown.add('read_bytes')
    finally:
        closing,occurrence['fd']=occurrence['fd'],None
        if closing is not None:
            try:os.close(closing);occurrence['closed']=True
            except BaseException as e:invocation.retain(e,'installed source/identity close');c.unknown.add('fd_close')
    if invocation.raw_first is not None:raise invocation.raw_first
    c.observe_clock()
    return occurrence['raw']

def _kernel_identity(path):
    # /proc namespace/exe links are fixed source-selected kernel paths only.
    value=os.stat(path)
    return {'device':value.st_dev,'inode':value.st_ino,'mode':value.st_mode}

def _process(invocation,pid,expected,mapping):
    raw=_read_selected(invocation,'/proc/'+str(pid)+'/stat',8192,exact=False)
    begin=raw.find(b'(');end=raw.rfind(b')')
    require(begin>0 and end>begin and int(raw[:begin].strip())==pid,'original proc owner')
    fields=raw[end+2:].split();require(len(fields)>=20,'complete original proc start')
    ticks=int(fields[19]);require(ticks>=0,'original nonnegative start ticks')
    start=ticks*1000000000//mapping['clock_ticks']+mapping['tick_to_monotonic_offset_ns']
    observed={**expected,'pid':pid,'start_monotonic_ns':start,'boot_id':mapping['boot_id']}
    require(observed==expected,'actual original PID/start/boot, not equal PID alone')
    return observed,ticks,int(fields[1])

def _source_members(invocation,closure):
    out=[];seen=set()
    for row in closure['members']:
        name=row['loaded_module'];require(name not in seen,'unique selected loaded module role');seen.add(name)
        d=row['descriptor'];path=row['installed_path'];module=sys.modules.get(name)
        require(type(module)is types.ModuleType and type(module.__file__)is str and module.__file__==path,
                'actual already-loaded exact installed module, no dynamic import')
        require(module.__spec__ is not None and module.__spec__.origin==path,
                'actual installed source origin')
        raw=_read_selected(invocation,path,d['bytes'],source=True)
        require(hashlib.sha256(raw).hexdigest()==d['sha256'] and _code_identity(module)==row['loaded_code_sha256'],
                'actual loaded module code and immutable original source bytes')
        invocation.loaded_source_map[name]=(module,row,raw)
        out.append(row)
    return out

def observe_installed_entry_v1(invocation):
    require(type(invocation)is InstalledOperatorInvocation and invocation is _CURRENT and
            not invocation.observe_attempted,'one actual fixed current-source observation')
    invocation.observe_attempted=True;c=invocation.intake;s=c.body;p=invocation.profile;a=invocation.launch_anchor
    try:
        require(c.close_known and not c.raw_first,'closed original intake before current probes')
        c.reserve('work_units',len(c.raw)*512+4096)
        c.reserve('retained_bytes',len(c.raw)*32+4096)
        validate_operator_record('OperatorEntrySelectionV3',s)
        require(sys.platform=='linux'and sys.flags.isolated==1,'qualified isolated Linux installed entry')
        require(os.getuid()==os.geteuid()==p['entry_uid'] and os.getgid()==os.getegid()==p['entry_gid'],
                'exact source-selected original entry principal')
        require(os.getpid()==s['entry_identity']['pid'] and os.getppid()==a['original_launcher']['pid'],
                'actual original parent/current process')
        mapping=s['clock_mapping'];require(os.sysconf('SC_CLK_TCK')==mapping['clock_ticks'],'original kernel tick domain')
        boot=_read_selected(invocation,'/proc/sys/kernel/random/boot_id',128,exact=False).decode('ascii').strip()
        require(boot==mapping['boot_id'],'actual current boot')
        entry,entry_ticks,parent=_process(invocation,os.getpid(),s['entry_identity'],mapping)
        launcher,launcher_ticks,_=_process(invocation,os.getppid(),a['original_launcher'],mapping)
        require(parent==launcher['pid'] and entry['source']==p['entry_source']==a['entry_source'],
                'original fixed entry source and parent ancestry')
        c.reserve('work_units',32768);c.reserve('retained_bytes',32768)
        env=s['environment'];observed_env={**env,
            'platform':sys.platform,'machine':os.uname().machine,
            'environment':[{'name':k,'value':v}for k,v in sorted(os.environ.items())],
            'interpreter_identity':_kernel_identity('/proc/self/exe'),
            'mount_namespace':_kernel_identity('/proc/self/ns/mnt'),
            'user_namespace':_kernel_identity('/proc/self/ns/user'),
            'pid_namespace':_kernel_identity('/proc/self/ns/pid'),
            'clock_ticks_per_second':os.sysconf('SC_CLK_TCK')}
        executable=_read_selected(invocation,env['interpreter_absolute'],env['interpreter']['bytes'],source=True)
        executable_stat=invocation.file_occurrences[-1]['stat']
        require(hashlib.sha256(executable).hexdigest()==env['interpreter']['sha256'] and
                observed_env['interpreter_identity']=={'device':executable_stat.st_dev,
                    'inode':executable_stat.st_ino,'mode':executable_stat.st_mode},
                'actual original interpreter bytes and same running executable object')
        require(observed_env==env and env['mount_namespace']==p['entry_mount_namespace'] and
                env['user_namespace']==p['entry_user_namespace'],'complete current selected environment/namespaces')
        source=_source_members(invocation,s['installed_closure']);deps=_source_members(invocation,s['dependencies'])
        for pair in s['static_values']['qualified_command_pairs']:
            executable=pair['qualified_executable']
            tool_raw=_read_selected(invocation,pair['command'],executable['bytes'],source=True)
            require(hashlib.sha256(tool_raw).hexdigest()==executable['sha256'],
                    'same immutable actual command executable as the earlier original qualifier')
        # Recheck anchored start identities after all source/environment reads.
        require(_process(invocation,entry['pid'],entry,mapping)[1]==entry_ticks and
                _process(invocation,launcher['pid'],launcher,mapping)[1]==launcher_ticks,
                'same still-anchored original processes after the full selected observation')
        o=s['intake_occurrence'];original=c.observation
        require(o['object_identity']=={k:original[k]for k in ('device','inode','mode')} and
                o['size']==original['size'] and o['creator_process']==launcher and
                o['launch_id']==a['original_attempt'],'actual earlier protected original FD occurrence')
        invocation.observed={'entry_identity':entry,'launcher_start_ticks':launcher_ticks,
            'entry_start_ticks':entry_ticks,'environment':observed_env,
            'source_members':source,'dependency_members':deps}
        return invocation
    except BaseException as e:invocation.retain(e,'installed-entry actual observer');raise invocation.raw_first

def installed_operator_entry_v1():
    """Fixed launch entry; no profile/qualifier/validator callback parameters."""
    global _CURRENT
    require(_CURRENT is None,'one original installed entry per process')
    invocation=InstalledOperatorInvocation(_ENTRY);_CURRENT=invocation
    try:
        # Own FD197 before clocks, argv or installed-profile parsing can fail.
        invocation.started_wall=time.monotonic_ns();invocation.started_cpu=time.process_time_ns()
        require(len(sys.argv)==2 and type(sys.argv[1])is str and len(sys.argv[1])<=8192,'one bounded trusted launch operand')
        raw=sys.argv[1].encode('utf-8');require(len(raw)<=8192,'bounded UTF8 launch operand')
        a=parse_canonical(raw,8192);validate_operator_record('InstalledOperatorLaunchAnchorV1',a)
        from .common import descriptor
        descriptor({'path':a['operator_selection_path'],'bytes':a['operator_selection_bytes'],
                    'sha256':a['operator_selection_sha256']})
        invocation.launch_anchor=a
        # This fixed literal-data module belongs to the qualified installed
        # launch, is loaded before entry and is not part of participant input.
        from .operator_installed_configuration import PROFILE_RAW
        require(type(PROFILE_RAW)is bytes and 0<len(PROFILE_RAW)<=65536,'genuine installed profile configuration required')
        c=begin_operator_intake(invocation,a,invocation.profile);invocation.pending_fd=None
        c.reserve('retained_bytes',len(PROFILE_RAW)*16+32768)
        c.reserve('work_units',len(PROFILE_RAW)*128+1048576)
        p=parse_canonical(PROFILE_RAW,65536);validate_operator_record('InstalledOperatorProfileV1',p)
        require(len(PROFILE_RAW)==a['installed_profile']['bytes'] and
                hashlib.sha256(PROFILE_RAW).hexdigest()==a['installed_profile']['sha256'],
                'external installed-launch exact configuration identity')
        invocation.profile.update(p)
        for dim in DIMENSIONS:
            require(a['original_reservation']['limits'][dim]<=p['maximum_bootstrap_limits'][dim] and
                    a['native_preentry_reserved'][dim]+a['original_reservation']['terminal_reserve'][dim]<=a['original_reservation']['limits'][dim],
                    'same original reservation inside installed finite limits')
        c.read_once();c.close_once()
        observe_installed_entry_v1(invocation)
        from .operator_qualification import verify_operator_evidence_v1
        verify_operator_evidence_v1(invocation)
        from .operator_bootstrap_owner import transfer_original_bootstrap_v1
        return transfer_original_bootstrap_v1(invocation)
    except BaseException as e:invocation.retain(e,'installed operator entry')
    finally:
        if invocation.intake is not None and not invocation.intake.close_entered:
            try:invocation.intake.close_once()
            except BaseException as e:invocation.retain(e,'original final FD close')
        invocation.close_unadopted_fd_once()
    if invocation.raw_first is not None:raise invocation.raw_first

