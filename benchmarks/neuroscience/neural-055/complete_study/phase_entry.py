"""Actual original native phase entry; source bindings are mounted read-only."""
import time
ORIGINAL_ENTRY=time.monotonic()
import json
import os
from pathlib import Path
import sys

def require(ok,message):
    if not ok:raise ValueError(message)

def main():
    require(len(sys.argv)==3 and sys.argv[1] in ('fit','infer') and sys.argv[2] in ('participant','reference'),'exact phase/role operands')
    phase,role=sys.argv[1:];profile=json.loads(Path('/input/HOST.json').read_text())
    require(profile['schema']=='neural055-visible-native-profile-v3','complete broker host ABI')
    root=Path('/sys/fs/cgroup')
    require(os.getuid()==65534,'unprivileged original actor')
    require((root/'memory.max').read_text().strip()==str(profile['memory_bytes']),'observed memory limit')
    require((root/'memory.swap.max').read_text().strip()=='0','observed swap disabled')
    quota,period=map(int,(root/'cpu.max').read_text().split());require(quota==period and period>0,'observed one CPU')
    require((root/'pids.max').read_text().strip()==str(profile['pids']),'observed PID bound')
    args=['fit','--train','/input/train.json','--model-output','/output/model.bin'] if phase=='fit' else ['infer','--query','/input/query.json','--model','/model/model.bin','--output','/output/prediction.json']
    # Existing literal fit/infer operands are preserved; new mandatory sidecars
    # live only under the separately versioned bounded output ABI.
    programme='/submission/program.py' if role=='participant' else '/runtime/reference_entry.py'
    if role=='participant':
        lease=json.loads(Path('/broker/LEASE.json').read_bytes())
        require(lease['schema']=='neural055-visible-broker-lease-v3' and lease['phase']==phase.upper(),'same actual visible broker phase')
        require(lease['cell']==json.loads(Path('/input/CELL.json').read_bytes()),'same actual broker cell')
    os.execv(sys.executable,[sys.executable,'-I','-B',programme,*args])

if __name__=='__main__':main()
