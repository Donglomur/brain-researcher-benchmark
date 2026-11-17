"""Explicit bounded acquisition of all exact pinned EDF sources; no preparation/model.

Already verified files are reused. A failure retains only a named partial until
the next explicit invocation; no partial file can satisfy preparation pins.
"""
import argparse
import hashlib
from pathlib import Path, PurePosixPath
import urllib.request
import urllib.parse
import io_contract as io


def acquire(lock,root,max_bytes):
    rows=lock['records'];io.need(lock['version']=='1.0.0' and len(rows)==686,'full release only')
    io.need(len({r['path'] for r in rows})==686 and sum(r['bytes'] for r in rows)<=max_bytes,'explicit full source budget')
    root.mkdir(parents=True,exist_ok=True);root=root.resolve();receipt=[]
    for r in rows:
        rel=PurePosixPath(r['path']);url='https://physionet.org/files/chbmit/1.0.0/'+urllib.parse.quote(str(rel),safe='/')
        io.need(not rel.is_absolute() and '..' not in rel.parts and r['url'] in (url,urllib.parse.unquote(url)),'exact primary release URL')
        dest=root/rel;io.need(dest.resolve().is_relative_to(root),'staging boundary');dest.parent.mkdir(exist_ok=True)
        if not dest.exists():
            partial=dest.with_name(dest.name+'.partial');digest=hashlib.sha256();size=0
            with urllib.request.urlopen(url,timeout=60) as response,partial.open('xb') as out:
                io.need(response.geturl()==url,'no redirect to unpinned host/path')
                while True:
                    block=response.read(1048576)
                    if not block:break
                    size+=len(block);io.need(size<=r['bytes'],'download exact size cap');digest.update(block);out.write(block)
            io.need(size==r['bytes'] and digest.hexdigest()==r['sha256'],'publisher size/SHA256 required')
            partial.rename(dest);dest.chmod(0o444)
        from edf_adapter import verify
        verify(dest,r);receipt.append({'path':r['path'],'bytes':r['bytes'],'sha256':r['sha256']})
    return {'task_id':io.TASK,'files':receipt,'source_bytes':sum(r['bytes'] for r in rows),'models_fit':0,'empirical_scores':0}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('lock','staged','receipt'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--max-bytes',type=int,required=True);a=p.parse_args()
    io.write(a.receipt,acquire(io.strict(io.read(a.lock,1000000)),a.staged,a.max_bytes))
