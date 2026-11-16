#!/usr/bin/env python3
"""Verify/copy opaque package members and emit the original public-file bindings."""
import argparse
import json
from pathlib import Path
import shutil
import sys
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from asset_io import stream_pin

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--repo-root", type=Path, help="Original repository for exact direct data/PDF sources before assembly")
    parser.add_argument("--destination", type=Path, help="Fresh directory for a separate byte-only export")
    parser.add_argument("--bindings-output", type=Path, help="Fresh JSON of the exact three runtime mounts; no execution")
    parser.add_argument("--session", type=int, choices=range(1, 18), help="Public request index for --bindings-output")
    args = parser.parse_args()
    if not args.verify and args.destination is None and args.bindings_output is None:
        parser.error("Choose --verify, --destination or --bindings-output")
    manifest = json.loads((HERE / "package_files.json").read_text())
    if manifest["schema"] != "thalamus_portable_file_pins_v1":
        raise ValueError("Exact file manifest required")
    if sum(row["bytes"] for row in manifest["files"].values()) > 200000000:
        raise ValueError("200 MB package cap")
    bindings = json.loads((HERE / "source_bindings.json").read_text())["direct_sources"]
    destination = args.destination.absolute() if args.destination else None
    if destination is not None:
        if destination.exists() or destination.is_symlink(): raise ValueError("Fresh destination required")
        destination.mkdir(parents=True)
    sources = {}
    for target, pin in sorted(manifest["files"].items()):
        relative = Path(target)
        if relative.is_absolute() or ".." in relative.parts or relative.parts[0] not in ("public", "private"):
            raise ValueError("Canonical export path required")
        source = ROOT / relative
        if not source.exists() and target in bindings and args.repo_root is not None:
            original = Path(bindings[target])
            if original.is_absolute() or ".." in original.parts: raise ValueError("Repository-relative source required")
            source = args.repo_root.absolute() / original
        if stream_pin(source) != pin: raise ValueError("Changed package bytes: " + target)
        sources[target] = source
        if destination is not None:
            out = destination / relative; out.parent.mkdir(parents=True, exist_ok=True)
            with source.open("rb") as src, out.open("xb") as sink:
                shutil.copyfileobj(src, sink, 1048576)
            if stream_pin(out) != pin: raise ValueError("Changed copied bytes")
    if destination is not None:
        shutil.copyfile(HERE / "package_files.json", destination / "private/package_files.json")
    if args.bindings_output is not None:
        if args.session is None: parser.error("--bindings-output requires --session 1..17")
        members = [("public/Figure3C_data.RData", "/input/Figure3C_data.RData"),
                   ("public/SESSION_MANIFEST.json", "/input/SESSION_MANIFEST.json"),
                   ("public/sessions/pair%03d.json" % args.session, "/input/session.json")]
        result = {"schema": "thalamus_three_file_runtime_bindings_v1", "execution_performed": False,
                  "session": args.session,
                  "files": [{"source": str(destination / member if destination else sources[member]),
                             "target": target, "read_only": True} for member, target in members]}
        with args.bindings_output.open("x") as stream: json.dump(result, stream, indent=2); stream.write("\n")
    print(json.dumps({"status": "package_bytes_verified", "files": len(sources),
                      "bytes": sum(p["bytes"] for p in manifest["files"].values()),
                      "copied": destination is not None, "scientific_calculations": 0, "scoring_calls": 0}))

if __name__ == "__main__": main()
