"""Safe outward source status. Run/score remain unavailable."""
import json
import sys
from alm.contracts import readiness
from alm.programme import run,score

def main():
    if sys.argv[1:]==['status']:
        print(json.dumps(readiness(),sort_keys=True))
        return
    raise SystemExit('Only source status is available; native/scientific execution is not admitted.')

if __name__=='__main__':
    main()
