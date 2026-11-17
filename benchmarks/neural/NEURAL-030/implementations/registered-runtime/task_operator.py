"""Inactive metadata inspection only; never dispatches source/data execution."""
import argparse
import json
from pathlib import Path


def inspect():
    base = Path(__file__).resolve().parent
    result = {}
    for name in ("manifest.json", "PROTOCOL.json", "SOURCE.json", "QUALIFICATION_GATES.json", "OPERATOR_API.json"):
        path = base / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 262144:
            raise ValueError("ordinary bounded metadata file required: " + name)
        result[name] = json.loads(path.read_text(encoding="utf8"))
    manifest = result["manifest.json"]
    if any(manifest["admission"].values()) or any(manifest[k] is not None for k in ("run", "score", "program_execution")):
        raise ValueError("source proposal must remain inactive")
    return {"task_id": "NEURAL-030", "inspection": "inactive_source_metadata_only",
            "scientific_qualification": False, "metadata": result}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["inspect"])
    parser.parse_args()
    print(json.dumps(inspect(), sort_keys=True, indent=2))
