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
    if len(sys.argv)!=3 or sys.argv[2]!='predict':raise ValueError('exact memory/predict operands')
    observed(int(sys.argv[1]))
    args=['--input','/input/input.npz','--case','/input/case.json','--output','/output/predictions.npz']
    os.execv(sys.executable,[sys.executable,'-I','-B','/submission/program.py',*args])
if __name__=='__main__':main()
