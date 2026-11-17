from .deadline import boundary
from .custody import Custody,custody,failure_notice,observation,reader_details
"""Immutable registered source copies; builds remain participant-owned processes."""
from pathlib import Path
import os
from .errors import require
from .objects import Reader,canonical,digest,fields,rel,unique_paths,write_new


class Sources:
    def begin_boundary(self,phase):
        if phase=='Sources.register':
            self.registration_stack.append(self.current_registration)
            self.current_registration=None

    def release_boundary_success(self,phase):
        if phase=='Sources.register':
            transaction=self.current_registration
            if transaction is not None and transaction['owner'] is self:self.complete_registration(transaction,self)
            self.current_registration=self.registration_stack.pop()

    def retain_boundary_failure(self,exc,phase):
        if phase=='Sources.register':
            try:
                if self.current_registration is not None:self.reject_registration(self.current_registration)
            finally:self.current_registration=self.registration_stack.pop()

    def __init__(self,root,exposure,ledger,author_hashes,guard=None):
        self.custody=Custody();self.guard=guard
        if guard:guard()
        self.root=Path(root);self.root.mkdir(mode=0o700,parents=True,exist_ok=True)
        self.exposure=exposure;self.ledger=ledger;self.author_hashes=set(author_hashes);self.registered={};self.frozen=set()
        self.registrations={};self.current_registration=None;self.registration_stack=[]

    def begin_registration(self,context,manifest,owner):
        """Allocate original ownership before copying or publishing new ancestry."""
        sid=digest(canonical(manifest));key=context+':'+sid
        # Refusing a replay must never acquire the earlier operation's ownership.
        require(key not in self.registered and key not in self.registrations and key not in self.exposure.artifacts,'source registration replay')
        transaction={'key':key,'context':context,'source_id':sid,'manifest':manifest,
                     'owner':owner,'status':'allocated','source':None,'copied':[],
                     'reader':None,'artifact_ids':[],'revoked_artifacts':[]}
        self.registrations[key]=transaction
        return transaction

    def _owned_registration(self,transaction):
        require(self.registrations.get(transaction['key']) is transaction,'unowned source registration')

    def complete_registration(self,transaction,owner):
        """Only memory publication remains after the owner's final guard passes."""
        self._owned_registration(transaction)
        require(transaction['owner'] is owner and transaction['status']=='ready','registration completion owner/state')
        key=transaction['key'];artifact=self.exposure.artifacts[key]
        require(artifact['kind']=='pending_source' and not artifact['eligible'],'registration pending ancestry')
        self.registered[key]=transaction['source']
        artifact['kind']='source';artifact['eligible']=True
        transaction['status']='committed'

    def reject_registration(self,transaction):
        """Keep original evidence; withdraw only this registration's ancestry."""
        self._owned_registration(transaction)
        transaction['status']='rejected'
        original=self.exposure.artifacts.get(transaction['key'])
        if original is not None:original['eligible']=False
        self.registered.pop(transaction['key'],None)
        # This bounded in-memory graph walk has no ordinary I/O or deadline
        # refresh. It also covers descendants if a later publication fails
        # after an otherwise completed registration became visible.
        reverse={}
        for identity,artifact in self.exposure.artifacts.items():
            for parent in artifact['parents']:reverse.setdefault(parent,[]).append(identity)
        pending=[transaction['key']];seen=set()
        while pending:
            identity=pending.pop()
            if identity in seen:continue
            seen.add(identity)
            artifact=self.exposure.artifacts.get(identity)
            if artifact is not None:artifact['eligible']=False
            self.registered.pop(identity,None)
            dependent=self.registrations.get(identity)
            if dependent is not None:dependent['status']='rejected'
            pending.extend(reverse.get(identity,()))
        transaction['status']='rejected';transaction['revoked_artifacts']=sorted(seen)

    @boundary
    def register(self,context,source_root,manifest,entrypoint,interpreter,environment,role,parents=(),*,transaction=None):
        require(context not in self.frozen and not self.exposure.contexts[context]['sealed'],'source revised after freeze')
        unique_paths(manifest);require(manifest and entrypoint in {x['path'] for x in manifest},'registered entrypoint')
        ctx=self.exposure.contexts[context];domain=self.exposure.domains[ctx['domain']]
        require(role==domain['role'],'source role')
        if role=='candidate_A':require(not any(x['sha256'] in self.author_hashes for x in manifest),'A contains author source bytes')
        # Byte exclusion is only one check; environment and original developer
        # source-exposure qualification remain independently mandatory.
        sid=digest(canonical(manifest));key=context+':'+sid
        if transaction is None:transaction=self.begin_registration(context,manifest,self)
        self._owned_registration(transaction)
        require(transaction['key']==key and transaction['context']==context and transaction['status']=='allocated','source registration transaction identity/state')
        self.current_registration=transaction;transaction['status']='copying'
        directory=self.root/digest(key.encode());directory.mkdir(mode=0o700,exist_ok=False)
        reader=Reader(source_root,sum(r['bytes']+1 for r in manifest)+1,len(manifest)+1,guard=self.guard)
        copied=transaction['copied'];transaction['reader']=reader
        custody(self).observations.append({'phase':'source_registration','copied':copied,'reader':reader})
        self.ledger.append('source_registration_begin',{'context':context,'source_id':sid,'source_root':str(source_root),'manifest':manifest,'entrypoint':entrypoint})
        try:
            for row in manifest:
                raw=reader.read(row);dest=directory/rel(row['path']);dest.parent.mkdir(mode=0o700,parents=True,exist_ok=True);write_new(dest,raw,guard=self.guard);os.chmod(dest,0o444);copied.append(row)
        except BaseException as exc:
            failure_notice(self,exc,'Sources.register','source_registration_failed',lambda:{'context':context,'source_id':sid,'original_error':custody(self).record(),'copied':copied,'reader_cost':reader_details(reader),'eligible':False})
            raise
        src={'root':str(directory),'manifest':manifest,'entrypoint':entrypoint,'interpreter':interpreter,'environment':environment,'role':role,'source_id':sid}
        transaction['source']=src
        receipt=self.ledger.append('source_registered',{'context':context,'source':src,'eligibility':'pending_original_owner_completion','reader_cost':{'reserved_bytes':reader.bytes,'consumed_bytes':reader.consumed_bytes,'files':reader.files,'partial_observations':reader.partial_observations}})
        transaction['artifact_ids'].append(key)
        self.exposure.register_artifact(key,context,parents,'pending_source',receipt)
        transaction['status']='ready'
        return key,src

    @boundary
    def freeze(self,contexts):
        for context in contexts:
            require(any(key.startswith(context+':') for key in self.registered),'context has no actual source')
            self.exposure.freeze(context);self.frozen.add(context)

    @boundary
    def resolve(self,key,context):
        require(key in self.registered,'source not registered')
        self.exposure.admit_reuse(key,context)
        return self.registered[key]
