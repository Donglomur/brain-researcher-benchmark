"""Actual prefix-accounted writes and reserved original failure custody."""
import hashlib
import os
from pathlib import Path
from .common import encoded, relative, require, diagnostic_projection, diagnostic_type

class Journal:
    def __init__(self, root, budget, carrier):
        self.root=Path(root); self.budget=budget; self.carrier=carrier
        require(self.root.is_absolute() and not self.root.exists() and self.root.parent.is_dir(), 'fresh journal')
        self.root.mkdir(mode=0o700)
        self.records=[]
        budget.reserve('external_terminal', 131072, 2)
    def write(self, name, body, reservation=None, emergency=False):
        p=self.root/str(relative(name));require(p.parent==self.root or p.parent.is_dir(),'declared journal parent')
        if not emergency:self.budget.check('before journal write')
        self.budget.admit_write(len(body),reservation)
        r={'path':name,'expected_bytes':len(body),'observed_bytes':0,'sha256':None,'closed':False,'status':'opening'}
        self.records.append(r)  # Retained before open/write/formatting can fail.
        h=hashlib.sha256();fd=None;first=None
        try:
            fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
            self.budget.file_created()
            r['status']='writing';offset=0
            while offset<len(body):
                tail=memoryview(body)[offset:]
                try:n=os.write(fd,tail)
                except BaseException as exc:
                    n=self.budget.failed_write('journal:'+name,exc,len(tail))
                    if type(n) is int and 0<n<=len(tail):
                        self.budget.written(n);h.update(tail[:n]);offset+=n;r['observed_bytes']=offset
                    elif n is None:r['unknown_write_extent']=True
                    raise
                n=self.budget.write_count('journal:'+name,n,len(tail))
                if n is None:r['unknown_write_extent']=True
                require(n is not None and n>0,'valid positive write return')
                self.budget.written(n);h.update(tail[:n]);offset+=n;r['observed_bytes']=offset
                if not emergency:self.budget.check('after write return')
            os.fsync(fd)
            if not emergency:self.budget.check('after file fsync')
        except BaseException as exc:
            first=exc;self.carrier.fail(exc,'journal:'+name);r['status']='failed'
        finally:
            r['sha256']=h.hexdigest()
            if fd is not None:
                try:os.close(fd);r['closed']=True
                except BaseException as exc:
                    self.carrier.fail(exc,'journal-close:'+name)
                    self.budget.uncertain('journal:'+name,'managed_descriptor_closure',exc,descriptor=fd)
                    r['status']='failed'
                    if first is None:first=exc
            if first is None:
                try:
                    d=os.open(p.parent,os.O_RDONLY);directory_error=None
                    try:os.fsync(d)
                    except BaseException as exc:directory_error=exc;self.carrier.fail(exc,'directory-sync:'+name)
                    finally:
                        try:os.close(d)
                        except BaseException as exc:
                            self.carrier.fail(exc,'directory-close:'+name)
                            self.budget.uncertain('journal-directory:'+name,'managed_descriptor_closure',exc,descriptor=d)
                            if directory_error is None:directory_error=exc
                    if directory_error is not None:raise directory_error
                    if not emergency:self.budget.check('after journal close')
                    r['status']='complete'
                except BaseException as exc:
                    self.carrier.fail(exc,'journal-final:'+name);first=exc;r['status']='failed'
        if first is not None:raise first
        return dict(r)
    def json(self,name,value,**kw):
        return self.write(name,encoded(value),**kw)
    def terminal(self,value):
        """A completed-custody construction failure is itself an original failure."""
        try:
            self.budget.check('before terminal construction')
            body=encoded(value)
            require(len(body)<=65536,'terminal extent')
            self.write('TERMINAL.json',body,reservation='external_terminal')
            self.budget.check('after terminal publication')
            self.carrier.durable=True
            return True
        except BaseException as exc:
            self.carrier.fail(exc,'terminal-construction-or-publication')
            # Prepare a diagnostic-only record independently of the failed
            # scientific/ordinary encoder. Preserve the raw primary and every
            # secondary before attempting any projection or publication.
            try:
                fallback={'schema':'n055-bounded-terminal-diagnostic-v1','status':'unavailable',
                          'original_failure':self.carrier.document(),'records':self.records,
                          'original_deadline':self.budget.deadline,'no_target_or_score_authority':True,
                          'diagnostic_only_not_authoritative_scientific_metadata':True}
                body=encoded(diagnostic_projection(fallback))
                if len(body)>65536:
                    body=encoded({'status':'unavailable','first_error_type':diagnostic_type(self.carrier.first[1]),
                                  'record_count':len(self.records),'error_count':len(self.carrier.failures),
                                  'diagnostic_extent_omitted':True,'full_original_objects_retained_in_supervisor':True})
            except BaseException as projection:
                self.carrier.fail(projection,'terminal-diagnostic-projection')
                # Fixed ASCII bytes require neither a formatter, a document()
                # callback nor the encoder that just failed. Same old reserve.
                body=b'{"status":"unavailable","diagnostic_projection_failed":true,"full_original_objects_retained_in_supervisor":true,"no_target_or_score_authority":true}'
            try:
                self.write('TERMINAL_FAILURE.json',body,reservation='external_terminal',emergency=True)
                self.carrier.durable=True
            except BaseException as secondary:
                self.carrier.fail(secondary,'external-terminal-failure');self.carrier.durable=False
            return False
