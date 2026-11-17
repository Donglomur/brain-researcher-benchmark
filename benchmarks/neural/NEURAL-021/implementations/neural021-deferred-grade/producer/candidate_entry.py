"""Observed resource gate then the same candidate in fit or batch infer mode."""
import os,sys
from pathlib import Path

def observed(memory):
    root=Path('/sys/fs/cgroup')
    def need(ok):
        if not ok:raise ValueError('observed candidate cgroup policy')
    need(os.getuid()==65534)
    need((root/'memory.max').read_text().strip()==str(memory))
    need((root/'memory.swap.max').read_text().strip()=='0')
    quota,period=map(int,(root/'cpu.max').read_text().split());need(quota==period and period>0)
    need((root/'pids.max').read_text().strip()=='64')

def main():
    if len(sys.argv)!=3 or sys.argv[2] not in ('fit','infer'):raise ValueError('exact memory and phase operands')
    observed(int(sys.argv[1]));phase=sys.argv[2]
    import numpy
    if sys.version_info[:3]!=(3,12,8) or numpy.__version__!='2.2.6':raise ValueError('selected runtime versions')
    argv=[sys.executable,'-I','-B','/submission/program.py','--phase',phase,'--input','/input','--output','/output']
    if phase=='infer':argv+=['--state','/state/state.bin']
    os.execv(sys.executable,argv)
if __name__=='__main__':main()
