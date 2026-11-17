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
    if len(sys.argv)!=3 or sys.argv[2] not in ('fit','infer'):raise ValueError('exact memory/mode operands')
    observed(int(sys.argv[1]))
    if sys.argv[2]=='fit':args=['fit','--input','/input','--out','/output/model.bin']
    elif sys.argv[2]=='infer':args=['infer','--input','/input','--model','/model/model.bin','--out','/output/predictions.json']
    else:args=['--input','/input','--out','/output/predictions.json','--mode',sys.argv[2]]
    os.execv(sys.executable,[sys.executable,'-I','-B','/submission/program.py',*args])
if __name__=='__main__':main()
