"""Stdlib bootstrap for original projector or an opaque candidate programme."""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys


def main():
    request_raw = Path('/request.json').read_bytes()
    request = json.loads(request_raw)
    mode = sys.argv[1]
    if mode == 'project':
        contract = Path('/source/CONTRACT.json').read_bytes()
        value = json.loads(contract)
        limits = value['packet_output_caps']
        command = [sys.executable,'-I','-B','/source/project.py','--contract','/source/CONTRACT.json',
                   '--contract-sha256',hashlib.sha256(contract).hexdigest(),'--out','/output']
    elif mode == 'candidate':
        limits = {'predictions.json':65536}
        command = [sys.executable,'-I','-B','/program/program.py','--input','/input','--out','/output']
    else:
        raise ValueError('Exact worker role')
    output = Path('/output')
    if list(output.iterdir()):
        raise ValueError('Fresh empty output')
    code = subprocess.run(command,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,close_fds=True).returncode
    files = {}
    for path in output.iterdir():
        if path.name not in limits:
            raise ValueError('Unlisted output')
        fd = os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or not 0 < before.st_size <= limits[path.name]:
                raise ValueError('Bounded ordinary output')
            with os.fdopen(fd,'rb',closefd=False) as stream:
                raw = stream.read(before.st_size+1)
            after = os.fstat(fd)
            if len(raw) != before.st_size or any(getattr(before,k) != getattr(after,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')):
                raise ValueError('Output changed during capture')
            files[path.name] = {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
        finally:
            os.close(fd)
    if code == 0 and set(files) != set(limits):
        raise ValueError('Successful worker requires complete output')
    result = (json.dumps({'schema':'neural022_worker_exit_v1','mode':mode,'exit_code':code})+'\n').encode()
    (output/'RESULT.json').write_bytes(result)
    files['RESULT.json'] = {'bytes':len(result),'sha256':hashlib.sha256(result).hexdigest()}
    manifest = {'schema':'osl_transport_output_manifest_v1','phase_id':request['phase_id'],
                'request_sha256':hashlib.sha256(request_raw).hexdigest(),'files':files}
    (output/'OUTPUTS.json').write_text(json.dumps(manifest,sort_keys=True,separators=(',',':'))+'\n')
    # The source-pinned trusted projector may return a preserved partial packet.
    # Allow archival only; the operator still requires its code 0 and all six files.
    if mode == 'project':
        return 0
    # Candidate-writable metadata is diagnostic; actual container exit is authoritative.
    return code if 0 <= code <= 125 else 125


if __name__ == '__main__':
    raise SystemExit(main())
