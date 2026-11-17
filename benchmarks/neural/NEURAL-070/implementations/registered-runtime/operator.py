"""Explicit source operator for all original N070 phases; inactive and unqualified.

This API does not accept a single candidate program. The independently signed
profile must bind all original evaluator sources, three arms, prepared inputs,
private targets, capacities and gates. This module creates no such authority.
"""
from argparse import Namespace
from programme.n070 import bootstrap

def run(*, profile, signature, key, profile_sha256, signature_sha256,
        key_sha256, root, profile_bytes, key_bytes, host_read_bytes, phase):
    """Forward exact original operands into the original bootstrap owner."""
    if phase not in ("prepare","evaluate","literal_a"):
        raise ValueError("Explicit complete original N070 phase required")
    args=Namespace(profile=profile,signature=signature,key=key,
        profile_sha256=profile_sha256,signature_sha256=signature_sha256,
        key_sha256=key_sha256,root=root,profile_bytes=profile_bytes,
        key_bytes=key_bytes,host_read_bytes=host_read_bytes,phase=phase)
    return bootstrap.run(args)

def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("profile","signature","key","profile-sha256","signature-sha256","key-sha256","root"):
        p.add_argument("--"+name,required=True)
    for name in ("profile-bytes","key-bytes","host-read-bytes"):
        p.add_argument("--"+name,required=True,type=int)
    p.add_argument("--phase",required=True,choices=("prepare","evaluate","literal_a"))
    return run(**vars(p.parse_args()))

if __name__=="__main__":
    main()
