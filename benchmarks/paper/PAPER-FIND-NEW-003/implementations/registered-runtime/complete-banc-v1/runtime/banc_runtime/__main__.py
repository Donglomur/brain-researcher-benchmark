"""Source-only complete-program inspection. No native/data execution command."""
import argparse
import sys
import time
from .codec import parse, encode, capture, pin, need
from .catalog import load_catalog
from .construct import construct, manifest
from .producers import complete_pipeline
from .resources import Limits,Meter


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog-sha256',required=True)
    parser.add_argument('--catalog-bytes',required=True,type=int)
    parser.add_argument('--arm',choices=('paper_and_data','paper_data_official_code'),required=True)
    parser.add_argument('--objective',choices=('reconstruction','fixed_quantity_improvement'),required=True)
    parser.add_argument('--annotation-profile',choices=('frozen_GCS_generation1787336614757441','deposited_manuscript_snapshot'),required=True)
    parser.add_argument('--operator-branch',default=None)
    args=parser.parse_args(argv)
    meter=Meter(Limits(8*1048576,2*1048576,100000,100000,1000,time.monotonic_ns()+30_000_000_000))
    d={'path':'SOURCE_CATALOG.json','bytes':args.catalog_bytes,'sha256':args.catalog_sha256}
    catalogue,members,captured,contracts=load_catalog(d,meter)
    program=construct(contracts,members,arm=args.arm,objective=args.objective,
                      annotation_profile=args.annotation_profile,data_descriptors={},
                      source_catalogue_identity=d,operator_branch=args.operator_branch)
    result={'programme':manifest(program),'pipeline':complete_pipeline(program,contracts,members),
            'source_only':True,'authentic_data_read':False,'native_execution':False,
            'whole_attempt_costs':meter.report()}
    # Reserve before serialization, then solve the tiny self-describing byte
    # count to a fixed point. Failed reservations are never refunded.
    meter.reserve_output(meter.limits.output_bytes)
    n=0
    for _ in range(12):
        costs=meter.report();costs['output_completed']=n
        result['whole_attempt_costs']=costs
        final=encode(result)
        if len(final)==n:break
        n=len(final)
    else:raise ValueError('self-describing output extent did not stabilize')
    meter.complete_output(len(final))
    sys.stdout.buffer.write(final)


if __name__=='__main__':main()
