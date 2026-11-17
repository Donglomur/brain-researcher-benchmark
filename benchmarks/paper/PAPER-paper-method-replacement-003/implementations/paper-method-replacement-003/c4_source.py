"""Prepare or verify exact ordinary source; never run a scientific benchmark."""
import argparse
import json
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parent
for _name, _module in tuple(sys.modules.items()):
    if _name == "c4_distribution" or _name.startswith("c4_distribution."):
        _file = getattr(_module, "__file__", None)
        if _file is None or _ROOT not in Path(_file).resolve().parents:
            raise RuntimeError("foreign preloaded C4 distribution module")
sys.path.insert(0, str(_ROOT))
from c4_distribution.dependencies import prepare_dependencies, verify_dependencies, specification

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    prep = sub.add_parser("prepare")
    origin = prep.add_mutually_exclusive_group(required=True)
    origin.add_argument("--source-root")
    origin.add_argument("--fetch", action="store_true")
    prep.add_argument("--output", required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--root", required=True)
    sub.add_parser("plan")
    args = parser.parse_args(argv)
    if args.operation == "prepare":
        result = prepare_dependencies(args.output, source_root=args.source_root, fetch=args.fetch)
    elif args.operation == "verify":
        checked = verify_dependencies(args.root)
        result = {"status": "verified-ordinary-source-only", "source_files": len(checked.files),
                  "manifest_sha256": checked.manifest_sha256,
                  "scientific_or_native_qualification": False, "rights_clearance": False}
    else:
        spec = specification()
        result = {"status": "unqualified-source-plan", "source_files": len(spec["files"]),
                  "source_bytes": spec["total_bytes"], "scientific_roles": 83,
                  "norms": 4, "programme_modules": 19, "open_gates": 25,
                  "direct_source_import_profile": "complete exact41 original members required",
                  "package_install_profile": "unavailable; README metadata and environment qualification missing",
                  "source_complete": False, "runnable": False, "rights_clearance": False}
    print(json.dumps(result, sort_keys=True))
    return result

if __name__ == "__main__":
    main()
