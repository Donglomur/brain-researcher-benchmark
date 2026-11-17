"""Concrete job composition over separate source-bound provider/observer clients."""
from ach_util import need,pin,pin_bytes,decode,require_pin,integer,exact_fields

class JobTransport:
    def __init__(self,provider,observer,ledger,controller_source_pin,limits):
        need(provider is not observer,'separate physical observer and provider')
        require_pin(controller_source_pin)
        self.provider,self.observer,self.ledger=provider,observer,ledger
        self.source_pin=controller_source_pin;self.limits=limits;self.contexts=set();self.records=[];self.bindings={};self.observations={}
        for name in ('index_bytes','output_bytes','files','failure_bytes'):integer(limits[name],1)

    def _failure(self,primary,secondary,context):
        descriptor={'context':context,'primary':{'type':type(primary).__name__,
            'message':str(primary).encode('utf-8')[:self.limits['failure_bytes']].decode('utf-8','replace')},
            'pending_authenticated_exchange':getattr(primary,'ach_measurement_exchange',None),
            'failed_observation':self.observations.get(context),
            'failed_observation_pin':pin(self.observations[context]) if context in self.observations else None,
            'secondary':[{'type':type(e).__name__,'message':str(e).encode('utf-8')[:self.limits['failure_bytes']].decode('utf-8','replace')}
                         for e in secondary], 'ledger':self.ledger.report()}
        try:setattr(primary,'ach_controller_failure',descriptor)
        except Exception:pass
        return descriptor

    def run(self,context,job_id,files,view,argv,purpose):
        try:return self._run(context,job_id,files,view,argv,purpose)
        except BaseException as error:
            if not hasattr(error,'ach_controller_failure'):
                self.ledger.fail(job_id+'/result_admission',error)
                descriptor=self._failure(error,[],context)
                if context in self.bindings:
                    try:self.observer.record_failure(self.bindings[context],descriptor,self.records,
                        self.ledger.origin,self.ledger.scientific)
                    except BaseException as secondary:
                        self.ledger.fail(job_id+'/result_failure_journal',secondary)
                        self._failure(error,[secondary],context)
            raise

    def _run(self,context,job_id,files,view,argv,purpose):
        need(context not in self.contexts,'fresh source-bound physical realm')
        self.contexts.add(context);self.ledger.tick()
        need(type(files) is dict and len(files)<=self.limits['files'],'complete bounded fixed-mount source/view files')
        need(type(argv) is list and argv and all(type(x) is str for x in argv),'literal command vector')
        binding=pin({'context':context,'job_id':job_id,'files':{k:pin_bytes(v) for k,v in files.items()},
            'view':view,'argv':argv,'purpose':purpose,'source_pin':self.source_pin,
            'origin_ns':self.ledger.origin,'deadline_ns':self.ledger.scientific})['sha256']
        self.bindings[context]=binding
        result=None;primary=None;secondary=[];observation=None
        try:
            self.ledger.tick()
            token=self.provider.stage_exact(context,files,view,binding,self.ledger.origin,self.ledger.scientific)
            self.ledger.tick() # Original cutoff after blocking staging and immediately before launch.
            result=self.provider.launch_exact(token,argv,binding,self.ledger.origin,self.ledger.scientific)
        except Exception as error:primary=error;self.ledger.fail(job_id+'/stage_or_launch',error)
        try:
            observation=self.observer.close_job(context,job_id,result,primary,binding,
                                                self.ledger.origin,self.ledger.scientific)
        except Exception as error:
            self.ledger.fail(job_id+'/independent_observation',error)
            if primary is None:primary=error
            else:secondary.append(error)
        if observation is not None:self.observations[context]=observation
        try:
            need(type(observation) is dict,'actual independent observation required')
            need(observation.get('job_id')==job_id and observation.get('binding_digest')==binding and
                 observation.get('origin_ns')==self.ledger.origin,
                 'same source/view/process/original-clock observation')
            # Never infer absent measurements or transfer producer Booleans into
            # independent custody. The admitted supervisor must own these facts.
            need(observation.get('resources_complete') is True and not observation.get('unknown'),
                 'complete independently measured operation accounting, not assumed zero')
            resources=observation['resources']
            exact_fields(resources,('read_bytes','write_bytes','retained_bytes','live_bytes'),
                         'complete independent job resource dimensions')
            for value in resources.values():integer(value)
            # Independent child physical counters and controller logical counters
            # are distinct named dimensions, preventing accidental double counting.
            charges={'observed_job_'+k:v for k,v in resources.items() if k!='live_bytes'}
            charges['observed_job_live_peak_bytes']=resources['live_bytes']
            self.ledger.observe(charges,job_id+'/independent_resources')
            need(type(observation.get('exit_code')) is int and observation['exit_code']==0 and
                 all(observation.get(k) is True for k in ('natural_exit','all_descendants_closed',
                    'stream_eof','parent_directories_fsynced','source_unchanged','view_isolation_verified',
                    'ordinary_files_only')) and observation.get('forced_stop') is False and
                 observation.get('unknown_foreign_custody') is False,
                 'actual independently observed natural-zero EOF descendants durability and source/view')
            finished=observation['finished_ns'];now=self.ledger.tick()
            need(type(finished) is int and self.ledger.origin<=finished<self.ledger.scientific and finished<=now,
                 'producer finished within original scientific cutoff')
        except Exception as error:
            self.ledger.fail(job_id+'/closure_admission',error)
            if primary is None:primary=error
            else:secondary.append(error)
        if primary is not None:
            descriptor=self._failure(primary,secondary,context)
            try:self.observer.record_failure(binding,descriptor,self.records,self.ledger.origin,self.ledger.scientific)
            except Exception as error:
                secondary.append(error);self.ledger.fail(job_id+'/durable_failure',error)
                self._failure(primary,secondary,context)
            raise primary
        exact_fields(result,('index',),'producer returns only immutable output index descriptor')
        descriptor=result['index'];exact_fields(descriptor,('path','bytes','sha256'),'output index descriptor')
        require_pin({k:descriptor[k] for k in ('bytes','sha256')})
        need(descriptor['bytes']<=self.limits['index_bytes'],'preventive output index cap')
        body=self.provider.read_closed_output(context,descriptor['path'],0,descriptor['bytes'])
        need(pin_bytes(body)=={k:descriptor[k] for k in ('bytes','sha256')},'closed output index identity')
        need(self.provider.read_closed_output(context,descriptor['path'],descriptor['bytes'],1)==b'',
             'closed index has no unindexed suffix')
        index=decode(body,self.limits['index_bytes'])
        exact_fields(index,('schema','job_id','outputs'),'generic immutable job index')
        # The independently observed source/view binding covers this index.
        # Embedding that digest inside its own input/argv hash would be circular.
        need(index['schema']=='ach_controller_job_index_v1' and index['job_id']==job_id,
             'same actual output invocation')
        need(type(index['outputs']) is dict and len(index['outputs'])<=self.limits['files'],'complete output inventory extent')
        need(type(observation['inventory']) is list and len(observation['inventory'])<=self.limits['files'],
             'complete independent inventory extent including index')
        inventory={d['path']:d for d in observation['inventory']}
        need(len(inventory)==len(observation['inventory']),'unique independent output paths')
        need(descriptor['path']=='RESULT_INDEX.json' and inventory.get('RESULT_INDEX.json')==descriptor,
             'index itself belongs to independently observed exact output inventory')
        need('EXECUTION.json' in index['outputs'],'trusted execution metadata required even for a failed training proposal')
        need(set(inventory)=={descriptor['path']}|{d['path'] for d in index['outputs'].values()},
             'complete output inventory, no unindexed result/model or extra output')
        need(all(name==d['path'] for name,d in index['outputs'].items()),'literal direct output identity')
        outputs={};total=0
        for name,d in index['outputs'].items():
            exact_fields(d,('path','bytes','sha256'),'immutable ordinary output descriptor')
            require_pin({k:d[k] for k in ('bytes','sha256')});total+=d['bytes']
            need(total<=self.limits['output_bytes'],'preventive complete output extent')
            need(d['path'] in inventory and inventory[d['path']]==d,'exact independently observed ordinary output')
        self.ledger.reserve({'retained_bytes':total},job_id+'/all closed output bodies')
        for name,d in index['outputs'].items():
            self.ledger.tick()
            raw=self.provider.read_closed_output(context,d['path'],0,d['bytes'])
            self.ledger.tick()
            need(pin_bytes(raw)=={k:d[k] for k in ('bytes','sha256')},'closed source/model/result bytes')
            need(self.provider.read_closed_output(context,d['path'],d['bytes'],1)==b'','closed output has exact end of file')
            outputs[name]=raw
        record={'context':context,'job_id':job_id,'binding_digest':binding,'purpose':purpose,
            'index_pin':pin(index),'observation_pin':pin(observation),'index':index,'observation':observation}
        self.records.append(record)
        return {'outputs':outputs,'record':record,'actual_external_entry_exit_still_required':True}
