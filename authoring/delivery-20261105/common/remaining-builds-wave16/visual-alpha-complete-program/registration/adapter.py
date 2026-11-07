"""Central-route source gate. Registration never grants execution qualification."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat

TASK='PAPER-ROOT-ADD-014'
CONDITION='full_released_typed_inputs_portable_training_v1'


def source_gate(path,expected):
    p=Path(path).absolute()
    if any(x.is_symlink() for x in (p,*p.parents)):raise ValueError('ordinary registration source')
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        a=os.fstat(fd)
        if not stat.S_ISREG(a.st_mode) or a.st_nlink!=1 or a.st_size!=expected['bytes'] or a.st_size>65536:raise ValueError('bounded exact registration source')
        raw=os.read(fd,a.st_size+1);b=os.fstat(fd)
        fields=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_nlink)
        if fields(a)!=fields(b) or fields(a)!=fields(p.lstat()) or len(raw)!=a.st_size or hashlib.sha256(raw).hexdigest()!=expected['sha256']:raise ValueError('changed exact registration source')
        return json.loads(raw)
    finally:os.close(fd)


def admit_registration(value):
    if value.get('task_id')!=TASK or value.get('condition')!=CONDITION or value.get('phases')!=85:raise ValueError('exact complete program route')
    # False qualifications cannot be promoted by caller flags, fixture controls,
    # a source commit, a collection marker, or a selected benchmark ID.
    for key in ('runtime_qualified','scientific_qualified','submission_ready'):
        if value.get(key) is not False:raise ValueError('registration records source-only state; use separately reviewed qualification successor')
    return {'status':'refused_unqualified_complete_program','task_id':TASK,'condition':CONDITION,'phases':85,'candidate_operand_opened':False,'private_grading_called':False}


def main(argv=None):
    p=argparse.ArgumentParser()
    for n in ('program','output','review','source-sha256'):p.add_argument('--'+n,required=True)
    for n in ('source-bytes','other-reserve-bytes'):p.add_argument('--'+n,required=True,type=int)
    a=p.parse_args(argv)
    # No candidate/output/review path is inspected before the mandatory installed
    # qualification refusal. Root owns adding an independently reviewed successor.
    value=source_gate(Path(__file__).with_name('REGISTRATION.json'),{'bytes':a.source_bytes,'sha256':a.source_sha256})
    result=admit_registration(value);print(json.dumps(result,sort_keys=True));return 2
if __name__=='__main__':raise SystemExit(main())
