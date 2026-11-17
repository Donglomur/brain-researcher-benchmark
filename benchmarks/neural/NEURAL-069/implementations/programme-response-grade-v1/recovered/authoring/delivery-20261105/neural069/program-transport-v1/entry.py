"""Observe cgroup resources, then exec one committed arbitrary Python program."""
import os,sys
from pathlib import Path
def main():
    if len(sys.argv)!=2:raise ValueError('Memory operand')
    memory=int(sys.argv[1]);r=Path('/sys/fs/cgroup')
    quota,period=map(int,(r/'cpu.max').read_text().split())
    if not(os.getuid()==65534 and (r/'memory.max').read_text().strip()==str(memory) and (r/'memory.swap.max').read_text().strip()=='0' and quota==period and period>0 and (r/'pids.max').read_text().strip()=='64'):raise ValueError('Observed resources')
    os.execv(sys.executable,[sys.executable,'-I','-B','/submission/program.py','--public-root','/public','--output-dir','/output'])
if __name__=='__main__':main()
