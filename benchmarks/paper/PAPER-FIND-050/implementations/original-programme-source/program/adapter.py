"""Source-only registry entry; construction does not select actual execution."""
import argparse,json

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['run','score']);p.add_argument('--invocation',required=True);a=p.parse_args()
    raise SystemExit('FIND050 complete empirical-core/forecast source is unqualified and execution-unselected. Root must independently admit authentic full29 inputs, images, method/exposure, compute, observer and protected grading; source registration alone cannot activate this program.')
if __name__=='__main__':main()
