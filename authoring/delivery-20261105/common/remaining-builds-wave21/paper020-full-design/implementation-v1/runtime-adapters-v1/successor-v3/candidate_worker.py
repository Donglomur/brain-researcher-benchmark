"""Minimal candidate-image worker; evaluator/reference source must be absent.

The installed image contains only this worker, wire.py, approved libraries and
the guardian. All candidate code executes inside the separately admitted OS
boundary; Python exec is deliberately not represented as a security sandbox.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import types

def _wire():
    # Standalone script under python -I: explicit adjacent qualified wire module.
    path=Path(__file__).with_name("wire.py")
    name="_it_candidate_wire"
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module

def execute(job,packet,model=None):
    """The small RAM-test seam is the same operation dispatch used in the image."""
    wire=_wire();wire.need(job["operation"] in ("probe","fit","predict","reproduce"),"Unknown candidate operation")
    source=job["source"]
    wire.need(hashlib.sha256(source.encode()).hexdigest()==job["source_digest"],"Candidate source changed")
    namespace={"__name__":"candidate", "__file__":"/paper020-view/candidate.py"}
    exec(compile(source,"/paper020-view/candidate.py","exec"),namespace)
    name=job["operation"];wire.need(callable(namespace.get(name)),"Candidate method absent")
    if name=="predict": return namespace[name](model,packet)
    result=namespace[name](packet)
    if name=="probe": wire.canonical(result) # only finite plain diagnostics reach the provider
    return result

def main(argv=None):
    args=argparse.ArgumentParser();args.add_argument("--job",required=True);args.add_argument("--output-root",required=True)
    ns=args.parse_args(argv);wire=_wire()
    raw=wire._read(Path(ns.job),16*1024*1024);job=wire.parse(raw,16*1024*1024)
    limits=wire.WireLimits(**job["wire_limits"])
    packet=wire.decode_bundle(wire._read(Path(job["packet_file"]),2*(limits.bytes+limits.metadata)+4096),limits)
    model=wire.decode_bundle(wire._read(Path(job["model_file"]),2*(limits.bytes+limits.metadata)+4096),limits) if job.get("model_file") else None
    result=execute(job,packet,model)
    wire.write_wire(Path(ns.output_root),result,limits)

if __name__=="__main__": main()
