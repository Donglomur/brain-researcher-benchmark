"""Future isolated trusted reference entry point; no work occurs on import."""
import argparse,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from n056 import reference_worker
def main():
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=('train','query'),required=True)
    p.add_argument('--alpha',type=float,default=1.0);a=p.parse_args()
    if a.stage=='train':reference_worker.train('/input/0','/output',a.alpha)
    else:reference_worker.query('/input/0','/model','/output')
if __name__=='__main__':main()

