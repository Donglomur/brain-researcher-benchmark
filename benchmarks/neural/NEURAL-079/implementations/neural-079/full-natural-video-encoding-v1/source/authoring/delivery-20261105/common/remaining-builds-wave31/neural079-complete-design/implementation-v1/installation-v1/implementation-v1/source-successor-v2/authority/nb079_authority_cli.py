"""Actual separately admitted CLI. Imports do not start authority or feeder."""
import argparse
import os
from nb079_launch_contract import canonical,require
from nb079_authority_io import bounded_encode,integer,secondary
from nb079_authority_service import AuthorityService
from nb079_authority_feeder import CredentialFeeder


def arguments(argv=None):
    p=argparse.ArgumentParser(allow_abbrev=False)
    p.add_argument('--mode',choices=('authority','feeder'),required=True)
    p.add_argument('--independently-enabled',action='store_true')
    for name in ('policy','request'):
        p.add_argument('--'+name,required=True);p.add_argument('--'+name+'-bytes',type=int,required=True);p.add_argument('--'+name+'-sha256',required=True)
    for name in ('origin','scientific','closeout','outer'):
        p.add_argument('--'+name+'-ns',type=int,required=True)
    for name in ('maximum-policy-bytes','maximum-request-bytes','maximum-bootstrap-read-bytes'):
        p.add_argument('--'+name,type=int,required=True)
    p.add_argument('--source-fd',type=int)
    return p.parse_args(argv)


def main(argv=None):
    a=arguments(argv)
    require(a.independently_enabled is True,'independent execution enabling required before any operational effect')
    require((a.mode=='feeder')==(a.source_fd is not None),'source FD only selected for sole feeder')
    bootstrap={'original_clock':{name:getattr(a,name+'_ns') for name in ('origin','scientific','closeout','outer')},
        **{name:getattr(a,name) for name in ('maximum_policy_bytes','maximum_request_bytes','maximum_bootstrap_read_bytes')}}
    descriptors={name:{'path':getattr(a,name),'pin':{'bytes':getattr(a,name+'_bytes'),'sha256':getattr(a,name+'_sha256')}} for name in ('policy','request')}
    obj=None
    try:
        if a.mode=='authority':
            obj=AuthorityService(descriptors['policy'],descriptors['request'],execution_enabled=True,bootstrap=bootstrap);result=obj.serve();phase='outer'
        else:
            obj=CredentialFeeder(descriptors['policy'],descriptors['request'],a.source_fd,execution_enabled=True,bootstrap=bootstrap);result=obj.run();phase='scientific'
        raw=bounded_encode({'schema':'nb079_authority_cli_terminal_v1','mode':a.mode,'status':'complete','result':result},obj.io.encoding)+b'\n'
        obj.capture.counters.charge({'write_bytes':len(raw),'log_bytes':len(raw)},'full original CLI stdout frame before output',phase)
        done=0
        while done<len(raw):
            obj.clock.tick(phase);n=os.write(1,memoryview(raw)[done:done+obj.io.limits['block_bytes']]);require(type(n) is int and 0<n<=min(obj.io.limits['block_bytes'],len(raw)-done),'full actual CLI stdout')
            done+=n;obj.capture.counters.observed('write_bytes',n)
        obj.clock.tick(phase);return result
    except BaseException as error:
        # Rich failed prefixes are retained by real source classes/artifacts.
        # No secret, exception text or unbounded traceback is published here.
        if obj is not None:
            obj.close(error)
            frame=canonical({'schema':'nb079_authority_cli_terminal_v1','mode':a.mode,'status':'failed_or_unknown','failure_type':type(error).__name__})+b'\n'
            try:
                obj.capture.counters.charge({'write_bytes':len(frame),'log_bytes':len(frame)},'typed diagnostic stderr frame','outer')
                done=0
                while done<len(frame):
                    obj.clock.tick('outer');n=os.write(2,memoryview(frame)[done:]);require(type(n) is int and 0<n<=len(frame)-done,'bounded diagnostic stderr');done+=n;obj.capture.counters.observed('write_bytes',n)
            except BaseException as other:secondary(error,other,'typed CLI diagnostic')
        raise


if __name__=='__main__':
    try:main()
    except BaseException:
        # Construction may fail before a selected logging ledger exists: no
        # uncharged fallback traceback/body. Caller retains actual exit/streams.
        raise SystemExit(1)
