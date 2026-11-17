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

def arguments(kind):
    if kind not in ('fit','adapt','infer','prior'):raise ValueError('exact selected phase')
    args=[kind,'--input','/input/INPUT.json']
    if kind in ('adapt','infer'):args+=['--model','/model/model.bin']
    if kind in ('fit','adapt'):args+=['--model-output','/output/model.bin']
    else:args+=['--output','/output/prediction.json']
    return args


def main():
    if len(sys.argv)!=3 or sys.argv[2] not in ('fit','adapt','infer','prior'):raise ValueError('exact memory/mode operands')
    observed(int(sys.argv[1]))
    args=arguments(sys.argv[2])
    os.execv(sys.executable,[sys.executable,'-I','-B','/submission/program.py',*args])
if __name__=='__main__':main()
