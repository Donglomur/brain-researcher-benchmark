#!/usr/bin/env python3
"""Fetch only hash-pinned source/checkpoints and the two original public input NWBs.

Run only after an external resource reservation. This tool does not acquire test
truth or install packages. All acquired payloads belong outside the public repo.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import urllib.request

from prepare import ensure_external, sha

HERE = Path(__file__).resolve().parent


def fetch(url, destination, expected_bytes, expected_sha256):
    destination = Path(destination)
    if destination.is_symlink():
        raise ValueError('Refuse symbolic-link destination')
    if destination.exists():
        digest=sha(destination)
        if destination.stat().st_size == expected_bytes and digest == expected_sha256:
            return
        raise ValueError('Existing destination differs: ' + str(destination))
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_name(destination.name + '.partial')
    if temp.exists():
        raise ValueError('Inspect prior partial acquisition before retrying')
    digest = hashlib.sha256()
    length = 0
    try:
        with urllib.request.urlopen(url, timeout=120) as response, temp.open('xb') as out:
            while chunk := response.read(1024*1024):
                length += len(chunk)
                if length > expected_bytes:
                    raise ValueError('Download exceeded pinned size')
                digest.update(chunk)
                out.write(chunk)
        if length != expected_bytes or digest.hexdigest() != expected_sha256:
            raise ValueError('Download does not match immutable asset manifest')
        temp.replace(destination)
    except BaseException:
        # Keep the partial payload as failed-attempt evidence; operator owns cleanup/accounting.
        raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--destination', type=Path, required=True)
    p.add_argument('--assets', choices=['source','inputs','both'], default='both')
    a = p.parse_args()
    if HERE.is_relative_to(a.destination.resolve()) or a.destination.resolve().is_relative_to(HERE):
        raise ValueError('Payload staging must be outside implementation directory')
    ensure_external(a.destination)
    source = json.loads((HERE/'source_manifest.json').read_text())
    data = json.loads((HERE/'data_manifest.json').read_text())
    downloads=[]
    if a.assets in ('source','both'):
        for row in source['files']:
            downloads.append((f"https://raw.githubusercontent.com/mackelab/smc_rnns/{source['source_commit']}/{row['path']}",a.destination/'author'/row['path'],row))
    if a.assets in ('inputs','both'):
        for row in data['nwb_inputs']:
            downloads.append((row['download_url'],a.destination/'nwb/sub-Jenkins'/row['name'],row))
    print(json.dumps({'planned_payload_bytes':sum(row['bytes'] for _,_,row in downloads),
                      'external_reservation_required':True}),flush=True)
    for url,dest,row in downloads:
        fetch(url,dest,row['bytes'],row['sha256'])
        print(json.dumps({'asset':dest.name,'bytes':row['bytes'],'sha256':row['sha256']}),flush=True)


if __name__=='__main__':
    main()
