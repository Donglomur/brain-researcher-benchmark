"""Metadata-only inspection CLI. Does not expose a native-run shortcut."""
import argparse
import hashlib
import json
from pathlib import Path
from .planner import unresolved_plan
from .admission import validate_manifest
from .protocol import parse_json

CATALOG_SHA256 = "e381949610dbc098944913de2f050b1ae9aaf8417bcd95a491e30f52e7f9ceb3"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["inventory", "validate-metadata"])
    parser.add_argument("--manifest")
    args = parser.parse_args()
    catalog_path = Path(__file__).resolve().parents[3] / "contracts" / "COMPLETE_CATALOG.json"
    body = catalog_path.read_bytes()
    if hashlib.sha256(body).hexdigest() != CATALOG_SHA256:
        raise ValueError("catalog pin mismatch")
    catalog = parse_json(body, 1024 * 1024)
    if args.command == "inventory":
        result = unresolved_plan(catalog)
    else:
        if not args.manifest:
            parser.error("--manifest required")
        manifest = parse_json(Path(args.manifest).read_bytes(), 4 * 1024 * 1024)
        result = validate_manifest(manifest, catalog)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
