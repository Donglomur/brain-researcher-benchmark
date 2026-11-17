"""Create the predeclared all-coordinate count+1 negative construction control.

The input is an owner-only named reference, never participant input. All cases,
families and rational moments remain present; only integer counts change.
"""
import argparse
from pathlib import Path
from conditional_kernel import need
from endpoint_cli import MAX_SUBMISSION,MAX_CASE,decode,read,json_bytes


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    lines=read(args.reference,MAX_SUBMISSION).splitlines()
    need(len(lines)>=2,'complete named reference')
    total=0
    with args.output.open('xb') as stream:
        for i,line in enumerate(lines):
            value=decode(line)
            if i:
                for family in value['families']:
                    family['counts']=[[n+1 for n in row] for row in family['counts']]
            body=json_bytes(value)
            need(len(body)<=MAX_CASE and total+len(body)<=MAX_SUBMISSION,'negative-control retention')
            stream.write(body);total+=len(body)
    print('{"negative_control":"all_counts_plus_one","historical_equivalence":false}')


if __name__=='__main__':main()
