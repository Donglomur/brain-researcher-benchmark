"""Read-only inspection by default; production needs exact future root selection."""
from pathlib import Path
import argparse
import json
import sys
sys.dont_write_bytecode=True
from reve.objects import Reader,decode,digest
from reve.errors import require
from reve.roster import Scope


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('operation',choices=('inspect','execute'))
    parser.add_argument('--manifest-sha256')
    parser.add_argument('--selection-root')
    parser.add_argument('--driver-path');parser.add_argument('--driver-bytes',type=int);parser.add_argument('--driver-sha256')
    parser.add_argument('--authority-path');parser.add_argument('--authority-bytes',type=int);parser.add_argument('--authority-sha256')
    args=parser.parse_args()
    root=Path(__file__).absolute().parent
    if args.operation=='inspect':
        scope=Scope()
        print(json.dumps({'status':'BUILD_ONLY_UNQUALIFIED','task':'PAPER-paper-method-003','scope':scope.identity,
                          'families':13,'obligations':54,'stages':22,'datasets':10,'legacy_cases':2144,'fewshot_cases':1800,
                          'principal_products':113,'author_files':87,'private_history_records_not_distributed':155,'discrepancies':37,'open_gates':30,
                          'unexecuted_full_scientific_controls':50,'empirical_qualification':False,'submission_ready':False}))
        return
    require(False,'PUBLIC_SOURCE_ONLY: execution disabled; external source/license, data, models, authority and all 30 scientific gates remain unresolved')
    require(all((args.manifest_sha256,args.selection_root,args.driver_path,args.driver_bytes,args.driver_sha256,args.authority_path,args.authority_bytes,args.authority_sha256)),'explicit complete source/driver selection required')
    from reve.deadline import Window
    require(type(args.authority_bytes) is int and 0<args.authority_bytes<=8*1024**2,'bounded initial authority discovery')
    selection_reader=Reader(args.selection_root,args.authority_bytes+1,1)
    authority_pin={'path':args.authority_path,'bytes':args.authority_bytes,'sha256':args.authority_sha256}
    selection=selection_reader.json(authority_pin);window=Window(selection['valid_after'],selection['expires_at']);window.check()
    window.check()
    manifest_reader=Reader(root,4*1024**2,1,guard=window.check)
    manifest_raw=manifest_reader.capture('SOURCE_MANIFEST.json')
    window.check()
    require(digest(manifest_raw)==args.manifest_sha256,'implementation manifest identity')
    manifest=decode(manifest_raw)
    reader=Reader(root,sum(x['bytes']+1 for x in manifest['files'])+1,len(manifest['files'])+1,guard=window.check)
    for row in manifest['files']:reader.read(row)
    from reve.driver import run_selected
    out=run_selected(args.selection_root,{'path':args.driver_path,'bytes':args.driver_bytes,'sha256':args.driver_sha256},authority_pin,digest(manifest_raw),window=window)
    print(json.dumps(out))


if __name__=='__main__':main()
