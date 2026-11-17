"""Trusted complete coordinator subprocess; public operation is cli.py run."""
import argparse,hashlib,json,os,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from eegpt.protocol import need,decode,encode,observation,HandleCustody
from eegpt.programme import Programme,OperationCustody

def main(custody=None):
    owner=OperationCustody() if custody is None else custody
    try:
        parser=argparse.ArgumentParser();parser.add_argument('--operation',choices=('programme','prepare_assets'),required=True);parser.add_argument('--configuration',required=True);parser.add_argument('--configuration-sha256',required=True);parser.add_argument('--origin-ns',type=int,required=True);parser.add_argument('--deadline-ns',type=int,required=True);args=parser.parse_args();need(0<=args.origin_ns<=time.monotonic_ns()<=args.deadline_ns,'original parent window before configuration');path=Path(args.configuration);need(path.is_absolute() and not path.is_symlink(),'original absolute configuration')
        with HandleCustody('worker_configuration') as owned:
            fd=owned.own_fd(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'configuration')
            st=os.fstat(fd);need(st.st_size<=16777216,'bounded whole operation configuration');parts=[];left=st.st_size+1
            while left:
                need(time.monotonic_ns()<=args.deadline_ns,'original deadline before child configuration chunk');chunk=os.read(fd,min(left,65536));parts.append(chunk);left-=len(chunk);need(time.monotonic_ns()<=args.deadline_ns,'original deadline after child configuration chunk')
                if not chunk:break
            raw=b''.join(parts);need(len(raw)==st.st_size and hashlib.sha256(raw).hexdigest()==args.configuration_sha256,'exact original configuration bytes')
        if args.operation=='programme':
            programme=Programme(Path(__file__).resolve().parent,decode(raw),origin=args.origin_ns,deadline=args.deadline_ns,custody=owner)
            result=programme.operate()
        else:
            from eegpt.data_preparation import build_assets
            from eegpt.budget import Budget
            from cli import scope
            config=decode(raw);result=build_assets(config,scope(),Budget(config['limits'],origin=args.origin_ns,deadline=args.deadline_ns,label='original complete raw asset construction'))
        need(time.monotonic_ns()<=args.deadline_ns,'original deadline before child result publication');sys.stdout.buffer.write(encode({'status':'original_operation_returned','result':result}));sys.stdout.buffer.flush();need(time.monotonic_ns()<=args.deadline_ns,'original deadline after child result publication');return 0
    except BaseException as exc:
        owner.fail('programme_worker_original_operation_or_return',exc)
        owner.attempt('programme_worker_original_final_ledger',owner.ledger)
        raise owner.refusal() from owner.original_exception


def failure_document(owner,exc):
    # Same owner and ledger survive the actual child boundary. Neither a fresh
    # Programme nor a successful synthetic terminal can stand in for them.
    owner.fail('programme_worker_failure_return',exc)
    owner.attempt('programme_worker_failure_ledger',owner.ledger)
    return {'status':'original_operation_failed','failure':owner.record['original_failure'],'original_operation_custody':owner.record}


if __name__=='__main__':
    raise SystemExit('Public inspection-source copy: scientific coordinator execution is unavailable; use inspect.py inspect.')
    original_owner=OperationCustody()
    try:status=main(original_owner)
    except BaseException as exc:
        packet=failure_document(original_owner,exc)
        try:sys.stderr.buffer.write(encode(packet));sys.stderr.buffer.flush()
        except BaseException as publication_error:
            original_owner.fail('programme_worker_stderr_failure_publication',publication_error)
            raise
        raise SystemExit(2)
    raise SystemExit(status)
