"""Source-frozen operator controller descriptors, never candidate-selected code.

The calling wrapper must hardcode its reviewed profile and freeze both this
closure and the actual controller. A descriptor is identity, not authorization.
"""
from pathlib import Path
import hashlib,re,stat,sys
ROOT=Path(__file__).resolve().parents[5]


def validate_controller(value,argv,check_bytes=True):
    if type(value)is not dict or set(value)!={'path','bytes','sha256'}:
        raise ValueError('Exact trusted controller descriptor')
    rel=value['path'];size=value['bytes'];sha=value['sha256']
    if type(rel)is not str or not re.fullmatch(r'authoring/[A-Za-z0-9_+.-]+(?:/[A-Za-z0-9_+.-]+)*\.py',rel)or any(x in('.', '..')for x in Path(rel).parts):
        raise ValueError('Canonical authoring Python controller only')
    if type(size)is not int or not 1<=size<=262144 or type(sha)is not str or not re.fullmatch('[a-f0-9]{64}',sha):
        raise ValueError('Bounded exact source identity')
    path=ROOT/rel
    if type(argv)is not list or len(argv)<2 or not all(type(x)is str and not any(c in x for c in ('\0','\n','\r'))for x in argv)or argv[:2]!=[sys.executable,str(path)]:
        raise ValueError('Exact Python and frozen trusted controller argv')
    if check_bytes:
        if any(x.is_symlink()for x in(path,*path.parents)):raise ValueError('No linked trusted controller')
        s=path.lstat()
        if not stat.S_ISREG(s.st_mode)or s.st_nlink!=1 or s.st_size!=size:raise ValueError('Exact ordinary single-link source file')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=sha:raise ValueError('Trusted controller source changed')
    return path


def descriptor_for(relative):
    """Used only by the fixed generated interruption fixture, not user input."""
    if relative!='authoring/shared-program-ownership-v3/interrupt_fixture.py':raise ValueError('Fixture identity only')
    p=ROOT/relative;value={'path':relative,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    validate_controller(value,[sys.executable,str(p)])
    return value
