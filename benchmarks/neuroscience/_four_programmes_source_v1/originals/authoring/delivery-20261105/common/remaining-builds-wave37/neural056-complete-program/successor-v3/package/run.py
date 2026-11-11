"""Source inspection is safe; execution requires exact external selection."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('inspect')
    r=sub.add_parser('run');r.add_argument('--authority',required=True);r.add_argument('--authority-bytes',type=int,required=True)
    r.add_argument('--authority-sha256',required=True);r.add_argument('--profile',required=True);r.add_argument('--output',required=True);r.add_argument('--outer-run-deadline-ns',type=int,required=True)
    a=p.parse_args()
    if a.command=='inspect':
        from n056.core import read_json,capture
        source=Path(__file__).resolve().parent;m=read_json(source/'RUNTIME_MANIFEST.json')
        for row in m['files']:capture(source/row['path'],row['bytes'],row)
        print(json.dumps({'task':'NEURAL-056','full_people':10,'blocks_per_role':30,'roles':4,'source_members':len(m['files']),
                          'scientific_execution':False,'scientific_qualification':False}));return
    from n056.caller import run
    result=run(a.authority,{'bytes':a.authority_bytes,'sha256':a.authority_sha256},a.profile,a.output,a.outer_run_deadline_ns)
    print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()

