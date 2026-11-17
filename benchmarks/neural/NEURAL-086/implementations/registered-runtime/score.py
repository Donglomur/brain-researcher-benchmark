"""Canonical NEURAL-086 scoring bridge; delegates the complete protected campaign."""
import argparse, hashlib, importlib.util, sys
from pathlib import Path
TASK='NEURAL-086'
SOURCE_BYTES=4348
SOURCE_SHA256='8c4c93b8905711da7b13b34200f68a1c1e7acad5695477c93560a35f7e38f58b'
def main(argv=None):
    root=Path(__file__).absolute().parent.parent/'zuco2-neural085-086-complete-v1'
    path=root/'score_campaign.py'
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):raise ValueError('ordinary shared score source required')
    before=path.stat()
    if before.st_nlink!=1 or before.st_size!=SOURCE_BYTES:raise ValueError('shared score source extent')
    with path.open('rb') as stream:raw=stream.read(SOURCE_BYTES+1)
    after=path.stat()
    if len(raw)!=SOURCE_BYTES or hashlib.sha256(raw).hexdigest()!=SOURCE_SHA256 or (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):raise ValueError('shared score source identity')
    if any(name=='zuco' or name.startswith('zuco.') for name in sys.modules):raise ValueError('fresh ZuCo scorer interpreter required')
    parser=argparse.ArgumentParser();parser.add_argument('--submission',required=True);parser.add_argument('--output',required=True);parser.add_argument('--review',required=True);parser.add_argument('--other-reserve-bytes',type=int,default=0)
    args=parser.parse_args(argv);args.task=TASK
    sys.path.insert(0,str(root))
    module=importlib.util.module_from_spec(importlib.util.spec_from_loader('_zuco2_canonical_score',loader=None));module.__file__=str(path)
    exec(compile(raw,str(path),'exec'),module.__dict__)
    return module.run(args)
if __name__=='__main__':main()
