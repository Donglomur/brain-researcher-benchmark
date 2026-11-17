"""Protected operator entry for future explicitly admitted full-source captures.

No default profile, native qualification, scoring or candidate authority is
issued here. Source construction never calls main. Bootstrap before the original
native observer is unmeasured and cannot be retroactively certified by this CLI.
"""
import argparse
from runtime.strict import Root,require,decode
from runtime.full_scientific_bindings import Failures
from runtime.full_scientific_controller import run_scientific_sources

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configuration-root',required=True)
    parser.add_argument('--configuration-path',required=True)
    parser.add_argument('--configuration-bytes',type=int,required=True)
    parser.add_argument('--configuration-sha256',required=True)
    args=parser.parse_args(argv)
    require(args.configuration_bytes>0,'explicit complete operator configuration extent')
    require(len(args.configuration_sha256)==64 and all(c in'0123456789abcdef'for c in args.configuration_sha256),'exact operator configuration SHA256')
    owner=Failures();value=None
    try:
        root=owner.own(Root(args.configuration_root,private=True))
        raw=root.read(args.configuration_path,args.configuration_bytes,
            pin={'bytes':args.configuration_bytes,'sha256':args.configuration_sha256})
        value=decode(raw)
        require(set(value)=={'schema','selection','global_limits','authority_limits','authority_root','authority_path','authority_pin'},'closed complete operator input')
        require(value['schema']=='jaxley_full_scientific_operator_configuration_v1','separate prospective source route')
    except BaseException as error:owner.catch(error)
    owner.close_all();owner.raise_first()
    return run_scientific_sources(value['authority_root'],value['authority_path'],value['authority_pin'],
                                  value['authority_limits'],value['selection'],value['global_limits'])

if __name__=='__main__':main()
