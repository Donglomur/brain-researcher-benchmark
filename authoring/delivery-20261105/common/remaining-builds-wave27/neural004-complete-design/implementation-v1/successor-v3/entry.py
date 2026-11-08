"""Concrete host bootstrap, independent deployment and source admissions required.

This module does not select a provider, read a credential, install a dependency
or start science on import. The qualified host passes an already authenticated
configuration body and an opaque credential only to selected actor methods.
"""
from pathlib import Path
from .common import fields,need,check_pin,read_body,Bodies
from .context_budget import ScopedLedger
from .bindings import authenticate_runtime
from .authority import Authorities
from .physical.transport import ProviderClient,ObserverClient
from .execution import JobTransport
from .controller import Programme

def construct(config,trusted_config_pin,repository_root,operator_seed):
    from .common import pin
    need(pin(config,16*1048576)==trusted_config_pin,'independently selected exact deployment configuration')
    fields(config,('schema','execution_enabled','run_id','source_root','runtime_sources','source_pin','authorities','clock',
        'logical_limits','body_root','body_cap','transport','job_limits','worker','python','policies','profile'))
    need(config['schema']=='neural004_complete_deployment_v1' and config['execution_enabled'] is True,'no production deployment selected by shipped source')
    clock=config['clock'];fields(clock,('origin_ns','scientific_ns','closeout_ns','outer_ns'))
    ledger=ScopedLedger(config['logical_limits'],clock['origin_ns'],clock['scientific_ns'],clock['closeout_ns'],clock['outer_ns'])
    check_pin(config['source_pin']);authenticate_runtime(config['source_root'],config['runtime_sources'],config['source_pin'],ledger)
    authority=Authorities(config['authorities'],config['source_pin'],config['run_id'],ledger)
    t=config['transport'];fields(t,('deployment_path','deployment_pin','provider_endpoint','observer_endpoint'))
    provider=ProviderClient(t['provider_endpoint'],t['deployment_path'],t['deployment_pin'],ledger)
    observer=ObserverClient(t['observer_endpoint'],t['deployment_path'],t['deployment_pin'],ledger)
    need(provider.admission['source_digest']==config['source_pin']['sha256'],'same source identity across controller/provider/observer')
    transport=JobTransport(provider,observer,ledger,config['source_pin'],config['job_limits'])
    bodies=Bodies(config['body_root'],ledger,config['body_cap'])
    w=config['worker'];fields(w,('path','bytes','sha256'));worker=read_body(Path(config['source_root'])/w['path'],{k:w[k] for k in ('bytes','sha256')},ledger,w['bytes'])
    need(w['path']=='candidate_worker.py','fixed generated worker source')
    return Programme(config['policies'],authority,ledger,bodies,transport,worker,{k:w[k] for k in ('bytes','sha256')},config['python'],config['source_pin'],operator_seed,config['profile'])

def start_supervisor(role,backend,endpoint,deployment_path,deployment_pin,ledger,controller_peer):
    """Actual independently installed server loop; requires real peer/PID admission."""
    from .physical.supervisor import serve_installed
    return serve_installed(role,backend,endpoint,deployment_path,deployment_pin,ledger,controller_peer)
