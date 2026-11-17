"""Fixed no-service actor entry; no parent/sibling state or target mounts."""
import time
ORIGINAL_ENTRY=time.monotonic()
import os,json,sys
from pathlib import Path

def need(value,message):
    if not value:raise ValueError(message)

def main():
    need(len(sys.argv)==3 and sys.argv[1] in ('fit','infer') and sys.argv[2] in ('participant','reference'),'fixed phase/role')
    phase,role=sys.argv[1:];p=json.loads(Path('/input/HOST.json').read_bytes());c=Path('/sys/fs/cgroup')
    need(p['schema']=='neural057-no-service-visible-profile-v1' and os.getuid()==65534,'qualified unprivileged fixed profile')
    need((c/'memory.max').read_text().strip()==str(p['memory_bytes']) and (c/'memory.swap.max').read_text().strip()=='0','original memory limits')
    q,t=map(int,(c/'cpu.max').read_text().split());need(q==t and t>0 and (c/'pids.max').read_text().strip()==str(p['pids']),'original CPU/PID limits')
    args=['fit','--train','/input/train.json','--model-output','/output/model.bin'] if phase=='fit' else ['infer','--query','/input/query.json','--model','/model/model.bin','--output','/output/prediction.json']
    programme='/submission/program.py' if role=='participant' else '/runtime/reference_entry.py'
    os.execv(sys.executable,[sys.executable,'-I','-B',programme,*args])

if __name__=='__main__':main()
