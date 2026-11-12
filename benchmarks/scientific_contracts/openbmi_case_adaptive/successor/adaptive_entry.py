"""Adaptive-only trusted entry. Candidate Python runs only inside its worker."""
import os
from pathlib import Path
import runpy
import sys

def observed(memory):
    root=Path('/sys/fs/cgroup')
    def need(ok):
        if not ok:
            raise ValueError('observed candidate cgroup policy')
    need(os.getuid()==65534)
    need((root/'memory.max').read_text().strip()==str(memory))
    need((root/'memory.swap.max').read_text().strip()=='0')
    quota,period=map(int,(root/'cpu.max').read_text().split())
    need(quota==period and period>0)
    need((root/'pids.max').read_text().strip()=='64')

def main():
    if len(sys.argv)!=4 or sys.argv[2] not in ('fit','infer'):
        raise ValueError('exact adaptive memory/mode/frame operands')
    memory,kind,frame_bytes=int(sys.argv[1]),sys.argv[2],int(sys.argv[3])
    if not 1<=frame_bytes<=0xffffffff:
        raise ValueError('explicit frame bound')
    observed(memory)
    wire_in=os.dup(0)
    wire_out=os.dup(1)
    os.dup2(2,1)
    os.environ['OPENBMI_BROKER_READ_FD']=str(wire_in)
    os.environ['OPENBMI_BROKER_WRITE_FD']=str(wire_out)
    os.environ['OPENBMI_BROKER_FRAME_BYTES']=str(frame_bytes)
    sys.path.insert(0,'/trusted')
    if kind=='fit':
        args=['fit','--input','/input','--out','/output/model.bin']
    else:
        args=['infer','--input','/input','--model','/model/model.bin','--out','/output/predictions.json']
    sys.argv=['/submission/program.py',*args]
    try:
        runpy.run_path('/submission/program.py',run_name='__main__')
    finally:
        client=sys.modules.get('openbmi_agent_tools')
        if client is not None:
            client.close()
        os.close(wire_in)
        os.close(wire_out)

if __name__=='__main__':
    main()
