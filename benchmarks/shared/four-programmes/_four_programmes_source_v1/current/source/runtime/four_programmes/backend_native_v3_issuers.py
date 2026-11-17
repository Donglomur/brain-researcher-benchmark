"""Prospective C00/C01/C01H/C02, from the sole installed operator admission.

No report is supplied by a worker. The original protected selection must carry
both separately qualified native domains; this source does not execute trials.
Every physical occurrence is owned before entry and relinquished once.
"""
import hashlib
import os
import stat
from .operator_intake import require
from .early_resources import retain_source_failure

_ANCHOR=object();_ROOT_HANDLE=object();_ENTRY_HANDLE=object()
NAMESPACES=('cgroup','ipc','mnt','net','pid','user','uts')

class BootstrapDescriptorSlotV4:
    def __init__(self,anchor,role):
        self.anchor=anchor;self.role=role;self.fd=None;self.entered=False
        self.close_entered=False;self.closed=False;self.raw_first=None
        self.ordinal=len(anchor.slots);self.parent_slot=None;self.entry_name=None
        anchor.slots.append(self)
    def open(self,path,flags,parent=None):
        a=self.anchor;a.work();require(not self.entered,'one original open occurrence')
        self.entered=True
        try:
            self.entry_name=path
            if parent is not None:
                parents=[slot for slot in a.slots if slot is not self and slot.fd==parent and
                         slot.entered and not slot.close_entered and slot.raw_first is None]
                require(len(parents)==1,'exact earlier still-owned original parent open occurrence')
                self.parent_slot=parents[0]
            self.fd=os.open(path,flags|os.O_CLOEXEC|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent)
            a.observations.append(('open',self,self.fd))
            require(type(self.fd)is int and self.fd>=0,'actual original returned descriptor')
            return self
        except BaseException as error:self.raw_first=error;a.retain(error,'open');raise a.raw_first
    def close_once(self):
        if self.close_entered:return self.closed
        self.close_entered=True;fd=self.fd;self.fd=None
        try:
            if fd is not None:os.close(fd)
            elif self.entered and self.raw_first is not None:
                self.anchor.unknowns.add('descriptor_acquisition');return False
            self.closed=True;self.anchor.closed_slots.append(self);return True
        except BaseException as error:
            self.raw_first=error;self.anchor.unknowns.add('descriptor_close');self.anchor.retain(error,'close');return False

class NativeRootAcquisitionV4:
    """Retained C00 observation only, never a final root grant."""
    def __init__(self,anchor,definition,slot,identity,mount,namespace):
        self.anchor=anchor;self.definition=definition;self.root_id=definition['root_id']
        self.anchor_fds=(slot,);self.actual_identity=identity
        self.mount_observation=mount;self.namespace_observation=namespace

class NativeArtifactRootHandle:
    def __init__(self,token,anchor,definition,slot,identity,mount,namespace):
        require(token is _ROOT_HANDLE,'fixed C01H root owner')
        self.anchor=anchor;self.issuer=anchor;self.root_id=definition['root_id']
        self.definition=definition;self.anchor_fds=(slot,);self.actual_identity=identity
        self.mount_observation=mount;self.namespace_observation=namespace
        self.qualification=anchor.qualification;self.policy_capture=None
        self.raw_first=None;self.ordered_secondaries=[];self.close_slots=()
    def require_original(self):
        if self.anchor.original_parent.first_raw is not None:raise self.anchor.original_parent.first_raw
        try:
            a=self.anchor;a.require_completed_policy_profile_v3()
            require(a.final_handles.get(self.root_id)is self and self.policy_capture is a.selection_captures['native_root_policy'] and
                    all(s.fd is not None and not s.close_entered for s in self.anchor_fds),'same live original root occurrence')
            return self
        except BaseException as error:
            self.anchor.retain(error,'root_handle_require');raise self.anchor.raw_first

class BootstrapEntryHandle:
    def __init__(self,token,anchor,root,interpreter,entry,identities):
        require(token is _ENTRY_HANDLE,'fixed C01H entry owner')
        self.anchor=anchor;self.root_handle=root;self.selection_capture=None
        self.interpreter_fd=interpreter;self.entry_fd=entry
        self.interpreter_identity,self.entry_identity=identities
        self.qualified_source_closure=anchor.original_selection['entry_configuration']['source_closure']
        self.raw_first=None;self.ordered_secondaries=[]
    def require_original(self):
        if self.anchor.original_parent.first_raw is not None:raise self.anchor.original_parent.first_raw
        try:
            self.anchor.require_completed_policy_profile_v3()
            require(self.anchor.entry_handle is self and self.selection_capture is self.anchor.selection_captures['bootstrap_entry'] and
                    self.interpreter_fd.fd is not None and self.entry_fd.fd is not None and
                    not self.interpreter_fd.close_entered and not self.entry_fd.close_entered,'same original qualified entry occurrences')
            return self
        except BaseException as error:
            self.anchor.retain(error,'entry_handle_require');raise self.anchor.raw_first

class RootBootstrapAnchorV2:
    def __init__(self,token,root,outputs):
        require(token is _ANCHOR,'sole fixed native root factory')
        self.original_admission=root;self.original_parent=root.parent
        self.original_selection=root.prior_static.configuration;self.outputs=outputs
        self.registration_id='native_C00_v4';self.qualification=None
        self.slots=[];self.root_slots={};self.root_observations={};self.entry_slots={};self.observations=[]
        self.selection_captures={};self.policy_profile_captures={};self.final_handles={}
        self.entry_handle=None;self.publisher=None;self.entered=True;self.complete=False
        self.raw_first=None;self.ordered_secondaries=[];self.unknowns=set();self.closed_slots=[]
        self.close_entered=False;self.closed=False;self.known_read=0;self.partial_reads=[]
        self.original_parent_unknown=set(root.parent.unknown)
    def retain(self,error,site):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.ordered_secondaries.append(error)
        retain_source_failure(self.original_parent,error,'RootBootstrapAnchorV2.'+site)
    def work(self,amount=1):
        if self.original_parent.first_raw is not None:raise self.original_parent.first_raw
        self.original_parent.share.charge('work_units',amount)
    def slot(self,role):
        self.work();self.original_parent.share.charge('retained_bytes',512)
        return BootstrapDescriptorSlotV4(self,role)
    def observed_stat(self,slot):
        self.work();v=os.fstat(slot.fd);self.observations.append(('fstat',slot,v));return v
    def bounded_read(self,slot,maximum):
        require(type(maximum)is int and 0<=maximum<=self.original_selection['plan_constants']['maximum_input_bytes'],'bounded original ordinary observation')
        self.original_parent.share.charge('retained_bytes',maximum+1)
        parts=[];total=0
        while total<maximum:
            n=min(4096,maximum-total);self.work();self.original_parent.share.charge('read_bytes',n)
            self.original_parent.share.charge('retained_bytes',n)
            try:part=os.read(slot.fd,n)
            except BaseException:self.unknowns.add('read_bytes');raise
            self.partial_reads.append((slot,part));require(type(part)is bytes,'actual original read bytes')
            total+=len(part);self.known_read+=len(part);parts.append(part)
            if not part:return b''.join(parts)
        self.work();self.original_parent.share.charge('read_bytes',1)
        self.original_parent.share.charge('retained_bytes',1)
        try:eof=os.read(slot.fd,1)
        except BaseException:self.unknowns.add('read_bytes');raise
        self.partial_reads.append((slot,eof));require(type(eof)is bytes,'actual original EOF bytes')
        self.known_read+=len(eof);require(eof==b'','exact extent EOF; no oversized observation')
        return b''.join(parts)
    def namespace(self):
        result={'schema':'four_namespace_identity_v1'}
        for key in NAMESPACES:
            self.work();self.original_parent.share.charge('read_bytes',256)
            self.original_parent.share.charge('retained_bytes',256)
            value=os.readlink('/proc/self/ns/'+key);self.observations.append(('namespace',key,value))
            require(type(value)is str and len(value.encode())<=255,'bounded original namespace link')
            result[key]=value
        return result
    def mount_id(self,slot):
        # The path names only this actually opened occurrence in this process.
        proc=self.slot('proc_fdinfo').open('/proc',os.O_RDONLY|os.O_DIRECTORY)
        self.work();pid=os.getpid();require(type(pid)is int and pid>0,'actual original H pid')
        own=self.slot('own_proc').open(str(pid),os.O_RDONLY|os.O_DIRECTORY,proc.fd)
        directory=self.slot('fdinfo').open('fdinfo',os.O_RDONLY|os.O_DIRECTORY,own.fd)
        info=self.slot('fdinfo_record').open(str(slot.fd),os.O_RDONLY,directory.fd)
        raw=self.bounded_read(info,8192);rows=[x.split(b':',1)[1].strip()for x in raw.splitlines()if x.startswith(b'mnt_id:')]
        require(len(rows)==1 and rows[0].isdigit(),'one exact actual opened mount id')
        value=int(rows[0]);require(value>0,'positive actual mount identity')
        for item in (info,directory,own,proc):require(item.close_once(),'completed original metadata descriptor close')
        return value
    def open_root(self,definition,expected,namespace):
        path=definition['absolute_mount'];parts=path.split('/')[1:]
        require(path.startswith('/')and 1<=len(parts)<=64 and all(p and p not in ('.','..')and len(p.encode())<=255 for p in parts),
                'closed absolute root components, no alternate path projection')
        current=self.slot('root_slash').open('/',os.O_RDONLY|os.O_DIRECTORY)
        ancestors=[]
        for name in parts:
            prior=current;current=self.slot('root_component').open(name,os.O_RDONLY|os.O_DIRECTORY,prior.fd)
            actual=self.observed_stat(current);self.work();named=os.stat(name,dir_fd=prior.fd,follow_symlinks=False)
            self.observations.append(('named_root',name,named))
            require(stat.S_ISDIR(actual.st_mode)and (actual.st_dev,actual.st_ino)==(named.st_dev,named.st_ino),'same nofollow opened root component')
            ancestors.append(prior)
        actual=self.observed_stat(current);self.work();fs=os.fstatvfs(current.fd);self.observations.append(('fstatvfs',current,fs))
        mount=self.mount_id(current)
        require(actual.st_uid==definition['selected_uid']==expected['uid']and
                (actual.st_dev,actual.st_ino,actual.st_mode)==(expected['device'],expected['inode'],expected['mode'])and
                fs.f_flag&os.ST_RDONLY and mount==expected['mount_id']and namespace==expected['namespace'],
                'actual installed readonly root/source/native qualification identity')
        for item in reversed(ancestors):require(item.close_once(),'completed ancestor close')
        self.root_slots[definition['root_id']]=current
        return NativeRootAcquisitionV4(self,definition,current,actual,mount,namespace)
    def open_entry(self,root,components,absolute,selected,role):
        require(type(components)is list and 1<=len(components)<=64 and all(type(p)is str and p and p not in ('.','..')and '/'not in p and '\0'not in p for p in components),'closed selected entry components')
        require(root.definition['absolute_mount'].rstrip('/')+'/'+('/'.join(components))==absolute,'exact selected root-relative entry, no inferred executable')
        current=root.anchor_fds[0];dirs=[]
        for name in components[:-1]:
            child=self.slot('entry_directory').open(name,os.O_RDONLY|os.O_DIRECTORY,current.fd)
            s=self.observed_stat(child);require(stat.S_ISDIR(s.st_mode)and s.st_dev==root.actual_identity.st_dev,'no intermediate mount crossing')
            dirs.append(child);current=child
        slot=self.slot(role).open(components[-1],os.O_RDONLY,current.fd)
        before=self.observed_stat(slot);self.work();named=os.stat(components[-1],dir_fd=current.fd,follow_symlinks=False)
        require(stat.S_ISREG(before.st_mode)and before.st_nlink==1 and before.st_size==selected['bytes']and
                (named.st_dev,named.st_ino)==(before.st_dev,before.st_ino)and before.st_dev==root.actual_identity.st_dev,
                'actual selected complete entry file on the admitted readonly root')
        require(selected['bytes']<=self.original_selection['plan_constants']['maximum_input_bytes'],'entry extent inside original input bound')
        raw=self.bounded_read(slot,selected['bytes']);self.work(len(raw))
        require(len(raw)==selected['bytes']and hashlib.sha256(raw).hexdigest()==selected['sha256'],'exact full qualified original entry source')
        after=self.observed_stat(slot)
        fields=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')
        require(tuple(getattr(before,k)for k in fields)==tuple(getattr(after,k)for k in fields),'stable original entry across complete read')
        for item in reversed(dirs):require(item.close_once(),'entry ancestors closed once')
        self.entry_slots[role]=slot;return slot,before
    def run(self):
        from .native_qualification_v4 import verify_native_qualification_v4
        from .backend_capture import CanonicalPublisher
        from .operator_native_static import expected_native_static_body_v4,SELECTIONS,POLICIES
        try:
            root=self.original_admission;root.require_verified_root_v1()
            # Required independently selected ordinary body, already admitted
            # by the actual original V3 protected operator/source owner. No
            # default value or generated stand-in is supplied by the anchor.
            from .operator_qualification import same_body
            from .backend_native_v3_codec import validate_native_type
            selected_input=self.original_selection['agent_input_selection']
            same_body(selected_input['descriptor'],selected_input['body'])
            validate_native_type('AgentInputSelectionV1',selected_input['body'])
            self.qualification=verify_native_qualification_v4(root)
            c=self.original_selection;self.work(len(root.prior_static.invocation.intake.raw)*64+4096)
            ns=self.namespace();observations=self.qualification.reports['native_root']['observations'][0]['body']['result']['roots']
            for definition,expected in zip(c['native_root_configuration']['roots'],observations):
                h=self.open_root(definition,expected,ns);require(h.root_id not in self.root_observations,'unique complete root roles');self.root_observations[h.root_id]=h
            entry=c['entry_configuration'];require(entry['source_root_id']in self.root_observations,'exact selected entry root')
            h=self.root_observations[entry['source_root_id']]
            interpreter,ii=self.open_entry(h,entry['interpreter_components'],entry['interpreter_absolute'],entry['interpreter'],'interpreter')
            script,si=self.open_entry(h,entry['entry_components'],entry['entry_absolute'],entry['entry_script'],'entry_script')
            p=c['plan_constants'];self.publisher=CanonicalPublisher(self.original_parent,self.outputs,
                maximum_bytes=p['maximum_output_bytes'],maximum_members=p['maximum_members'],maximum_depth=p['maximum_depth'])
            self.publisher.require_native_source_v3();captures={}
            for key,kind in {**SELECTIONS,**POLICIES}.items():
                body=expected_native_static_body_v4(root.prior_static,captures,key)
                captured=self.publisher.capture('native_static_'+key+'.json',kind,body)
                captures[key]=captured
                (self.selection_captures if key in SELECTIONS else self.policy_profile_captures)[key]=captured
                if key=='bootstrap_entry':
                    # Only the complete C01 triple can mint final C01H handles.
                    for root_id,observed in self.root_observations.items():
                        handle=NativeArtifactRootHandle(_ROOT_HANDLE,self,observed.definition,
                            observed.anchor_fds[0],observed.actual_identity,observed.mount_observation,observed.namespace_observation)
                        self.final_handles[root_id]=handle
                        handle.policy_capture=self.selection_captures['native_root_policy']
                    self.entry_handle=BootstrapEntryHandle(_ENTRY_HANDLE,self,self.final_handles[entry['source_root_id']],
                        interpreter,script,(ii,si))
                    self.entry_handle.selection_capture=captured
            require(self.namespace()==ns,'same actual namespace after all native static publications')
            for observed in self.root_observations.values():
                slot=observed.anchor_fds[0];after=self.observed_stat(slot);self.work();fs=os.fstatvfs(slot.fd)
                self.observations.append(('final_fstatvfs',slot,fs))
                require((after.st_dev,after.st_ino,after.st_uid,after.st_mode)==
                    (observed.actual_identity.st_dev,observed.actual_identity.st_ino,observed.actual_identity.st_uid,observed.actual_identity.st_mode)and
                    fs.f_flag&os.ST_RDONLY and self.mount_id(slot)==observed.mount_observation,
                    'same original readonly root occurrence after complete selection publication')
            self.complete=True;return self.require_completed_policy_profile_v3()
        except BaseException as error:
            self.retain(error,'run');self.close_all_once();raise self.raw_first
    def require_completed_policy_profile_v3(self):
        parent=self.original_parent
        if parent.first_raw is not None:raise parent.first_raw
        try:
            root=self.original_admission;root.require_verified_root_v1()
            require(root.native_context_anchor_attempts.get(self.registration_id)is self and self.complete and
                    not self.close_entered and self.raw_first is None and not self.unknowns and
                    len(self.selection_captures)==3 and len(self.policy_profile_captures)==3,
                    'same live completed registered C00-C02 original owner')
            self.qualification.require_original();return self
        except BaseException as error:self.retain(error,'require_completed');raise self.raw_first
    def close_all_once(self):
        if self.close_entered:return self.closed
        self.close_entered=True;complete=True
        for slot in reversed(self.slots):complete=slot.close_once()and complete
        self.closed=complete;return complete

def admit_native_static_v4(root,outputs):
    from .operator_bootstrap_owner import RootBootstrapAdmission
    from .common import Store
    require(type(root)is RootBootstrapAdmission,'sole earlier installed operator issuer')
    parent=root.parent
    if parent.first_raw is not None:raise parent.first_raw
    try:
        root.require_verified_root_v1()
        require(type(outputs)is Store and outputs.meter is parent.share and parent.owner is None and
                root.phase=='verified_root'and not root.native_context_anchor_attempts and
                str(outputs.root)==root.prior_static.configuration['policy_constants']['capture_root'],
                'one original earlier native static producer and original output Store')
        anchor=RootBootstrapAnchorV2(_ANCHOR,root,outputs)
        root.native_context_anchor_attempts[anchor.registration_id]=anchor
        return anchor.run()
    except BaseException as error:raise retain_source_failure(parent,error,'admit_native_static_v4')
