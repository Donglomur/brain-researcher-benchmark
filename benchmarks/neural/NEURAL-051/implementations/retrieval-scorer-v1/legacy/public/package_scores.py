"""Package six already-written scores; no execution, fitting, private data or scoring."""
import argparse,hashlib,json
from pathlib import Path
from io_utils import capture,decode,write_json
from protocol import SUBJECTS,ROIS

def package(directory,roster):
    expected=[f'sub-{p}_{r}' for p in SUBJECTS for r in ROIS]
    if set(roster)!=set(expected):raise ValueError('complete public roster')
    root=Path(directory)
    if root.is_symlink() or not root.is_dir() or {p.name for p in root.iterdir()}!={k+'.npy' for k in expected}:raise ValueError('exact six input score files, no existing manifest')
    files={}
    for k in expected:
        _,sha=capture(root/(k+'.npy'),50_000_000)
        files[k]={'file':k+'.npy','sha256':sha}
    digest=hashlib.sha256(json.dumps(roster,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()).hexdigest()
    return {'schema':'neural051-scores-v1','roster_sha256':digest,'files':files}
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--directory',required=True);a.add_argument('--roster',required=True);v=a.parse_args()
    roster=decode(capture(v.roster,3_000_000)[0]);write_json(Path(v.directory)/'submission.json',package(v.directory,roster))
