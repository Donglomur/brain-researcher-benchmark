"""Trusted reference/native image entrypoint; never installed in candidate views."""
import argparse
import dataclasses
import importlib.util
from pathlib import Path
import sys
import types

def _package():
    name="_it_runtime_worker_package"
    if name not in sys.modules:
        module=types.ModuleType(name);module.__path__=[str(Path(__file__).resolve().parent)];sys.modules[name]=module
    return name

def execute(job,packet):
    import importlib
    package=_package();wire=importlib.import_module(package+".wire");basis=importlib.import_module(package+".basis").basis
    operation=job["operation"]
    if operation=="literal_native":
        return importlib.import_module(package+".native_execution").run_native(job,packet)
    kernels=basis("dispatcher").KERNELS
    wire.need(operation in kernels,"Only reviewed reference kernel names accepted")
    if operation=="portable_reproduction":
        packet={**packet,"arguments":dict(packet["arguments"])}
        manifest=packet["arguments"]["index_manifest"]
        if isinstance(manifest,wire.IndexManifest):
            packet["arguments"]["index_manifest"]=basis("reproduction").IndexManifest(**dataclasses.asdict(manifest))
    return kernels[operation](packet)

def main(argv=None):
    import importlib
    wire=importlib.import_module(_package()+".wire")
    parser=argparse.ArgumentParser();parser.add_argument("--job",required=True);parser.add_argument("--output-root",required=True)
    args=parser.parse_args(argv)
    job=wire.parse(wire._read(Path(args.job),16*1024*1024),16*1024*1024)
    limits=wire.WireLimits(**job["wire_limits"])
    packet=wire.decode_bundle(wire._read(Path(job["packet_file"]),2*(limits.bytes+limits.metadata)+4096),limits)
    try:
        result=execute(job,packet)
    except Exception as error:
        native=importlib.import_module(_package()+".native_execution")
        if isinstance(error,native.NativeExecutionFailure):
            wire.write_wire(Path(args.output_root),{"status":"native_execution_failed",
                "exception_type":type(error).__name__,"artifacts":error.artifacts},limits)
            return 2
        raise
    wire.write_wire(Path(args.output_root),result,limits)
    return 0

if __name__=="__main__": raise SystemExit(main())
