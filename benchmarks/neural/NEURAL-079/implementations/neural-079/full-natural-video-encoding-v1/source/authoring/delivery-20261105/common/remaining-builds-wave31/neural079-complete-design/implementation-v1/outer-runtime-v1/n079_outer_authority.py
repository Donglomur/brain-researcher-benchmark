"""Protected file exchange for independently installed release metadata only."""
import os
import stat
from pathlib import PurePosixPath
from ach_resource_common import require, fields, integer, check_pin, body_pin, bounded_encode, bounded_decode, close_all
from n079_outer_common import open_directory, canonical_path, identity


class FileAuthority:
    def __init__(self, selected, source_pin, io, pump):
        fields(selected,('schema','issuer_pin','nonce','request_root','response_root','response_owner_uid',
            'operand_roots','maximum_exchanges','maximum_wait_ns'), 'complete independently installed file authority')
        require(selected['schema']=='n079_outer_file_authority_v1','native file authority schema')
        check_pin(selected['issuer_pin']); integer(selected['response_owner_uid'])
        integer(selected['maximum_exchanges'],1); integer(selected['maximum_wait_ns'],1)
        require(type(selected['nonce']) is str and selected['nonce'] and len(selected['nonce'])<=128 and
                all(c in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in selected['nonce']), 'selected unique safe nonce')
        require(type(selected['operand_roots']) is list and selected['operand_roots'],'admitted configuration operand roots')
        for path in selected['operand_roots']: canonical_path(path)
        self.selected,self.source_pin,self.io,self.pump = selected,source_pin,io,pump
        self.fds={}; self.sequence=0; self.records=[]; self.closed=False
        self.clocks={name:getattr(io.clock,name) for name in ('origin','scientific','closeout','outer')}
        try:
            for name in ('request_root','response_root'):
                root=selected[name]; fields(root,('path','identity'),'protected exact root')
                fd=open_directory(root['path']); self.fds[name]=fd; st=os.fstat(fd)
                require(identity(fd)==root['identity'] and st.st_mode&0o022==0,'same protected authority root')
                expected=os.getuid() if name=='request_root' else selected['response_owner_uid']
                require(st.st_uid==expected,'independently selected authority owner')
            a=PurePosixPath(selected['request_root']['path']); b=PurePosixPath(selected['response_root']['path'])
            require(a!=b and a not in b.parents and b not in a.parents,'disjoint protected request/response roots')
        except BaseException as error:self.close(error);raise

    def exchange(self,kind,payload,phase='scientific'):
        require(kind in ('blocked_roles','release_role','observed_product','terminal_acknowledgement'),'metadata-only protocol kind')
        require((kind=='terminal_acknowledgement')==(phase=='outer'),'fixed original protocol phase')
        require(self.sequence<self.selected['maximum_exchanges'],'complete finite file exchange roster')
        self.sequence+=1; name=self.selected['nonce']+'-%04d.json'%self.sequence
        record={'kind':kind,'sequence':self.sequence,'request':None,'response':None,'status':'attempted'};self.records.append(record)
        try:
            try:os.stat(name,dir_fd=self.fds['response_root'],follow_symlinks=False)
            except FileNotFoundError:pass
            else:raise ValueError('preexisting authority response is replay')
            request={'schema':'n079_outer_authority_request_v1','kind':kind,'sequence':self.sequence,
                'nonce':self.selected['nonce'],'source_pin':self.source_pin,'issuer_pin':self.selected['issuer_pin'],
                'clocks':self.clocks,'payload':payload}
            raw=bounded_encode(request,self.io.encoding)
            descriptor=self.io.write(self.fds['request_root'],name,raw,phase)
            request_pin=body_pin(raw);record['request']={**descriptor,'root':self.selected['request_root']}
            deadline=min(getattr(self.io.clock,phase),self.io.clock.tick(phase)+self.selected['maximum_wait_ns'])
            while True:
                require(self.io.clock.tick(phase)<deadline,'original bounded independent issuer wait')
                self.pump.once(phase,min(self.pump.limits['poll_ns'],deadline-self.io.clock.tick(phase)))
                try:st=os.stat(name,dir_fd=self.fds['response_root'],follow_symlinks=False)
                except FileNotFoundError:continue
                require(stat.S_ISREG(st.st_mode) and st.st_nlink==1 and st.st_uid==self.selected['response_owner_uid'] and st.st_mode&0o022==0,
                    'ordinary independently owned response')
                break
            response_path=self.selected['response_root']['path']+'/'+name
            raw=self.io.read(response_path,phase=phase);response=bounded_decode(raw,self.io.encoding)
            record['response']={'path':response_path,**body_pin(raw),'body':response};record['status']='received_unvalidated'
            fields(response,('schema','kind','sequence','nonce','request_pin','source_pin','issuer_pin','clocks','decision','admitted'), 'exact independent file response')
            require(response['schema']=='n079_outer_authority_response_v1' and response['kind']==kind and
                response['sequence']==self.sequence and response['nonce']==self.selected['nonce'] and
                response['request_pin']==request_pin and response['source_pin']==self.source_pin and
                response['issuer_pin']==self.selected['issuer_pin'] and response['clocks']==self.clocks and
                response['decision']=='independently_approved_exact_request','same selected independent authority/request/clock')
            admitted=response['admitted']
            if kind=='release_role':
                fields(admitted,('path','pin'),'installed release receipt only');check_pin(admitted['pin'])
                path=PurePosixPath(canonical_path(admitted['path']))
                require(any(PurePosixPath(root) in path.parents for root in self.selected['operand_roots']),'release under admitted protected operand root')
            else:
                fields(admitted,('payload_pin',),'metadata acknowledgement only')
                require(admitted['payload_pin']==body_pin(bounded_encode(payload,self.io.encoding)),'exact observed metadata acknowledgement')
            for key,fd in self.fds.items():
                require(identity(fd)==self.selected[key]['identity'],'authority held namespace unchanged')
                current=open_directory(self.selected[key]['path']);inner=None
                try:require(identity(current)==self.selected[key]['identity'],'authority path still resolves to selected protected namespace')
                except BaseException as exc:inner=exc;raise
                finally:close_all([('authority root revalidation close',lambda current=current:os.close(current))],inner)
            require(self.io.clock.tick(phase)<deadline,'independent response original wait bound')
            record['status']='authenticated_selected_custody';return admitted
        except BaseException as error:
            record['failure_type']=type(error).__name__;error.n079_file_authority_prefix=record;raise

    def close(self,primary=None):
        if self.closed:return
        self.closed=True;ops=[]
        for name,fd in list(self.fds.items()):del self.fds[name];ops.append((name+' close',lambda fd=fd:os.close(fd)))
        close_all(ops,primary)
