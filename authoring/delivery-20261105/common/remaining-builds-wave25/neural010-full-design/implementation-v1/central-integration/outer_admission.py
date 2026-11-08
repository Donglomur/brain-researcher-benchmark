"""Separate qualified caller's original-exit predicate; never central self-use.

The protected expected launch and post-exit approval registry are independent
deployment operands. This source performs no process launch or score computation.
"""

def admit(env,observed_pin,approved_registry_pin,expected,reader):
    p.exact(expected,('task_id','argv','working_directory','program','review','source_manifest',
                     'qualified_source_rows','central_receipt_path','original_origin','scientific_deadline',
                     'final_deadline','outer_deadline_monotonic'))
    u.need(expected['task_id']==p.TASK,'exact externally selected task')
    origin=u.finite(expected['original_origin']);end=u.finite(expected['outer_deadline_monotonic'])
    u.need(origin<u.finite(expected['scientific_deadline'])<=u.finite(expected['final_deadline'])<=end,'same selected original-clock chain')
    reader.tick(end)
    registry=p.read_pin(reader,approved_registry_pin)
    u.need(registry.get('schema')=='neural010-external-central-observer-approval-v1'
        and type(registry.get('approved_receipts'))is list,'separately protected independent observer registry')
    record=p.read_pin(reader,observed_pin)
    u.need(record.get('schema')=='neural010-independent-central-exit-v1'and p.same(record.get('expected'),expected)
        and u.digest(record)in registry['approved_receipts']and record.get('source_state_unchanged')is True,'independently selected exact post-exit observation')
    # Reuse original complete natural closure predicate, with an externally
    # preselected outer interval on the same origin, never the child own claim.
    class Clock:
        pass
    clock=Clock();clock.origin=origin;clock.end=end
    env['parent_observer'].natural(record['observation'],expected['argv'],clock)
    obs=record['observation']
    u.need(record['working_directory']==expected['working_directory'],'actual caller cwd')
    for name in ('stdout','stderr'):
        desc=record[name];env['c'].descriptor(desc,allow_empty=True)
        row=obs['streams'][name]
        u.need(type(row['bytes'])is int and row['bytes']==desc['bytes']and row['sha256']==desc['sha256'],'observed original full stream identity')
    u.need(record['stderr']['bytes']==0 and record['stderr']['sha256']==u.pin(b'')['sha256'],'no unobserved stderr or derived success')
    value=p.read_pin(reader,record['stdout'],65537)
    u.need(value.get('status')=='provisional_full_parent_completed_outer_exit_required'and value.get('task_id')==p.TASK
        and value.get('own_future_exit_established')is False and value.get('outer_deadline_monotonic')==end
        and value['receipt']['path']==expected['central_receipt_path'],'exact provisional stdout')
    receipt=p.read_pin(reader,value['receipt'],16777216)
    u.need(receipt.get('schema')=='neural010-central-provisional-completion-v1'and p.same(receipt.get('scope'),p.SCOPE)
        and receipt.get('own_future_exit_established')is False and receipt.get('new_score_computation')is False,'complete provisional original science receipt')
    for key in ('program','review','source_manifest','qualified_source_rows'):u.need(p.same(receipt[key],expected[key]),'exact independently expected '+key)
    u.need(receipt['actual_argv']==expected['argv']and receipt['working_directory']==expected['working_directory'],'actual source-bound invocation')
    for key in ('original_origin','scientific_deadline','final_deadline','outer_deadline_monotonic'):u.need(p.same(receipt[key],float(expected[key])),'exact endpoint '+key)
    u.need(type(receipt['channel_count'])is int and receipt['channel_count']==22
        and len(receipt['channel_records'])==22 and [r['phase']for r in receipt['phases']]==list(p.PHASES),'whole original22-exchange five-phase closure')
    for row in receipt['phases']:
        u.need(row['observed_original_root_exit']is True and row['scientific_deadline_admission_complete']is True,'no partial or late scientific phase')
    for name,pin in expected['qualified_source_rows'].items():
        u.relative(name);reader.opaque({'path':str(env['repo']/name),**u.only_pin(pin)},16777216)
    reader.tick(end)
    return {'schema':'neural010-independently-admitted-central-completion-v1','observed_receipt':observed_pin,
        'central_receipt':value['receipt'],'scope':p.SCOPE,'independently_observed_natural_exit':True,
        'scientific_result_qualification_conferred':False,'physical_IO_RSS_certified':False}
