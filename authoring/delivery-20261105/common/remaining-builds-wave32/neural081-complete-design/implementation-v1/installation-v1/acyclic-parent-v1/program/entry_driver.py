"""Source-owned actual entry selection and original-clock startup accounting."""
import common as c
import authority

def start(operation,envelope,envelope_desc,source,source_files,run,initial_reads,cli):
    c.exact(envelope,('schema','source_manifest','controller','launch_request','outer_authority','outer_output','controller_entry','bootstrap_read_cap'))
    c.need(envelope['schema']=='neural081_selected_execution_envelope_v2'and c.typed_equal(envelope['source_manifest'],source),'complete exact actual acyclic execution envelope')
    limits=run['outer_limits']if operation=='outer'else run['whole_limits']
    budget=c.Budget(run['origin'],limits);c.need(budget.end==run['normal_endpoint'],'original whole endpoint')
    budget.charge('read_bytes',initial_reads);budget.charge('host_processes',1)
    c.need(envelope['bootstrap_read_cap']==int(cli['bootstrap_read_cap']),'same selected startup read ceiling')
    if operation=='outer':
        import outer
        return outer.execute(envelope,envelope_desc,source,source_files,run,budget)
    c.need(operation=='controller','source-owned selected operation')
    authority.run_allocation(run,budget)
    # Independent outer work has its own physical process/counters; reserve its
    # complete selected share here so the complete-study ledger cannot omit it.
    for key,value in run['outer_limits'].items():
        if key!='seconds':budget.charge(key,value)
    import controller
    return controller.run(envelope['controller'],source,source_files,budget)
