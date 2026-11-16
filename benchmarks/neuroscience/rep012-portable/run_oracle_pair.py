"""Concrete authored-oracle driver; execute only inside the admitted owner episode.

No model/provider, private reference or grader is loaded. Candidate source is
opaque on the host and staged through the same public tool API in both arms.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import stat
import types


def load_controller(size,digest):
    path=Path(__file__).absolute().with_name('controller.py')
    if type(size) is not int or not 0<size<=262144 or type(digest) is not str or not re.fullmatch('[0-9a-f]{64}',digest):
        raise ValueError('bounded exact controller source descriptor')
    if any(p.is_symlink() for p in (path,*path.parents)):
        raise ValueError('controller path and ancestry must not be symlinks')
    before=path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size!=size:
        raise ValueError('one ordinary controller with the selected exact extent')
    signature=lambda s:tuple(getattr(s,k) for k in ('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns'))
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        if signature(before)!=signature(os.fstat(fd)):raise ValueError('stable controller open')
        with os.fdopen(fd,'rb',closefd=False) as stream:body=stream.read(size+1)
        if signature(before)!=signature(os.fstat(fd)) or signature(before)!=signature(path.lstat()):
            raise ValueError('stable complete controller source')
    finally:os.close(fd)
    if len(body)!=size or hashlib.sha256(body).hexdigest()!=digest:
        raise ValueError('selected exact controller source required')
    module=types.ModuleType('_rep012_shared_runtime_controller'); module.__file__=str(path)
    exec(compile(body,str(path),'exec'),module.__dict__)
    return module


def stage_commands(body,python):
    """Bounded argv operands inside the candidate shell, never a host shell."""
    if type(body) is not bytes or not 0<len(body)<=262144:
        raise ValueError('one complete bounded frozen Python source')
    commands=[]
    for offset in range(0,len(body),8192):
        chunk=base64.b64encode(body[offset:offset+8192]).decode('ascii')
        mode='xb' if offset==0 else 'ab'
        code="import base64; f=open('/scratch/oracle.py',"+repr(mode)+"); f.write(base64.b64decode("+repr(chunk)+",validate=True)); f.close()"
        commands.append(shlex.join([python,'-I','-B','-c',code]))
    digest=hashlib.sha256(body).hexdigest()
    verify="import hashlib; assert hashlib.sha256(open('/scratch/oracle.py','rb').read()).hexdigest()=="+repr(digest)
    commands.append(shlex.join([python,'-I','-B','-c',verify]))
    wrapper=("import runpy,sys\nsys.argv=['/scratch/oracle.py','--input','/public','--output','/output/result.json']\n"
             "runpy.run_path('/scratch/oracle.py',run_name='__main__')\n").encode()
    code="import base64; f=open('/scratch/run_oracle.py','xb'); f.write(base64.b64decode("+repr(base64.b64encode(wrapper).decode())+",validate=True)); f.close()"
    commands.append(shlex.join([python,'-I','-B','-c',code]))
    if len(commands)>34 or any(len(x.encode())>16384 for x in commands):
        raise ValueError('staging within unchanged interactive API ceilings')
    return commands


def run_pair(c,options):
    program=c.plain(options.program)
    c.need(program.suffix=='.py','frozen Python oracle source, never a saved result')
    expected={'bytes':options.program_bytes,'sha256':options.program_sha256}
    body=c.captured(program,262144,expected)
    commands=stage_commands(body,c.PYTHON)
    pair=c.PairController(options.repository,Path(__file__).absolute().with_name('PACKET_BINDING.json'),
                          options.output_root,options.docker,options.docker_config,
                          options.docker_socket,options.nonce)
    pair.budget.write(pair.root/'ORACLE_SOURCE.json',c.encode({'path':str(program),**expected,
        'role':'same competent authored program in both arms; no model/code-benefit claim'}))
    try:
        for arm in ('A','B'):
            condition=pair.begin(arm)
            pair.budget.write(condition.folder/'RUNTIME_INVOCATION.json',c.encode(condition.runtime_invocation))
            for command in commands:
                reply=condition.call('terminal',command)
                c.need(reply['returncode']==0,'complete exact oracle staging')
            reply=condition.call('python','/scratch/run_oracle.py')
            c.need(reply['returncode']==0,'competent oracle exits successfully')
            frozen=condition.freeze()
            c.need(frozen['output']['status']=='captured','authored oracle must produce its result file')
        barrier=pair.finish()
    except BaseException as error:
        for condition in pair.conditions.values():
            if not condition.closed and condition.cid is not None:
                condition.failure('authored-oracle driver',error)
        raise
    return {'barrier':str(pair.root/'PAIR_BARRIER.json'),'barrier_sha256':
            hashlib.sha256(c.encode(barrier)).hexdigest(),'runtime_profile':c.RUNTIME_PROFILE,
            'private_grading_started':False,'scientific_qualification':False}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('repository','output-root','docker','docker-config','docker-socket','nonce','program',
                 'program-sha256','controller-sha256'):
        parser.add_argument('--'+name,required=True)
    for name in ('program-bytes','controller-bytes'):
        parser.add_argument('--'+name,required=True,type=int)
    args=parser.parse_args(argv)
    c=load_controller(args.controller_bytes,args.controller_sha256)
    print(json.dumps(run_pair(c,args),sort_keys=True))


if __name__=='__main__': main()
