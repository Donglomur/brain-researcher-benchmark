"""One original monotonic lifetime and separate physical/attributable cost ledgers."""
import time
from .common import require, finite, integer,diagnostic_type

class Budget:
    def __init__(self, origin, limits, clock=time.monotonic, cpu_origin=None):
        self.clock = clock
        self.origin = finite(origin)
        self.cpu_origin = time.process_time() if cpu_origin is None else finite(cpu_origin)
        self.limits = dict(limits)
        self.global_limits = dict(limits)
        self.active_cell = None
        self.cell_accounts = []
        self.action_deadlines = []
        self.boundary_errors = []
        for k in ('wall_seconds', 'cpu_seconds'):
            finite(limits[k], True)
        for k in ('read_bytes', 'write_bytes', 'live_bytes', 'files', 'model_calls', 'stream_bytes'):
            integer(limits[k], 1)
        self.deadline = origin + limits['wall_seconds']
        self.read_bytes = self.write_bytes = self.live_bytes = self.files = self.model_calls = self.stream_bytes = 0
        self.cpu = 0.0
        self.unknown = []
        self.reservations = {}
        self.operations = {}
        self.attributable = []
        self.resource_policy=None;self.resource_definition=None;self.native_unobserved=[]
        self.capacity_reservations={};self.capacity_events=[];self.file_creation_acknowledgments=0
        self.admission_failures=[];self.token_ledger=None;self.managed_failures=[]
    def bind_resource_policy(self,identity,definition):
        from .resource_policy import VERSION,EXCLUDED
        require(self.resource_policy is None and not self.operations,'policy bound before original physical execution')
        require(identity['version']==VERSION and definition['schema']==VERSION and definition['expected_unobserved_native_quantities']==list(EXCLUDED),'exact selected measured policy')
        self.resource_policy=dict(identity);self.resource_definition=definition
    def admit(self,stage,deadline=None):
        require(not self.unknown and not self.admission_failures,'required unknown or exceeded original envelope blocks dependent work: '+stage)
        self.check(stage,deadline)
    def uncertain(self,operation,quantity,error=None,**facts):
        # The original exception stays alive independently of fallible formatting.
        if error is not None:self.managed_failures.append((operation,quantity,error))
        self.unknown.append({'operation':operation,'quantity':quantity,'observed':None,**facts})
    def write_count(self,operation,value,maximum):
        if type(value)is int and 0<=value<=maximum:return value
        self.managed_failures.append((operation,'invalid_write_return',value))
        self.uncertain(operation,'managed_write_extent',reported_count=value if type(value)is int else None,reported_type=diagnostic_type(value),maximum=maximum)
        return None
    def failed_write(self,operation,error,maximum):
        self.managed_failures.append((operation,'original_write_error',error))
        # Only this exact builtin descriptor is trusted prefix evidence.
        # Unknown exception attributes/properties are never inspected.
        if type(error) is not BlockingIOError:
            self.uncertain(operation,'managed_write_extent',error,reason='no_safe_original_prefix_evidence')
            return None
        try:value=BlockingIOError.characters_written.__get__(error,BlockingIOError)
        except BaseException as secondary:
            self.uncertain(operation,'managed_write_extent',secondary,reason='builtin_prefix_evidence_unavailable')
            return None
        return self.write_count(operation,value,maximum)
    def file_created(self):self.file_creation_acknowledgments+=1
    def capacity(self):
        return (sum(v['bytes']for v in self.capacity_reservations.values()),sum(v['inodes']for v in self.capacity_reservations.values()))
    def reserve_capacity(self,name,nbytes,nfiles):
        integer(nbytes);integer(nfiles);require(name not in self.capacity_reservations,'one original live capacity reservation')
        rb,rf=self.reserved();cb,cf=self.capacity()
        require(self.live_bytes+rb+cb+nbytes<=self.limits['live_bytes'],'original live byte capacity')
        require(self.files+rf+cf+nfiles<=self.limits['files'],'original conservative live inode headroom')
        row={'name':name,'bytes':nbytes,'inodes':nfiles,'status':'reserved_live_capacity','cumulative_transfer_debit':False}
        self.capacity_reservations[name]=row;self.capacity_events.append(dict(row))
    def release_capacity(self,name):
        row=self.capacity_reservations.pop(name);self.capacity_events.append({**row,'status':'confirmed_absent_live_capacity_released'})
    def check(self, stage, deadline=None):
        local=self.active_cell['deadline'] if self.active_cell is not None else self.deadline
        require(self.clock() <= min([self.deadline, deadline or self.deadline, local,*self.action_deadlines]), 'deadline: '+stage)
        require(self.cpu + self.own_cpu() <= self.limits['cpu_seconds'], 'CPU allowance: '+stage)
        for k in ('read_bytes','write_bytes','live_bytes','files','model_calls','stream_bytes'):
            require(getattr(self,k)<=self.limits[k], 'original '+k+' allowance: '+stage)
    def own_cpu(self):
        return time.process_time()-self.cpu_origin
    def cost_point(self):
        return {'clock':self.clock(),'cpu_seconds':self.cpu+self.own_cpu(),'read_bytes':self.read_bytes,
                'write_bytes':self.write_bytes,'files':self.files,'model_calls':self.model_calls,'stream_bytes':self.stream_bytes}
    def action_deadline(self,seconds):
        local=self.active_cell['deadline'] if self.active_cell is not None else self.deadline
        return min([self.deadline,local,self.clock()+seconds,*self.action_deadlines])
    def action(self,deadline):
        return Action(self,deadline)
    def begin_cell(self,cell,limits,setup=None):
        require(self.active_cell is None,'no overlapping mutable cell allowance')
        setup=setup or {'wall_seconds':0.,'cpu_seconds':0.,'read_bytes':0,'write_bytes':0,'files':0,'model_calls':0,'stream_bytes':0}
        measured=('wall_seconds','cpu_seconds','read_bytes','write_bytes','model_calls','stream_bytes')+(('files',)if self.resource_policy is not None else())
        for k in measured:
            require(k in setup and setup[k] is not None and setup[k]>=0,'known complete standalone setup cost')
            require(k in limits and limits[k]>=setup[k],'standalone setup fits original matched cell allowance')
        base=self.cost_point();self.active_cell={'cell':cell,'baseline':base,'setup':dict(setup),'limits':dict(limits),
                                                  'deadline':min(self.deadline,base['clock']+limits['wall_seconds']-setup['wall_seconds']),'resource_policy':self.resource_policy}
        # Counters never reset. Effective limits are intersections of the original
        # global budget and the prospectively frozen current cell envelope.
        self.limits=dict(self.global_limits)
        for k in tuple(x for x in measured if x!='wall_seconds'):
            self.limits[k]=min(self.global_limits[k],base[k]+limits[k]-setup[k])
        self.admit('matched per-cell standalone setup admission')
    def finish_cell(self):
        require(self.active_cell is not None,'active original cell')
        current=self.active_cell
        try:
            end=self.cost_point();current['original_end']=end
            current['attributable']={k:current['setup'][k]+end[k]-current['baseline'][k] for k in ('cpu_seconds','read_bytes','write_bytes','model_calls','stream_bytes')+(('files',)if self.resource_policy is not None else())}
            current['attributable']['wall_seconds']=current['setup']['wall_seconds']+end['clock']-current['baseline']['clock']
            self.check('after complete original cell lifetime');current['within_allowance']=True
        except BaseException as exc:
            if 'original_end' not in current:self.unknown.append({'operation':'cell-finalization','cell':current['cell'],'quantity':'original_complete_cell_cost'})
            current['within_allowance']=False;current['original_error_type']=diagnostic_type(exc);raise
        finally:
            if not current.get('within_allowance',False):self.admission_failures.append({'stage':'original_cell_close','cell':current['cell'],'reason':'original cell envelope incomplete or exceeded'})
            self.cell_accounts.append(current);self.active_cell=None;self.limits=dict(self.global_limits)
    def reserved(self):
        return (sum(v['bytes'] for v in self.reservations.values()), sum(v['files'] for v in self.reservations.values()))
    def reserve(self, name, nbytes, nfiles):
        integer(nbytes); integer(nfiles)
        require(name not in self.reservations, 'unique reservation')
        rb, rf = self.reserved()
        cb,cf=self.capacity()
        require(self.live_bytes + rb + cb + nbytes <= self.limits['live_bytes'], 'reserve live bytes')
        require(self.files + rf + cf + nfiles <= self.limits['files'], 'reserve file slots')
        require(self.write_bytes + rb + nbytes <= self.limits['write_bytes'], 'reserve cumulative writes')
        self.reservations[name] = {'bytes': nbytes, 'files': nfiles}
    def admit_write(self, nbytes, reservation=None):
        integer(nbytes)
        if reservation is None:
            rb, rf = self.reserved()
            cb,cf=self.capacity()
            require(self.files + rf + cf + 1 <= self.limits['files'], 'ordinary file would steal reserved slot')
            require(self.live_bytes + rb + cb + nbytes <= self.limits['live_bytes'], 'ordinary live extent')
            require(self.write_bytes + rb + nbytes <= self.limits['write_bytes'], 'ordinary write extent')
        else:
            r = self.reservations[reservation]
            require(r['files'] >= 1 and r['bytes'] >= nbytes, 'owned reservation')
            r['files'] -= 1; r['bytes'] -= nbytes
        self.files += 1
    def written(self, count):
        integer(count); self.write_bytes += count; self.live_bytes += count
    def admit_read(self, count):
        require(self.read_bytes + integer(count) <= self.limits['read_bytes'], 'read allowance')
    def read(self, count):
        self.read_bytes += integer(count)
        require(self.read_bytes <= self.limits['read_bytes'], 'actual read allowance')
    def stream(self, count):
        self.stream_bytes += integer(count)
        require(self.stream_bytes <= self.limits['stream_bytes'], 'actual stream allowance')
    def physical(self, op_id, observation):
        require(op_id not in self.operations, 'original physical operation counted once')
        self.operations[op_id] = observation
        cpu = observation.get('cpu_seconds')
        if cpu is None:
            self.unknown.append({'operation': op_id, 'quantity': 'cpu_seconds'})
        else:
            self.cpu += finite(cpu)
        if observation.get('kind') in ('participant','reference'):
            # The present cgroup backend observes CPU/closure, not repeated
            # actor/provider logical I/O. Live tmpfs capacity is not cumulative
            # write usage. Preserve each unavailable quantity as unknown.
            if self.resource_policy is None:
                for quantity in ('read_bytes','write_bytes','files'):self.unknown.append({'operation':op_id,'quantity':'native_logical_'+quantity,'observed':None,'reason':'no selected measured policy or qualified total native observer'})
            else:
                from .resource_policy import unobserved
                require(observation.get('resource_policy')==self.resource_policy,'no mixed original native resource policy')
                self.native_unobserved.extend(unobserved(op_id,self.resource_policy))
                for quantity in ('wall_seconds','memory_peak_bytes'):
                    value=observation.get(quantity)
                    if value is None:self.unknown.append({'operation':op_id,'quantity':quantity,'observed':None})
                    else:finite(value);require(value>=0,'known original native '+quantity)
        self.model_calls += int(observation.get('kind') == 'investigator')
        require(self.model_calls <= self.limits['model_calls'], 'model call allowance')
    def attribute(self, cell, operation_ids, setup_ids):
        ids = list(dict.fromkeys([*setup_ids, *operation_ids]))
        require(all(i in self.operations for i in ids), 'attribution only from actual originals')
        self.attributable.append({'cell': cell, 'standalone_operation_ids': ids, 'separate_from_physical': True,
                                 'resource_policy':self.resource_policy,'native_expected_unobserved':[x for x in self.native_unobserved if x['operation']in ids]})
    def snapshot(self):
        return {'origin': self.origin, 'deadline': self.deadline, 'observed_elapsed': self.clock()-self.origin,
                'read_bytes': self.read_bytes, 'write_bytes': self.write_bytes, 'live_bytes': self.live_bytes,
                'files': self.files, 'cpu_seconds_known_subtotal': self.cpu+self.own_cpu(), 'controller_cpu_seconds':self.own_cpu(), 'unknown': list(self.unknown),
                'stream_bytes': self.stream_bytes, 'model_calls': self.model_calls,
                'open_reservations': dict(self.reservations), 'physical': self.operations,
                'standalone_attributable': self.attributable, 'matched_original_cell_accounts':self.cell_accounts,
                'active_original_cell':self.active_cell,'active_action_deadlines':list(self.action_deadlines),
                'boundary_errors':[{'stage':s,'type':diagnostic_type(e)} for s,e in self.boundary_errors],
                'original_token_ledger':None if self.token_ledger is None else{'used':dict(self.token_ledger.used),'records':list(self.token_ledger.records),'limits':self.token_ledger.limits},
                'resource_policy':self.resource_policy,'required_unknowns':list(self.unknown),'expected_unobserved_native_quantities':list(self.native_unobserved),
                'measured_regular_file_creation_attempts':self.files,'acknowledged_managed_file_creations':self.file_creation_acknowledgments,
                'native_live_capacity_reservations':dict(self.capacity_reservations),'native_capacity_events':list(self.capacity_events),
                'remaining_envelope_admission_failures':list(self.admission_failures),
                'managed_original_errors':[{'operation':op,'quantity':q,'type':diagnostic_type(e)}for op,q,e in self.managed_failures],'same_allowances_not_same_consumption':True,
                'ledgers_are_not_additive': True}

class Action:
    """Owned boundary closure without contextlib touching raw exception attributes."""
    __slots__=('budget','deadline','original')
    def __init__(self,budget,deadline):
        self.budget=budget;self.deadline=deadline;self.original=None
    def __enter__(self):
        budget=self.budget
        require(self.deadline<=budget.deadline,'action contained by original whole deadline')
        budget.action_deadlines.append(self.deadline)
        try:budget.check('before original action')
        except BaseException as original:
            self.original=original
            self.close()
            raise
        return None
    def __exit__(self,kind,original,traceback):
        self.original=original
        self.close()
        return False
    def close(self):
        budget=self.budget
        try:budget.check('after original action closure')
        except BaseException as secondary:
            budget.boundary_errors.append(('action_close',secondary))
            budget.admission_failures.append({'stage':'original_action_close','type':diagnostic_type(secondary)})
            if self.original is None:raise
        finally:budget.action_deadlines.pop()
