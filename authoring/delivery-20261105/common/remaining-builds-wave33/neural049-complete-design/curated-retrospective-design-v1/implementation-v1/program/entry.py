"""Captured concrete roles; exact external qualification precedes resource effects."""
import time


def main(config, load, launch_account):
    started = time.monotonic()
    context = {'origin':config['origin'],'deadline':config['bootstrap_deadline'],
               'read_cap':config['source_read_cap'],'read_reserved':0,'read_observed':0,'attempted_paths':[]}
    captured = pre = budget = None
    limit = {'attempted':False,'returned':False,'successful_clock_close':False}
    try:
        captured = load(config['source_root'],config['manifest_path'],config['manifest'],context)
        from core import Budget, need, capture, parse, canonical, descriptor, finite
        role = config['role']; need(role in ('worker','observe','grade'), 'explicit complete programme role')
        pre = Budget(config['origin'],config['bootstrap_deadline'],8<<20,0)
        d = config['authority']; descriptor(d['pin'])
        # The external launcher must independently select/authenticate this
        # authority path. Its bytes cannot authenticate its own selected name.
        raw,_ = capture(canonical(d['path']),d['pin'],2<<20,pre,readonly=True)
        a = parse(raw)
        from authority import qualify
        need(a.get('active') is True, 'inactive source-only construction')
        need(a['clock']['origin'] == config['origin'] and a['roots']['source'] == config['source_root'],
             'same inherited origin and captured source root')
        end = a['clock']['production_end'] if role == 'worker' else a['clock']['readback_end']
        need(config['bootstrap_deadline'] == end, 'unchanged selected role deadline; no clock extension')
        r = a['resources']; budget = Budget(config['origin'],end,r['host_read_bytes'],r['host_write_bytes'])
        budget.reserve_read(context['read_reserved']+launch_account['reserved']+pre.read_bytes)
        gates = qualify(a,captured['pin'],budget)
        need(started <= budget.tick() < started+120., 'local source-startup cap, not production-origin reset')
        # Even a late grade is bounded by the ORIGINAL readback endpoint. The
        # lazy captured importer keeps that endpoint, not a 120s lifetime.
        import resource
        budget.tick(); limit['attempted'] = True
        resource.setrlimit(resource.RLIMIT_AS,(r['host_live_bytes'],r['host_live_bytes']))
        limit['returned'] = True; budget.tick(); limit['successful_clock_close'] = True
        captured.update(authority_pin=d['pin'],authority_descriptor=d,manifest_path=config['manifest_path'],gates=gates)
        if role == 'worker':
            from controller import collect
            result = collect(a,captured,budget,gates)
        elif role == 'observe':
            from outer import observe
            result = observe(a,captured,budget)
        else:
            from grade import execute
            result = execute(a,captured,config['grading'],budget)
        budget.tick(); return result
    except BaseException as error:
        prior = getattr(error,'failure_record',None)
        def costs(b):
            return None if b is None else {'origin':b.origin,'deadline':b.deadline,
                'read_reserved':b.read_bytes,'write_reserved':b.write_bytes}
        error.failure_record = {'source_accounting':context,'launch_accounting':launch_account,
            'authority_budget':costs(pre),'role_budget':costs(budget),'resource_limit':limit,'cause':prior,
            'no_automatic_retry':True,'physical_usage_not_inferred':True}
        raise
