"""Check observed cgroup limits before replacing this process with the program."""
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
    if len(sys.argv)!=2:raise ValueError('exact memory operand')
    observed(int(sys.argv[1]))
    import numpy,h5py
    if sys.version_info[:2]!=(3,12) or numpy.__version__!="2.2.6" or h5py.__version__!="3.13.0":raise ValueError("selected task runtime versions")
    os.execv(sys.executable,[sys.executable,'-I','-B','/submission/program.py','--input','/input','--output-report','/output/report.json','--output-claims','/output/claims.json'])
if __name__=='__main__':main()
