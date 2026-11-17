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
        self.records=[];self.finalization=None
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
            try:self.budget.uncertain('terminal','terminal_publication_suffix',exc)
            except BaseException as secondary:self.carrier.fail(secondary,'terminal-publication-unknown-custody')
            return self._terminal_failure()

    def _terminal_failure(self):
        # Prepare a diagnostic-only record independently of the failed
        # scientific/ordinary encoder. Preserve the raw primary and every
        # secondary before attempting any projection or publication.
        try:
            fallback={'schema':'n057-bounded-terminal-diagnostic-v1','status':'unavailable',
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

    def complete_terminal(self, report):
        """Own full final construction before any clock/CPU/diagnostic callback.

        The large complete ledger is an earlier actual publication. The terminal
        refers to it; no records are removed to satisfy the unchanged 64 KiB cap.
        """
        if self.finalization is not None:
            try:require(False,'one original finalization attempt; no retry')
            except BaseException as exc:self.carrier.fail(exc,'terminal-repeat')
            return False
        attempt={'journal':self,'budget':self.budget,'carrier':self.carrier,
                 'report':report,'stage':'retained','snapshot':None,'body':None,
                 'record':None,'publication':None,'original_error':None,
                 'status':'attempted','costs_after_prefix_not_self_inclusive':True}
        self.finalization=attempt
        self.carrier.retain(attempt)
        try:
            attempt['stage']='snapshot'
            attempt['snapshot']=self.budget.snapshot()
            attempt['stage']='failure-diagnostics'
            failures=self.carrier.document()
            attempt['stage']='complete-cost-encoding'
            value={'schema':'n057-final-cost-prefix-v2','budget':attempt['snapshot'],
                   'failures':failures,'expected_cells':160,'expected_native_phases':320,
                   'timing':'before own cost-prefix publication; no record filtering',
                   'later_original_publication_and_cleanup_suffix':'not included; retained on same original Budget/Journal'}
            body=encoded(value);attempt['body']=body
            attempt['stage']='cost-prefix-reservation'
            self.budget.reserve('final_cost_prefix',len(body),1)
            attempt['stage']='cost-prefix-publication'
            index=len(self.records);attempt['record_ordinal']=index
            self.write('FINAL_COST_PREFIX.json',body,reservation='final_cost_prefix')
            record=self.records[index];attempt['record']=record
            require(record['path']=='FINAL_COST_PREFIX.json' and record['status']=='complete'
                    and record['closed'] and record['expected_bytes']==len(body)
                    and record['observed_bytes']==len(body)
                    and record['sha256']==hashlib.sha256(body).hexdigest(),
                    'actual complete original cost-prefix publication')
            publication={'path':record['path'],'bytes':record['observed_bytes'],
                         'sha256':record['sha256'],'original_journal_record_ordinal':index}
            attempt['publication']=publication
            attempt['stage']='later-cost-observation'
            point=self.budget.cost_point()
            # These are original cumulative observations, not a second ledger
            # added to the prefix. No full population is repeated here.
            tail={'original_origin':self.budget.origin,'original_deadline':self.budget.deadline,
                  'cumulative_point_after_cost_publication':point,
                  'live_bytes_at_point':self.budget.live_bytes,
                  'acknowledged_file_creations_at_point':self.budget.file_creation_acknowledgments,
                  'same_original_open_reservations':{k:dict(v) for k,v in self.budget.reservations.items()},
                  'required_unknown_count_at_point':len(self.budget.unknown),
                  'points_are_not_additive':True,
                  'terminal_self_write_and_later_cleanup':'not yet observed at encoding; same original reserve/owner retained, never zero',
                  'full_snapshot_is_earlier_prefix_not_whole_host_exit':True}
            attempt['stage']='bounded-terminal'
            terminal={'schema':'neural057-original-terminal-v2',
                      'status':'complete' if report is not None and self.carrier.first is None else 'failed_or_unavailable',
                      'report':report,'expected_cells':160,'expected_native_phases':320,
                      'cost_prefix':publication,'publication_tail':tail,'failures':failures,
                      'qualification_not_inferred_from_construction':True}
            ok=self.terminal(terminal)
            attempt['status']='terminal_published' if ok else 'terminal_failed'
            return ok
        except BaseException as exc:
            # Retain the exact original before any diagnostic/unknown projection.
            attempt['original_error']=exc;attempt['status']='failed'
            self.carrier.fail(exc,'complete-terminal:'+attempt['stage'])
            if 'record_ordinal' in attempt and attempt['record_ordinal']<len(self.records):
                attempt['record']=self.records[attempt['record_ordinal']]
            try:
                self.budget.uncertain('complete-terminal','final_cost_or_publication_suffix',
                                      exc,stage=attempt['stage'],prefix_published=attempt['publication'] is not None)
            except BaseException as secondary:self.carrier.fail(secondary,'terminal-unknown-custody')
            return self._terminal_failure()

