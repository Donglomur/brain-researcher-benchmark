"""Captured role entry. Actual gate admission precedes all operational operands."""
import json,time

def main(config,load,launch_account):
    context={'origin':config['origin'],'deadline':config['bootstrap_deadline'],'read_cap':config['source_read_cap'],'read_reserved':0,'read_observed':0,'attempted_paths':[]}
    captured=None;pre=None;b=None
    try:
        captured=load(config['source_root'],config['manifest_path'],config['manifest'],context)
        from core import need,Budget,capture,parse,canonical,descriptor
        pre=Budget(config['origin'],config['bootstrap_deadline'],8<<20,0)
        desc=config['authority'];descriptor(desc['pin']);need(desc['pin']['bytes']<=2<<20,'bounded selected authority')
        raw,_=capture(canonical(desc['path']),desc['pin'],2<<20,pre,readonly=True);a=parse(raw)
        from authority import selected,qualify
        role=config['role'];selected(a,captured['pin'],config['origin'],role)
        need(a['roots']['source']==config['source_root'],'selected captured source root')
        end=a['clock']['production_end']if role in('prepare','worker')else a['clock']['readback_end']
        r=a['resources'];b=Budget(config['origin'],end,r['observer_read_bytes']if role=='observe'else r['host_read_bytes'],r['observer_write_bytes']if role=='observe'else r['host_write_bytes'])
        b.reserve_read(context['read_reserved']+launch_account['reserved']+pre.read_bytes)
        gates=qualify(a,captured['pin'],config['origin'],role,b)
        captured.update(authority_pin=desc['pin'],authority_descriptor=desc,manifest_path=config['manifest_path'],gates=gates)
        if role=='prepare':
            from preparation.prepare import run
            result=run(a,b,captured)
        elif role=='worker':
            from controller import run
            result=run(a,captured,b)
        elif role=='observe':
            from outer import observe
            result=observe(a,captured,b)
        elif role=='grade':
            from grade import execute
            result=execute(a,captured,config['grading'],b)
        else:raise ValueError('no arbitrary operational role')
        b.tick();return result
    except BaseException as error:
        prior=getattr(error,'failure_record',None)
        def cost(x):return None if x is None else {'origin':x.origin,'deadline':x.deadline,'read_reserved':x.read_bytes,'write_reserved':x.write_bytes}
        error.failure_record={'source_accounting':context,'launch_accounting':launch_account,'authority_budget':cost(pre),'role_budget':cost(b),'cause':prior,'actual_runtime_qualified':False}
        raise
