"""Complete routes with one original clock and independent failure channels."""
import argparse,json,time,os
from banc_runtime.codec import encode
from banc_runtime.resources import Limits
from .budget import Meter
from .source import inspect_source,load_source,STAGES
from .authority import admit
from .engine import execute
from .clock import AttemptClock,guard
from .custody import close_all
from .failures import FailureEnvelope,combine

LAST_FAILURE=None

def emit(raw,fd):
    view=memoryview(raw)
    while view:
        n=os.write(fd,view)
        if n<=0:raise OSError('short terminal publication')
        view=view[n:]

def main(argv=None,origin=None):
    global LAST_FAILURE
    clock=AttemptClock(origin);primary=None;result=None;meter=None
    p=argparse.ArgumentParser(description='Complete BANC source programme; deployment ships unconfigured.')
    p.add_argument('action',choices=('inspect','run','candidate')+STAGES)
    for name in ('program','output','deployment','deployment-sha256','review'):p.add_argument('--'+name)
    p.add_argument('--other-reserve-bytes',type=int);a=p.parse_args(argv)
    try:
        if a.action=='inspect':result=inspect_source()
        else:
            action='actor' if a.action=='candidate' else a.action
            for name in ('program','output','deployment','deployment_sha256','review','other_reserve_bytes'):
                if getattr(a,name) is None:raise ValueError('execution requires --'+name.replace('_','-'))
            source=load_source();bootstrap=Meter(Limits(32*1048576,8*1048576,1000000,1000000,1000,clock.entry_mono+60_000_000_000))
            ctx=admit(source,action,a.program,a.output,a.review,a.deployment,a.deployment_sha256,a.other_reserve_bytes,bootstrap,clock)
            l=ctx['deployment']['limits'];meter=Meter(Limits(l['read_bytes'],l['output_bytes'],l['row_count'],l['pair_work'],l['jobs'],clock.record['deadline_monotonic_ns']))
            meter.attempt_clock=clock;meter.cpu_seconds_limit=l['cpu_seconds'];meter.cpu_seconds_reserved=0
            meter.address_space_ceiling=l['address_space_bytes'];meter.file_bytes_ceiling=l['file_bytes']
            for report in (source['source_read_costs'],bootstrap.report()):
                meter.reserve_read(report['read_reserved']);meter.complete_read(report['read_completed'])
            guard(meter,'after_all_startup_admission');result=execute(ctx,action,meter)
            guard(meter,'before_directory_capability_retirement')
    except BaseException as exc:primary=FailureEnvelope(exc,'entry')
    # Every directory close is attempted once even when another close fails.
    for failure in close_all():
        primary=combine(primary,RuntimeError(json.dumps(failure,sort_keys=True)),'directory_close_ambiguous_no_retry')
    if primary is None:
        try:
            if meter is not None:guard(meter,'after_directory_retirement_before_final_encoding')
            raw=encode(result)+b'\n'
            if meter is not None:guard(meter,'after_final_encoding_before_terminal_publication')
            emit(raw,1)
            if meter is not None:guard(meter,'after_terminal_publication')
            # Final OS exit/stdio custody is deliberately left to the outer
            # runner; printed journals/results do not claim terminal closure.
            return 0
        except BaseException as exc:primary=FailureEnvelope(exc,'terminal_publication')
    LAST_FAILURE=primary.document()
    diagnostic={'status':'refused_or_failed','observations':LAST_FAILURE,'scientific_qualification':False,'terminal_success':False}
    try:emit(encode(diagnostic)+b'\n',2)
    except BaseException as exc:
        primary.add(exc,'secondary_terminal_diagnostic_publication');LAST_FAILURE=primary.document()
    return 2
