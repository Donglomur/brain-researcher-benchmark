"""Fixed preactivation barrier, before any candidate/reference/tool code."""
import json,os,sys,time
from pathlib import Path

def main():
    if not(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode)or len(sys.argv)!=2:raise ValueError('fixed barrier argv')
    p=Path(sys.argv[1]);raw=p.read_bytes()
    if len(raw)>131072:raise ValueError('finite launch frame')
    cfg=json.loads(raw)
    if set(cfg)!={'argv','deadline','go','nonce'}or not isinstance(cfg['argv'],list)or not cfg['argv']or not all(type(x)is str and '\0'not in x for x in cfg['argv']):raise ValueError('fixed launch fields')
    gate=p.parent/cfg['go']
    if cfg['go']!='GO' or '/'in cfg['go']:raise ValueError('fixed gate member')
    while not gate.exists():
        if time.monotonic()>=cfg['deadline']:raise TimeoutError('original activation cutoff')
        time.sleep(min(.01,max(0,cfg['deadline']-time.monotonic())))
    if gate.read_bytes()!=cfg['nonce'].encode()or time.monotonic()>=cfg['deadline']:raise ValueError('exact timely host activation')
    os.execv(cfg['argv'][0],cfg['argv'])
if __name__=='__main__':main()
