"""Typed receipt validation, not native qualification or a source of authority.

Only the concrete guard reads kernel state and issues custody capabilities. These
pure validators let its consumer reject diagnostic receipts before scoring.
"""
import json
from .custody import canonical, digest, CustodyError
from .resources import CandidateCaps
from .oom_witness import WitnessError,validate_protection_receipt


class OutcomeError(RuntimeError):
    pass


_SEAL = object()


class _Outcome:
    __slots__ = ('_raw', '_classification', '_reasons')

    def __init__(self, seal, receipt, classification, reasons):
        if seal is not _SEAL:
            raise OutcomeError('use the exact receipt validator')
        object.__setattr__(self, '_raw', canonical(receipt))
        object.__setattr__(self, '_classification', classification)
        object.__setattr__(self, '_reasons', tuple(reasons))

    def __setattr__(self, name, value):
        raise OutcomeError('validated outcomes are immutable')

    @property
    def classification(self): return self._classification

    @property
    def reasons(self): return self._reasons

    @property
    def original_receipt(self): return json.loads(self._raw)

    def require_scoreable(self):
        if self.classification == 'infrastructure_invalid':
            raise OutcomeError('; '.join(self.reasons))
        return self

    def to_dict(self):
        return {'schema': 'n073_validated_outcome_v2', 'kind': type(self).__name__,
                'classification': self.classification, 'reasons': list(self.reasons),
                'original_receipt': self.original_receipt,
                'validation_scope': 'receipt semantics; actual native custody remains the guard obligation'}


class ProcessOutcome(_Outcome): pass
class AggregateOutcome(_Outcome): pass


def _hash_valid(row, key='receipt_digest'):
    return isinstance(row, dict) and isinstance(row.get(key), str) and row[key] == digest({k:v for k,v in row.items() if k != key})


def _nonnegative_int(x): return type(x) is int and x >= 0


def valid_violation(v):
    """Exact selected ceiling; no arbitrary exception name is exhaustion evidence."""
    if not isinstance(v, dict): return False
    caps = CandidateCaps()
    limits = {'wall_ns':caps.wall_ns, 'cpu_ns':caps.cpu_ns, 'private_rss_bytes':caps.private_rss_bytes,
              'private_rss_conservative_memory_peak':caps.private_rss_bytes, 'writable_bytes':caps.writable_bytes,
              'model_calls':caps.model_calls, 'input_tokens':caps.input_tokens, 'output_tokens':caps.output_tokens,
              'output_tokens_reserved':caps.output_tokens, 'tool_calls':caps.tool_calls,
              'aggregate_memory_oom_events':0}
    d = v.get('dimension')
    if d == 'aggregate_memory_oom':
        e = v.get('events')
        return isinstance(e,dict) and all(_nonnegative_int(n) for n in e.values()) and e.get('oom',0)+e.get('oom_kill',0)>0
    return (d in limits and _nonnegative_int(v.get('used')) and type(v.get('cap')) is int
            and v['cap'] == limits[d] and v['used'] > v['cap'])


def monitor_event_valid(event):
    return (_hash_valid(event,'digest') and _nonnegative_int(event.get('index'))
            and isinstance(event.get('previous'),str) and len(event['previous'])==64
            and isinstance(event.get('body'),dict))


def monitor_exhaustion_valid(event):
    if not monitor_event_valid(event) or event.get('kind')!='violation': return False
    b=event['body'];v=b.get('violation');o=b.get('observation')
    if not valid_violation(v) or not isinstance(o,dict): return False
    d=v['dimension']
    fields={'cpu_ns':'total_context_cpu_ns','private_rss_conservative_memory_peak':'memory_peak_bytes','writable_bytes':'allocated_scratch_bytes'}
    if d in fields:return o.get(fields[d])==v['used']
    if d=='wall_ns':return _nonnegative_int(b.get('started_ns')) and o.get('monotonic_ns',-1)-b['started_ns']==v['used']
    return d=='aggregate_memory_oom' and o.get('memory_events')==v['events']


def ledger_exhaustion_valid(event, context_id):
    return (_hash_valid(event,'digest') and event.get('context_id')==context_id
            and event.get('kind')=='violation' and valid_violation(event.get('values')))


def observation_valid(row):
    fields=('monotonic_ns','aggregate_cpu_ns','guardian_cpu_upper_bound_ns','guardian_tick_ns_ceiling',
            'total_context_cpu_ns','memory_current_bytes','memory_peak_bytes','allocated_scratch_bytes','populated')
    return (isinstance(row,dict) and all(_nonnegative_int(row.get(k)) for k in fields)
            and row['populated'] in (0,1) and row['guardian_tick_ns_ceiling']>0
            and row['memory_peak_bytes']>=row['memory_current_bytes']
            and row['total_context_cpu_ns']>=row['aggregate_cpu_ns']+row['guardian_cpu_upper_bound_ns']
            and isinstance(row.get('memory_events'),dict)
            and all(_nonnegative_int(v) for v in row['memory_events'].values()))


def classify_process(receipt, *, context_id):
    if not isinstance(receipt,dict):raise OutcomeError('receipt must be a concrete mapping')
    reasons=[]
    if not _hash_valid(receipt): reasons.append('process receipt digest invalid')
    if receipt.get('schema')!='n073_process_original_outcome_v1' or receipt.get('context_id')!=context_id:
        reasons.append('process schema/context mismatch')
    if receipt.get('qualification_invalid') or receipt.get('resource_reclassification'):
        reasons.append('process qualification/capacity reclassification')
    if receipt.get('receipt_persistence_error'):reasons.append('process receipt persistence failed')
    if receipt.get('capture_complete') is not True:reasons.append('process capture incomplete')
    if type(receipt.get('returncode')) is not int:reasons.append('process leader termination unproven')
    if not isinstance(receipt.get('capture_bytes'),dict) or set(receipt['capture_bytes'])!={'stdout','stderr'} or not all(_nonnegative_int(x) for x in receipt['capture_bytes'].values()):
        reasons.append('process capture extents invalid')
    term=receipt.get('termination')
    allowed={'natural','candidate_memory_exhaustion','candidate_budget_exhaustion','candidate_scratch_exhaustion'}
    if term not in allowed:reasons.append('unexpected/infrastructure process termination')
    category='infrastructure_invalid' if reasons else ('completed' if term=='natural' and receipt['returncode']==0 else 'candidate_failure')
    return ProcessOutcome(_SEAL,receipt,category,reasons)


def classify_aggregate(receipt, *, context_id):
    if not isinstance(receipt,dict):raise OutcomeError('receipt must be a concrete mapping')
    reasons=[]
    if not _hash_valid(receipt):reasons.append('aggregate receipt digest invalid')
    if receipt.get('schema')!='n073_actual_aggregate_close_v3' or receipt.get('context_id')!=context_id:
        reasons.append('aggregate schema/context mismatch')
    for name in ('aggregate_failure','resource_reclassifications','closure_errors','unresolved_provider_usage','process_invalid_outcomes'):
        if receipt.get(name):reasons.append(name)
    if receipt.get('populated')!=0 or type(receipt.get('populated')) is not int:reasons.append('aggregate drain unproven')
    if receipt.get('monitor_returncode')!=0 or type(receipt.get('monitor_returncode')) is not int:reasons.append('monitor nonzero/missing termination')
    if type(receipt.get('broker_expected')) is not bool:reasons.append('broker expectation absent')
    # The durable monitor's OOM survival contract is joined to this exact
    # runtime/configuration/PID/leaf. A metadata validator grants no native
    # capability; the guard must have produced the actual writer/readback proof.
    protection=None
    try:
        protection=validate_protection_receipt(receipt.get('oom_protection_receipt'),
            context_id=context_id,config_digest=receipt.get('monitor_config_digest'),
            runtime_digest=receipt.get('monitor_runtime_digest'),contract_digest=receipt.get('oom_contract_digest'),
            monitor_identity=receipt.get('monitor_identity'),monitor_pid=receipt.get('monitor_pid'))
    except (WitnessError,CustodyError,TypeError,ValueError,KeyError) as exc:
        reasons.append('monitor OOM protection missing/invalid: '+str(exc))
    terminal=receipt.get('monitor_terminal_event');stop=receipt.get('monitor_stop')
    if protection is not None:
        if (not isinstance(terminal,dict) or terminal.get('config_digest')!=receipt['monitor_config_digest']
            or terminal.get('oom_protection_digest')!=protection['digest']):
            reasons.append('terminal monitor OOM protection/configuration join mismatch')
        original=receipt.get('original_exhaustion_event')
        if original is not None and (not isinstance(original,dict)
            or original.get('config_digest')!=receipt['monitor_config_digest']
            or original.get('oom_protection_digest')!=protection['digest']):
            reasons.append('original exhaustion OOM protection/configuration join mismatch')
    if not monitor_event_valid(terminal):reasons.append('missing/invalid durable terminal monitor evidence')
    elif terminal.get('context_id')!=context_id:reasons.append('monitor terminal context mismatch')
    elif stop=='requested':
        if terminal.get('kind')!='stopped':reasons.append('monitor normal stop not durable')
    elif stop=='exhaustion_completed':
        original=receipt.get('original_exhaustion_event')
        if not monitor_exhaustion_valid(original) or original.get('context_id')!=context_id or original.get('config_digest')!=terminal.get('config_digest'):reasons.append('native exhaustion source invalid')
        elif terminal.get('kind')!='exhausted_drained' or terminal['body'].get('violation_digest')!=original['digest']:
            reasons.append('exhaustion drain not joined to original violation')
        if any(type(terminal['body'].get(k)) is not int or terminal['body'][k]!=0 for k in ('candidate_populated','broker_populated')):
            reasons.append('exhaustion leaf drain unproven')
    else:reasons.append('unexpected/forced monitor close')
    required={'aggregate_failure','resource_reclassifications','closure_errors','unresolved_provider_usage','process_invalid_outcomes',
              'final_meter_error','resource_violation','original_exhaustion_event','broker_closure'}
    if not required.issubset(receipt):reasons.append('aggregate diagnostic fields absent')
    if monitor_event_valid(terminal) and not observation_valid(terminal['body'].get('observation')):
        reasons.append('terminal monitor counters incomplete/invalid')
    final=receipt.get('final_observation')
    if not observation_valid(final) or final.get('populated')!=0:reasons.append('final native observation missing/drain incomplete')
    if (observation_valid(final) and
        final['memory_events'].get('oom',0)+final['memory_events'].get('oom_kill',0)>0
        and stop!='exhaustion_completed'):
        reasons.append('final kernel OOM lacks authoritative exhausted monitor closure')
    err=receipt.get('final_meter_error')
    if err and (not isinstance(err,dict) or err.get('type')!='BudgetExceeded' or not valid_violation(receipt.get('resource_violation'))):
        reasons.append('final meter infrastructure failure')
    violation=receipt.get('resource_violation')
    if violation is not None and not valid_violation(violation):reasons.append('unrecognized resource violation')
    if receipt.get('broker_expected') is True:
        broker=receipt.get('broker_closure')
        if not _hash_valid(broker,'digest') or broker.get('context_id')!=context_id or broker.get('populated')!=0:
            reasons.append('broker closure missing/invalid')
        else:
            if protection is None or broker.get('oom_protection_digest')!=protection['digest']:
                reasons.append('broker drain OOM protection join mismatch')
            transport=broker.get('transport_receipt')
            if not _hash_valid(transport) or transport.get('context_id')!=context_id or transport.get('capture_complete') is not True or transport.get('unresolved_usage'):
                reasons.append('broker original transport/capture invalid')
    category='infrastructure_invalid' if reasons else ('candidate_failure' if violation or stop=='exhaustion_completed' else 'completed')
    return AggregateOutcome(_SEAL,receipt,category,reasons)
