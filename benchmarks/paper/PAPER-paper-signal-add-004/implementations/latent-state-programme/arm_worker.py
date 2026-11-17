"""Common candidate process/envelope entry. Contains no author/scorer method.

The actual immutable candidate program is committed before any scientific input
is opened. The external Docker provider, not this process, attests termination,
isolation, resource enforcement and final output capture.
"""
import argparse
import hashlib
from pathlib import Path
import subprocess
import sys
from core import encoded, need
from safe_io import capture, strict, new_json, pin


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--program',required=True)
    parser.add_argument('--program-sha256',required=True);args=parser.parse_args()
    raw=capture('/request.json',1048576);request=strict(raw)
    need(request['role'] in ('A','B') and request['action'] in ('native_attempt','held_attempt'),
         'Candidate role and scientific output family')
    program=capture(args.program,1048576)
    need(hashlib.sha256(program).hexdigest()==args.program_sha256,'Global pre-data candidate source commitment')
    loader='import sys,runpy; p=sys.argv.pop(1); sys.path.insert(0,"/source"); sys.argv[0]=p; runpy.run_path(p,run_name="__main__")'
    result=subprocess.run([sys.executable,'-I','-c',loader,args.program,'--request','/request.json',
                           '--case','/input/CASE.json','--output','/output'],check=False)
    need(result.returncode==0,'Candidate returned a complete successful program')
    need(capture(args.program,1048576)==program,'Immutable candidate source through execution')
    output=Path('/output')
    if request['action']=='native_attempt':
        need((output/'CAPTURE.json').is_file(),'Complete native observable manifest required')
        return
    files={};total=0;r=request['resources']
    need((output/'MODEL.json').is_file(),'Complete fixed-family HMM parameters required')
    # The two wrapper files are exclusively created after the candidate returns.
    need(not (output/'RESULT.json').exists() and not (output/'OUTPUTS.json').exists(),
         'Candidate cannot prewrite trusted wrapper completion records')
    new_json(output/'RESULT.json',{'candidate_return_code':result.returncode,
                                 'submitted_model':'MODEL.json','execution_attested_here':False})
    for p in sorted(output.rglob('*')):
        need(not p.is_symlink(),'No candidate output links')
        if p.is_file():
            body=capture(p,r['max_file_bytes']);files[str(p.relative_to(output))]=pin(body);total+=len(body)
    need(len(files)<=r['max_files'] and total<=r['max_output_bytes'],'Complete bounded candidate outputs')
    manifest={'schema':'osl_transport_output_manifest_v1','phase_id':request['phase_id'],
              'request_sha256':hashlib.sha256(raw).hexdigest(),'files':files}
    need(len(encoded(manifest))<=r['manifest_bytes'],'Complete immutable output manifest fits')
    need(len(files)+1<=r['max_files'] and total+len(encoded(manifest))<=r['max_output_bytes'],'Envelope included in complete output allocation')
    new_json(output/'OUTPUTS.json',manifest)


if __name__=='__main__':
    main()
