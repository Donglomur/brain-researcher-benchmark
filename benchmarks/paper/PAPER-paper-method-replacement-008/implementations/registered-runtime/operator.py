"""Inspect-only command line. Scientific operator APIs are not CLI dispatchers."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from barista_operator import Operator

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['inspect'])
    parser.parse_args()
    print(json.dumps(Operator(Path(__file__).resolve().parent).inspect(),indent=2,sort_keys=True))
if __name__=='__main__':main()
