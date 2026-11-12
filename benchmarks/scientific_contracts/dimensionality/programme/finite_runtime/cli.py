"""CLI for the ordinary file ABI, retaining bootstrap and post-entry failures."""
import argparse
import os
import sys
from pathlib import Path
from .common import encode,error_record
from .entry import run

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest',required=True)
    parser.add_argument('--output-dir',required=True)
    parser.add_argument('--condition',default=None)
    args=parser.parse_args(argv)
    # Fixed bootstrap closure is independent of scientific allowance. No caller
    # manifest, input descriptor, primary or participant source is read here.
    root=Path(args.output_dir);root.mkdir(parents=True,exist_ok=True)
    fd=os.open(root/'BOOTSTRAP_COMPLETION.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    reserve=65536;os.ftruncate(fd,reserve);primary=None;secondary=[];result=None
    try:result=run(args.manifest,args.output_dir,args.condition)
    except BaseException as exc:primary=exc
    closure={'schema':'finite_bootstrap_completion_v1','status':'failed' if primary else 'complete',
        'result':result,'primary':error_record(primary) if primary else None,
        'bootstrap_reserved_bytes':reserve,'scientific_execution_not_inferred':True,
        'ordinary_original_job_closures_are_separate':True}
    try:
        body=encode(closure,reserve-1)+b'\n';os.lseek(fd,0,os.SEEK_SET)
        sent=0
        while sent<len(body):
            n=os.write(fd,body[sent:])
            if n<=0:raise OSError('zero bootstrap closure write')
            sent+=n
        os.ftruncate(fd,sent);os.fsync(fd)
    except BaseException as exc:secondary.append(error_record(exc))
    finally:
        try:os.close(fd)
        except BaseException as exc:secondary.append(error_record(exc))
    # The original primary is never replaced with an output/cleanup exception.
    output={'status':closure['status'],'primary':closure['primary'],'secondary':secondary,
            'completion_path':str(root/'BOOTSTRAP_COMPLETION.json')}
    sys.stdout.buffer.write(encode(output)+b'\n');sys.stdout.buffer.flush()
    return 1 if primary or secondary else 0

if __name__=='__main__':raise SystemExit(main())
