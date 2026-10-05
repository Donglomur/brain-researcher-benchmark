"""Stage the pinned public Haxby subject-1 files during the image build."""
import argparse
import hashlib
import json
import shutil
import tarfile
import tempfile
import urllib.request
from pathlib import Path


SOURCE_FILES = {"subj1/bold.nii.gz", "subj1/mask4_vt.nii.gz", "subj1/labels.txt"}


def verify_file(path, expected):
    """Reject truncated or changed bytes before they can become task inputs."""
    if path.stat().st_size != expected["size_bytes"]:
        raise ValueError(f"Size mismatch: {path.name}")
    digests = {name: hashlib.new(name) for name in ("sha256", "md5") if name in expected}
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            for digest in digests.values():
                digest.update(block)
    for name, digest in digests.items():
        if digest.hexdigest() != expected[name]:
            raise ValueError(f"{name} mismatch: {path.name}")


def stage_data(destination, manifest_path, archive_path=None):
    manifest = json.loads(manifest_path.read_text())
    records = manifest["files"]
    if len(records) != len(SOURCE_FILES) or {item["path"] for item in records} != SOURCE_FILES:
        raise ValueError("Manifest must contain exactly the three subject-1 source files")
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="haxby-build-", dir=destination.parent) as temp:
        staging = Path(temp)
        if archive_path is None:
            archive_path = staging / "subject1.tar.gz"
            with urllib.request.urlopen(manifest["archive"]["url"], timeout=120) as response:
                with archive_path.open("wb") as output:
                    shutil.copyfileobj(response, output)
        verify_file(archive_path, manifest["archive"])
        with tarfile.open(archive_path, "r:gz") as archive:
            for record in records:
                member = archive.getmember(record["path"])
                if not member.isfile() or member.size != record["size_bytes"]:
                    raise ValueError(f"Invalid archive member: {record['path']}")
                target = staging / record["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                # Never extract archive paths or links; write only fixed allowlisted names.
                with archive.extractfile(member) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
                verify_file(target, record)
        # Publish only after every source file has passed its digest check.
        for record in records:
            target = destination / record["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            (staging / record["path"]).replace(target)
        (destination / "data_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=Path("/app/data"))
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("data_manifest.json"))
    parser.add_argument("--archive", type=Path, help="Optional local archive; identical checksum checks apply")
    args = parser.parse_args()
    manifest = stage_data(args.destination, args.manifest, args.archive)
    print(f"Staged {len(manifest['files'])} verified Haxby subject-1 files in {args.destination}")


if __name__ == "__main__":
    main()
