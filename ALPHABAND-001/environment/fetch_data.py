"""Build-time acquisition only; verify EDF bytes against PhysioNet's published hashes."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen


def acquire(manifest_path, destination):
    manifest_path = Path(manifest_path)
    destination = Path(destination)
    manifest = json.loads(manifest_path.read_text())
    for relative_path, expected_hash in manifest["files"].items():
        target = destination / relative_path
        # Do not overwrite an existing, possibly user-owned or corrupt recording.
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest() != expected_hash:
                raise ValueError(f"checksum mismatch: {target}")
            print(f"verified {relative_path}", flush=True)
            continue
        with urlopen(manifest["base_url"] + relative_path, timeout=60) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != expected_hash:
            raise ValueError(f"checksum mismatch downloading {relative_path}")
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(data)
        print(f"downloaded and verified {relative_path}: {len(data)} bytes", flush=True)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "data_manifest.json").write_bytes(manifest_path.read_bytes())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("data_manifest.json"))
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    acquire(args.manifest, args.destination)
