"""Explicit full-condition N062 operator; the central one-program runner stays disabled.

Every invocation supplies the genuine independently selected root/config, grant,
trusted-key pins and full limits. This source issues none of those authorities.
Both candidate F/I scripts are required by the original closed programme config.
"""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import argparse,json

def run_operator(config,config_pin,grant,trusted_key,trusted_key_pin,output,limits):
    # This fixed private source directory is installed with all original28 roles.
    # Bootstrap imports have the same trusted-source prerequisite as programme.py;
    # no input body is opened here before the original execute creates its Owner.
    private=Path(__file__).absolute().parent/'source'/'private'
    sys.path.insert(0,str(private))
    try:
        from programme import execute
        return execute(config,config_pin,grant,trusted_key,trusted_key_pin,output,limits)
    finally:
        # Restore only this inserted element; no candidate code is loaded here.
        if sys.path and sys.path[0]==str(private):sys.path.pop(0)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','config-pin','grant','trusted-key','trusted-key-pin','output','limits'):
        p.add_argument('--'+name,required=True)
    a=p.parse_args()
    # Inline ordinary pins/limits are trusted operator arguments, never issuers.
    # The original source performs all closed-field, signature and resource checks.
    private=Path(__file__).absolute().parent/'source'/'private'
    sys.path.insert(0,str(private))
    try:
        from delivery_io import decode
        config_pin=decode(a.config_pin.encode())
        key_pin=decode(a.trusted_key_pin.encode())
        limits=decode(a.limits.encode())
    finally:
        if sys.path and sys.path[0]==str(private):sys.path.pop(0)
    report=run_operator(a.config,config_pin,a.grant,a.trusted_key,key_pin,a.output,limits)
    print(json.dumps({'status':report['status'],'full_job_count':report['full_job_count'],
                     'phase_count':report['phase_count'],'qualified':False}))
    return 0

if __name__=='__main__':raise SystemExit(main())

