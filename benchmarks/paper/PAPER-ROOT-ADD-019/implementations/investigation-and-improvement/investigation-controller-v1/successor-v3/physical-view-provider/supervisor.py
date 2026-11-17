"""Real supervisor dispatch; the independent observer owns worker processes.

No daemon is installed. Production startup requires independent deployment,
source/environment/peer admission. This module is not a scientific executor:
it forwards exact bytes/commands and observes its own actual process records.
"""
import base64
import os
import socket
import struct
from pathlib import Path
from wire import need, encode, decode, pin, body_pin, check_pin, Cleanup
from transport import Client, METHOD_CUTOFF, peer_identity, receive, deployment
from linux_backend import LinuxBackend

class ObserverExecutionClient(Client):
    role='observer'

class ForwardingProvider:
    """The provider endpoint forwards to the separately admitted observer PID."""
    def __init__(self, client):
        need(type(client) is ObserverExecutionClient,'concrete observer transport');self.client=client
    def read_committed_program(self, descriptor):
        r=self.client.request('read_committed_observed',{'descriptor':descriptor},self.client.ledger.origin,self.client.ledger.scientific)
        return base64.b64decode(r['body_base64'],validate=True)
    def stage_exact(self, context, files, view, binding, origin, deadline):
        cap=self.client.admission['max_message_bytes'];extent=sum(4*((len(v)+2)//3) for v in files.values())
        need(extent<=cap,'forwarded staged byte extent')
        with self.client.ledger.live(2*extent,'forward staged source'):
            r=self.client.request('stage_observed',{'context':context,'files_base64':{k:base64.b64encode(v).decode('ascii') for k,v in files.items()},
                'view':view,'binding':binding},origin,deadline)
        return r['token']
    def launch_exact(self, token, argv, binding, origin, deadline):
        return self.client.request('launch_observed',{'token':token,'argv':argv,'binding':binding},origin,deadline)
    def read_closed_output(self, context, name, offset, count):
        r=self.client.request('read_observed_output',{'context':context,'name':name,'offset':offset,'count':count},
            self.client.ledger.origin,self.client.ledger.scientific)
        return base64.b64decode(r['body_base64'],validate=True)

class OwnedObserver:
    def __init__(self, backend, *, source_environment_admission, independent_process_admission):
        need(type(backend) is LinuxBackend,'observer owns concrete Linux supervisor')
        check_pin(source_environment_admission);check_pin(independent_process_admission)
        self.backend=backend;self.ledger=backend.ledger;self.commitment=None;self.closed={}
        self.source_environment_admission=source_environment_admission
        self.independent_process_admission=independent_process_admission

    def commit_all_programs(self, freeze, origin, deadline):
        need(not self.backend.jobs and self.commitment is None,'commit before numeric process staging')
        need(set(freeze['programs'])==set(freeze['contexts'])=={'A/native','A/improvement','B/native','B/improvement'},'all four global programmes')
        captured={}
        for key,descriptor in freeze['programs'].items():captured[key]=body_pin(self.backend.read_committed_program(descriptor))
        self.commitment=pin({'freeze':freeze,'captured':captured})
        return {'commitment_digest':pin(freeze)['sha256'],'captured_sources':captured,'durable_source_seal':False,
            'all_four_independently_authored':False,'before_numeric_exposure':False,'authoring_views_verified':False,
            'current_supervisor_has_no_numeric_jobs':True,'unknown':['independent historical authoring/exposure evidence',
                'owner complete durable commitment journal'],'source_semantics_not_authenticated_by_hash':True}

    def close_job(self, context, job_id, result, primary, binding, origin, deadline):
        need(origin==self.ledger.origin and deadline==self.ledger.scientific,'original observation clock')
        self.ledger.tick('closeout');job=self.backend.jobs[context];need(job['binding']==binding,'same owned observed job')
        own=job.get('result');process=job.get('process')
        if process is None or own is None:
            return {'job_id':job_id,'binding_digest':binding,'origin_ns':origin,'finished_ns':self.ledger.clock(),
                'exit_code':None if process is None else process.poll(),'natural_exit':False,
                'forced_stop':job.get('forced_stop',False),'all_descendants_closed':process is None,
                'stream_eof':False,'source_unchanged':False,'view_isolation_verified':False,
                'ordinary_files_only':False,'parent_directories_fsynced':False,'unknown_foreign_custody':process is not None,
                'resources_complete':False,'resources':None,'inventory':[],
                'partial_stage':self.backend.store.stage_states.get(context),'phase':job.get('phase'),
                'selected_logical_accounting':self.ledger.report(),
                'unknown':job['unknown']+['complete process/capture closure unavailable'],'scientific_qualified':False}
        # This is the Popen owned by this independent observer process. An
        # untrusted producer result has no exit/EOF/custody fields to consult.
        need(process.poll() is not None,'own actual process closure record')
        facts=self.backend.cgroup_facts(job);need(not facts['populated'],'all cgroup descendants closed')
        self.backend.store.seal(context,cutoff='closeout');inventory=self.backend.inventory(job)
        need(result is None or result=={'index':job.get('index')},'only own exact index descriptor')
        dirs={Path(job['output'])}|{p.parent for p in Path(job['output']).rglob('*')}
        def sync_directory(directory):
            with Cleanup(self.ledger,job) as cleanup:
                fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
                cleanup.defer('close observed output directory',lambda:os.close(fd));os.fsync(fd)
        with Cleanup(self.ledger,job) as cleanup:
            for directory in reversed(sorted(dirs,key=str)):
                cleanup.defer('fsync observed output directory',lambda directory=directory:sync_directory(directory))
        streams={name:{'path':name+'.log',**body_pin(own[name])} for name in ('stdout','stderr')}
        receipt={'job_id':job_id,'binding_digest':binding,'origin_ns':origin,'finished_ns':self.ledger.clock(),
            'exit_code':own['exit_code'],'natural_exit':own['natural_exit'],'forced_stop':job.get('forced_stop',False),
            'all_descendants_closed':True,'stream_eof':own['stream_eof'],'source_unchanged':True,
            'ordinary_files_only':True,'parent_directories_fsynced':True,'inventory':inventory,**streams,
            'view_isolation_verified':False,'unknown_foreign_custody':True,'resources_complete':False,
            'resources':None,'observed_cgroup_facts':facts,'selected_logical_accounting':self.ledger.report(),
            'independent_process_admission':self.independent_process_admission,
            'source_environment_admission':self.source_environment_admission,
            'unknown':['owner complete joined physical/resource profile','actual fixed-mount/source/environment qualification'],
            'scientific_qualified':False}
        job['observer_closed']=True;job['inventory']=inventory;self.closed[context]=receipt
        return receipt

    def close_dispatch(self, binding, origin, deadline):
        self.ledger.tick('closeout')
        remaining=[k for k in self.backend.jobs if k not in self.closed]
        return {'binding_digest':binding,'origin_ns':origin,'finished_ns':self.ledger.clock(),
            'all_owned_descendants_closed':not remaining,'remaining_contexts':remaining,
            'complete_non_job_accounting':False,'non_job_resources':None,
            'selected_logical_accounting':self.ledger.report(),'unknown':['whole-operation independent resource/outer-exit qualification']}

    def record_failure(self, binding, descriptor, completed_prefix, origin, deadline):
        self.ledger.tick('closeout');raw=encode({'binding':binding,'failure':descriptor,'completed_prefix':completed_prefix,
            'origin_ns':origin,'scientific_deadline_ns':deadline,'own_observations':self.closed},1048576)
        self.ledger.reserve({'write_bytes':len(raw),'retained_bytes':len(raw)},'durable supervisor failure',cutoff='closeout')
        name='failure-'+body_pin(raw)['sha256']+'.json'
        with Cleanup(self.ledger) as cleanup:
            # Parent fsync receives an independent attempt even after a failed
            # write, file fsync or file close; no durable result then succeeds.
            cleanup.defer('fsync failure journal parent',lambda:os.fsync(self.backend.store.fd))
            fd=os.open(self.backend.store.root/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
            cleanup.defer('close failure journal',lambda:os.close(fd))
            view=memoryview(raw)
            while view:
                n=os.write(fd,view);need(n>0,'complete failure write');view=view[n:]
            os.fsync(fd)
        return {'path':name,**body_pin(raw),'durable':True,'outer_entry_exit_proven':False}

class ServerDispatcher:
    """Exact method dispatch, separately admitted local peer/operation envelope."""
    def __init__(self, role, backend, admission, ledger, controller_peer):
        need(role in ('provider','observer'),'server role')
        need(type(backend) is (ForwardingProvider if role=='provider' else OwnedObserver),'concrete server backend')
        self.role=role;self.backend=backend;self.admission=admission;self.ledger=ledger
        self.controller_peer=controller_peer;self.sequences={};self.finished=False

    def dispatch(self, request, peer):
        required={'schema','role','method','sequence','origin_ns','scientific_deadline_ns','closeout_deadline_ns',
                  'outer_deadline_ns','source_digest','authority_receipt','payload'}
        need(type(request) is dict and set(request)==required and request['schema']=='ach_supervisor_request_v1','exact operation envelope')
        method=request['method'];need(method in METHOD_CUTOFF,'fixed method')
        internal=method in ('stage_observed','launch_observed','read_observed_output','read_committed_observed')
        provider_methods={'stage_exact','launch_exact','read_closed_output','read_committed_program'}
        need(method=='finish_transport' or (method in provider_methods if self.role=='provider' else method not in provider_methods),'role-specific method allowlist')
        expected_peer=self.admission['peers']['provider'] if internal else self.controller_peer
        need(peer['uid']==expected_peer['uid'] and peer['pid']==expected_peer['pid'],'independently admitted calling process')
        need(request['role']==self.role and request['source_digest']==self.admission['source_digest'] and
             request['authority_receipt']==self.admission['authority_receipt'],'same independent source/authority operation')
        need((request['origin_ns'],request['scientific_deadline_ns'],request['closeout_deadline_ns'],request['outer_deadline_ns'])==
             (self.ledger.origin,self.ledger.scientific,self.ledger.closeout,self.ledger.outer),'original whole-operation cutoffs')
        identity=(peer['uid'],peer['pid']);need(type(request['sequence']) is int and request['sequence']>self.sequences.get(identity,0),'fresh request sequence')
        self.sequences[identity]=request['sequence'];self.ledger.tick(METHOD_CUTOFF[method])
        payload=request['payload'];need(type(payload) is dict,'plain exact method payload')
        if method=='finish_transport':
            need(not payload,'empty transport finish')
            if self.role=='observer':
                need(all(k in self.backend.closed for k in self.backend.backend.jobs),'all owned jobs closed before transport finish')
            self.finished=True
            return {'finish_requested':True,'outer_exit_observed':False,'scientific_qualified':False}
        base=self.backend.backend if internal else self.backend
        origin=self.ledger.origin;deadline=self.ledger.scientific
        if method in ('stage_exact','stage_observed'):
            need(set(payload)=={'context','files_base64','view','binding'},'exact stage request')
            files={k:base64.b64decode(v,validate=True) for k,v in payload['files_base64'].items()}
            stage=base.stage_exact(payload['context'],files,payload['view'],payload['binding'],origin,deadline)
            return {'context':payload['context'],'binding':payload['binding'],'token':stage}
        if method in ('launch_exact','launch_observed'):
            need(set(payload)=={'token','argv','binding'},'exact launch request')
            return base.launch_exact(payload['token'],payload['argv'],payload['binding'],origin,deadline)
        if method in ('read_closed_output','read_observed_output'):
            need(set(payload)=={'context','name','offset','count'},'exact output request')
            return {'body_base64':base64.b64encode(base.read_closed_output(**payload)).decode('ascii')}
        if method in ('read_committed_program','read_committed_observed'):
            need(set(payload)=={'descriptor'},'exact source request')
            return {'body_base64':base64.b64encode(base.read_committed_program(payload['descriptor'])).decode('ascii')}
        need(self.role=='observer' and not internal,'observer-only closure method')
        if method=='commit_all_programs':
            need(set(payload)=={'freeze'},'commit request');return base.commit_all_programs(payload['freeze'],origin,deadline)
        if method=='close_job':
            need(set(payload)=={'context','job_id','result','primary','binding'},'close job request')
            return base.close_job(**payload,origin=origin,deadline=deadline)
        if method=='close_dispatch':
            need(set(payload)=={'binding'},'dispatch close request');return base.close_dispatch(payload['binding'],origin,deadline)
        need(set(payload)=={'binding','descriptor','completed_prefix'},'failure request')
        return base.record_failure(**payload,origin=origin,deadline=deadline)

    def serve_connection(self, connection):
        peer=peer_identity(connection);cap=self.admission['max_message_bytes'];deadline=self.ledger.closeout
        with self.ledger.live(3*cap,'supervisor framed request/reply',cutoff='closeout'):
            extent=struct.unpack('!Q',receive(connection,8,self.ledger,deadline,'closeout'))[0];need(extent<=cap,'request extent before allocation')
            raw=receive(connection,extent,self.ledger,deadline,'closeout');request=decode(raw,cap)
            try:payload=self.dispatch(request,peer);status='ok'
            except BaseException as error:
                self.ledger.fail('supervisor dispatch',error);status='refused'
                payload={'type':type(error).__name__,'message':str(error)[:1024],'costs':self.ledger.report()}
            reply=encode({'request_pin':body_pin(raw),'source_digest':self.admission['source_digest'],
                'sequence':request.get('sequence'),'status':status,'payload':payload},cap)
            self.ledger.reserve({'write_bytes':len(reply)+8},'supervisor reply',cutoff='closeout')
            connection.sendall(struct.pack('!Q',len(reply))+reply)

def serve_installed(role, backend, endpoint, deployment_path, deployment_pin, ledger, controller_peer):
    """Actual daemon loop; disabled by the shipped deployment before bind."""
    admitted=deployment(deployment_path,deployment_pin,ledger,role)
    need(endpoint==admitted[role+'_endpoint'] and admitted['peers'][role]=={'pid':os.getpid(),'uid':os.getuid()},
         'exact independently installed daemon process')
    dispatcher=ServerDispatcher(role,backend,admitted,ledger,controller_peer)
    identity=None
    def unlink_owned_socket():
        if identity is not None:
            current=os.stat(endpoint,follow_symlinks=False)
            need((current.st_dev,current.st_ino)==(identity.st_dev,identity.st_ino),'only own socket cleanup')
            os.unlink(endpoint)
    with Cleanup(ledger) as cleanup:
        cleanup.defer('unlink independently identified owned socket',unlink_owned_socket)
        listener=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        cleanup.defer('close supervisor listener',listener.close)
        ledger.tick();need(not os.path.lexists(endpoint),'new exclusive socket endpoint')
        ledger.reserve({'write_bytes':4096,'retained_bytes':4096},'socket namespace metadata')
        listener.bind(endpoint)
        identity=os.stat(endpoint,follow_symlinks=False)  # Before chmod can fail.
        os.chmod(endpoint,0o600)
        listener.listen(1)
        while not dispatcher.finished:
            ledger.tick('closeout');listener.settimeout(max(.001,(ledger.closeout-ledger.clock())/1e9))
            connection,_=listener.accept()
            with Cleanup(ledger) as accepted:
                accepted.defer('close accepted supervisor connection',connection.close)
                dispatcher.serve_connection(connection)
        return {'transport_loop_completed':True,'outer_process_exit_observed':False,'scientific_qualified':False}
